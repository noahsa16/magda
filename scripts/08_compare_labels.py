"""Vergleichsschritt: wie nah liegen die LLM-Labels am Goldstandard?

    python scripts/08_compare_labels.py                  # alle Modellordner
    python scripts/08_compare_labels.py --model qwen3.6-27b
    python scripts/08_compare_labels.py --per-label      # Aufschlüsselung je Entity-Typ

Misst jeden Ordner unter data/labeled/ gegen die handannotierten Seiten in
gold/ und schreibt einen Report nach data/eval/labels_vs_gold.json. Das ist
die Entscheidungsgrundlage dafür, welches Modell den Trainingssatz labelt –
ohne sie ist die Modellwahl Bauchgefühl.

Verglichen wird nur auf Seiten, die ein Modell *und* Gold haben. Fehlt eine
Gold-Seite im Modellordner, steht sie als "fehlend" im Report statt still den
Schnitt zu verbessern.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from magda.config import EVAL_DIR, labeled_dir, labeled_models
from magda.evaluation import word_level_report, word_level_report_dict
from magda.gold import load_gold_pages


def _score(model: str, gold_pages: list[dict]) -> dict | None:
    """Report eines Modellordners gegen die Gold-Seiten."""
    directory = labeled_dir(model)
    references, predictions, compared, missing = [], [], [], []

    for gold in gold_pages:
        page_id = gold["page_id"]
        path = directory / f"{page_id}.json"
        if not path.exists():
            missing.append(page_id)
            continue
        with open(path) as f:
            tags = json.load(f).get("tags")
        # Ein Tag je Wort ist der Vertrag. Weicht die Länge ab, zeigen die
        # Indizes auf andere Wörter – dann ist der Vergleich wertlos, nicht
        # bloß ungenau.
        if not tags or len(tags) != len(gold["tags"]):
            missing.append(f"{page_id} (Tag-Anzahl passt nicht)")
            continue
        references.append(gold["tags"])
        predictions.append(tags)
        compared.append(page_id)

    if not references:
        return None
    return {
        "model": model,
        "pages_compared": len(compared),
        "page_ids": compared,
        "missing": missing,
        "report": word_level_report_dict(references, predictions),
        "_text": word_level_report(references, predictions),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", help="Nur dieses Modell (mehrfach möglich).")
    parser.add_argument("--per-label", action="store_true", help="Report je Entity-Typ ausgeben.")
    args = parser.parse_args()

    gold = load_gold_pages()
    if not gold.pages:
        sys.exit(
            "Keine verwertbaren Gold-Seiten. Im Annotator mindestens eine Seite "
            "fertig markieren (status=done)."
        )
    print(f"{len(gold.pages)} Gold-Seiten als Referenz.")
    if gold.stale:
        print(f"  übersprungen, Wortliste geändert: {', '.join(gold.stale)}")
    if gold.in_progress:
        print(f"  übersprungen, noch in Arbeit: {', '.join(gold.in_progress)}")

    models = args.model or labeled_models()
    if not models:
        sys.exit("Keine Labels unter data/labeled/. Erst 03_label_words.py laufen lassen.")

    results = [r for r in (_score(m, gold.pages) for m in models) if r]
    if not results:
        sys.exit("Kein Modell hat Labels für eine der Gold-Seiten.")

    # Nach micro-F1 sortiert, bestes zuerst – die Rangfolge ist der Zweck.
    results.sort(key=lambda r: r["report"].get("micro avg", {}).get("f1-score", 0), reverse=True)

    print(f"\n{'Modell':<32}{'Seiten':>7}{'F1':>8}{'Prec':>8}{'Rec':>8}")
    print("-" * 63)
    for r in results:
        micro = r["report"].get("micro avg", {})
        print(
            f"{r['model']:<32}{r['pages_compared']:>7}"
            f"{micro.get('f1-score', 0):>8.3f}{micro.get('precision', 0):>8.3f}"
            f"{micro.get('recall', 0):>8.3f}"
        )
        if r["missing"]:
            print(f"{'':<32}  ohne Vergleich: {', '.join(r['missing'])}")

    if args.per_label:
        for r in results:
            print(f"\n--- {r['model']} ---")
            print(r["_text"])

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_file = EVAL_DIR / "labels_vs_gold.json"
    with open(out_file, "w") as f:
        json.dump(
            {
                "gold_pages": [p["page_id"] for p in gold.pages],
                "results": [{k: v for k, v in r.items() if k != "_text"} for r in results],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nReport geschrieben: {out_file}")
    print(
        f"Achtung beim Zitieren: {len(gold.pages)} Gold-Seiten sind eine schmale "
        "Basis. Große Unterschiede sind aussagekräftig, kleine nicht."
    )


if __name__ == "__main__":
    main()
