"""Ein kleines MLP entscheidet je Entity-Paar: gehoert das zusammen?

Die Heuristik in `offers.py` ordnet ueber Nachbarschaft zu, und die Geometrie
allein trifft gemessen 0.463 bis 0.620. Der Grund steht im Layout: Penny
setzt den Preis in einen gelben Kasten, der weiter vom zugehoerigen
Produktnamen entfernt liegt als vom Nachbarangebot. Wer daran mit
Schwellwerten dreht, arbeitet gegen die Seitengestaltung.

Ein gelerntes Paarmodell dreht die Frage um: nicht "wie nah ist nah genug",
sondern "welche Kombination aus Abstand, Typ, Schriftgroesse und
Zwischenliegendem hat der Lehrer zusammengefasst". Der Aufbau ist der der
Line-Item-Literatur - Merkmalsvektor je Paar, MLP, Schwelle,
Zusammenhangskomponenten (DocILE arXiv:2302.05658).

**Was das Modell nicht sieht, ist die Rechnung Menge x Grundpreis.** Sie
bleibt der unabhaengige Richter in `magda offers-verify`; als Merkmal
gefuettert wuerde sie sich hinterher selbst bewerten. Begruendung in
`offer_pairs`.

**Der Lehrer faerbt ab.** Ein Modell, das aus `data/offer_groups/` gelernt
hat, kann nicht besser werden als die Gruppierung, aus der es lernt - genau
wie GBERT an der Konsistenzgrenze von sonnet-5 haengt. Deshalb steht die
Herkunft im Checkpoint und wandert in jeden Report.
"""

from __future__ import annotations

from pathlib import Path

from magda import offer_pairs

# Klein gehalten, nicht aus Bescheidenheit: Bei rund 30 gruppierten Seiten
# stehen wenige zehntausend Paare zur Verfuegung, und die Positiven sind eine
# Minderheit davon. Ein groesseres Netz lernt die Trainingsseiten auswendig,
# und der Effekt zeigt sich erst auf Dev.
HIDDEN = (64, 32)
DROPOUT = 0.2
LEARNING_RATE = 1e-3

# Dieselbe Schwelle, mit der `dataset._dev_clusters` Dev zieht: Seiten ueber
# 0.7 Jaccard sind Regionalfassungen derselben Vorlage und duerfen bei der
# Kalibrierung nicht auf verschiedene Folds fallen.
CLUSTER_THRESHOLD = 0.7


def _build_network(features: int, hidden: tuple[int, ...] = HIDDEN):
    from torch import nn

    layers, previous = [], features
    for size in hidden:
        layers += [nn.Linear(previous, size), nn.ReLU(), nn.Dropout(DROPOUT)]
        previous = size
    layers.append(nn.Linear(previous, 1))
    return nn.Sequential(*layers)


