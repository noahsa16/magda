"""Die Lernkurve auslesen: wie viel Lehrer braucht der Schüler?

    magda curve --points 25,50,100,175

Das Projekt *ist* Knowledge Distillation mit LLM-Silberlabels. Es so zu
nennen ist Verpackung; die Kurve ist der Befund. Sie beantwortet die Frage,
die über den Nutzen weiterer LLM-Zeit entscheidet: Sättigt der Schüler, und
wenn ja, wo?

**Die x-Achse ist die Clusterzahl, nicht die Seitenzahl.** Penny gibt je
Woche 44 fast gleiche Regionalfassungen heraus; wer Seiten zählt, zählt
Kopien. 25 Seiten können neun unabhängige Vorlagen sein oder drei – je
nachdem, wie gezogen wurde.

**Die Zahl hier ist Dev, und sie ist optimistisch.** Berichtet wird das beste
`eval_f1` über alle Epochen, also genau das Kriterium, nach dem der
Checkpoint ausgewählt wurde – ein Maximum über zehn Ziehungen. Der Bias ist
für jeden Punkt derselbe, die *Form* der Kurve also vergleichbar; ihr
*Niveau* ist es nicht. Die belastbaren Zahlen entstehen im gebündelten
Schlussbatch auf Test.

**Die Kurve ist deskriptiv, nicht selektiv.** An ihrem Ergebnis hängt keine
Auswahl – nur so ist es regelkonform, mehrere Checkpoints gegen denselben
Split zu halten.
"""

from __future__ import annotations

import argparse
import json

from magda import checkpoints, config


def best_dev_f1(checkpoint_dir) -> float | None:
    """Bestes `eval_f1` aus dem Trainingsverlauf eines Lauf-Ordners.

    Wo der Verlauf steht, entscheidet `checkpoints.training_state_path`:
    `trainer.save_model()` schreibt in `best/` kein `trainer_state.json`, und
    nach `magda prune-checkpoints` liegt er im Lauf-Ordner statt in
    `checkpoint-N/` – derselbe Grund, aus dem `/api/model` so vorgeht.
    """
    state_file = checkpoints.training_state_path(checkpoint_dir)
    if state_file is None:
        return None
    history = json.loads(state_file.read_text()).get("log_history") or []
    return max((e["eval_f1"] for e in history if "eval_f1" in e), default=None)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="magda curve",
        description="Lernkurve über clusterweise gezogene Trainingsteilmengen.")
    parser.add_argument("--points", default="25,50,100,175",
                        help="Seitenzahlen der Kurvenpunkte, kommagetrennt")
    parser.add_argument("--variant", default="gbert", choices=list(config.VARIANTS))
    parser.add_argument("--labels-from", default=config.CANONICAL_LABELS)
    args = parser.parse_args(argv)

    from magda.dataset import (
        duplicate_clusters,
        get_or_create_splits,
        load_labeled_pages,
        select_split,
        subset_by_clusters,
    )

    pages = load_labeled_pages(args.labels_from)
    splits = get_or_create_splits(pages)
    train = select_split(pages, splits, "train")
    dev = select_split(pages, splits, "dev")

    rows = []
    for point in [int(p) for p in args.points.split(",") if p.strip()]:
        wanted = set(subset_by_clusters(train, point))
        subset = [p for p in train if p["page_id"] in wanted]
        directory = config.CHECKPOINTS_DIR / f"{args.variant}-p{point}"
        rows.append({
            "point": point,
            "pages": len(subset),
            "clusters": len(duplicate_clusters(subset)),
            "dev_f1": best_dev_f1(directory) if directory.is_dir() else None,
            "checkpoint": directory.name,
        })

    print(f"Lernkurve {args.variant}, Labels von {args.labels_from}")
    print(f"Voll: {len(train)} Seiten in {len(duplicate_clusters(train))} Clustern; "
          f"Dev {len(dev)} Seiten in {len(duplicate_clusters(dev))} Clustern\n")
    print(f"  {'Punkt':<8}{'Seiten':>8}{'Cluster':>9}{'bestes Dev-F1':>15}")
    for row in rows:
        f1 = "  -  " if row["dev_f1"] is None else f"{row['dev_f1']:.4f}"
        print(f"  {'p' + str(row['point']):<8}{row['pages']:>8}"
              f"{row['clusters']:>9}{f1:>15}")

    print("\n  Dev-Zahl = bestes eval_f1 über alle Epochen, also das Kriterium")
    print("  der Checkpoint-Auswahl selbst: ein Maximum über zehn Ziehungen und")
    print("  damit optimistisch. Der Bias ist je Punkt derselbe, die Form der")
    print("  Kurve also vergleichbar, ihr Niveau nicht. Belastbar wird das erst")
    print("  im Schlussbatch auf Test. Die Kurve ist deskriptiv, nicht selektiv.")

    payload = {"variant": args.variant,
               "labels_from": config.model_slug(args.labels_from),
               "metric": "best eval_f1 over epochs, dev split",
               "descriptive_only": True,
               "train_pages": len(train),
               "train_clusters": len(duplicate_clusters(train)),
               "dev_pages": len(dev),
               "dev_clusters": len(duplicate_clusters(dev)),
               "points": rows}
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.EVAL_DIR / f"learning_curve_{args.variant}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nReport: {out_path}")
