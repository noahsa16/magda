"""Entity-F1 vorhandener Studentenvorhersagen gegen menschliche Spans.

    magda eval-gold layoutxlm --pages data/eval/test_cluster_pages.txt

Liest ausschließlich; geschrieben wird ein eigener Report in data/eval/.
Die Referenz in data/labeled/ wird weder benötigt noch verändert.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from magda import config, gold_evaluation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=list(config.VARIANTS))
    parser.add_argument("--pages", required=True, help="Feste Seitenliste, eine ID je Zeile")
    parser.add_argument("--allow-partial", action="store_true",
                        help="Unfertige Handspans auslassen; nur für explorative Teilmessungen")
    args = parser.parse_args(argv)
    from magda.cli.evaluate import read_page_ids

    try:
        report = gold_evaluation.score_predictions(
            config.DATA_DIR / "predictions" / args.variant,
            read_page_ids(args.pages), allow_partial=args.allow_partial,
        )
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    report.update(variant=args.variant, split=Path(args.pages).stem,
                  scope_kind="pages", created=datetime.now().isoformat(timespec="seconds"))
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    path = config.EVAL_DIR / f"{args.variant}_gold_{report['reference_sha256'][:12]}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    score = report["report"]["micro avg"]
    print(f"{report['num_pages']} Seiten gegen Handspans: Entity-F1 {score['f1-score']:.4f}")
    print(f"Report: {path}")
