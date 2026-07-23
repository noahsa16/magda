"""Laden der gelabelten Seiten und Aufbau der PyTorch-Datasets.

Eine gelabelte Seite (data/labeled/*.json) sieht so aus:
    {
      "page_id": "462828_p3",
      "width": 595.28, "height": 841.89,
      "words": [{"text": "Rinderhackfleisch", "bbox": [x0, y0, x1, y1]}, ...],
      "tags":  ["B-PRODUCT", ...]          # ein BIO-Tag pro Wort
    }
"""

import json
import random

import torch
from torch.utils.data import Dataset

from magda.alignment import align_word_labels
from magda.config import LABELED_DIR, SEED, SPLITS_DIR
from magda.ocr import normalize_bbox


def load_labeled_pages() -> list[dict]:
    pages = []
    for path in sorted(LABELED_DIR.glob("*.json")):
        with open(path) as f:
            pages.append(json.load(f))
    return pages


def get_or_create_splits(pages: list[dict]) -> dict[str, list[str]]:
    """80/10/10-Split auf Seitenebene, einmal gewürfelt und dann eingefroren.

    Der Split liegt als Datei in data/splits/, damit alle im Team (und alle
    Trainingsläufe) dieselbe Aufteilung benutzen. Neu würfeln = Datei löschen.

    TODO: aktuell wird über Seiten gesplittet. Diskutieren, ob wir stattdessen
    über Kataloge splitten sollten, damit kein Prospekt gleichzeitig in Train
    und Test landet (Angebote wiederholen sich zwischen Wochen).
    """
    split_file = SPLITS_DIR / "split.json"
    if split_file.exists():
        with open(split_file) as f:
            return json.load(f)

    page_ids = [p["page_id"] for p in pages]
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
    """

    def __init__(self, pages: list[dict], tokenizer, max_length: int):
        self.encodings = []
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

    def __len__(self):
        return len(self.encodings)

    def __getitem__(self, idx):
        return {k: torch.tensor(v) for k, v in self.encodings[idx].items()}
