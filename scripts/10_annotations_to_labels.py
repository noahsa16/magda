"""Macht aus Annotationen einen Trainingsdatensatz.

    python scripts/10_annotations_to_labels.py --annotator "sonnet-5 (vorannotiert, ungeprueft)"
    python scripts/10_annotations_to_labels.py --annotator Noah --name gold-noah

Die Annotationen unter gold/ sind Spans; zum Trainieren braucht es BIO-Tags in
derselben Form, die Schritt 03 schreibt. Dieses Skript übersetzt das eine ins
andere und legt das Ergebnis als Modellordner unter data/labeled/ ab.

Damit rutschen von Hand oder von einem Agenten erzeugte Labels in dieselbe
Maschinerie wie die LLM-Läufe: `04_train --labels-from`, der Gold-Vergleich in
Schritt 08 und die Agreement-Analyse in Schritt 09 funktionieren unverändert.

gold/ bleibt dabei unangetastet. Es ist die Referenz, gegen die gemessen wird –
wer daraus zugleich den Trainingssatz macht, misst im Kreis.
"""

import argparse
import json
import sys
from pathlib import Path

from magda.config import GOLD_DIR, WORDS_DIR, labeled_dir
from magda.gold import words_hash
from magda.labels import spans_to_bio


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--annotator", required=True, help="Nur Annotationen dieses Urhebers übernehmen."
    )
    parser.add_argument(
        "--name",
        help="Zielordner unter data/labeled/. Ohne Angabe der Urhebername ohne Klammerzusatz.",
    )
    parser.add_argument(
        "--only-done",
        action="store_true",
        help="Nur freigegebene Seiten (status=done) übernehmen.",
    )
    args = parser.parse_args()

    name = args.name or args.annotator.split("(")[0].strip()
    out_dir = labeled_dir(name)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = skipped_status = skipped_stale = 0
    for gold_file in sorted(GOLD_DIR.glob("*.json")):
        try:
            with open(gold_file) as f:
                annotation = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if annotation.get("annotator") != args.annotator:
            continue
        if args.only_done and annotation.get("status") != "done":
            skipped_status += 1
            continue

        words_file = WORDS_DIR / f"{gold_file.stem}.json"
        if not words_file.exists():
            continue
        with open(words_file) as f:
            page = json.load(f)

        # Dieselbe Absicherung wie beim Gold-Lesen: passt der Hash nicht, zeigen
        # die Span-Indizes auf andere Wörter. Solche Seiten in den Trainingssatz
        # zu übernehmen hieße, das Modell auf verschobene Labels zu trainieren.
        if annotation.get("words_hash") and annotation["words_hash"] != words_hash(page["words"]):
            skipped_stale += 1
            continue

        page["tags"] = spans_to_bio(len(page["words"]), annotation.get("spans", []))
        page["model"] = name
        page["source"] = "annotation"
        with open(out_dir / f"{gold_file.stem}.json", "w") as f:
            json.dump(page, f, ensure_ascii=False)
        written += 1

    print(f"{written} Seiten nach {out_dir.relative_to(Path.cwd())} geschrieben.")
    if skipped_status:
        print(f"  {skipped_status} übersprungen, weil noch nicht freigegeben (--only-done)")
    if skipped_stale:
        print(f"  {skipped_stale} übersprungen, weil sich die Wortliste geändert hat")
    if not written:
        sys.exit(f"Nichts gefunden. Vorhandene Urheber: siehe /api/sources oder gold/.")


if __name__ == "__main__":
    main()
