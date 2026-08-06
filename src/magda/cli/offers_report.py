"""Misst das Angebots-Clustering ehrlich per Ablation (Issue #6, Punkt 2).

Aufruf:
    magda offers-report
    magda offers-report --labels-from sonnet-5 --splits train,dev
    magda offers-report --splits test

Schaltet den arithmetischen Zuordnungsweg in `_match_badges` ab (Menge x
Grundpreis) und laesst die Geometrie allein zuordnen; die Arithmetik urteilt
anschliessend unbeteiligt. Damit misst der Report genau das schwache Bein
des Verfahrens - den geometrischen Rueckfall, der alles ohne Grundpreis
traegt, also praktisch das gesamte Non-Food-Sortiment.

Gemessen wird per Default auf Train + Dev (`data/splits/split.json`): der
Testsplit ist zum Messen von Modellen da, nicht von Heuristiken, und bleibt
hier unberuehrt, sofern nicht ausdruecklich mit `--splits test` angefordert.

Details: docs/superpowers/specs/2026-08-06-offers-messung-und-regressionstests-design.md
"""

import argparse
import json
from datetime import datetime

from magda import config
from magda.dataset import get_or_create_splits, load_labeled_pages, select_split
from magda.offers_report import collect


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--labels-from", default="sonnet-5",
        help="Modellordner unter data/labeled/ (Default: sonnet-5)",
    )
    parser.add_argument(
        "--splits", default="train,dev",
        help="Kommagetrennte Splits, z.B. 'train,dev' oder 'test' (Default: train,dev)",
    )
    args = parser.parse_args(argv)

    if not config.labeled_dir(args.labels_from).is_dir():
        parser.error(f"Labelquelle nicht gefunden: {args.labels_from}")

    pages = load_labeled_pages(args.labels_from)
    if not pages:
        parser.exit(1, f"Keine gelabelten Seiten unter {config.labeled_dir(args.labels_from)}.\n")

    try:
        splits = get_or_create_splits(pages)
    except FileNotFoundError as exc:
        parser.exit(1, f"{exc}\n")

    names = [s.strip() for s in args.splits.split(",") if s.strip()]
    unknown = [n for n in names if n not in splits]
    if unknown:
        parser.error(
            f"Unbekannter Split: {', '.join(unknown)} (bekannt: {', '.join(sorted(splits))})"
        )

    measured_pages = [page for name in names for page in select_split(pages, splits, name)]
    report = collect(measured_pages)

    print(
        f"{report.pages} Seiten gemessen ({', '.join(names)}), "
        f"{report.pages_skipped} ohne Wortliste uebersprungen."
    )
    print(
        f"Angebote: {report.offers_total}, davon {report.offers_with_product_and_price} "
        f"mit Produkt und Preis, {report.fragments} Fragmente."
    )
    print(
        f"Bloecke mit Menge und Grundpreis ohne passende Paarung: "
        f"{report.blocks_without_matching_pairing}"
    )
    if report.judged == 0:
        print("Ablation: keine beurteilbaren Zuordnungen (kein Preis-Badge mit Grundpreis-Beleg).")
    else:
        print(
            f"Ablation (Geometrie allein, Arithmetik als Richter): "
            f"{report.confirmed} confirmed, {report.contradicted} contradicted, "
            f"{report.unjudgeable} unjudgeable -> Trefferquote {report.confirmation_rate:.1%}"
        )

    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    splits_slug = "-".join(names)
    out_file = config.EVAL_DIR / f"offers_report_{config.model_slug(args.labels_from)}_{splits_slug}.json"
    with open(out_file, "w") as f:
        json.dump(
            {
                "labels_from": args.labels_from,
                "splits": names,
                "created": datetime.now().isoformat(timespec="seconds"),
                **report.to_dict(),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Report gespeichert: {out_file}")
