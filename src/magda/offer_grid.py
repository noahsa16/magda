"""Merkmalsbloecke einzeln messen - das 2x2-Gitter des Paarmodells.

Eine Leiter (erst Geometrie, dann Farbe obendrauf) schriebe der Farbe nur
den *Rest*-Beitrag zu. Raeumen die Kontextmerkmale die Legendenfaelle schon
ab, saehe Farbe insgesamt nutzlos aus - waehrend sie in Non-Food womoeglich
allein traegt. Bei 16,8 s Training je Variante kostet das Gitter nichts.

**Die Aufschlaesselung nach blindem Fleck ist die eigentliche Kennzahl.**
Farbmerkmale sind fuer den Bereich gebaut, in dem die Arithmetik schweigt;
eine Gesamtzahl kann steigen, weil das Modell in der ohnehin prueffbaren
Haelfte besser wird. Ein Paar zaehlt hier als **blind**, wenn keine der
beiden Referenzgruppen einen UNIT_PRICE enthaelt - ohne Grundpreis in der
Gruppe ist keine Rechnung moeglich.
"""

from __future__ import annotations

# Warum es die Kreuzvalidierung gibt (11.08.2026):
#
# Die Konfidenzintervalle der Gruppen-F1 waren so breit, dass keine Variante
# von einer anderen zu unterscheiden war. Der naheliegende Schluss war "mehr
# Referenz" - und er war halb falsch. Gemessen wird auf **Dev**, und Dev hat
# 21 Seiten in 14 Duplikat-Clustern, *alle* davon bereits gruppiert. Die
# Breite des Intervalls haengt an der Zahl der Auswertungs-Cluster, also an
# 14, und keine weitere Trainingsseite aendert daran etwas. Das Planziel
# "Dev auf 25-30 Seiten ausbauen" war nicht schwer, sondern unmoeglich.
#
# Der Ausweg ist keine Datenfrage, sondern eine Frage des Messaufbaus: jede
# Referenzseite einmal auswerten, mit einem Modell, das sie nicht gesehen
# hat. Aus 14 Clustern werden so alle Cluster der Referenz.

import math
import random
from dataclasses import dataclass, field

from magda import offer_pairs
from magda.offers import VALUE_TYPES, entities_from_page

VARIANTS: dict[str, tuple[str, ...]] = {
    "basis": offer_pairs.DEFAULT_BLOCKS,
    "geometrie": offer_pairs.GEOMETRY_BLOCKS,
    "farbe": ("types", "geometry_base", "color"),
    "beide": offer_pairs.ALL_BLOCKS,
}

# Duplikat-Cluster, ueber die das Bootstrap resampelt - dieselbe Schwelle,
# mit der Dev gezogen wurde. Elf Regionalfassungen einer Vorlage sind eine
# Beobachtung, nicht elf.
CLUSTER_THRESHOLD = 0.7
BOOTSTRAP_ROUNDS = 1000


@dataclass
class Counts:
    """Paar- und Gruppenzahlen, getrennt nach blindem Fleck."""

    ref_pairs: int = 0
    sys_pairs: int = 0
    shared_pairs: int = 0
    ref_groups: int = 0
    sys_groups: int = 0
    exact_groups: int = 0

    def add(self, other: "Counts") -> "Counts":
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(self, name) + getattr(other, name))
        return self

    @property
    def pair_f1(self) -> float | None:
        return _f1(self.shared_pairs, self.sys_pairs, self.ref_pairs)

    @property
    def group_f1(self) -> float | None:
        return _f1(self.exact_groups, self.sys_groups, self.ref_groups)

    def to_dict(self) -> dict:
        out = {name: getattr(self, name) for name in self.__dataclass_fields__}
        out["pair_f1"] = self.pair_f1
        out["group_f1"] = self.group_f1
        return out


@dataclass
class PageCounts:
    page_id: str
    total: Counts = field(default_factory=Counts)
    blind: Counts = field(default_factory=Counts)
    checkable: Counts = field(default_factory=Counts)


def _f1(shared: int, system: int, reference: int) -> float | None:
    if system == 0 and reference == 0:
        return None
    precision = shared / system if system else 0.0
    recall = shared / reference if reference else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _pairs_of(members) -> set[frozenset]:
    ordered = sorted(members)
    return {frozenset((a, b))
            for i, a in enumerate(ordered) for b in ordered[i + 1:]}


