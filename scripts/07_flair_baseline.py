"""Vergleichsarm: fertiges deutsches NER-Modell ohne jede Anpassung.

Aufruf:
    python scripts/07_flair_baseline.py --reference gold
    python scripts/07_flair_baseline.py --reference llm --split test

Beantwortet, was man ohne Training geschenkt bekommt – und beziffert damit,
was die Domänenanpassung wert ist. Verglichen wird nur auf BRAND: das Modell
kennt PER/LOC/ORG/MISC, und nur ORG hat im Projekt-Schema eine Entsprechung.

Braucht flair, das bewusst nicht in requirements.txt steht:
    pip install -r requirements-flair.txt
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from magda.config import EVAL_DIR
from magda.dataset import get_or_create_splits, load_labeled_pages, select_split
from magda.evaluation import word_level_report, word_level_report_dict
from magda.flair_baseline import (
    FLAIR_MODEL,
    REPORTED_LABELS,
    TAG_MAPPING,
    load_tagger,
    predict_pages,
    restrict_to,
)
from magda.gold import load_gold_pages


def _gold_pages(split: str) -> tuple[list[dict], dict]:
    result = load_gold_pages()
    if result.stale:
        print(f"Übersprungen (words_hash veraltet): {', '.join(result.stale)}")
    if result.in_progress:
        print(f"Übersprungen (noch nicht fertig): {', '.join(result.in_progress)}")
    if not result.pages:
        sys.exit(
            "Keine fertig annotierte Gold-Seite gefunden. Im Annotator mit 'f' als "
            "fertig markieren – oder für einen Rauchtest --reference llm nehmen."
        )

    pages = result.pages
    if split != "all":
        splits = get_or_create_splits(load_labeled_pages())
        pages = select_split(pages, splits, split)
        if not pages:
            sys.exit(
                f"Keine Gold-Seite liegt im '{split}'-Split. Mit --split all über alle "
                "fertigen Gold-Seiten evaluieren – bei Flair unbedenklich, weil nichts "
                "trainiert wurde, aber nicht mit den trainierten Armen vergleichbar."
            )
    return pages, {"stale": result.stale, "in_progress": result.in_progress}


def _llm_pages(split: str) -> tuple[list[dict], dict]:
    print(
        "Achtung: --reference llm misst, wie gut Flair Mistral imitiert, nicht wie gut "
        "es Angebote extrahiert. Als Rauchtest brauchbar, nicht berichtsfähig."
    )
    pages = load_labeled_pages()
    if split != "all":
        pages = select_split(pages, get_or_create_splits(pages), split)
    return pages, {"stale": [], "in_progress": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default="gold", choices=["gold", "llm"])
    parser.add_argument("--split", default="test", choices=["dev", "test", "all"])
    parser.add_argument("--model", default=FLAIR_MODEL)
    args = parser.parse_args()

    pages, skipped = _gold_pages(args.split) if args.reference == "gold" else _llm_pages(args.split)
    print(
        f"Evaluiere '{args.model}' auf {len(pages)} Seiten "
        f"(Referenz: {args.reference}, Split: {args.split})."
    )

    print("Lade Modell – beim ersten Mal wird es heruntergeladen (~1,5 GB).")
    tagger = load_tagger(args.model)

    predictions = predict_pages(pages, tagger)
    # Beide Seiten einschränken: Labels, die das Modell gar nicht vorhersagen
    # kann, dürfen weder als Falsch-Negativ noch als Treffer zählen.
    references = [restrict_to(page["tags"], REPORTED_LABELS) for page in pages]

    # Ein Tag je Wort ist der Vertrag. Bricht er, hat flair die Seite still
    # abgeschnitten und der Report wäre eine Zahl über weniger Wörter.
    for page, tags in zip(pages, predictions):
        if len(tags) != len(page["words"]):
            sys.exit(
                f"{page['page_id']}: {len(tags)} Tags für {len(page['words'])} Wörter. "
                "Die Seite wurde abgeschnitten – Report wäre nicht aussagekräftig."
            )

    print(word_level_report(references, predictions))

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_file = EVAL_DIR / f"flair_{args.reference}_{args.split}.json"
    with open(out_file, "w") as f:
        json.dump(
            {
                "variant": "flair",
                "model": args.model,
                "reference": args.reference,
                "split": args.split,
                "num_pages": len(pages),
                "mapping": TAG_MAPPING,
                "restricted_to": sorted(REPORTED_LABELS),
                "skipped": skipped,
                "created": datetime.now().isoformat(timespec="seconds"),
                "report": word_level_report_dict(references, predictions),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Report gespeichert: {out_file}")


if __name__ == "__main__":
    main()
