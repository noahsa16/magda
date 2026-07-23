"""Tests fürs Subword-Alignment – die klassische stille Fehlerquelle:
falsch gesetzte -100er sieht man im Training nicht, nur in schlechten Metriken.
"""

from magda.alignment import IGNORE_INDEX, align_word_labels
from magda.labels import label2id


def test_erstes_subword_traegt_label():
    # Simuliert: [CLS] wort0 wort1a wort1b [SEP]
    word_ids = [None, 0, 1, 1, None]
    tags = ["B-PRODUCT", "I-PRODUCT"]

    labels = align_word_labels(word_ids, tags)

    assert labels == [
        IGNORE_INDEX,
        label2id["B-PRODUCT"],
        label2id["I-PRODUCT"],  # erstes Subword von Wort 1
        IGNORE_INDEX,           # Fortsetzungs-Subword -> maskiert
        IGNORE_INDEX,
    ]


def test_padding_wird_maskiert():
    word_ids = [None, 0, None, None, None]
    labels = align_word_labels(word_ids, ["O"])
    assert labels[2:] == [IGNORE_INDEX] * 3


def test_laenge_stimmt_immer():
    word_ids = [None, 0, 0, 1, 2, 2, 2, None]
    labels = align_word_labels(word_ids, ["O", "B-PRICE", "O"])
    assert len(labels) == len(word_ids)
