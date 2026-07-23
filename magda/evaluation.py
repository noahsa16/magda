"""Entity-Level-Evaluation mit seqeval (Precision, Recall, F1).

Wichtig: seqeval bewertet auf Entity-Ebene, nicht pro Token. Ein Entity
zählt nur dann als richtig, wenn Span UND Typ exakt stimmen – das ist
deutlich strenger als Token-Accuracy und genau die Metrik aus dem Proposal.
"""

import numpy as np
from seqeval.metrics import classification_report, f1_score, precision_score, recall_score

from magda.alignment import IGNORE_INDEX
from magda.labels import id2label


def _decode(predictions: np.ndarray, label_ids: np.ndarray):
    """Filtert die mit -100 maskierten Positionen raus und mappt IDs auf Tags."""
    true_tags, pred_tags = [], []
    for pred_row, label_row in zip(predictions, label_ids):
        row_true, row_pred = [], []
        for p, l in zip(pred_row, label_row):
            if l == IGNORE_INDEX:
                continue
            row_true.append(id2label[int(l)])
            row_pred.append(id2label[int(p)])
        true_tags.append(row_true)
        pred_tags.append(row_pred)
    return true_tags, pred_tags


def compute_metrics(eval_pred):
    """Für den HF-Trainer (compute_metrics-Callback)."""
    logits, label_ids = eval_pred
    predictions = np.argmax(logits, axis=-1)
    true_tags, pred_tags = _decode(predictions, label_ids)
    return {
        "precision": precision_score(true_tags, pred_tags),
        "recall": recall_score(true_tags, pred_tags),
        "f1": f1_score(true_tags, pred_tags),
    }


def full_report(predictions: np.ndarray, label_ids: np.ndarray) -> str:
    """Ausführlicher Report pro Entity-Typ, für die Fehleranalyse in Phase 3."""
    true_tags, pred_tags = _decode(predictions, label_ids)
    return classification_report(true_tags, pred_tags, digits=3)


def report_dict(predictions: np.ndarray, label_ids: np.ndarray) -> dict:
    """Wie full_report, aber als Dict – für den JSON-Export ans Frontend."""
    true_tags, pred_tags = _decode(predictions, label_ids)
    return classification_report(true_tags, pred_tags, digits=3, output_dict=True)
