"""Studentenvorhersagen gegen fertige Handspans auf einer festen Seitenliste."""

import json
from pathlib import Path

from magda import gold, provenance
from magda.evaluation import word_level_report_dict


def score_predictions(directory: Path, page_ids: list[str], *, allow_partial=False) -> dict:
    reference = {page["page_id"]: page for page in gold.load_gold_pages().pages}
    missing = [pid for pid in page_ids if pid not in reference]
    if missing and not allow_partial:
        raise ValueError("Handspans fehlen oder sind unfertig/veraltet: " + ", ".join(missing))
    selected = [reference[pid] for pid in page_ids if pid in reference]
    if not selected:
        raise ValueError("Keine fertigen Handspans auf der angeforderten Seitenliste.")
    predictions = []
    for page in selected:
        path = directory / f"{page['page_id']}.json"
        payload = json.loads(path.read_text())
        words = payload["words"]
        if payload.get("page_id") != page["page_id"] or [w["text"] for w in words] != [w["text"] for w in page["words"]]:
            raise ValueError(f"Vorhersage passt nicht zur Wortliste: {path}")
        if any("label" not in word for word in words):
            raise ValueError(f"Wortlabels fehlen in {path}. Erst magda predict ausführen.")
        predictions.append([w["label"] or "O" for w in words])
    ids = [p["page_id"] for p in selected]
    return {
        "reference": "gold", "reference_is_llm": False,
        "requested_pages": page_ids, "gold_missing": missing,
        "num_pages": len(selected), "protocol": "saved-predictions",
        **provenance.reference_identity(selected),
        "predictions_sha256": provenance.prediction_identity(directory, ids),
        "code": provenance.code_version(),
        "report": word_level_report_dict([p["tags"] for p in selected], predictions),
    }
