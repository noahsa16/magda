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

from magda.alignment import align_word_labels
from magda.config import (
    IMAGES_DIR,
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
    """80/10/10-Split auf Seitenebene, einmal gewürfelt und dann eingefroren.

    Der Split liegt als Datei in data/splits/, damit alle im Team (und alle
    Trainingsläufe) dieselbe Aufteilung benutzen. Neu würfeln = Datei löschen.

    Gewürfelt wird über *alle* extrahierten Seiten, nicht über die gerade
    gelabelten. Sonst hinge die Aufteilung am Fortschritt des Labelings: wer
    bei 141 von 196 Seiten trainiert, fröre einen Split ein, dem 55 Seiten
    fehlen, und die nachgelieferten landeten sämtlich im Training. Seiten ohne
    Labels tauchen in `select_split` schlicht nicht auf.

    TODO: aktuell wird über Seiten gesplittet. Diskutieren, ob wir stattdessen
    über Kataloge splitten sollten, damit kein Prospekt gleichzeitig in Train
    und Test landet (Angebote wiederholen sich zwischen Wochen).
    """
    split_file = SPLITS_DIR / "split.json"
    if split_file.exists():
        with open(split_file) as f:
            return json.load(f)

    extracted = sorted(p.stem for p in WORDS_DIR.glob("*.json"))
    page_ids = extracted or [p["page_id"] for p in pages]
    rng = random.Random(SEED)
    rng.shuffle(page_ids)

    n = len(page_ids)
    n_dev = max(1, n // 10)
    splits = {
        "train": page_ids[: n - 2 * n_dev],
        "dev": page_ids[n - 2 * n_dev : n - n_dev],
        "test": page_ids[n - n_dev :],
    }

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    with open(split_file, "w") as f:
        json.dump(splits, f, indent=2)
    return splits


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


def split_by_week(page_ids: list[str], dev_share: float = 0.1) -> dict[str, list[str]]:
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
    """
    wochen = group_by_week(page_ids)
    if len(wochen) < 2:
        raise ValueError(
            f"Wochen-Split braucht mindestens zwei Erscheinungswochen, "
            f"gefunden: {len(wochen)}. Erst mehr Wochen ernten."
        )

    test = wochen[-1]
    train = [pid for woche in wochen[:-1] for pid in woche]

    rng = random.Random(SEED)
    gemischt = sorted(train)
    rng.shuffle(gemischt)
    n_dev = max(1, int(len(gemischt) * dev_share))
    return {
        "train": sorted(gemischt[n_dev:]),
        "dev": sorted(gemischt[:n_dev]),
        "test": sorted(test),
    }


def select_split(pages: list[dict], splits: dict, name: str) -> list[dict]:
    wanted = set(splits[name])
    return [p for p in pages if p["page_id"] in wanted]


class TextDataset(Dataset):
    """Dataset für die text-only Baseline (GBERT). Nur Wörter, keine Positionen.

    TODO: Seiten mit mehr als 512 Subwords werden aktuell schlicht abgeschnitten
    (truncation). Falls das messbar Entities kostet, auf Sliding Window umstellen.
    """

    def __init__(self, pages: list[dict], tokenizer, max_length: int):
        self.encodings = []
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
            self.encodings.append(enc)

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
