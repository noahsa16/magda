"""Tests für den JSON-Export der Evaluation (Frontend-Dashboard liest diese Dicts)."""

import json

import numpy as np

from magda.evaluation import report_dict, word_level_report_dict
from magda.labels import label2id


def test_report_dict_liefert_metriken_pro_entity():
    # Eine Sequenz: B-PRODUCT I-PRODUCT O, letzte Position maskiert (-100).
    label_ids = np.array(
        [[label2id["B-PRODUCT"], label2id["I-PRODUCT"], label2id["O"], -100]]
    )
    predictions = np.array(
        [[label2id["B-PRODUCT"], label2id["I-PRODUCT"], label2id["O"], label2id["O"]]]
    )

    report = report_dict(predictions, label_ids)

    assert report["PRODUCT"]["f1-score"] == 1.0
    assert report["PRODUCT"]["support"] == 1
    assert "micro avg" in report


def test_word_level_report_dict_auf_wort_tags():
    """Für Modelle ohne HF-Trainer (Flair-Arm, später Gold gegen LLM)."""
    true_tags = [["B-BRAND", "I-BRAND", "O"], ["B-BRAND", "O"]]
    pred_tags = [["B-BRAND", "I-BRAND", "O"], ["O", "O"]]

    report = word_level_report_dict(true_tags, pred_tags)

    assert report["BRAND"]["support"] == 2
    assert report["BRAND"]["recall"] == 0.5
    assert report["BRAND"]["precision"] == 1.0


def test_word_level_report_dict_ist_json_serialisierbar():
    """seqeval liefert support als numpy.int64, worüber json.dump stolpert."""
    report = word_level_report_dict([["B-BRAND"]], [["B-BRAND"]])

    json.dumps(report)
