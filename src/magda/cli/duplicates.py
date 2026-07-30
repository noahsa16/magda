"""Prüft data/words/ auf doppelte und beinah doppelte Seiten.

Aufruf:
    magda dedupe                  # nur berichten
    magda dedupe --threshold 0.98 # strenger
    magda dedupe --apply          # Duplikate entfernen

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

from magda import catalog_meta, dedupe
from magda.config import (
    GOLD_DIR,
    IMAGES_DIR,
    WORDS_DIR,
    labeled_dir,
    labeled_models,
    labeled_page_ids,
)


def _catalog_of(page_id: str) -> str:
    return page_id.rsplit("_p", 1)[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=0.95,
                        help="Ab welcher Jaccard-Ähnlichkeit zwei Seiten dieselbe sind")
    parser.add_argument("--apply", action="store_true",
                        help="Duplikate wirklich entfernen (sonst nur berichten)")
    args = parser.parse_args(argv)

    pages = {}
    for f in sorted(WORDS_DIR.glob("*.json")):
        with open(f) as fh:
            pages[f.stem] = [w["text"] for w in json.load(fh)["words"]]
    if not pages:
        sys.exit("Keine Seiten in data/words/. Erst `magda extract` laufen lassen.")

    # Zwei verschiedene Begriffe, die man leicht verwechselt:
    #
    #   bevorzugt  – wer eine Gruppe vertreten darf. Eine gelabelte Seite zu
    #                behalten spart einen LLM-Aufruf.
    #   unantastbar – wer auf keinen Fall verschwindet. Das ist nur Gold:
    #                Handarbeit ist nicht reproduzierbar, LLM-Labels schon.
    #
    # Beides gleichzusetzen war ein Fehler: sobald auch die Duplikate gelabelt
    # waren, schützte sich der Datensatz gegen seine eigene Bereinigung.
    preferred = labeled_page_ids() | {f.stem for f in GOLD_DIR.glob("*.json")}
    protected = {f.stem for f in GOLD_DIR.glob("*.json")}
    groups = dedupe.group(pages, args.threshold)
    duplicates = [g for g in groups if len(g) > 1]

    print(f"{len(pages)} Seiten in data/words/")
    print(f"{len(groups)} verschiedene Seiten bei Jaccard >= {args.threshold}")
    print(f"{len(pages) - len(groups)} redundant, verteilt auf {len(duplicates)} Gruppen\n")

    meta = catalog_meta.load()
    for group in duplicates[:15]:
        representative = dedupe.choose(group, preferred)
        print(f"  behalten: {representative}  ({catalog_meta.label(_catalog_of(representative), meta) or 'Region unbekannt'})")
        for pid in group:
            if pid == representative:
                continue
            marker = dedupe.print_marker(pages[pid]) or "–"
            print(f"     duplikat: {pid:22} Druckkennung {marker}")
    if len(duplicates) > 15:
        print(f"  … und {len(duplicates) - 15} weitere Gruppen")

    if not args.apply:
        print("\nNichts verändert. Mit --apply entfernen.")
        return

    # Die Ausschlussliste ist der eigentliche Wirkmechanismus. Nur zu löschen
    # genügt nicht: Schritt 02 baut data/words aus data/raw wieder auf und
    # erkennt dabei nur exakt gleiche Wortlisten – die Beinah-Duplikate kämen
    # beim nächsten Lauf zurück und würden beim übernächsten gelabelt.
    excluded = dedupe.load_excluded()
    removed = 0
    for group in duplicates:
        representative = dedupe.choose(group, preferred)
        for pid in group:
            if pid == representative:
                continue
            if pid in protected:
                # Zwei Gold-Seiten in einer Gruppe: beide behalten. Handarbeit
                # wegzuwerfen wäre schlimmer als ein Duplikat im Datensatz.
                print(f"  übersprungen (Gold): {pid}")
                continue
            excluded[pid] = representative
            (WORDS_DIR / f"{pid}.json").unlink(missing_ok=True)
            (IMAGES_DIR / f"{pid}.png").unlink(missing_ok=True)
            # Das Label gehört zur Seite. Es stehen zu lassen hieße, eine
            # ausgeschlossene Seite weiter im Trainingssatz zu führen – und
            # zwar in jedem Modellordner, nicht nur im gerade aktiven.
            for labeler in labeled_models():
                (labeled_dir(labeler) / f"{pid}.json").unlink(missing_ok=True)
            removed += 1
    dedupe.save_excluded(excluded)

    print(f"\n{removed} Seiten entfernt, {len(list(WORDS_DIR.glob('*.json')))} bleiben.")
    print(f"{len(excluded)} Seiten stehen jetzt in data/excluded.json – Schritt 02 "
          "überspringt sie künftig.")
    print("data/raw/ ist unberührt: die Ausschlussliste löschen stellt alles wieder her.")

