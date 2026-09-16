"""Fallstudie mit bestehender Referenz und offengelegten Einschränkungen abschließen."""

import argparse
import json
import shlex
from pathlib import Path

from magda import annotation_review, evaluation_study, review_packet, study_report
from magda.cli.evaluate import read_page_ids


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", default="data/eval/test_cluster_pages.txt")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--review-packet", type=Path,
                        help="Optionales Paket für eine zusätzliche Kontrollannotation außerhalb des Studienabschlusses.")
    parser.add_argument("--review-a", type=Path)
    parser.add_argument("--review-b", type=Path)
    parser.add_argument("--resamples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    if bool(args.review_a) != bool(args.review_b):
        parser.error("Beide Originalabgaben gemeinsam angeben.")
    if args.review_a and not args.review_packet:
        parser.error("Originalabgaben benötigen ihr ursprüngliches --review-packet.")
    try:
        study = evaluation_study.run_study(read_page_ids(args.pages), resamples_count=args.resamples, seed=args.seed)
        status = {
            "status": "not_performed", "scores": None,
            "reason": "Keine zusätzliche Kontrollannotation im festgelegten Studienumfang; als Limitation berichtet.",
        }
        if args.review_packet:
            packet = annotation_review.create_packet(args.review_packet, study["pages"], study["clusters"])
            review_packet.write_editors(args.review_packet, packet)
            status = annotation_review.score_reviews(packet, args.review_a, args.review_b)
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    args.output.mkdir(parents=True, exist_ok=True)
    study["control_annotation"] = status
    command = (f".venv/bin/magda study-eval --pages {shlex.quote(args.pages)} "
               f"--output {shlex.quote(str(args.output))} "
               f"--resamples {args.resamples} --seed {args.seed}")
    if args.review_packet:
        command += f" --review-packet {shlex.quote(str(args.review_packet))}"
    if args.review_a:
        command += f" --review-a {shlex.quote(str(args.review_a))} --review-b {shlex.quote(str(args.review_b))}"
    for filename, payload in (("study.json", study), ("reference-audit.json", study["reference_audit"]),
                              ("review-status.json", status)):
        (args.output / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    (args.output / "report.md").write_text(study_report.render(study, status, command))
    (args.output / "reference-diagnostics.md").write_text(study_report.render_audit(study["reference_audit"]))
    print(f"Bericht: {args.output / 'report.md'}")
    if args.review_packet:
        print(f"Optionales Prüfpaket: {args.review_packet}")
    print(f"Menschliche Kontrollannotation: {status['status']}")


if __name__ == "__main__":
    main()
