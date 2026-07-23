"""Tests für den JSON-Export der Evaluation (Frontend-Dashboard liest diese Dicts)."""

import numpy as np

from magda.evaluation import report_dict
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
