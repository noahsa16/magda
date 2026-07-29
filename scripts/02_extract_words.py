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

from magda.config import GOLD_DIR, IMAGES_DIR, LABELED_DIR, RAW_DIR, WORDS_DIR
from magda.gold import words_hash
from magda.ocr import extract_words, render_png


def main():
    WORDS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(RAW_DIR.glob("*/bk_*.pdf"))
    if not pdfs:
        sys.exit("Keine PDFs in data/raw/ gefunden. Erst 01_download_flyers.py laufen lassen.")

    # Seiten, an denen schon Arbeit hängt, zuerst: bei einer Dublette gewinnt,
    # wer zuerst drankommt. In reiner Sortierreihenfolge gewönne der Katalog
    # mit der kleineren Nummer – und die vorhandenen Labels zeigten danach auf
    # eine Seite, die es nicht mehr gibt.
    bearbeitet = {f.stem for f in LABELED_DIR.glob("*.json")} | {f.stem for f in GOLD_DIR.glob("*.json")}

    def vorrang(pdf_path):
        page_id = f"{pdf_path.parent.name}_p{pdf_path.stem.removeprefix('bk_')}"
        return (0 if page_id in bearbeitet else 1, pdf_path.parent.name, int(pdf_path.stem.removeprefix("bk_")))

    pdfs.sort(key=vorrang)

    # Wortlisten, die schon vorliegen – gegen sie wird entdoppelt.
    gesehen = {}
    for f in sorted(WORDS_DIR.glob("*.json")):
        with open(f) as fh:
            gesehen.setdefault(words_hash(json.load(fh)["words"]), f.stem)

    done = skipped = doppelt = leer = 0
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

        if not page["words"]:
            leer += 1
            continue

        # Penny gibt je Woche 44 Regionalausgaben heraus, die zu über 90 %
        # identisch sind. Wer die Dublette durchlässt, zahlt sie zweimal: in
        # Schritt 03 mit LLM-Zeit, und im Ergebnis mit einem Testsplit, der
        # Seiten aus dem Trainingssplit enthält.
        h = words_hash(page["words"])
        if h in gesehen:
            doppelt += 1
            continue
        gesehen[h] = page_id

        (IMAGES_DIR / f"{page_id}.png").write_bytes(render_png(pdf_bytes))
        with open(out_json, "w") as f:
            json.dump(page, f, ensure_ascii=False)
        done += 1

    print(
        f"{done} Seiten verarbeitet, {skipped} schon vorhanden, "
        f"{doppelt} als Dublette verworfen, {leer} ohne Textlayer."
    )


if __name__ == "__main__":
    main()
