"""Misst eine Angebots-Gruppierung gegen die handannotierte Referenz.

Aufruf:
    magda offers-gold
    magda offers-gold --labels-from sonnet-5
    magda offers-gold --predictions gbert

Die Referenz liegt unter gold/offers/ und gruppiert Wortindizes. Dieselbe
Annotation beurteilt deshalb die Heuristik auf Labels, die Heuristik auf
Modellvorhersagen und spaeter einen LLM-Teacher oder einen OFFER-Kopf.

Zwei Zahlen: `pair_f1` ueber Entity-Paare (teilweise richtige Gruppen zaehlen
anteilig, die uebliche Primaerzahl der Line-Item-Literatur) und `group_f1`
ueber exakt getroffene Angebote - die Zahl, die "die Zeile in der Datenbank
stimmt" entspricht.

Ohne Referenz gibt es keine Zahl, sondern einen Hinweis auf `magda
offers-queue`. Eine leere Messung als 0.0 auszuweisen waere die falsche
Aussage: "alles falsch" statt "nichts gemessen".
"""

import argparse
import json

from magda import config, offers_gold
from magda.cli.offers import _load_labeled_pages, _load_predicted_pages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-from", dest="labels_from", default=None,
                        help="Labelordner unter data/labeled/. Default: konfiguriertes/groesstes Modell")
    parser.add_argument("--predictions", default=None,
                        help="Variante unter data/predictions/ statt data/labeled/")
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

    reference = offers_gold.load_reference()
    if not reference.assignments:
        parser.exit(1, "Keine fertige Referenzseite unter gold/offers/. "
                       "`magda offers-queue` sagt, womit anzufangen ist.\n")

    report = offers_gold.collect(pages, reference)
    payload = report.to_dict()
    payload.update({
        "source": source,
        "reference_pages": sorted(reference.assignments),
        "stale": reference.stale,
        "in_progress": reference.in_progress,
        "broken": reference.broken,
    })

    out_dir = config.EVAL_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"offers_gold_{config.model_slug(source)}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    def _rate(value):
        return "nicht messbar" if value is None else f"{value:.3f}"

    print(f"Quelle: {source}   Referenzseiten: {report.pages}")
    for name, ids in (("veraltet", reference.stale), ("offen", reference.in_progress),
                      ("kaputt", reference.broken)):
        if ids:
            print(f"  {len(ids)} Seiten {name}: {', '.join(ids)}")
    print()
    print(f"  Paar-F1     {_rate(report.pair_f1):>13}   "
          f"({report.shared_pairs} von {report.sys_pairs} vorhergesagt, "
          f"{report.ref_pairs} in der Referenz)")
    print(f"  Gruppen-F1  {_rate(report.group_f1):>13}   "
          f"({report.exact_groups} exakt von {report.sys_groups} vorhergesagt, "
          f"{report.ref_groups} in der Referenz)")
    print()
    print(f"  Entities                        {report.entities}")
    print(f"  davon keinem Angebot zugeordnet {report.unassignable}")
    if report.ref_groups_without_entities:
        print(f"  Referenzangebote ohne Entity    {report.ref_groups_without_entities}"
              "   (Labelfehler, kein Gruppierungsfehler)")
    print()
    print(f"Report: {out_path}")
