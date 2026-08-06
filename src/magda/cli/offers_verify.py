"""Rechnet eine Angebots-Gruppierung nach: Menge x Grundpreis gegen den Preis.

Aufruf:
    magda offers-verify --reference-from claude-sonnet-5
    magda offers-verify --reference-from claude-sonnet-5 --labels-from sonnet-5
    magda offers-verify --gold                  # gegen gold/offers/

Das ist die Kontrolle ueber eine Referenz, die selbst aus einem Modell kommt.
Ein Vision-Modell gruppiert nach dem Seitenbild und hat dabei nie gerechnet -
die Arithmetik ist deshalb ein unbeteiligter Richter und braucht hier, anders
als in `magda offers-report`, keine Ablation.

Zwei Zahlen zusammen lesen: `accuracy` sagt, wie oft die Rechnung die Gruppe
bestaetigt, `coverage`, ueber welchen Anteil der Preise sie ueberhaupt etwas
sagen konnte. Eine Genauigkeit von 0.9 ueber ein Fuenftel der Preise ist eine
Aussage ueber ein Fuenftel.
"""

import argparse
import json

from magda import config, offer_teacher, offers_gold, offers_verify
from magda.cli.offers import _load_labeled_pages, _load_predicted_pages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reference-from", dest="reference_from", default=None,
                        help="Ordner unter data/offer_groups/ statt gold/offers/")
    parser.add_argument("--gold", action="store_true",
                        help="Gegen die Handannotation unter gold/offers/ rechnen")
    parser.add_argument("--labels-from", dest="labels_from", default=None,
                        help="Labelordner unter data/labeled/")
    parser.add_argument("--predictions", default=None,
                        help="Variante unter data/predictions/ statt data/labeled/")
    args = parser.parse_args(argv)

    if bool(args.reference_from) == bool(args.gold):
        parser.error("Genau eines von --reference-from und --gold angeben.")

    if args.predictions:
        source = args.predictions
        pages = _load_predicted_pages(source)
    else:
        source = args.labels_from or config.default_labeled_model()
        if source is None:
            parser.exit(1, "Keine Labelquelle gefunden. Erst `magda label` laufen lassen.\n")
        pages = _load_labeled_pages(source)

    if args.gold:
        reference = offers_gold.load_reference()
        basis = "gold/offers"
    else:
        reference = offers_gold.load_reference(offer_teacher.teacher_dir(args.reference_from))
        basis = f"data/offer_groups/{config.model_slug(args.reference_from)}"
    if not reference.assignments:
        parser.exit(1, f"Keine fertige Gruppierung in {basis}.\n")

    report = offers_verify.collect(pages, reference.assignments)
    payload = report.to_dict()
    payload.update({"source": source, "basis": basis,
                    "pages_measured": sorted(reference.assignments)})

    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    slug = config.model_slug(args.reference_from) if args.reference_from else "gold"
    out_path = config.EVAL_DIR / f"offers_verify_{slug}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    def _rate(value):
        return "nicht messbar" if value is None else f"{value:.3f}"

    kinds = sorted(set(reference.provenance.values()))
    print(f"Gruppierung: {basis}   Labels: {source}   Seiten: {report.pages}")
    print(f"Herkunft der Referenz: {', '.join(kinds) or 'unbekannt'}")
    if "llm" in kinds:
        print("  Achtung: maschinell erzeugt. Die Rechnung unten ist die einzige")
        print("  unabhaengige Kontrolle daran - kein Ersatz fuer eine Handannotation.")
    print()
    print(f"  bestaetigt        {report.confirmed:>6}")
    print(f"  widerlegt         {report.contradicted:>6}   (Rechnung zeigt auf eine andere Gruppe)")
    print(f"  ohne Treffer      {report.unresolved:>6}   (Grundpreis da, geht nirgends auf)")
    print(f"  nicht beurteilbar {report.unjudgeable:>6}   (kein Grundpreis - praktisch Non-Food)")
    print()
    print(f"  Genauigkeit  {_rate(report.accuracy):>13}   ({report.confirmed} von {report.judged} beurteilten)")
    print(f"  Abdeckung    {_rate(report.coverage):>13}   ({report.judged} von {report.prices} Preisen)")
    print(f"\nReport: {out_path}")
