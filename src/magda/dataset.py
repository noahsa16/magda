"""Laden der gelabelten Seiten und Aufbau der PyTorch-Datasets.

Eine gelabelte Seite (data/labeled/<modell>/*.json) sieht so aus:
    {
      "page_id": "462828_p3",
      "width": 595.28, "height": 841.89,
      "words": [{"text": "Rinderhackfleisch", "bbox": [x0, y0, x1, y1]}, ...],
      "tags":  ["B-PRODUCT", ...],         # ein BIO-Tag pro Wort
      "model": "mistral-medium-3.5-128b"   # wer die Tags erzeugt hat
    }
"""

import json
import random

import torch
from PIL import Image
from torch.utils.data import Dataset
from transformers import LayoutLMv2ImageProcessor

from magda.alignment import align_word_labels, subword_boxes
from magda.config import (
    IMAGES_DIR,
    Variant,
    SEED,
    SPLITS_DIR,
    WORDS_DIR,
    default_labeled_model,
    labeled_dir,
)
from magda.ocr import normalize_bbox


def load_labeled_pages(model: str | None = None) -> list[dict]:
    """Lädt die Labels genau eines Modells.

    Bewusst nicht "alle Ordner einsammeln": derselbe page_id liegt in jedem
    Modellordner, und eine Mischung daraus wäre ein Trainingssatz, dessen
    Labelqualität von Seite zu Seite springt. Welches Modell trainiert wird,
    ist eine Entscheidung und keine Nebenwirkung des Dateisystems.
    """
    model = model or default_labeled_model()
    if model is None:
        return []
    pages = []
    for path in sorted(labeled_dir(model).glob("*.json")):
        with open(path) as f:
            pages.append(json.load(f))
    return pages


def get_or_create_splits(pages: list[dict]) -> dict[str, list[str]]:
    """Die eingefrorene Aufteilung aus data/splits/split.json.

    Früher wurde hier ein 80/10/10-Split über Seiten gewürfelt, falls die Datei
    fehlte. Das war der gefährlichste Zweig im Projekt: Genau dieser Seiten-Split
    leckt (12 von 19 Testseiten hatten einen Trainingszwilling, Median-Jaccard
    0.851), und er entstand kommentarlos – auf einer frischen GPU-Instanz, bei
    einem Teammitglied ohne die Datei, nach einem versehentlichen Löschen. Die
    Zahlen sehen dabei *besser* aus als beim korrekten Wochen-Split, es fällt
    also nicht einmal negativ auf.

    Der Split wird deshalb nur noch gelesen. Angelegt wird er ausdrücklich mit
    `magda split`, wo die Strategie eine bewusste Entscheidung ist.
    """
    split_file = SPLITS_DIR / "split.json"
    if not split_file.exists():
        raise FileNotFoundError(
            f"{split_file} fehlt. Die Aufteilung wird nicht mehr automatisch "
            f"gewürfelt – ein Seiten-Split leckt zwischen Train und Test.\n"
            f"Anlegen mit: magda split --strategy week"
        )
    with open(split_file) as f:
        return json.load(f)


# Innerhalb einer Erscheinungswoche liegen Pennys Katalog-IDs dicht beieinander
# (gemessen: höchstens 24 auseinander), zwischen zwei Wochen klafft eine Lücke
# von mehreren tausend. Die Schwelle trennt großzügig, ohne auf feste Nummern
# zu setzen – die wären beim nächsten Erntelauf veraltet.
WEEK_GAP = 200


def group_by_week(page_ids: list[str]) -> list[list[str]]:
    """Teilt Seiten nach Erscheinungswoche, absteigend sortiert nach Alter.

    Die Woche steht nirgends in den Daten: `catalog_meta.json` kennt nur die
    Region, und Pennys Markt-API kennt nur die laufende Woche. Ableitbar ist
    sie aber aus dem Abstand der Katalog-IDs.
    """
    kataloge = sorted({int(pid.rsplit("_p", 1)[0]) for pid in page_ids})
    if not kataloge:
        return []

    wochen: list[set[int]] = [{kataloge[0]}]
    for vorher, jetzt in zip(kataloge, kataloge[1:]):
        if jetzt - vorher > WEEK_GAP:
            wochen.append(set())
        wochen[-1].add(jetzt)

    return [
        sorted(pid for pid in page_ids if int(pid.rsplit("_p", 1)[0]) in woche)
        for woche in wochen
    ]


