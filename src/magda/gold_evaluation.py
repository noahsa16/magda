"""Studentenvorhersagen gegen fertige Handspans auf einer festen Seitenliste."""

import json
from pathlib import Path

from magda import config, gold, provenance, semeval
from magda.evaluation import word_level_report_dict
from magda.labels import LABELS, bio_to_spans, validate_spans


def score_predictions(directory: Path, page_ids: list[str], *, allow_partial=False) -> dict:
    if len(set(page_ids)) != len(page_ids) or not page_ids:
        raise ValueError("Seitenliste muss nichtleer und eindeutig sein.")
    reference = {page["page_id"]: page for page in gold.load_gold_pages().pages}
    missing = [pid for pid in page_ids if pid not in reference]
    if missing and not allow_partial:
        raise ValueError("Handspans fehlen oder sind unfertig/veraltet: " + ", ".join(missing))
    selected = [reference[pid] for pid in page_ids if pid in reference]
    if not selected:
        raise ValueError("Keine fertigen Handspans auf der angeforderten Seitenliste.")
    predictions, prediction_metadata, null_words = [], {}, {}
    for page in selected:
        annotation = json.loads((config.GOLD_DIR / f"{page['page_id']}.json").read_text())
        errors = validate_spans(annotation.get("spans", []), len(page["words"]))
        if errors:
            raise ValueError(f"Ungültige Gold-Spans: {page['page_id']}: {errors}")
        path = directory / f"{page['page_id']}.json"
        payload = json.loads(path.read_text())
        words = payload["words"]
        if payload.get("page_id") != page["page_id"] or [w["text"] for w in words] != [w["text"] for w in page["words"]]:
            raise ValueError(f"Vorhersage passt nicht zur Wortliste: {path}")
        if any("label" not in word for word in words):
            raise ValueError(f"Wortlabels fehlen in {path}. Erst magda predict ausführen.")
        if any(w["label"] is not None and w["label"] not in LABELS for w in words):
            raise ValueError(f"Unbekannte Wortlabels: {path}")
        predictions.append([w["label"] or "O" for w in words])
        null_words[page["page_id"]] = sum(w["label"] is None for w in words)
        prediction_metadata[page["page_id"]] = {
            key: payload.get(key) for key in ("model", "created", "checkpoint_sha256", "code")
        }
    ids = [p["page_id"] for p in selected]
    reference_spans = [bio_to_spans(p["tags"]) for p in selected]
    predicted_spans = [bio_to_spans(tags) for tags in predictions]
    schemes = semeval.evaluate(reference_spans, predicted_spans)
    report = word_level_report_dict([p["tags"] for p in selected], predictions)
    if abs(report.get("micro avg", {}).get("f1-score", 0) - schemes["matching_schemes"]["strict"]["f1"]) > 1e-10:
        raise ValueError("Strict-F1 stimmt zwischen seqeval und nervaluate nicht überein.")
    return {
        "reference": "gold", "reference_is_llm": False,
        "requested_pages": page_ids, "gold_missing": missing,
        "num_pages": len(selected), "protocol": "saved-predictions",
        **provenance.reference_identity(selected),
        "predictions_sha256": provenance.prediction_identity(directory, ids),
        "code": provenance.code_version(),
        "report": report, **schemes,
        "prediction_metadata": prediction_metadata, "unpredicted_words": null_words,
        "per_page": {
            pid: semeval.evaluate([ref], [pred])["matching_schemes"]
            for pid, ref, pred in zip(ids, reference_spans, predicted_spans, strict=True)
        },
    }
