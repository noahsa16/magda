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


def word_level_report(true_tags: list[list[str]], pred_tags: list[list[str]]) -> str:
    """Report über zwei Wort-Tag-Listen statt über Subword-Arrays.

    Modelle ohne HF-Trainer – der Flair-Vergleichsarm, später der Vergleich
    von Gold gegen die LLM-Labels – liefern Tags pro Wort. Die Metrik ist
    dieselbe, nur die Eingabe kommt nicht aus einem maskierten Tensor.
    """
    return classification_report(true_tags, pred_tags, digits=3)


def word_level_report_dict(true_tags: list[list[str]], pred_tags: list[list[str]]) -> dict:
    """Wie word_level_report, aber als Dict – für den JSON-Export.

    seqeval gibt "support" als numpy.int64 zurück, worüber json.dump stolpert.
    Deshalb hier gleich in native Python-Typen umwandeln.
    """
    report = classification_report(true_tags, pred_tags, digits=3, output_dict=True)
    return {
        entity: {metric: value.item() if hasattr(value, "item") else value
                 for metric, value in scores.items()}
        for entity, scores in report.items()
    }


def full_report(predictions: np.ndarray, label_ids: np.ndarray) -> str:
    """Ausführlicher Report pro Entity-Typ, für die Fehleranalyse in Phase 3."""
    return word_level_report(*_decode(predictions, label_ids))


def report_dict(predictions: np.ndarray, label_ids: np.ndarray) -> dict:
    """Wie full_report, aber als Dict – für den JSON-Export ans Frontend."""
    return word_level_report_dict(*_decode(predictions, label_ids))