# Ab dieser Ähnlichkeit zeigen zwei Seiten dieselbe Vorlage und dürfen nicht
# auf Train und Dev verteilt werden. Dieselbe Schwelle, mit der `magda queue`
# die Annotationsreihenfolge clustert – wer sie hier lockert, macht Dev wieder
# zum Spiegel des Trainings.
DEV_CLUSTER_THRESHOLD = 0.7


def load_page_words(page_ids: list[str]) -> dict[str, list[str]]:
    """Wortlisten aus data/words – für Ähnlichkeitsvergleiche, nicht fürs Modell.

    Fehlende Dateien werden übergangen statt zu werfen: der Aufrufer vergleicht
    damit nur, und eine Seite ohne Wortliste ist schlicht mit keiner anderen
    ähnlich.
    """
    words = {}
    for pid in page_ids:
        path = WORDS_DIR / f"{pid}.json"
        if not path.exists():
            continue
        with open(path) as f:
            words[pid] = [w["text"] for w in json.load(f)["words"]]
    return words


def split_by_week(
    page_ids: list[str],
    dev_share: float = 0.1,
    pages: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Älteste Woche(n) trainieren, die jüngste testen.

    Der Seiten-Split leckt: Penny gibt je Woche 44 fast identische
    Regionalausgaben heraus, und die Entdopplung greift erst ab Jaccard 0.95 –
    zwei Seiten bei 0.949 landen also in Train *und* Test. Gemessen hatte
    darum jede zweite Testseite einen nahen Zwilling im Training.

    Über Wochen getrennt sinkt die Median-Ähnlichkeit von 0.851 auf 0.257.
    Zugleich entspricht die Richtung dem Einsatzfall: auf alten Prospekten
    lernen, auf neuen anwenden.

    Dev wird aus den Trainingswochen gezogen, nicht aus der Testwoche – sonst
    wählt die Modellauswahl auf denselben Daten aus, auf denen gemessen wird.
    Und es wird *clusterweise* gezogen: zufällig je Seite gemessen (02.08.2026,
    drei Wochen) lag Dev bei Median-Ähnlichkeit 0.721 zum Training, vier von
    19 Seiten über 0.9. Der Testsplit war da längst sauber – die Modellauswahl
    lief trotzdem auf halb auswendig Gelerntem und griff damit zum falschen
    Checkpoint. Ein gruppierter Split kostet nichts außer etwas Ungenauigkeit
    in der Dev-Größe.

    `pages` bildet page_id auf Wortliste ab; ohne Angabe wird aus data/words
    geladen. Seiten ohne Wortliste bilden je einen eigenen Cluster.
    """
    weeks = group_by_week(page_ids)
    if len(weeks) < 2:
        raise ValueError(
            f"Wochen-Split braucht mindestens zwei Erscheinungswochen, "
            f"gefunden: {len(weeks)}. Erst mehr Wochen ernten."
        )

    test = weeks[-1]
    train = sorted(pid for week in weeks[:-1] for pid in week)

    words = pages if pages is not None else load_page_words(train)
    clusters = _dev_clusters(train, words)

    rng = random.Random(SEED)
    rng.shuffle(clusters)

    # Ganze Cluster aufnehmen, bis das Ziel erreicht ist. Der letzte darf
    # überschießen – ihn zu überspringen und einen kleineren zu nehmen füllte
    # Dev systematisch mit Einzelseiten, also mit den seltenen Layouts.
    goal = max(1, int(len(train) * dev_share))
    dev: list[str] = []
    rest: list[str] = []
    for cluster in clusters:
        (dev if len(dev) < goal else rest).extend(cluster)

    return {"train": sorted(rest), "dev": sorted(dev), "test": sorted(test)}


def _dev_clusters(page_ids: list[str], words: dict[str, list[str]]) -> list[list[str]]:
    """Duplikat-Cluster der Trainingswochen, jede Seite in genau einem."""
    from magda.dedupe import group

    known = {pid: words[pid] for pid in page_ids if pid in words}
    clusters = [list(g) for g in group(known, threshold=DEV_CLUSTER_THRESHOLD)]
    clusters += [[pid] for pid in page_ids if pid not in known]
    return clusters


def select_split(pages: list[dict], splits: dict, name: str) -> list[dict]:
    wanted = set(splits[name])
    return [p for p in pages if p["page_id"] in wanted]


def duplicate_clusters(pages: list[dict]) -> list[list[str]]:
    """Duplikat-Cluster der Seiten (Jaccard 0.7), Einzelseiten eingeschlossen.

    Die unabhängige Einheit des Projekts. Penny gibt je Woche 44 fast
    gleiche Regionalfassungen heraus; wer Seiten zählt, zählt Kopien.
    """
    from magda.dedupe import group

    words = {p["page_id"]: [w["text"] for w in (p.get("words") or [])] for p in pages}
    clusters = [sorted(c) for c in group(words, threshold=0.7)]
    known = {page_id for cluster in clusters for page_id in cluster}
    return clusters + [[p["page_id"]] for p in pages if p["page_id"] not in known]


def subset_by_clusters(pages: list[dict], limit: int) -> list[str]:
    """Höchstens `limit` Seiten, aber nur in ganzen Duplikat-Clustern.

    Für die Lernkurve: seitenweise gezogen zählen elf Regionalfassungen
    derselben Vorlage als elf Datenpunkte, und die Kurve sähe steiler aus,
    als sie ist – derselbe Fehler, der schon den Seiten-Split lecken ließ.

    Die Cluster stehen in einer festen Reihenfolge, und genommen wird das
    längste **Präfix**, das unter die Grenze passt. Nicht das gierigste
    Paket: ein Präfix ist ineinandergeschachtelt, gieriges Auffüllen nicht.
    Bei den Clustergrößen 3/2/1 nähme die gierige Variante zu 4 die Cluster
    3+1 und zu 5 die Cluster 3+2 – der zweite Kurvenpunkt enthielte den
    ersten dann nicht mehr, und die Kurve vergliche verschiedene Stichproben
    statt mehr von derselben.

    Sortiert wird nach `page_id`, **nicht nach Clustergröße**. Größe zuerst
    war der naheliegende Griff und kehrt den Zweck um: auf den 175
    Trainingsseiten (93 Cluster) ergäbe eine Grenze von 25 dann 23 Seiten
    aus **drei** Vorlagen – die Duplikate landen zuerst im Budget, und der
    erste Kurvenpunkt misst elf Regionalfassungen statt Datenmenge. Nach
    `page_id` sind es 25 Seiten aus 9 Clustern; über alle vier Punkte
    9/16/50/93 statt 3/9/25/93.

    Passt schon der größte Cluster nicht, wird abgebrochen statt eine leere
    Menge zurückzugeben: ein Training über null Seiten läuft sonst durch und
    liefert eine Zahl.
    """
    clusters = duplicate_clusters(pages)
    clusters.sort(key=lambda c: c[0])

    if clusters and len(clusters[0]) > limit:
        raise ValueError(
            f"Grenze {limit} liegt unter dem größten Duplikat-Cluster "
            f"({len(clusters[0])} Seiten). Clusterweise ziehen heißt: ganz "
            f"oder gar nicht."
        )

    chosen: list[str] = []
    for cluster in clusters:
        if len(chosen) + len(cluster) > limit:
            break
        chosen.extend(cluster)
    return sorted(chosen)


class TextDataset(Dataset):
    """Dataset für die text-only Baseline (GBERT). Nur Wörter, keine Positionen.

    TODO: Seiten mit mehr als 512 Subwords werden aktuell schlicht abgeschnitten
    (truncation). Falls das messbar Entities kostet, auf Sliding Window umstellen.
    """

    def __init__(self, pages: list[dict], tokenizer, max_length: int):
        self.encodings = []
        self.page_ids = []
        self.word_ids = []
        for page in pages:
            words = [w["text"] for w in page["words"]]
            enc = tokenizer(
                words,
                is_split_into_words=True,
                truncation=True,
                max_length=max_length,
                padding="max_length",
            )
            enc["labels"] = align_word_labels(enc.word_ids(), page["tags"])
            self.word_ids.append(enc.word_ids())
            self.encodings.append(enc)
            self.page_ids.append(page["page_id"])

    def __len__(self):
        return len(self.encodings)

    def __getitem__(self, idx):
        return {k: torch.tensor(v) for k, v in self.encodings[idx].items()}


class LayoutDataset(Dataset):
    """Dataset für LayoutXLM: Wörter + normalisierte Bounding-Boxen.

    Die Boxen werden hier von PDF-Punkten auf das 0-1000-Raster skaliert,
    das LayoutLM erwartet. Der Tokenizer (LayoutXLMTokenizerFast) übernimmt
    das Vervielfachen der Box auf die Subwords selbst.

    Zusätzlich zu Text und Boxen braucht das Modell das Seitenbild: LayoutXLM
    ist eine LayoutLMv2-Architektur, und deren visueller Backbone ist kein
    optionales Extra, sondern Teil des Vorwärtsdurchlaufs. Ohne `image`
    scheitert er mit einem nichtssagenden AttributeError im Backbone.

    Die Bilder werden erst in `__getitem__` geladen, nicht im Konstruktor: ein
    Tensor je Seite sind 224*224*3 Byte, bei ein paar hundert Seiten noch
    harmlos, bei ein paar tausend nicht mehr.
    """

    def __init__(self, pages: list[dict], tokenizer, max_length: int):
        self.encodings = []
        self.page_ids = []
        self.word_ids = []
        self.image_processor = LayoutLMv2ImageProcessor(apply_ocr=False)
        for page in pages:
            words = [w["text"] for w in page["words"]]
            boxes = [
                normalize_bbox(w["bbox"], page["width"], page["height"])
                for w in page["words"]
            ]
            enc = tokenizer(
                words,
                boxes=boxes,
                truncation=True,
                max_length=max_length,
                padding="max_length",
            )
            enc["labels"] = align_word_labels(enc.word_ids(), page["tags"])
            self.word_ids.append(enc.word_ids())
            self.encodings.append(enc)
            self.page_ids.append(page["page_id"])

    def __len__(self):
        return len(self.encodings)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v) for k, v in self.encodings[idx].items()}
        image_file = IMAGES_DIR / f"{self.page_ids[idx]}.png"
        with Image.open(image_file) as page_image:
            pixels = self.image_processor(
                page_image.convert("RGB"), return_tensors="pt"
            )["pixel_values"]
        item["image"] = pixels[0]
        return item


class LiltDataset(Dataset):
    """Dataset für LiLT: Wörter + Boxen, aber kein Seitenbild.

    Der Unterschied zu `LayoutDataset` sieht klein aus und ist der Kern des
    Arms. LayoutXLMs Tokenizer nimmt `boxes=` entgegen und vervielfacht sie
    selbst auf die Subwords; LiLTs Tokenizer ist ein reiner XLM-R-Tokenizer
    und kennt das Argument gar nicht. Die `bbox`-Spalte entsteht deshalb hier
    über `alignment.subword_boxes`.

    Fehlt sie, kommt keine Fehlermeldung: `LiltModel` setzt `bbox` still auf
    Null und trainiert ein Modell ohne jede Positionsinformation – also ein
    teureres GBERT, das im Vergleich dann den Layout-Anteil widerlegt, den es
    nie gesehen hat.
    """

    def __init__(self, pages: list[dict], tokenizer, max_length: int):
        self.encodings = []
        self.page_ids = []
        self.word_ids = []
        for page in pages:
            words = [w["text"] for w in page["words"]]
            boxes = [
                normalize_bbox(w["bbox"], page["width"], page["height"])
                for w in page["words"]
            ]
            enc = tokenizer(
                words,
                is_split_into_words=True,
                truncation=True,
                max_length=max_length,
                padding="max_length",
            )
            word_ids = enc.word_ids()
            enc["labels"] = align_word_labels(word_ids, page["tags"])
            enc["bbox"] = subword_boxes(word_ids, boxes)
            self.word_ids.append(word_ids)
            self.encodings.append(enc)
            self.page_ids.append(page["page_id"])

    def __len__(self):
        return len(self.encodings)

    def __getitem__(self, idx):
        return {k: torch.tensor(v) for k, v in self.encodings[idx].items()}


DATASETS = {
    "none": TextDataset,
    "manual": LiltDataset,
    "tokenizer": LayoutDataset,
}


def dataset_for(variant: Variant, pages: list[dict], tokenizer, max_length: int):
    """Das zur Variante passende Dataset – eine Stelle für alle vier Arme.

    Vorher stand in `train`, `eval` und `predict` je ein
    `layout = variant == "layoutxlm"`. Ein Boolean trug zwei Arme; beim
    dritten hätte jede der drei Stellen einzeln nachgezogen werden müssen,
    und eine vergessene hätte nicht gecrasht, sondern leise das falsche
    Modell gemessen.
    """
    return DATASETS[variant.boxes](pages, tokenizer, max_length)
