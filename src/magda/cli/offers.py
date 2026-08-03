"""Gruppiert gelabelte Entities zu Angeboten und schreibt SQLite.

Aufruf:
    magda offers
    magda offers --source layoutxlm-test
    magda offers --db data/offers/offers.sqlite

Quelle ist ein Labelordner unter data/labeled/. Die Dateien muessen das normale
Magda-Format haben: words[] mit bbox und tags[] als BIO-Folge. Damit passt der
Schritt sowohl auf LLM-Labels als auch auf gespeicherte LayoutXLM-Ausgaben.
"""

import argparse
import json
from pathlib import Path

from magda import config, offers


DEFAULT_DB = config.DATA_DIR / "offers" / "offers.sqlite"


def _load_pages(source: str) -> list[dict]:
    directory = config.labeled_dir(source)
    pages = []
    for path in sorted(directory.glob("*.json")):
        with open(path) as f:
            page = json.load(f)
        if page.get("words") and page.get("tags"):
            pages.append(page)
    return pages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=None,
                        help="Labelordner unter data/labeled/. Default: konfiguriertes/groesstes Modell")
    parser.add_argument("--db", default=str(DEFAULT_DB),
                        help="SQLite-Zieldatei")
    args = parser.parse_args(argv)

    source = args.source or config.default_labeled_model()
    if source is None:
        parser.exit(1, "Keine Labelquelle gefunden. Erst `magda label` laufen lassen.\n")
    if not config.labeled_dir(source).is_dir():
        parser.error(f"Labelquelle nicht gefunden: {source}")

    pages = _load_pages(source)
    if not pages:
        parser.exit(1, f"Keine gelabelten Seiten in {config.labeled_dir(source)} gefunden.\n")

    stats = offers.write_sqlite(pages, db_path=Path(args.db), source=source)
    print(
        f"{stats['offers']} Angebote aus {stats['entities']} Entities "
        f"auf {stats['pages']} Seiten geschrieben."
    )
    print(f"DB: {args.db}")