def judge_page(page: dict, assignment: dict[int, int],
               groups: list[list[int]]) -> PageCounts:
    """Eine Systemgruppierung gegen die Referenz, aufgeschluesselt.

    `groups` sind Wortindex-Gruppen, wie sie `group_page_words` liefert.
    Die Entity-Grundmenge kommt aus der *Seite*, nicht aus `groups` - sonst
    verbesserte ein System seinen Recall, indem es Entities weglaesst.
    """
    from magda.offers_gold import _reference_group

    result = PageCounts(page_id=page.get("page_id") or "unknown")
    universe = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]

    system_of: dict[int, int] = {}
    for index, words in enumerate(groups):
        for word in words:
            system_of[word] = index

    reference_members: dict[int, set] = {}
    system_members: dict[int, set] = {}
    types_of_group: dict[int, set[str]] = {}
    loose = len(groups)

    for entity in universe:
        key = (entity.start, entity.end)
        group = _reference_group(entity, assignment)
        if group is None:
            continue                      # der Mensch hat geschwiegen
        reference_members.setdefault(group, set()).add(key)
        types_of_group.setdefault(group, set()).add(entity.type)
        found = {system_of[w] for w in range(entity.start, entity.end)
                 if w in system_of}
        if len(found) == 1:
            system_members.setdefault(found.pop(), set()).add(key)
        else:
            system_members[loose] = {key}
            loose += 1

    # Blind ist eine Eigenschaft der Referenzgruppe, nicht der Vorhersage -
    # sonst haenge die Einteilung am zu bewertenden System.
    blind_group = {g: "UNIT_PRICE" not in t for g, t in types_of_group.items()}
    group_of = {key: g for g, m in reference_members.items() for key in m}

    def bucket(pair) -> str:
        a, b = tuple(pair)
        return "blind" if blind_group[group_of[a]] and blind_group[group_of[b]] \
            else "checkable"

    reference_pairs = {p for m in reference_members.values() for p in _pairs_of(m)}
    system_pairs = {p for m in system_members.values() for p in _pairs_of(m)
                    if all(k in group_of for k in p)}
    shared = reference_pairs & system_pairs

    exact = {frozenset(m) for m in reference_members.values()}
    for group, members in reference_members.items():
        target = result.blind if blind_group[group] else result.checkable
        for counts in (result.total, target):
            counts.ref_groups += 1
    for members in system_members.values():
        keys = [k for k in members if k in group_of]
        if not keys:
            continue
        is_blind = all(blind_group[group_of[k]] for k in keys)
        target = result.blind if is_blind else result.checkable
        hit = 1 if frozenset(members) in exact else 0
        for counts in (result.total, target):
            counts.sys_groups += 1
            counts.exact_groups += hit

    for pairs, name in ((reference_pairs, "ref_pairs"),
                        (system_pairs, "sys_pairs"),
                        (shared, "shared_pairs")):
        for pair in pairs:
            target = result.blind if bucket(pair) == "blind" else result.checkable
            for counts in (result.total, target):
                setattr(counts, name, getattr(counts, name) + 1)

    return result


def cross_validate(pages: list[dict], assignments: dict, blocks,
                   folds: int = 5, epochs: int = 300, seed: int = 0,
                   objective: str = "group_f1", decoder: str = "union",
                   progress=None) -> tuple[list[PageCounts], list[float]]:
    """Jede Referenzseite einmal auswerten - mit einem Modell ohne sie.

    Die Schwelle wird **geschachtelt** gewaehlt: `calibrate` laeuft auf den
    inneren Folds und macht dort seine eigene Kreuzvalidierung, die
    Auswertung trifft nur den aeusseren Fold. Eine einmal auf allem gewaehlte
    Schwelle waere bequemer und genau der Zirkelschluss, gegen den
    `offers_report` die Ablation braucht - die Schwelle ist ein Freiheitsgrad
    wie jeder andere.

    Der Preis ist Rechenzeit: `folds` mal Kalibrierung plus Training. Der
    Gewinn ist die Zahl der unabhaengigen Auswertungseinheiten, und die
    bestimmt die Breite jedes Intervalls.
    """
    per_page: list[PageCounts] = []
    thresholds: list[float] = []
    for model, outer in fold_models(pages, assignments, blocks, folds=folds,
                                    epochs=epochs, seed=seed,
                                    objective=objective, decoder=decoder,
                                    progress=progress):
        thresholds.append(model.threshold)
        for page in outer:
            per_page.append(
                judge_page(page, assignments[page["page_id"]],
                           model.group_page_words(page, model.threshold)))
    return per_page, thresholds


