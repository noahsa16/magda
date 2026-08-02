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

import numpy as np
from transformers import AutoModelForTokenClassification, AutoTokenizer, Trainer

from magda.config import (
    CHECKPOINTS_DIR,
    DATA_DIR,
    LAYOUT_MODEL,
    MAX_SEQ_LENGTH,
    TEXT_MODEL,
    WORDS_DIR,
    default_labeled_model,
)
from magda.dataset import (
    LayoutDataset,
    TextDataset,
    get_or_create_splits,
    load_labeled_pages,
    select_split,
)
from magda.predict import (
    WINDOW_STRIDE,
    merge_windows,
    page_output,
    word_predictions,
    write_pages,
)
from magda.windows import WindowDataset


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
    parser.add_argument("variant", choices=["gbert", "layoutxlm"])
    parser.add_argument("--split", default="test", choices=["train", "dev", "test"])
    parser.add_argument(
        "--all-words", action="store_true",
        help="Über alle extrahierten Seiten statt über einen Split. Braucht keine Labels.",
    )
    parser.add_argument(
        "--labels-from",
        help="Modellordner unter data/labeled/. Muss derselbe sein wie beim Training.",
    )
    parser.add_argument("--out", help="Zielordner (Standard: data/predictions/<variante>)")
    parser.add_argument(
        "--no-windows", action="store_true",
        help="Lange Seiten abschneiden statt in überlappenden Fenstern vorhersagen. "
             "Nur zum Vergleich – kostet auf der Testwoche 7 %% der Wörter.",
    )
    args = parser.parse_args(argv)

    model_dir = CHECKPOINTS_DIR / args.variant / "best"
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

    base_model = TEXT_MODEL if args.variant == "gbert" else LAYOUT_MODEL
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    layout = args.variant == "layoutxlm"

    if args.no_windows:
        dataset_cls = LayoutDataset if layout else TextDataset
        ds = dataset_cls(pages, tokenizer, MAX_SEQ_LENGTH)
    else:
        ds = WindowDataset(pages, tokenizer, MAX_SEQ_LENGTH, WINDOW_STRIDE, layout)
        print(f"{len(ds)} Fenster über {len(pages)} Seiten "
              f"(Überlappung {WINDOW_STRIDE} Subwords).")

    model = AutoModelForTokenClassification.from_pretrained(model_dir)
    logits = Trainer(model=model).predict(ds).predictions
    if isinstance(logits, tuple):
        logits = logits[0]
    logits = np.asarray(logits)

    outputs = []
    for i, page in enumerate(pages):
        if args.no_windows:
            tags, scores = word_predictions(logits[i], ds.word_ids[i], len(page["words"]))
        else:
            windows = ds.windows_of(i)
            tags, scores = merge_windows(
                [logits[w] for w in windows],
                [ds.word_ids[w] for w in windows],
                len(page["words"]),
            )
        outputs.append(page_output(page, tags, scores, args.variant, labels_from))

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
