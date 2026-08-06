"""Misst, ob eine flache OFFER-Tag-Folge die Angebote ueberhaupt ausdruecken kann.

Aufruf:
    magda offers-sequence
    magda offers-sequence --labels-from sonnet-5
    magda offers-sequence --predictions gbert
    magda offers-sequence --reference        # gegen gold/offers/ statt Heuristik

Ein Span kann nur zusammenfassen, was benachbart ist. Faellt ein Angebot in
zwei Laeufe, kann eine flache Folge es nicht als eines ausdruecken - dann
braucht das Gruppieren paarweise Relationsklassifikation statt einer zweiten
Tag-Folge. Das ist die Vorbedingung fuer den OFFER-Kopf, und sie stand
bisher als Zahl in CLAUDE.md ohne das Skript dazu.

Die Zahl ist nur so gut wie die Gruppierung, ueber die sie gerechnet wird.
Ohne `--reference` ist das die Heuristik - also eine Aussage darueber, was
*sie* produziert, nicht darueber, wie die Angebote wirklich liegen.
"""

import argparse
import json

from magda import config, offers_gold, offers_sequence
from magda.cli.offers import _load_labeled_pages, _load_predicted_pages


def _reference_grouping(reference):
    """Baut aus der Handannotation Angebote in der Form, die run_counts erwartet."""
    from magda.offers import VALUE_TYPES, _make_offer, entities_from_page

    def grouping(page):
        assignment = reference.assignments.get(page.get("page_id"))
        if assignment is None:
            return []
        members: dict[int, list] = {}
        for entity in entities_from_page(page):
            if entity.type not in VALUE_TYPES:
                continue
            group = offers_gold._reference_group(entity, assignment)
            if group is not None:
                members.setdefault(group, []).append(entity)
        return [_make_offer(page["page_id"], i, entities)
                for i, entities in enumerate(members.values())]

    return grouping


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-from", dest="labels_from", default=None,
                        help="Labelordner unter data/labeled/. Default: konfiguriertes/groesstes Modell")
    parser.add_argument("--predictions", default=None,
                        help="Variante unter data/predictions/ statt data/labeled/")
    parser.add_argument("--reference", action="store_true",
                        help="Gegen gold/offers/ rechnen statt gegen die Heuristik")
    args = parser.parse_args(argv)

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

    grouping = offers_sequence.collect
    if args.reference:
        reference = offers_gold.load_reference()
        if not reference.assignments:
            parser.exit(1, "Keine fertige Referenzseite unter gold/offers/. "
                           "`magda offers-queue` sagt, womit anzufangen ist.\n")
        report = offers_sequence.collect(pages, grouping=_reference_grouping(reference))
        basis = "gold/offers"
    else:
        report = grouping(pages)
        basis = "Heuristik"

    payload = report.to_dict()
    payload.update({"source": source, "basis": basis})
    out_dir = config.EVAL_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "reference" if args.reference else "heuristic"
    out_path = out_dir / f"offers_sequence_{config.model_slug(source)}_{suffix}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    def _rate(value):
        return "nicht messbar" if value is None else f"{value:.3f}"

    print(f"Quelle: {source}   Gruppierung: {basis}   Seiten: {report.pages}")
    print()
    print("Mit Preis-Badge (das vollstaendige Angebot):")
    print(f"  Angebote                           {report.offers}")
    print(f"  davon ein zusammenhaengender Lauf  {report.contiguous}   "
          f"({_rate(report.share)})")
    for runs, count in sorted(report.by_runs.items()):
        print(f"    {runs} {'Lauf ' if runs == 1 else 'Laeufe'}  {count}")
    print()
    print("Ohne Preis-Badge (nur die Beschreibung):")
    print(f"  Angebote                           {report.offers_without_badges}")
    print(f"  davon ein zusammenhaengender Lauf  {report.contiguous_without_badges}   "
          f"({_rate(report.share_without_badges)})")
    for runs, count in sorted(report.by_runs_without_badges.items()):
        print(f"    {runs} {'Lauf ' if runs == 1 else 'Laeufe'}  {count}")
    print()
    print("Die Differenz ist der Befund: Pennys Preis steht in einem gelben")
    print("Kasten, im Textlayer weit weg vom Produktnamen. Eine flache")
    print("OFFER-Folge kann die Beschreibung fassen, den Preis nicht mit.")
    print(f"\nReport: {out_path}")