def fold_models(pages: list[dict], assignments: dict, blocks,
                folds: int = 5, epochs: int = 300, seed: int = 0,
                objective: str = "group_f1", decoder: str = "union",
                progress=None):
    """Liefert je Fold (Modell, gehaltene Seiten) - das Modell hat sie nie gesehen.

    Herausgezogen, damit jede weitere Out-of-fold-Auswertung dieselben
    Modelle sieht wie `cross_validate`. Zwei getrennte Fold-Schleifen waeren
    zwei Gelegenheiten, die geschachtelte Kalibrierung falsch zu bauen - und
    eine davon faellt niemandem auf, weil beide plausible Zahlen liefern.
    """
    from magda import offer_model

    for number, fold in enumerate(offer_model.page_folds(pages, folds), 1):
        held_out = set(fold)
        inner = [p for p in pages if p["page_id"] not in held_out]
        outer = [p for p in pages if p["page_id"] in held_out]
        if not inner or not outer:
            continue
        calibration = offer_model.calibrate(
            inner, assignments, folds=folds, epochs=epochs, seed=seed,
            objective=objective, blocks=blocks, decoder=decoder)
        model = offer_model.train(inner, assignments, epochs=epochs, seed=seed,
                                  blocks=blocks, decoder=decoder)
        model.threshold = calibration["threshold"]
        if progress:
            progress(number, len(outer), model.threshold)
        yield model, outer


def clusters_of(pages: list[dict]) -> list[list[str]]:
    """Duplikat-Cluster der Seiten - die Einheit, ueber die resampelt wird."""
    from magda.dedupe import group

    words = {p["page_id"]: [w["text"] for w in (p.get("words") or [])] for p in pages}
    clusters = [sorted(c) for c in group(words, threshold=CLUSTER_THRESHOLD)]
    known = {page_id for cluster in clusters for page_id in cluster}
    clusters += [[p["page_id"]] for p in pages if p["page_id"] not in known]
    return clusters


def bootstrap(per_page: list[PageCounts], clusters: list[list[str]],
              field_name: str = "total", metric: str = "pair_f1",
              rounds: int = BOOTSTRAP_ROUNDS, seed: int = 0) -> dict:
    """Konfidenzintervall ueber Cluster, nicht ueber Seiten.

    Elf Regionalfassungen derselben Vorlage sind eine Beobachtung. Ueber
    Seiten resampelt waere das Intervall zu eng - genau der Fehler, den
    `magda significance` fuer die Labelmetriken vermeidet.
    """
    by_page = {p.page_id: p for p in per_page}
    usable = [[pid for pid in c if pid in by_page] for c in clusters]
    usable = [c for c in usable if c]
    if len(usable) < 2:
        return {"clusters": len(usable), "low": None, "high": None}

    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(rounds):
        total = Counts()
        for _ in range(len(usable)):
            for page_id in rng.choice(usable):
                total.add(getattr(by_page[page_id], field_name))
        value = getattr(total, metric)
        if value is not None:
            values.append(value)
    if not values:
        return {"clusters": len(usable), "low": None, "high": None}
    values.sort()
    return {
        "clusters": len(usable),
        "low": values[int(0.025 * len(values))],
        "high": values[min(int(0.975 * len(values)), len(values) - 1)],
    }


