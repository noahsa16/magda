"""Bewertet gespeicherte API-Antworten gegen dieselben Gold-Angebote wie der Bericht.

Die Laufzeitdatei stammt aus benchmark_offer_runtime.py. Fehlgeschlagene
Seiten zählen als leere Ausgabe, wie in der bisherigen Blackbox-Auswertung.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from magda import blackbox, blackbox_eval, resampling
from magda.cli.blackbox_eval import _gold_deals_by_page


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "data/eval/test_cluster_pages.txt"
STUDY = ROOT / "data/eval/study-2026-09-16/study.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--system-name", default="thl_qwen",
                        help="Name des gespeicherten Vergleichssystems")
    args = parser.parse_args()
    if args.system_name == "local_pipeline":
        parser.error("Vergleichssystem darf nicht local_pipeline heißen")

    runtime = json.loads(args.runtime.read_text())
    page_ids = [line.strip() for line in PAGES.read_text().splitlines() if line.strip()]
    if runtime["page_list_sha256"] != hashlib.sha256(PAGES.read_bytes()).hexdigest():
        parser.error("Seitenliste stimmt nicht mit der Laufzeitmessung überein")
    rows = runtime["per_page"]
    if [row["page_id"] for row in rows] != page_ids:
        parser.error("Laufzeitmessung enthält nicht alle Testseiten in derselben Reihenfolge")

    reference, missing = _gold_deals_by_page(page_ids)
    if missing:
        parser.error(f"Gold-Angebote fehlen für {len(missing)} Seiten")
    reference.pop("__fragments__")
    study = json.loads(STUDY.read_text())
    if study["pages"] != page_ids or study["reference_deals"] != reference:
        parser.error("Referenz weicht vom gespeicherten Studienvergleich ab")

    predictions = {}
    raw_count = fragment_count = 0
    for row in rows:
        deals = []
        for record in row.get("records") or []:
            if not isinstance(record, dict):
                continue
            raw_count += 1
            name = " ".join(str(part).strip() for part in
                            (record.get("brand"), record.get("product")) if part)
            price = blackbox_eval.parse_price(record.get("price"))
            if name and price is not None:
                deals.append({"name": name, "price": price})
            else:
                fragment_count += 1
        predictions[row["page_id"]] = deals

    counts = blackbox_eval.compare_pages({
        page_id: (predictions[page_id], reference[page_id]) for page_id in page_ids
    })
    per_system = {}
    for name, deals_by_page in ((args.system_name, predictions), ("local_pipeline", study["own_deals"])):
        per_system[name] = []
        for page_id in page_ids:
            page_counts = blackbox_eval.match_deals(deals_by_page[page_id], reference[page_id])
            per_system[name].append((page_counts["matched"], page_counts["system"],
                                     page_counts["reference"]))
    paired = resampling.compare_counts(
        per_system, study["clusters"], [(args.system_name, "local_pipeline")]
    )
    report = {
        "protocol": blackbox_eval.EVALUATION_VERSION,
        "prompt_version": blackbox.PROMPT_VERSION,
        "model": runtime["api_model"],
        "api_host": runtime["api_host"],
        "system": args.system_name,
        "source_protocol": runtime.get("protocol"),
        "runtime_sha256": hashlib.sha256(args.runtime.read_bytes()).hexdigest(),
        "reference": "gold/ + gold/offers/",
        "matching_fields": list(blackbox_eval.COMMON_FIELDS),
        "name_similarity": blackbox_eval.NAME_SIMILARITY,
        "failed_pages": [row["page_id"] for row in rows if row["error"]],
        "raw_records": raw_count,
        "unscored_fragments": fragment_count,
        "counts": counts,
        "paired_with_local": paired,
        "study_sha256": hashlib.sha256(STUDY.read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
