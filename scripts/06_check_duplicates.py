"""Prüft data/words/ auf doppelte und beinah doppelte Seiten.

Aufruf:
    python scripts/06_check_duplicates.py                  # nur berichten
    python scripts/06_check_duplicates.py --threshold 0.98 # strenger
    python scripts/06_check_duplicates.py --apply          # Dubletten entfernen

Ohne --apply wird nichts verändert. Der Bericht sagt, wie viele Seiten der
Datensatz *wirklich* hat – und das ist die Zahl, die in den Projektbericht
gehört, nicht die Zahl der Dateien.

Entfernt werden nur data/words/ und data/images/. Die PDFs unter data/raw/
bleiben liegen: sie sind die Herkunft, und Schritt 02 baut daraus jederzeit
alles neu auf.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from magda import catalog_meta, dedupe
from magda.config import GOLD_DIR, IMAGES_DIR, LABELED_DIR, WORDS_DIR


def _catalog_of(page_id: str) -> str:
    return page_id.rsplit("_p", 1)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=0.95,
                        help="Ab welcher Jaccard-Ähnlichkeit zwei Seiten dieselbe sind")
    parser.add_argument("--apply", action="store_true",
                        help="Dubletten wirklich entfernen (sonst nur berichten)")
    args = parser.parse_args()

    pages = {}
    for f in sorted(WORDS_DIR.glob("*.json")):
        with open(f) as fh:
            pages[f.stem] = [w["text"] for w in json.load(fh)["words"]]
    if not pages:
        sys.exit("Keine Seiten in data/words/. Erst 02_extract_words.py laufen lassen.")

    geschuetzt = {f.stem for f in LABELED_DIR.glob("*.json")} | {f.stem for f in GOLD_DIR.glob("*.json")}
    gruppen = dedupe.group(pages, args.threshold)
    mehrfach = [g for g in gruppen if len(g) > 1]

    print(f"{len(pages)} Seiten in data/words/")
    print(f"{len(gruppen)} verschiedene Seiten bei Jaccard >= {args.threshold}")
    print(f"{len(pages) - len(gruppen)} redundant, verteilt auf {len(mehrfach)} Gruppen\n")

    meta = catalog_meta.load()
    for gruppe in mehrfach[:15]:
        vertreter = dedupe.choose(gruppe, geschuetzt)
        print(f"  behalten: {vertreter}  ({catalog_meta.label(_catalog_of(vertreter), meta) or 'Region unbekannt'})")
        for pid in gruppe:
            if pid == vertreter:
                continue
            marker = dedupe.print_marker(pages[pid]) or "–"
            print(f"     dublett: {pid:22} Druckkennung {marker}")
    if len(mehrfach) > 15:
        print(f"  … und {len(mehrfach) - 15} weitere Gruppen")

    if not args.apply:
        print("\nNichts verändert. Mit --apply entfernen.")
        return

    entfernt = 0
    for gruppe in mehrfach:
        vertreter = dedupe.choose(gruppe, geschuetzt)
        for pid in gruppe:
            if pid == vertreter:
                continue
            if pid in geschuetzt:
                # Sollte durch choose() nicht vorkommen; wenn doch, ist Handarbeit
                # dahin – lieber die Dublette behalten als ein Label verlieren.
                print(f"  übersprungen (gelabelt/Gold): {pid}")
                continue
            (WORDS_DIR / f"{pid}.json").unlink(missing_ok=True)
            (IMAGES_DIR / f"{pid}.png").unlink(missing_ok=True)
            entfernt += 1

    print(f"\n{entfernt} Seiten entfernt, {len(list(WORDS_DIR.glob('*.json')))} bleiben.")
    print("data/raw/ ist unberührt – Schritt 02 stellt jederzeit alles wieder her.")


if __name__ == "__main__":
    main()
