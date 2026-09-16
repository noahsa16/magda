"""Belegt, dass der Studienabschluss nur Einordnung und Annotationsumfang ändert."""

import argparse
import json
from pathlib import Path

from magda import config, evaluation_study, provenance


def read_json(path):
    return json.loads(path.read_text())


def require_equal(before, after, label):
    if before != after:
        raise SystemExit(f"Unerwartete Änderung: {label}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, default=Path("data/eval/study-2026-09-15"))
    parser.add_argument("--after", type=Path, default=Path("data/eval/study-2026-09-16"))
    parser.add_argument("--gold-snapshot", type=Path,
                        default=Path("data/eval/blackbox_gold_ready_2026-09-15.json"))
    args = parser.parse_args()
    before, after = [read_json(path / "study.json") for path in (args.before, args.after)]
    # Status und Quellenhash ändern sich absichtlich; Messgrundlage und Zähler nicht.
    unchanged = (
        "pages", "clusters", "full_test_clusters", "cluster_word_hashes", "split", "split_sha256",
        "ner_uncertainty", "grouping", "offer_uncertainty", "replays", "offer_protocol",
        "reference_deals", "own_deals", "reference_fragments", "own_fragments", "error_analysis",
        "pair_checkpoint_sha256", "pair_model", "pair_threshold",
    )
    for key in unchanged:
        require_equal(before[key], after[key], key)
    for variant in evaluation_study.VARIANTS:
        results = [{key: value for key, value in study["ner"][variant].items() if key != "code"}
                   for study in (before, after)]
        require_equal(*results, f"NER {variant}")
    for key in before["reference_audit"]:
        results = [study["reference_audit"][key] for study in (before, after)]
        if key == "issues":
            results = [[{k: v for k, v in row.items() if k != "status"} for row in rows] for rows in results]
        require_equal(*results, f"Referenzdiagnostik {key}")

    require_equal(after["status"], "completed_exploratory", "Studienstatus")
    require_equal(after["reference_policy"]["reference_changed"], False, "Referenzänderung")
    review = read_json(args.after / "review-status.json")
    require_equal(review, after["control_annotation"], "Kontrollannotationsmetadaten")
    require_equal(review["status"], "not_performed", "Keine weitere Annotation")
    require_equal(review["scores"], None, "Keine erfundene Übereinstimmung")

    for page in read_json(args.gold_snapshot)["pages"]:
        for kind, directory in (("spans", config.GOLD_DIR), ("groups", config.GOLD_DIR / "offers")):
            path = directory / f"{page['page_id']}.json"
            require_equal(provenance.file_digest(path), page[f"{kind}_sha256"], str(path))
    evaluation_study.verify_snapshot(after, require_same_revision=False)

    report = (args.after / "report.md").read_text()
    if "awaiting_two_human_submissions" in report or "**Arbeitsstand:" in report:
        raise SystemExit("Der Abschlussbericht verwendet noch den überholten Annotationsauftrag.")
    print("Alle NER-, Gruppierungs- und Angebotswerte einschließlich Intervalle unverändert.")
    print("Referenzdateien stimmen mit dem gesicherten Goldstand überein; aktuelle Eingabe- und Codehashes geprüft.")
    print("Studienabschluss dokumentiert; keine weitere Annotation und keine erfundene Agreement-Zahl.")


if __name__ == "__main__":
    main()