def paired_bootstrap(left: list[PageCounts], right: list[PageCounts],
                     clusters: list[list[str]], field_name: str = "total",
                     metric: str = "group_f1", rounds: int = BOOTSTRAP_ROUNDS,
                     seed: int = 0) -> dict:
    """Die **Differenz** zweier Varianten bootstrappen, nicht zwei Intervalle.

    Zwei überlappende Einzelintervalle heißen *nicht* „kein Unterschied".
    Beide Varianten sehen dieselben Seiten, und der größte Teil der Streuung
    kommt aus den Seiten, nicht aus der Variante – wer sie einzeln
    resampelt, zählt diese gemeinsame Streuung zweimal und verdeckt damit
    genau den Effekt, den er messen will. Gepaart resampelt fällt sie heraus.

    Dieselbe Konstruktion wie in `magda significance` für den
    Modellvergleich, nur über Duplikat-Cluster statt über Seiten.

    `p_two_sided` ist der Anteil der Ziehungen, in denen die Differenz das
    Vorzeichen wechselt, verdoppelt – kein exakter Test, aber die
    gebräuchliche Bootstrap-Näherung, und sie sagt dasselbe wie die Frage,
    ob das Intervall die Null überdeckt.
    """
    by_left = {p.page_id: p for p in left}
    by_right = {p.page_id: p for p in right}
    shared = set(by_left) & set(by_right)
    usable = [[pid for pid in c if pid in shared] for c in clusters]
    usable = [c for c in usable if c]
    if len(usable) < 2:
        return {"clusters": len(usable), "low": None, "high": None,
                "difference": None, "p_two_sided": None}

    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(rounds):
        total_left, total_right = Counts(), Counts()
        for _ in range(len(usable)):
            for page_id in rng.choice(usable):
                total_left.add(getattr(by_left[page_id], field_name))
                total_right.add(getattr(by_right[page_id], field_name))
        a, b = getattr(total_left, metric), getattr(total_right, metric)
        if a is not None and b is not None:
            values.append(a - b)
    if not values:
        return {"clusters": len(usable), "low": None, "high": None,
                "difference": None, "p_two_sided": None}

    observed_left = total_of([by_left[p] for c in usable for p in c], field_name)
    observed_right = total_of([by_right[p] for c in usable for p in c], field_name)
    difference = (getattr(observed_left, metric) or 0.0) - (getattr(observed_right, metric) or 0.0)
    # Anteil der Ziehungen, die gegen das beobachtete Vorzeichen sprechen.
    if difference > 0:
        against = sum(1 for value in values if value <= 0)
    else:
        against = sum(1 for value in values if value >= 0)
    values.sort()
    return {
        "clusters": len(usable),
        "difference": difference,
        "low": values[int(0.025 * len(values))],
        "high": values[min(int(0.975 * len(values)), len(values) - 1)],
        "p_two_sided": min(1.0, 2 * against / len(values)),
    }


def total_of(per_page: list[PageCounts], field_name: str) -> Counts:
    total = Counts()
    for page in per_page:
        total.add(getattr(page, field_name))
    return total


def edge_auc(labels: list[int], scores: list[float]) -> float | None:
    """Wie gut die Kantenwahrscheinlichkeiten trennen - ohne Schwelle.

    Die Zahl beantwortet die Frage, die Gruppen-F1 offen laesst: Liegt der
    verbleibende Fehler an den Kanten oder am Dekodieren? Gruppen-F1 mischt
    beides, und die Konsequenzen sind entgegengesetzt - bessere Merkmale
    gegen besseres Dekodieren.

    Gerechnet als Anteil der Paare (positiv, negativ), in denen das
    positive hoeher bewertet ist; Gleichstaende zaehlen halb. Das ist
    dieselbe Groesse wie die Flaeche unter der ROC-Kurve, nur ohne
    zusaetzliche Abhaengigkeit. Ueber Raenge statt ueber alle Paare, sonst
    ist es quadratisch in der Paarzahl - und davon gibt es je Seite schon
    tausende.

    `None`, wenn eine der beiden Klassen fehlt: Ohne Negativbeispiele ist
    nichts zu trennen, und 0.5 hiesse "raet", was etwas anderes ist.
    """
    positive = [s for label, s in zip(labels, scores) if label == 1]
    negative = [s for label, s in zip(labels, scores) if label == 0]
    if not positive or not negative:
        return None

    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    index = 0
    while index < len(order):
        stop = index
        while stop + 1 < len(order) and scores[order[stop + 1]] == scores[order[index]]:
            stop += 1
        shared = (index + stop) / 2 + 1        # mittlerer Rang der Gruppe
        for position in range(index, stop + 1):
            ranks[order[position]] = shared
        index = stop + 1

    rank_sum = sum(rank for rank, label in zip(ranks, labels) if label == 1)
    count_positive, count_negative = len(positive), len(negative)
    u = rank_sum - count_positive * (count_positive + 1) / 2
    return u / (count_positive * count_negative)


