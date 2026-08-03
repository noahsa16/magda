"""Gruppiert gelabelte Entities zu Angeboten und schreibt SQLite.

Aufruf:
    magda offers
    magda offers --source layoutxlm-test
    magda offers --predictions gbert
    magda offers --db data/offers/offers.sqlite

Quelle ist standardmaessig ein Labelordner unter data/labeled/ (words[] mit
bbox und tags[] als BIO-Folge). Mit --predictions wird stattdessen
data/predictions/<variante>/ gelesen, das Ausgabeformat von `magda predict`:
Labels stehen dort direkt am Wort statt als BIO-Folge, dazu liegen die Spans
schon als entities[] vor. _load_predicted_pages baut daraus tags[], damit
cluster_page beide Quellen gleich behandelt.
"""

import argparse
import json
from pathlib import Path

from magda import config, offers
from magda.labels import spans_to_bio


DEFAULT_DB = config.DATA_DIR / "offers" / "offers.sqlite"


def _load_labeled_pages(source: str) -> list[dict]:
    directory = config.labeled_dir(source)
    pages = []
    for path in sorted(directory.glob("*.json")):
        with open(path) as f:
            page = json.load(f)
        if page.get("words") and page.get("tags"):
            pages.append(page)
    return pages


def _load_predicted_pages(variant: str) -> list[dict]:
    directory = config.DATA_DIR / "predictions" / config.model_slug(variant)
    pages = []
    for path in sorted(directory.glob("*.json")):
        if path.name == "index.json":
            continue
        with open(path) as f:
            page = json.load(f)
        words = page.get("words")
        if not words or page.get("entities") is None:
            continue
        page["tags"] = spans_to_bio(len(words), page["entities"])
        pages.append(page)
    return pages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=None,
                        help="Labelordner unter data/labeled/. Default: konfiguriertes/groesstes Modell")
    parser.add_argument("--predictions", default=None,
                        help="Variante unter data/predictions/ statt data/labeled/ (z.B. gbert)")
    parser.add_argument("--db", default=str(DEFAULT_DB),
                        help="SQLite-Zieldatei")
    args = parser.parse_args(argv)

    if args.predictions:
        source = args.predictions
        directory = config.DATA_DIR / "predictions" / config.model_slug(source)
        if not directory.is_dir():
            parser.error(f"Vorhersagequelle nicht gefunden: {directory}")
        pages = _load_predicted_pages(source)
        if not pages:
            parser.exit(1, f"Keine Vorhersagen in {directory} gefunden. Erst `magda predict {source}` laufen lassen.\n")
    else:
        source = args.source or config.default_labeled_model()
        if source is None:
            parser.exit(1, "Keine Labelquelle gefunden. Erst `magda label` laufen lassen.\n")
        if not config.labeled_dir(source).is_dir():
            parser.error(f"Labelquelle nicht gefunden: {source}")
        pages = _load_labeled_pages(source)
        if not pages:
            parser.exit(1, f"Keine gelabelten Seiten in {config.labeled_dir(source)} gefunden.\n")

    stats = offers.write_sqlite(pages, db_path=Path(args.db), source=source)
    print(
        f"{stats['offers']} Angebote aus {stats['entities']} Entities "
        f"auf {stats['pages']} Seiten geschrieben."
    )
    print(f"DB: {args.db}")
