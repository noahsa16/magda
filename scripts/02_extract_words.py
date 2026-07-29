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

from magda.config import GOLD_DIR, IMAGES_DIR, RAW_DIR, WORDS_DIR, labeled_page_ids
from magda.dedupe import load_excluded, save_excluded
from magda.gold import words_hash
from magda.ocr import extract_words, render_png


def main():
    WORDS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(RAW_DIR.glob("*/bk_*.pdf"))
    if not pdfs:
        sys.exit("Keine PDFs in data/raw/ gefunden. Erst 01_download_flyers.py laufen lassen.")

    # Seiten, an denen schon Arbeit hängt, zuerst: bei einer Duplikat gewinnt,
    # wer zuerst drankommt. In reiner Sortierreihenfolge gewönne der Katalog
    # mit der kleineren Nummer – und die vorhandenen Labels zeigten danach auf
    # eine Seite, die es nicht mehr gibt.
    worked_on = labeled_page_ids() | {f.stem for f in GOLD_DIR.glob("*.json")}

    def priority(pdf_path):
        page_id = f"{pdf_path.parent.name}_p{pdf_path.stem.removeprefix('bk_')}"
        return (0 if page_id in worked_on else 1, pdf_path.parent.name, int(pdf_path.stem.removeprefix("bk_")))

    pdfs.sort(key=priority)

    # Wortlisten, die schon vorliegen – gegen sie wird entdoppelt.
    seen = {}
    for f in sorted(WORDS_DIR.glob("*.json")):
        with open(f) as fh:
            seen.setdefault(words_hash(json.load(fh)["words"]), f.stem)

    # Was 06_check_duplicates als Beinah-Duplikat aussortiert hat, bleibt
    # draußen. Ohne diese Liste käme es hier zurück und würde in Schritt 03
    # mit LLM-Zeit bezahlt.
    excluded = load_excluded()
    excluded_before = len(excluded)

    done = skipped = duplicate_count = empty_count = 0
    for pdf_path in tqdm(pdfs, desc="Extrahiere Wörter", unit="Seite"):
        catalog_id = pdf_path.parent.name
        page_num = pdf_path.stem.removeprefix("bk_")
        page_id = f"{catalog_id}_p{page_num}"

        out_json = WORDS_DIR / f"{page_id}.json"
        if out_json.exists():
            skipped += 1
            continue
        if page_id in excluded:
            duplicate_count += 1
            continue

        pdf_bytes = pdf_path.read_bytes()
        page = extract_words(pdf_bytes)
        page["page_id"] = page_id

        if not page["words"]:
            empty_count += 1
            continue

        # Penny gibt je Woche 44 Regionalausgaben heraus, die zu über 90 %
        # identisch sind. Wer das Duplikat durchlässt, zahlt sie zweimal: in
        # Schritt 03 mit LLM-Zeit, und im Ergebnis mit einem Testsplit, der
        # Seiten aus dem Trainingssplit enthält.
        h = words_hash(page["words"])
        if h in seen:
            # Nicht nur überspringen, sondern festhalten wovon. Sonst fehlt die
            # Seite in jeder Bilanz: data/raw hat 327 Seiten, data/words 196,
            # und die Differenz sähe nach Ausfall aus statt nach Duplikat.
            excluded[page_id] = seen[h]
            duplicate_count += 1
            continue
        seen[h] = page_id

        (IMAGES_DIR / f"{page_id}.png").write_bytes(render_png(pdf_bytes))
        with open(out_json, "w") as f:
            json.dump(page, f, ensure_ascii=False)
        done += 1

    if len(excluded) != excluded_before:
        save_excluded(excluded)

    print(
        f"{done} Seiten verarbeitet, {skipped} schon vorhanden, "
        f"{duplicate_count} als Duplikat verworfen, {empty_count} ohne Textlayer."
    )
    print(f"{len(excluded)} Seiten stehen in data/excluded.json, je mit der Seite, "
          "die sie vertritt.")


if __name__ == "__main__":
    main()
