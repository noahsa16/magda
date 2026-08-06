"""Misst das Angebots-Clustering per Ablation und schreibt einen Report.

Aufruf:
    magda offers-report
    magda offers-report --labels-from sonnet-5
    magda offers-report --splits train,dev
    magda offers-report --predictions gbert --splits test

Default sind Train + Dev. Der Testsplit ist zum Messen am Ende da, nicht zum
Entwickeln von Heuristiken - wer eine Schwelle an Testseiten dreht und danach
an denselben misst, bekommt eine In-Sample-Zahl.

Die Zahl, auf die es ankommt, ist `geometric_accuracy`: der Anteil der
Zuordnungen, die die Geometrie *allein* richtig trifft, gemessen an der
Rechnung Menge x Grundpreis als unabhaengigem Richter. Sie beantwortet, was
der geometrische Rueckfall taugt - und der traegt alles ohne Grundpreis.
"""

import argparse
import json

from magda import config, offers_report
from magda.cli.offers import _load_labeled_pages, _load_predicted_pages

SPLIT_FILE = config.DATA_DIR / "splits" / "split.json"


def _selected_page_ids(splits: list[str], parser: argparse.ArgumentParser) -> set[str]:
    if not SPLIT_FILE.is_file():
        parser.exit(1, f"{SPLIT_FILE} fehlt. Erst `magda split` laufen lassen.\n")
    with open(SPLIT_FILE) as f:
        split = json.load(f)
    unknown = [s for s in splits if s not in split]
    if unknown:
        parser.error(f"Unbekannte Splits: {', '.join(unknown)}. Bekannt: {', '.join(sorted(split))}")
    return {page_id for name in splits for page_id in split[name]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-from", dest="labels_from", default=None,
                        help="Labelordner unter data/labeled/. Default: konfiguriertes/groesstes Modell")
    parser.add_argument("--predictions", default=None,
                        help="Variante unter data/predictions/ statt data/labeled/ (z.B. gbert)")
    parser.add_argument("--splits", default="train,dev",
                        help="Komma-getrennt. Default train,dev - test ist zulaessig, aber nicht Default")
    args = parser.parse_args(argv)

    splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    if not splits:
        parser.error("--splits ist leer")
    selected = _selected_page_ids(splits, parser)

    if args.predictions:
        source = args.predictions
        pages = _load_predicted_pages(source)
    else:
        source = args.labels_from or config.default_labeled_model()
        if source is None:
            parser.exit(1, "Keine Labelquelle gefunden. Erst `magda label` laufen lassen.\n")
        if not config.labeled_dir(source).is_dir():
            parser.error(f"Labelquelle nicht gefunden: {source}")
        pages = _load_labeled_pages(source)

    available = {p.get("page_id") for p in pages}
    pages = [p for p in pages if p.get("page_id") in selected]
    missing = len(selected - available)
    if not pages:
        parser.exit(1, f"Keine Seiten aus {', '.join(splits)} in {source} gefunden.\n")

    report = offers_report.collect(pages)
    payload = report.to_dict()
    payload.update({"source": source, "splits": splits, "pages_missing": missing})

    out_dir = config.DATA_DIR / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"offers_report_{config.model_slug(source)}_{'-'.join(splits)}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    def _rate(value):
        return "nicht messbar" if value is None else f"{value:.3f}"

    print(f"Quelle: {source}   Splits: {', '.join(splits)}   Seiten: {report.pages}")
    if missing:
        print(f"  {missing} Seiten des Splits fehlen in der Quelle")
    print()
    print("Ablation - Geometrie ordnet allein zu, die Rechnung urteilt:")
    print(f"  bestaetigt          {report.confirmed}")
    print()
    print("  nachsichtig (nur unbelegte Bloecke zaehlen als Alternative):")
    print(f"    widerlegt           {report.contradicted}")
    print(f"    nicht beurteilbar   {report.unjudgeable}")
    print(f"    Trefferquote        {_rate(report.geometric_accuracy)}")
    print()
    print("  streng (auch belegte Bloecke zaehlen als Alternative):")
    print(f"    widerlegt           {report.contradicted_strict}")
    print(f"    nicht beurteilbar   {report.unjudgeable_strict}")
    print(f"    Trefferquote        {_rate(report.geometric_accuracy_strict)}")
    print()
    print(f"  Die Trefferquote liegt zwischen {_rate(report.geometric_accuracy_strict)} "
          f"und {_rate(report.geometric_accuracy)}.")
    print()
    print("Normalbetrieb - wie die Preise tatsaechlich zugeordnet werden:")
    print(f"  ueber die Rechnung  {report.arithmetic_assignments}")
    print(f"  ueber die Naehe     {report.geometric_assignments}")
    print(f"  gar nicht           {report.unmatched}")
    print()
    print("Zaehler ohne Zirkelschluss:")
    print(f"  Angebote gesamt                 {report.offers_total}")
    print(f"  davon mit Produkt und Preis     {report.offers_with_product_and_price}")
    print(f"  Fragmente                       {report.fragments}")
    print(f"  Bloecke ohne stimmige Paarung   {report.blocks_without_matching_pairing}")
    print()
    print(f"Report: {out_path}")
