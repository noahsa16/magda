"""Phase 4: Modellausgabe je Seite exportieren – Wort, Koordinate, Label.

    magda predict gbert --split test --labels-from sonnet-5
    magda predict layoutxlm --split test --labels-from sonnet-5
    magda predict gbert --all-words          # alle extrahierten Seiten

Das Ergebnis liegt in `data/predictions/<variante>/` als eine Datei je Seite
plus `index.json`. Darauf setzt die Rekonstruktion der Angebote auf: aus
getaggten Wörtern mit Koordinaten wird ein strukturiertes Angebot.

`--all-words` braucht keine Labels und ist der eigentliche Einsatzfall – eine
frisch geerntete Woche durchs Modell schicken, ohne vorher ein LLM zu fragen.
Der Standard geht dagegen über einen Split der gelabelten Seiten, damit man
Vorhersage und Referenz nebeneinander legen kann.
"""

import argparse
import json
import sys
from pathlib import Path

from magda.config import (
    CHECKPOINTS_DIR,
    DATA_DIR,
    MAX_SEQ_LENGTH,
    VARIANTS,
    WORDS_DIR,
    default_labeled_model,
)
from magda.dataset import (
    get_or_create_splits,
    load_labeled_pages,
    select_split,
)
from magda.predict import WINDOW_STRIDE, load_ner_model, page_output, predict_pages, write_pages


def pages_from_words() -> list[dict]:
    """Alle extrahierten Seiten, mit "O" als Platzhalter-Tags.

    Die Dataset-Klassen erwarten `tags`, weil sie dieselbe Klasse fürs
    Training benutzen. Für die reine Vorhersage sind die Werte bedeutungslos –
    sie landen im `labels`-Feld, das hier niemand liest.
    """
    pages = []
    for path in sorted(WORDS_DIR.glob("*.json")):
        with open(path) as f:
            page = json.load(f)
        page["tags"] = ["O"] * len(page["words"])
        pages.append(page)
    return pages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("variant", choices=list(VARIANTS))
    parser.add_argument("--split", default="test", choices=["train", "dev", "test"])
    parser.add_argument(
        "--all-words", action="store_true",
        help="Über alle extrahierten Seiten statt über einen Split. Braucht keine Labels.",
    )
    parser.add_argument(
        "--labels-from",
        help="Modellordner unter data/labeled/. Muss derselbe sein wie beim Training.",
    )
    parser.add_argument(
        "--checkpoint",
        help="Checkpoint-Ordner unter checkpoints/, falls nicht der "
        "gleichnamige. Für Nebenläufe: gbert-sonnet-5-app, gbert-p50.",
    )
    parser.add_argument("--out", help="Zielordner (Standard: data/predictions/<variante>)")
    parser.add_argument(
        "--no-windows", action="store_true",
        help="Lange Seiten abschneiden statt in überlappenden Fenstern vorhersagen. "
             "Nur zum Vergleich – kostet auf der Testwoche 7 %% der Wörter.",
    )
    args = parser.parse_args(argv)

    model_dir = CHECKPOINTS_DIR / (args.checkpoint or args.variant) / "best"
    if not model_dir.exists():
        sys.exit(f"Kein trainiertes Modell unter {model_dir}. Erst `magda train` laufen lassen.")

    if args.all_words:
        pages = pages_from_words()
        source = "alle extrahierten Seiten"
    else:
        labeled = load_labeled_pages(args.labels_from)
        if not labeled:
            sys.exit("Keine gelabelten Seiten gefunden. --all-words braucht keine.")
        pages = select_split(labeled, get_or_create_splits(labeled), args.split)
        source = f"{args.split}-Split"

    if not pages:
        sys.exit(f"Keine Seiten in {source}.")

    labels_from = args.labels_from or (None if args.all_words else default_labeled_model())
    print(f"Sage '{args.variant}' auf {len(pages)} Seiten voraus ({source}).")

    def _report_windows(count: int) -> None:
        print(f"{count} Fenster über {len(pages)} Seiten "
              f"(Überlappung {WINDOW_STRIDE} Subwords).")

    model, tokenizer, spec = load_ner_model(args.variant, args.checkpoint)
    predictions = predict_pages(
        pages, model, tokenizer, spec,
        no_windows=args.no_windows, on_windows_built=_report_windows,
    )

    outputs = [
        page_output(page, tags, scores, args.variant, labels_from)
        for page, (tags, scores) in zip(pages, predictions)
    ]

    target = Path(args.out) if args.out else DATA_DIR / "predictions" / args.variant
    index = write_pages(outputs, target)

    print(f"\n{index['num_pages']} Seiten, {index['num_words']} Wörter, "
          f"{index['num_entities']} Entities -> {target}")
    for label, count in index["entities_per_label"].items():
        print(f"  {label:<12} {count:>5}")
    if index["truncated_pages"]:
        print(f"\nAbgeschnitten (über {MAX_SEQ_LENGTH} Subwords), hintere Wörter ohne "
              f"Vorhersage: {len(index['truncated_pages'])} Seiten")
        for pid in index["truncated_pages"][:10]:
            print(f"  {pid}")