class PairClassifier:
    """Ein trainiertes Paarmodell samt Merkmalsvertrag und Herkunft."""

    def __init__(self, network, feature_names: list[str], provenance: dict | None = None,
                 hidden: tuple[int, ...] = HIDDEN, threshold: float = 0.5,
                 blocks: tuple[str, ...] = offer_pairs.DEFAULT_BLOCKS):
        self.network = network
        self.feature_names = feature_names
        self.provenance = provenance or {}
        self.hidden = tuple(hidden)
        # Welche Merkmalsbloecke dieses Modell erwartet. Gehoert zum
        # Checkpoint, sonst rechnet ein Modell mit vertauschten Spalten
        # weiter und faellt durch keine Pruefung auf.
        self.blocks = tuple(blocks)
        # Die out-of-fold gewaehlte Schwelle gehoert zum Modell, nicht zum
        # Aufruf: wer sie beim Messen neu setzt, misst ein anderes System.
        self.threshold = threshold

    def score_page(self, page: dict, pixels=None) -> dict[tuple[int, int], float]:
        """Wahrscheinlichkeit je Entity-Paar, dass beide zum selben Angebot gehoeren."""
        import torch

        pairs = offer_pairs.page_pairs(
            page, pixels=_pixels_for(page, self.blocks, pixels), blocks=self.blocks)
        if not pairs.index_pairs:
            return {}
        self.network.eval()
        with torch.no_grad():
            logits = self.network(torch.tensor(pairs.features, dtype=torch.float32))
            scores = torch.sigmoid(logits).squeeze(-1)
        return dict(zip(pairs.index_pairs, (round(float(s), 6) for s in scores)))

    def group_page(self, page: dict, threshold: float = 0.5, pixels=None) -> list[list[int]]:
        """Entity-Gruppen der Seite."""
        pixels = _pixels_for(page, self.blocks, pixels)
        pairs = offer_pairs.page_pairs(page, pixels=pixels, blocks=self.blocks)
        if not pairs.index_pairs:
            # Eine einzelne Entity ist ein Angebot, keine Entity ist keines.
            return [[0]] if pairs.entities else []
        return offer_pairs.groups_from_edges(
            len(pairs.entities), self.score_page(page, pixels), threshold
        )

    def group_page_words(self, page: dict, threshold: float = 0.5,
                         pixels=None) -> list[list[int]]:
        """Dieselben Gruppen als Wortindizes - die Einheit, die gespeichert wird."""
        return offer_pairs.entity_groups_to_words(
            page, self.group_page(page, threshold, pixels))

    def save(self, path) -> Path:
        import torch

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.network.state_dict(),
                "feature_names": list(self.feature_names),
                "blocks": list(self.blocks),
                "hidden": list(self.hidden),
                "threshold": float(self.threshold),
                "provenance": dict(self.provenance),
            },
            path,
        )
        return path


def _pixels_for(page: dict, blocks, pixels=None):
    """Das Seitenbild, aber nur wenn der Farbblock es braucht.

    Ohne Farbmerkmale wird nichts von der Platte gelesen - die 30 alten
    Merkmale kommen wie bisher ohne `data/images/` aus.
    """
    if "color" not in blocks or pixels is not None:
        return pixels
    return offer_pairs.load_pixels(page.get("page_id") or "")


def _examples(pages: list[dict], reference: dict[str, dict[int, int]],
              blocks=offer_pairs.DEFAULT_BLOCKS):
    """Merkmale und Labels aller trainierbaren Paare, ueber alle Seiten."""
    features: list[list[float]] = []
    labels: list[float] = []
    skipped = 0
    for page in pages:
        assignment = reference.get(page.get("page_id"))
        if assignment is None:
            continue
        pairs = offer_pairs.page_pairs(
            page, assignment, pixels=_pixels_for(page, blocks), blocks=blocks)
        for row, label in zip(pairs.features, pairs.labels):
            if label is None:
                skipped += 1
                continue
            features.append(row)
            labels.append(float(label))
    return features, labels, skipped


def training_stats(pages: list[dict], reference: dict[str, dict[int, int]]) -> dict:
    """Wie viele Paare das Training sieht - und wie schief sie verteilt sind.

    Die Schieflage ist der Punkt: Auf einer Seite mit 48 Entities gibt es
    1128 Paare, von denen nur eine Handvoll positiv ist. Ohne Gegengewicht
    lernt das Netz "nie zusammen" und hat damit ueber 95 % Genauigkeit.
    """
    features, labels, skipped = _examples(pages, reference)
    positive = int(sum(labels))
    return {
        "pages": sum(1 for p in pages if p.get("page_id") in reference),
        "pairs": len(labels),
        "positive": positive,
        "negative": len(labels) - positive,
        "skipped": skipped,
    }


