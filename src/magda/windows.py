"""Seiten in überlappenden Fenstern – nur für die Vorhersage.

Bewusst getrennt von `dataset.py`: dort hängen Training und Evaluation dran,
und deren Zahlen sollen mit den bisher berichteten vergleichbar bleiben. Wer
das Fenster auch beim Messen verschiebt, misst auf einem anderen Testsatz als
in `reports/`, ohne dass es jemandem auffällt.

Gemessen über die Testwoche (100 Seiten, GBERT): abgeschnitten wurden 1476 von
20952 Wörtern (7,0 %), darin 186 Referenz-Entities (3,6 %). Für den F1 fällt
das kaum auf – die Metrik zählt nur, was im Fenster liegt. Für die
Angebots-Rekonstruktion schon: auf `1351605_p19` fehlten 27 Entities am Stück.
"""

from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import Dataset
from transformers import LayoutLMv2ImageProcessor

from magda.alignment import subword_boxes
from magda.config import IMAGES_DIR, Variant
from magda.ocr import normalize_bbox


class WindowDataset(Dataset):
    """Ein Eintrag je Fenster, nicht je Seite.

    `page_index[i]` sagt, zu welcher Seite Fenster i gehört, `word_ids[i]`
    welche Wörter darin liegen. Beides braucht `predict.merge_windows`, um die
    Fenster wieder zu einer Seite zusammenzulegen.
    """

    def __init__(self, pages: list[dict], tokenizer, max_length: int, stride: int,
                 variant: Variant, images_dir=None):
        self.encodings = []
        self.word_ids = []
        self.page_index = []
        self.variant = variant
        self.page_ids = [page["page_id"] for page in pages]
        # None statt eines Default-Arguments: `IMAGES_DIR` an dieser Stelle
        # fest zu binden hätte den Wert beim Modulimport eingefroren und
        # `magda.pipeline.extract_offers` gezwungen, entweder nach data/images/
        # zu schreiben oder das globale `config.IMAGES_DIR` zu verbiegen.
        self.images_dir = Path(images_dir) if images_dir is not None else IMAGES_DIR
        self.image_processor = (
            LayoutLMv2ImageProcessor(apply_ocr=False) if variant.image else None
        )

        for page_nr, page in enumerate(pages):
            words = [w["text"] for w in page["words"]]
            arguments = {
                "truncation": True,
                "max_length": max_length,
                "padding": "max_length",
                "stride": stride,
                "return_overflowing_tokens": True,
            }
            boxes = [
                normalize_bbox(w["bbox"], page["width"], page["height"])
                for w in page["words"]
            ]
            if variant.boxes == "tokenizer":
                encoded = tokenizer(words, boxes=boxes, **arguments)
            else:
                encoded = tokenizer(words, is_split_into_words=True, **arguments)

            for window in range(len(encoded["input_ids"])):
                # overflow_to_sample_mapping und die Bildkanäle gehören nicht
                # in den Vorwärtsdurchlauf; sie sind Buchhaltung des Tokenizers.
                fenster = {
                    key: value[window]
                    for key, value in encoded.items()
                    if key != "overflow_to_sample_mapping"
                }
                # Je Fenster eigene Wortindizes, also auch eigene Boxen: das
                # zweite Fenster beginnt mitten auf der Seite, seine erste
                # Position traegt nicht die Box von Wort 0.
                if variant.boxes == "manual":
                    fenster["bbox"] = subword_boxes(encoded.word_ids(window), boxes)
                self.encodings.append(fenster)
                self.word_ids.append(encoded.word_ids(window))
                self.page_index.append(page_nr)

    def __len__(self):
        return len(self.encodings)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v) for k, v in self.encodings[idx].items()}
        if not self.variant.image:
            return item
        image_file = self.images_dir / f"{self.page_ids[self.page_index[idx]]}.png"
        with Image.open(image_file) as page_image:
            pixels = self.image_processor(
                page_image.convert("RGB"), return_tensors="pt"
            )["pixel_values"]
        item["image"] = pixels[0]
        return item

    def windows_of(self, page_nr: int) -> list[int]:
        """Indizes aller Fenster einer Seite, in Reihenfolge."""
        return [i for i, p in enumerate(self.page_index) if p == page_nr]
