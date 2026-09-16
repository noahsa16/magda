"""Prüft die Eingaben des Abschlussvergleichs, ohne Annotationen zu ändern.

    .venv/bin/python scripts/check_blackbox_gold.py

Die feste Vergleichsliste bleibt unverändert. Eine leere Gruppierung trotz
fertiger Produkt- und Preisspans ist ein Hinweis zur Handprüfung, keine
automatisch korrigierbare Annotation.
"""

import json

from magda import config, gold, offers_gold, provenance
from magda.cli.evaluate import read_page_ids
from magda.cli.offers import _load_predicted_pages


def main():
    page_ids = read_page_ids(config.EVAL_DIR / "test_cluster_pages.txt")
    span_pages = {page["page_id"]: page for page in gold.load_gold_pages().pages}
    groups = offers_gold.load_reference()
    rows = []
    for page_id in page_ids:
        span_path = config.GOLD_DIR / f"{page_id}.json"
        group_path = config.GOLD_DIR / "offers" / f"{page_id}.json"
        span_data = json.loads(span_path.read_text()) if span_path.exists() else {}
        group_data = json.loads(group_path.read_text()) if group_path.exists() else {}
        spans = span_data.get("spans", [])
        rows.append({
            "page_id": page_id,
            "spans_status": span_data.get("status", "missing"),
            "groups_status": group_data.get("status", "missing"),
            "spans_valid": page_id in span_pages,
            "groups_valid": page_id in groups.assignments,
            "span_count": len(spans),
            "group_count": len(group_data.get("groups", [])),
            "spans_annotator": span_data.get("annotator"),
            "groups_annotator": group_data.get("annotator"),
            "spans_provenance": span_data.get("provenance"),
            "groups_provenance": group_data.get("provenance"),
            "empty_groups_with_product_and_price": (
                not group_data.get("groups")
                and {"PRODUCT", "PRICE"} <= {span["label"] for span in spans}
            ),
            "spans_sha256": provenance.file_digest(span_path) if span_path.exists() else None,
            "groups_sha256": provenance.file_digest(group_path) if group_path.exists() else None,
        })

    prediction_issues = {}
    for variant in ("gbert", "xlmr", "lilt", "layoutxlm"):
        predictions = {page["page_id"]: page for page in _load_predicted_pages(variant)}
        issues = []
        for page_id in page_ids:
            page = predictions.get(page_id)
            if page is None:
                issues.append({"page_id": page_id, "reason": "missing"})
            elif page_id in span_pages and gold.words_hash(page["words"]) != gold.words_hash(span_pages[page_id]["words"]):
                issues.append({"page_id": page_id, "reason": "words_mismatch"})
        prediction_issues[variant] = issues

    replays = []
    for path in sorted(config.EVAL_DIR.glob("blackbox_test_*_pair-model_ref-teacher.json")):
        replay = json.loads(path.read_text())
        replays.append({
            "file": str(path.relative_to(config.PROJECT_ROOT)),
            "sha256": provenance.file_digest(path),
            "missing_attempted_pages": sorted(set(page_ids) - set(replay["pages"])),
            "missing_responses": sorted(set(page_ids) - set(replay["blackbox_deals"])),
            "errors": replay.get("errors", []),
        })

    print(json.dumps({
        "code": provenance.code_version(),
        "requested_pages": len(page_ids),
        "ready_pages": sum(row["spans_valid"] and row["groups_valid"] for row in rows),
        "pages": rows,
        "prediction_issues": prediction_issues,
        "pair_checkpoint_exists": (config.PROJECT_ROOT / "checkpoints/offer_pairs/model.pt").is_file(),
        "replays": replays,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
