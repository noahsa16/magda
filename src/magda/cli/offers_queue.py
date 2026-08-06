"""Sagt, welche Seiten die Gruppierungsreferenz zuerst brauchen.

Aufruf:
    magda offers-queue
    magda offers-queue --limit 50
    magda offers-queue --labels-from sonnet-5

Annotiert werden 30 bis 50 Seiten, nicht 196 - welche 30, entscheidet ueber
den Wert der Messung. Sortiert wird abwechselnd nach dem blinden Fleck der
Ablationsmessung (kein Grundpreis, also kein Urteil moeglich) und nach der
Clustergroesse (eine Vorlage, die fuer elf Seiten steht). Nur nach dem
blinden Fleck sortiert entstuende eine reine Non-Food-Referenz.

Nur Train und Dev. Der Testsplit ist zum Messen am Ende da.
"""

import argparse

from magda import config, review
from magda.cli.offers import _load_labeled_pages, _load_predicted_pages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-from", dest="labels_from", default=None,
                        help="Labelordner unter data/labeled/. Default: konfiguriertes/groesstes Modell")
    parser.add_argument("--predictions", default=None,
                        help="Variante unter data/predictions/ statt data/labeled/")
    parser.add_argument("--limit", type=int, default=40,
                        help="Wie viele Vorschlaege (Default 40)")
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

    try:
        suggestions = review.offer_queue(pages, limit=args.limit)
    except FileNotFoundError as error:
        parser.exit(1, f"{error}\n")

    if not suggestions:
        print("Nichts offen: jeder Duplikat-Cluster aus Train/Dev hat schon eine Referenzseite.")
        return

    print(f"Quelle: {source}   Vorschlaege: {len(suggestions)}\n")
    print(f"{'#':>3}  {'Seite':<16} {'Split':<6} {'Grund':<7} {'Cluster':>7} "
          f"{'blind':>6} {'prüfbar':>7}")
    for rank, entry in enumerate(suggestions, start=1):
        print(f"{rank:>3}  {entry['page_id']:<16} {entry['split']:<6} {entry['reason']:<7} "
              f"{entry['cluster_size']:>7} {entry['unjudgeable']:>6} {entry['judgeable']:>7}")

    blind = sum(1 for e in suggestions if e["reason"] == "luecke")
    covered = sum(e["cluster_size"] for e in suggestions)
    print(f"\n{blind} Vorschlaege wegen fehlender Pruefbarkeit, "
          f"{len(suggestions) - blind} wegen Vorlagengroesse.")
    print(f"Zusammen vertreten sie {covered} Seiten.")
    print("\nAnnotiert wird unter /offers-gold in der Oberflaeche (`magda serve --frontend`).")
