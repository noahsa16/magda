"""Pipeline-Schritt 1: Wörter + Positionen aus allen PDFs in data/raw/ ziehen.

Schreibt pro Seite eine JSON-Datei nach data/words/ und das gerenderte
Seitenbild nach data/images/. Bereits verarbeitete Seiten werden übersprungen,
das Skript lässt sich also jederzeit erneut laufen lassen.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tqdm import tqdm

from magda.config import IMAGES_DIR, RAW_DIR, WORDS_DIR
from magda.ocr import extract_words, render_png


def main():
    WORDS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(RAW_DIR.glob("*/bk_*.pdf"))
    if not pdfs:
        sys.exit("Keine PDFs in data/raw/ gefunden. Erst 01_download_flyers.py laufen lassen.")

    done = skipped = 0
    for pdf_path in tqdm(pdfs, desc="Extrahiere Wörter", unit="Seite"):
        catalog_id = pdf_path.parent.name
        page_num = pdf_path.stem.removeprefix("bk_")
        page_id = f"{catalog_id}_p{page_num}"

        out_json = WORDS_DIR / f"{page_id}.json"
        if out_json.exists():
            skipped += 1
            continue

        pdf_bytes = pdf_path.read_bytes()
        page = extract_words(pdf_bytes)
        page["page_id"] = page_id

        (IMAGES_DIR / f"{page_id}.png").write_bytes(render_png(pdf_bytes))
        with open(out_json, "w") as f:
            json.dump(page, f, ensure_ascii=False)
        done += 1

    print(f"{done} Seiten verarbeitet, {skipped} übersprungen (schon vorhanden).")


if __name__ == "__main__":
    main()