def failure_kinds(pages: list[dict], assignments: dict, model) -> dict:
    """Woran die verfehlten Gruppen scheitern - zerfallen oder verschmolzen?

    Die Unterscheidung entscheidet ueber die Richtung: Zerfall heisst, dem
    System fehlen Kanten (mehr Recall noetig), Verschmelzung heisst, es hat
    zu viele (mehr Precision). Beides aus einer Gruppen-F1-Zahl abzulesen
    ist unmoeglich, und die Massnahmen sind gegenlaeufig.
    """
    import collections

    from magda.offers_gold import _reference_group

    kinds = collections.Counter()
    hit_size, miss_size = [], []
    blind_hit = blind_miss = 0

    for page in pages:
        assignment = assignments.get(page.get("page_id"))
        if assignment is None:
            continue
        entities = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]
        groups = model.group_page_words(page, model.threshold)
        system_of = {w: g for g, words in enumerate(groups) for w in words}

        reference, types = {}, {}
        for entity in entities:
            group = _reference_group(entity, assignment)
            if group is None:
                continue
            reference.setdefault(group, set()).add((entity.start, entity.end))
            types.setdefault(group, set()).add(entity.type)

        system = {}
        for entity in entities:
            if _reference_group(entity, assignment) is None:
                continue
            found = {system_of[w] for w in range(entity.start, entity.end)
                     if w in system_of}
            if len(found) == 1:
                system.setdefault(found.pop(), set()).add((entity.start, entity.end))

        exact = {frozenset(m) for m in system.values()}
        for group, members in reference.items():
            blind = "UNIT_PRICE" not in types[group]
            if frozenset(members) in exact:
                hit_size.append(len(members))
                blind_hit += blind
                continue
            miss_size.append(len(members))
            blind_miss += blind
            landed = collections.Counter()
            for key in members:
                for index, group_members in system.items():
                    if key in group_members:
                        landed[index] += 1
            foreign = any(len(system.get(i, ())) > landed[i] for i in landed)
            if len(landed) > 1 and foreign:
                kinds["zerfallen_und_verschmolzen"] += 1
            elif len(landed) > 1:
                kinds["zerfallen"] += 1
            elif foreign:
                kinds["verschmolzen"] += 1
            else:
                kinds["entity_fehlt"] += 1

    return {
        "hit": len(hit_size),
        "miss": len(miss_size),
        "kinds": dict(kinds),
        "mean_size_hit": sum(hit_size) / len(hit_size) if hit_size else None,
        "mean_size_miss": sum(miss_size) / len(miss_size) if miss_size else None,
        "blind_share_hit": blind_hit / len(hit_size) if hit_size else None,
        "blind_share_miss": blind_miss / len(miss_size) if miss_size else None,
    }


# Ein Variantenblock ist eine Referenzgruppe, die denselben Werttyp mehrfach
# traegt - "Pfanne: 20 cm 9.99 / 24 cm 14.99". Genau die Form, die ein flaches
# Gruppenlabel nicht abbilden kann (Issue #6).
VARIANT_MULTIPLES = ("PRICE", "QUANTITY")