def train(pages: list[dict], reference: dict[str, dict[int, int]],
          epochs: int = 300, seed: int = 0, provenance: dict | None = None,
          hidden: tuple[int, ...] = HIDDEN,
          blocks=offer_pairs.DEFAULT_BLOCKS) -> PairClassifier:
    """Trainiert das Paarmodell auf einer vorhandenen Gruppierung.

    Voller Batch statt Minibatches: Die Datenmenge passt in den Speicher, und
    ein deterministischer Lauf macht zwei Messungen ueberhaupt erst
    vergleichbar. `pos_weight` gleicht die Schieflage aus - siehe
    `training_stats`.
    """
    import torch
    from torch import nn

    names = offer_pairs.feature_names(blocks)
    features, labels, _ = _examples(pages, reference, blocks)
    if not labels:
        raise ValueError(
            "Kein einziges trainierbares Paar. Liegt fuer die Seiten eine "
            "Gruppierung vor? `magda offers-teacher pages` sagt, was fehlt."
        )

    torch.manual_seed(seed)
    x = torch.tensor(features, dtype=torch.float32)
    y = torch.tensor(labels, dtype=torch.float32).unsqueeze(-1)

    positive = float(y.sum())
    pos_weight = torch.tensor([(len(labels) - positive) / positive]) if positive else None

    network = _build_network(len(names), hidden)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.Adam(network.parameters(), lr=LEARNING_RATE)

    network.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        loss = loss_fn(network(x), y)
        loss.backward()
        optimizer.step()

    return PairClassifier(network, names, provenance, hidden, blocks=blocks)


def page_folds(pages: list[dict], folds: int = 5) -> list[list[str]]:
    """Seiten auf Folds verteilen - ganze Duplikat-Cluster, nie einzelne Seiten.

    Penny gibt je Woche 44 fast gleiche Regionalausgaben heraus. Zufaellig
    auf Folds verteilt bewertet ein Fold-Modell eine Vorlage, die es in einer
    anderen Fassung im Training hatte, und die gewaehlte Schwelle faellt zu
    nachsichtig aus. Derselbe Grund, aus dem Dev clusterweise gezogen wird.

    Groesste Cluster zuerst in den jeweils kleinsten Fold - sonst haengt die
    Groessenverteilung an der Reihenfolge der Seiten auf der Platte.
    """
    from magda.dedupe import group

    words = {p["page_id"]: [w["text"] for w in (p.get("words") or [])] for p in pages}
    clusters = [sorted(c) for c in group(words, threshold=CLUSTER_THRESHOLD)]
    known = {page_id for cluster in clusters for page_id in cluster}
    clusters += [[p["page_id"]] for p in pages if p["page_id"] not in known]

    buckets: list[list[str]] = [[] for _ in range(max(folds, 1))]
    for cluster in sorted(clusters, key=lambda c: (-len(c), c[0])):
        smallest = min(buckets, key=lambda b: (len(b), buckets.index(b)))
        smallest.extend(cluster)
    return [b for b in buckets if b]


