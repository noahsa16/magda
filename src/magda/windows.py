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

import torch
from PIL import Image
from torch.utils.data import Dataset
from transformers import LayoutLMv2ImageProcessor

from magda.config import IMAGES_DIR
from magda.ocr import normalize_bbox


class WindowDataset(Dataset):
    """Ein Eintrag je Fenster, nicht je Seite.

    `page_index[i]` sagt, zu welcher Seite Fenster i gehört, `word_ids[i]`
    welche Wörter darin liegen. Beides braucht `predict.merge_windows`, um die
    Fenster wieder zu einer Seite zusammenzulegen.
    """

    def __init__(self, pages: list[dict], tokenizer, max_length: int, stride: int,
                 layout: bool):
        self.encodings = []
        self.word_ids = []
        self.page_index = []
        self.layout = layout
        self.page_ids = [page["page_id"] for page in pages]
        self.image_processor = LayoutLMv2ImageProcessor(apply_ocr=False) if layout else None

        for page_nr, page in enumerate(pages):
            words = [w["text"] for w in page["words"]]
            arguments = {
                "truncation": True,
                "max_length": max_length,
                "padding": "max_length",
                "stride": stride,
                "return_overflowing_tokens": True,
            }
            if layout:
                boxes = [
                    normalize_bbox(w["bbox"], page["width"], page["height"])
                    for w in page["words"]
                ]
                encoded = tokenizer(words, boxes=boxes, **arguments)
            else:
                encoded = tokenizer(words, is_split_into_words=True, **arguments)

            for window in range(len(encoded["input_ids"])):
                # overflow_to_sample_mapping und die Bildkanäle gehören nicht
                # in den Vorwärtsdurchlauf; sie sind Buchhaltung des Tokenizers.
                self.encodings.append(
                    {
                        key: value[window]
                        for key, value in encoded.items()
                        if key != "overflow_to_sample_mapping"
                    }
                )
                self.word_ids.append(encoded.word_ids(window))
                self.page_index.append(page_nr)

    def __len__(self):
        return len(self.encodings)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v) for k, v in self.encodings[idx].items()}
        if not self.layout:
            return item
        image_file = IMAGES_DIR / f"{self.page_ids[self.page_index[idx]]}.png"
        with Image.open(image_file) as page_image:
            pixels = self.image_processor(
                page_image.convert("RGB"), return_tensors="pt"
            )["pixel_values"]
        item["image"] = pixels[0]
        return item

    def windows_of(self, page_nr: int) -> list[int]:
        """Indizes aller Fenster einer Seite, in Reihenfolge."""
        return [i for i, p in enumerate(self.page_index) if p == page_nr]
