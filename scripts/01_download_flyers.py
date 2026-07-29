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
    try:
        catalog_id = scraping.extract_catalog_id(args.url)
    except ValueError:
        # Ein Traceback im Konsolenfenster der Steuerzentrale sieht aus wie ein
        # Programmfehler, ist aber ein Tippfehler in der Eingabe.
        sys.exit(
            f"In dieser Adresse steckt keine catalogId: {args.url}\n"
            "Gebraucht wird die Blätterkatalog-Adresse, nicht die Prospektseite von "
            "penny.de. Sie sieht so aus:\n"
            "  https://penny-publish.blaetterkatalog.de/frontend/getcatalog.do?catalogId=1347375"
        )

    out_dir = RAW_DIR / catalog_id
    count = 0
    for page, pdf_bytes in tqdm(
        scraping.download_catalog(args.url, session, args.max_pages),
        desc=f"Katalog {catalog_id}",
        unit="Seite",
    ):
        # Verzeichnis erst anlegen, wenn wirklich etwas kommt. Sonst bleibt
        # nach einem Fehlschlag ein leerer Ordner zurück, den die Übersicht
        # als Katalog mit null Seiten zeigt.
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"bk_{page}.pdf").write_bytes(pdf_bytes)
        count += 1

    if count == 0:
        sys.exit(f"Katalog {catalog_id} hat keine abrufbare Seite geliefert.")
    print(f"{count} Seiten gespeichert unter {out_dir}")


if __name__ == "__main__":
    main()