def calibrate(pages: list[dict], reference: dict[str, dict[int, int]],
              folds: int = 5, epochs: int = 300, seed: int = 0,
              hidden: tuple[int, ...] = HIDDEN,
              thresholds: list[float] | None = None,
              objective: str = "pair_f1",
              blocks=offer_pairs.DEFAULT_BLOCKS) -> dict:
    """Die Schwelle out-of-fold waehlen, statt sie zu raten.

    0.5 waere nur dann der natuerliche Schnitt, wenn die Klassen gleich
    haeufig waeren. Sind sie nicht: `pos_weight` hebt die Positiven um Faktor
    10 an und schiebt damit alle Wahrscheinlichkeiten nach oben.

    Gewaehlt wird nach Paar-F1, gemessen wird gegen die Referenz - aber immer
    auf Seiten, die das jeweilige Fold-Modell nicht gesehen hat. Auf Dev zu
    optimieren und dort zu berichten waere In-Sample, auch wenn das *Modell*
    die Seiten nie gesehen hat.
    """
    from magda.offers_gold import Report, judge_page, offers_from_reference

    thresholds = thresholds or [round(0.50 + 0.02 * i, 2) for i in range(25)]
    curve: list[dict] = []

    # Die Kantenwahrscheinlichkeiten haengen nicht von der Schwelle ab.
    # Einmal je Seite berechnen statt einmal je Schwelle - sonst laeuft
    # dieselbe Vorhersage 25-mal durchs Netz.
    scored: list[tuple[dict, dict, int]] = []
    for fold in page_folds(pages, folds):
        held_out = set(fold)
        inner = [p for p in pages if p["page_id"] not in held_out]
        outer = [p for p in pages if p["page_id"] in held_out]
        if not inner or not outer:
            continue
        model = train(inner, reference, epochs, seed, hidden=hidden, blocks=blocks)
        for page in outer:
            entities = offer_pairs.page_pairs(page).entities
            scored.append((page, model.score_page(page), len(entities)))


    if not scored:
        raise ValueError("Zu wenige Seiten fuer eine Kalibrierung.")

    for threshold in thresholds:
        report = Report()
        for page, scores, count in scored:
            assignment = reference.get(page.get("page_id"))
            if assignment is None:
                continue
            groups = offer_pairs.entity_groups_to_words(
                page, offer_pairs.groups_from_edges(count, scores, threshold)
            )
            predicted = {word: group_id
                         for group_id, members in enumerate(groups) for word in members}
            _add(report, judge_page(page, assignment,
                                    offers_from_reference(page, predicted)))
        curve.append({
            "threshold": threshold,
            "pair_f1": report.pair_f1,
            "group_f1": report.group_f1,
            "groups": report.sys_groups,
            "reference_groups": report.ref_groups,
        })

    # Die beiden Kriterien waehlen verschiedene Schwellen, und das ist keine
    # Feinheit: Paar-F1 belohnt Vorsicht (kleine Gruppen haben wenige Paare
    # zu verlieren), Gruppen-F1 verlangt das ganze Angebot. Welche Zahl das
    # Projekt tragen soll, ist eine Teamentscheidung - hier wird sie
    # sichtbar gemacht, nicht getroffen.
    def _best(key):
        return max(curve, key=lambda row: (row[key] or 0.0, row["threshold"]))

    chosen = _best(objective)
    return {
        "threshold": chosen["threshold"],
        "objective": objective,
        "pages": len(scored),
        "best_pair_f1": _best("pair_f1"),
        "best_group_f1": _best("group_f1"),
        "curve": curve,
    }


def _add(left, right):
    from dataclasses import fields

    for f in fields(left):
        setattr(left, f.name, getattr(left, f.name) + getattr(right, f.name))
    return left


def load(path) -> PairClassifier:
    """Laedt einen Checkpoint und prueft den Merkmalsvertrag.

    Eine andere Merkmalsreihenfolge erzeugt keine Ausnahme, sondern
    wohlgeformten Unsinn: Das Netz rechnet mit vertauschten Spalten weiter
    und liefert Wahrscheinlichkeiten, die nichts bedeuten. Deshalb hier
    abbrechen statt spaeter an einer Zahl raetseln.
    """
    import torch

    payload = torch.load(path, weights_only=True)
    stored = list(payload.get("feature_names") or [])
    # Aeltere Checkpoints kennen keine Bloecke - die stammen aus der Zeit
    # der 30 Merkmale und werden ueber die Namensliste ohnehin geprueft.
    blocks = tuple(payload.get("blocks") or offer_pairs.DEFAULT_BLOCKS)
    expected = offer_pairs.feature_names(blocks)
    if stored != expected:
        raise ValueError(
            f"Der Checkpoint erwartet andere Merkmale ({len(stored)} statt "
            f"{len(expected)}). Neu trainieren."
        )
    hidden = tuple(payload.get("hidden") or HIDDEN)
    network = _build_network(len(stored), hidden)
    network.load_state_dict(payload["state_dict"])
    return PairClassifier(network, stored, payload.get("provenance") or {}, hidden,
                          float(payload.get("threshold", 0.5)), blocks=blocks)
