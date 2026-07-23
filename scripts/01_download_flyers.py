"""Lädt alle Seiten eines Penny-Prospekts als einzelne PDFs nach data/raw/.

Aufruf:
    python scripts/01_download_flyers.py "https://...blaetterkatalog.de/...?catalogId=123456"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
from tqdm import tqdm

from magda import scraping
from magda.config import RAW_DIR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Blätterkatalog-URL mit catalogId")
    parser.add_argument("--max-pages", type=int, default=40)
    args = parser.parse_args()

    session = requests.Session()
    catalog_id = scraping.extract_catalog_id(args.url)
    out_dir = RAW_DIR / catalog_id
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for page, pdf_bytes in tqdm(
        scraping.download_catalog(args.url, session, args.max_pages),
        desc=f"Katalog {catalog_id}",
        unit="Seite",
    ):
        (out_dir / f"bk_{page}.pdf").write_bytes(pdf_bytes)
        count += 1

    print(f"{count} Seiten gespeichert unter {out_dir}")


if __name__ == "__main__":
    main()