def _variant_rows(page: dict, assignment: dict, model):
    """Je Referenzgruppe eine Zeile, je *positivem* Paar eine Zeile.

    Getrennt von der Aggregation, weil dieselben Rohzeilen einmal aus einem
    Modell und einmal aus fuenf Fold-Modellen kommen. Zwei Zaehlschleifen
    waeren zwei Gelegenheiten, verschieden zu zaehlen.
    """
    import collections

    from magda.offers_gold import _reference_group

    entities = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]
    groups = model.group_page_words(page, model.threshold)
    system_of = {w: g for g, words in enumerate(groups) for w in words}

    reference: dict = {}
    for entity in entities:
        group = _reference_group(entity, assignment)
        if group is not None:
            reference.setdefault(group, []).append(entity)

    system: dict = {}
    for entity in entities:
        if _reference_group(entity, assignment) is None:
            continue
        found = {system_of[w] for w in range(entity.start, entity.end)
                 if w in system_of}
        if len(found) == 1:
            system.setdefault(found.pop(), set()).add((entity.start, entity.end))
    exact = {frozenset(members) for members in system.values()}

    group_rows, variant_of = [], {}
    for group, members in reference.items():
        counts = collections.Counter(e.type for e in members)
        variant = any(counts[t] > 1 for t in VARIANT_MULTIPLES)
        variant_of[group] = variant
        keys = frozenset((e.start, e.end) for e in members)
        group_rows.append({"variant": variant, "hit": keys in exact,
                           "size": len(members)})

    # Nur positive Paare: die Frage ist, welche Kante das System *verliert*,
    # nicht wie gut es trennt - dafuer ist die AUC in `diagnose` zustaendig.
    edge_rows = []
    pairs = offer_pairs.page_pairs(page, blocks=model.blocks)
    if pairs.index_pairs:
        edges = model.score_page(page)
        of_index = [_reference_group(e, assignment) for e in pairs.entities]
        for (i, j) in pairs.index_pairs:
            if of_index[i] is None or of_index[i] != of_index[j]:
                continue
            kinds = sorted((pairs.entities[i].type, pairs.entities[j].type))
            edge_rows.append({
                "variant": variant_of.get(of_index[i], False),
                "pair": "|".join(kinds),
                "probability": edges[(i, j)],
                "above": edges[(i, j)] >= model.threshold,
            })
    return group_rows, edge_rows


def _variant_summary(group_rows: list[dict], edge_rows: list[dict]) -> dict:
    """Rohe Zaehlungen. Bei 19 Gruppen ist eine Prozentzahl allein bedeutungslos."""
    groups = {}
    for bucket, rows in (("all", group_rows),
                         ("variant", [r for r in group_rows if r["variant"]]),
                         ("plain", [r for r in group_rows if not r["variant"]])):
        hit = sum(1 for r in rows if r["hit"])
        groups[bucket] = {
            "total": len(rows),
            "hit": hit,
            "recall": hit / len(rows) if rows else None,
            "mean_size": sum(r["size"] for r in rows) / len(rows) if rows else None,
        }

    edges: dict = {}
    for bucket in ("variant", "plain"):
        rows = [r for r in edge_rows if r["variant"] == (bucket == "variant")]
        by_pair: dict = {}
        for row in rows:
            entry = by_pair.setdefault(row["pair"], {"total": 0, "above": 0,
                                                     "sum": 0.0})
            entry["total"] += 1
            entry["above"] += int(row["above"])
            entry["sum"] += row["probability"]
        for entry in by_pair.values():
            entry["recall"] = entry["above"] / entry["total"]
            entry["mean_probability"] = entry.pop("sum") / entry["total"]
        edges[bucket] = dict(sorted(by_pair.items(),
                                    key=lambda kv: -kv[1]["total"]))
    return {"groups": groups, "edges": edges}


def variant_blocks(pages: list[dict], assignments: dict, model) -> dict:
    """Trifft das System Variantenbloecke schlechter - und an welcher Kante?

    Zwei Fragen in einem Durchgang, weil sie zusammen erst eine Konsequenz
    ergeben. Zerfallen die Bloecke, *und* liegen die PRICE|PRICE-Kanten unter
    der Schwelle, fehlt dem Paarmodell ein Merkmal. Zerfallen sie bei
    ordentlichen Kanten, verschenkt der Dekoder sie - beim ILP naheliegend,
    weil ein Variantenblock ein Stern um den Produktnamen ist, die
    Transitivitaet aber eine Clique verlangt.
    """
    group_rows: list[dict] = []
    edge_rows: list[dict] = []
    for page in pages:
        assignment = assignments.get(page.get("page_id"))
        if assignment is None:
            continue
        rows, edges = _variant_rows(page, assignment, model)
        group_rows += rows
        edge_rows += edges
    return _variant_summary(group_rows, edge_rows)


def variant_blocks_cv(pages: list[dict], assignments: dict, blocks,
                      folds: int = 5, epochs: int = 300, seed: int = 0,
                      objective: str = "group_f1", decoder: str = "union",
                      progress=None) -> dict:
    """Dieselbe Auszaehlung out-of-fold - jede Seite von einem Modell ohne sie.

    In-sample waeren gerade die seltenen Kanten geschoent: das Modell hat die
    19 Bloecke gesehen, die hier beurteilt werden. Nebeneffekt ist die
    Stichprobe - ueber alle Referenzseiten statt ueber Dev allein.
    """
    group_rows: list[dict] = []
    edge_rows: list[dict] = []
    thresholds: list[float] = []
    for model, outer in fold_models(pages, assignments, blocks, folds=folds,
                                    epochs=epochs, seed=seed,
                                    objective=objective, decoder=decoder,
                                    progress=progress):
        thresholds.append(model.threshold)
        for page in outer:
            rows, edges = _variant_rows(page, assignments[page["page_id"]], model)
            group_rows += rows
            edge_rows += edges
    summary = _variant_summary(group_rows, edge_rows)
    summary["thresholds"] = thresholds
    return summary


def diagnose(pages: list[dict], assignments: dict, model,
             thresholds: list[float] | None = None) -> dict:
    """Zerlegt "wer deckelt?" in Kantenqualitaet, Schwellenwahl und Dekoder.

    Vier Zahlen, die sich gegenseitig einordnen:

        auc           Trennschaerfe der Kanten, ohne Schwelle. Nur das
                      Paarmodell.
        achieved      Gruppen-F1 bei der kalibrierten Schwelle - was das
                      System heute liefert.
        ceiling       Bestes Gruppen-F1 ueber alle Schwellen. **Post-hoc auf
                      den Messseiten gewaehlt, also keine erreichbare
                      Leistung**, sondern die Obergrenze dieses Dekoders bei
                      diesen Kanten. Der Abstand zu `achieved` ist der Preis
                      der Schwellenwahl.
        oracle        Gruppen-F1, wenn die Kanten *perfekt* waeren. Muss 1.0
                      sein; ist es das nicht, verliert der Dekoder selbst
                      Information, unabhaengig vom Modell.

    Die Lesart: Hohe `auc` bei niedriger `ceiling` heisst, die Kanten sind
    gut und das Dekodieren verschenkt sie - dann lohnen Constraints und
    bessere Verfahren. Niedrige `auc` heisst, das Paarmodell ist der
    Deckel - dann helfen nur bessere Merkmale oder eine bessere Referenz,
    und kein Dekodierverfahren der Welt.
    """
    from magda import offer_model
    from magda.offers_gold import _reference_group

    thresholds = thresholds or [round(0.50 + 0.02 * i, 2) for i in range(25)]

    labels: list[int] = []
    scores: list[float] = []
    scored: list[tuple[dict, dict, list, dict]] = []
    for page in pages:
        assignment = assignments.get(page.get("page_id"))
        if assignment is None:
            continue
        pairs = offer_pairs.page_pairs(page, blocks=model.blocks)
        if not pairs.index_pairs:
            continue
        edges = model.score_page(page)
        groups = [_reference_group(e, assignment) for e in pairs.entities]
        truth: dict[tuple[int, int], float] = {}
        for (i, j) in pairs.index_pairs:
            together = None
            if groups[i] is not None and groups[j] is not None:
                together = 1 if groups[i] == groups[j] else 0
                labels.append(together)
                scores.append(edges[(i, j)])
            truth[(i, j)] = 1.0 if together == 1 else 0.0
        scored.append((page, edges, pairs.entities, truth))

    def measure(edge_source, threshold: float) -> Counts:
        total = Counts()
        for page, edges, entities, truth in scored:
            chosen = truth if edge_source == "oracle" else edges
            groups = offer_model.decode(model.decoder, len(entities), chosen, threshold)
            total.add(judge_page(page, assignments[page["page_id"]],
                                 offer_pairs.entity_groups_to_words(page, groups)).total)
        return total

    curve = [{"threshold": t, "group_f1": measure("model", t).group_f1,
              } for t in thresholds]
    best = max(curve, key=lambda row: (row["group_f1"] or 0.0,))

    return {
        "pages": len(scored),
        "pairs": len(labels),
        "positive": sum(labels),
        "decoder": model.decoder,
        "auc": edge_auc(labels, scores),
        "threshold": model.threshold,
        "achieved": measure("model", model.threshold).group_f1,
        "ceiling": best["group_f1"],
        "ceiling_threshold": best["threshold"],
        "oracle": measure("oracle", 0.5).group_f1,
        "failures": failure_kinds(pages, assignments, model),
        "curve": curve,
    }
