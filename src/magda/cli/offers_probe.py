"""Sonde: bringt ein eingefrorenes Span-Embedding dem Paarmodell etwas?

Aufruf:
    magda offers-probe --encoder lilt
    magda offers-probe --encoder gbert --limit 40
    magda offers-probe --encoder lilt --linear

Vergleicht auf denselben Paaren fuenf Merkmalsmengen: die 35 Merkmale, sie
plus den Lexikblock, das Embedding allein, Merkmale plus Embedding und
alles. Gerechnet wird auf Train-Seiten, aufgeteilt nach Duplikat-Clustern.

**Die Sonde ersetzt `magda offers-grid` nicht.** Sie kennt keinen Dekoder
und wertet Paar-F1 aus; Merkmale, die trennen, wirken aber ueber den
Dekoder auf Gruppen-F1. Sie beantwortet nur die Vorfrage, ob ein
Embedding-Block ueberhaupt zu bauen lohnt - der volle Weg braucht eine
Dimensionsreduktion, und die waere ohne diese Antwort blind gewaehlt.
"""

from __future__ import annotations

import argparse
import json

from magda import config, offer_teacher, offers_gold


def _pages(args, parser):
    from magda import dataset
    from magda.cli.offers import _load_labeled_pages

    split_file = config.DATA_DIR / "splits" / "split.json"
    if not split_file.is_file():
        parser.exit(1, f"{split_file} fehlt. Erst `magda split` laufen lassen.\n")
    wanted = set(json.loads(split_file.read_text())["train"])

    reference = offers_gold.load_reference(
        offer_teacher.teacher_dir(args.reference_from))
    if not reference.assignments:
        parser.exit(1, f"Keine Gruppierung unter data/offer_groups/"
                       f"{config.model_slug(args.reference_from)}.\n")

    source = args.labels_from or config.CANONICAL_LABELS
    pages = [page for page in _load_labeled_pages(source)
             if page["page_id"] in wanted
             and page["page_id"] in reference.assignments]
    if not pages:
        parser.exit(1, "Keine Train-Seite traegt eine Gruppierung.\n")

    # Eine Seite je Duplikat-Cluster: sonst sind `--limit` Seiten nur
    # `--limit` Regionalfassungen weniger Vorlagen, und die Sonde misst
    # Kopien statt Layouts.
    clusters = dataset.duplicate_clusters(pages)
    chosen = {cluster[0] for cluster in clusters[:args.limit]}
    return source, [p for p in pages if p["page_id"] in chosen], reference, len(clusters)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encoder", default="lilt",
                        choices=sorted(config.VARIANTS),
                        help="Welcher trainierte Arm die Vektoren liefert")
    parser.add_argument("--checkpoint", default=None,
                        help="Abweichender Checkpoint (Default: checkpoints/<arm>/best)")
    parser.add_argument("--limit", type=int, default=30,
                        help="Wie viele Duplikat-Cluster (je eine Seite)")
    parser.add_argument("--holdout", type=int, default=3,
                        help="Jede n-te Seite wird zurueckgehalten")
    parser.add_argument("--linear", action="store_true",
                        help="Lineare Sonde statt des MLP")
    parser.add_argument("--labels-from", default=None)
    parser.add_argument("--reference-from", default="claude-sonnet-5")
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args(argv)

    import numpy as np

    from magda import offer_pairs, offer_probe

    source, pages, reference, clusters = _pages(args, parser)
    checkpoint = args.checkpoint or (
        config.PROJECT_ROOT / "checkpoints" / args.encoder / "best")
    print(f"{len(pages)} Seiten aus {clusters} Clustern   Labels: {source}   "
          f"Encoder: {args.encoder}")

    vectors = offer_probe.span_vectors(pages, args.encoder, checkpoint)

    features, embeddings, labels, page_of_row = [], [], [], []
    for page in pages:
        for row in offer_probe.pair_rows(
                page, reference.assignments[page["page_id"]],
                vectors[page["page_id"]], offer_pairs.LEXICAL_BLOCKS):
            features.append(row[0])
            embeddings.append(row[1])
            labels.append(row[2])
            page_of_row.append(page["page_id"])

    if not labels:
        parser.exit(1, "Kein trainierbares Paar mit Embedding.\n")

    features = np.asarray(features, dtype="float32")
    embeddings = np.asarray(embeddings, dtype="float32")
    labels = np.asarray(labels)
    base = len(offer_pairs.feature_names(offer_pairs.GEOMETRY_BLOCKS))

    order = sorted({p for p in page_of_row})
    holdout = set(order[::args.holdout])
    test = np.array([p in holdout for p in page_of_row])
    print(f"{len(labels)} Paare, davon {int(labels.sum())} positiv; "
          f"Sonden-Test {int(test.sum())} Paare aus {len(holdout)} Seiten")

    variants = {
        f"geometrie ({base})": features[:, :base],
        f"+lexik ({features.shape[1]})": features,
        f"{args.encoder} allein ({embeddings.shape[1]})": embeddings,
        f"geometrie + {args.encoder}": np.hstack([features[:, :base], embeddings]),
        "alles": np.hstack([features, embeddings]),
    }
    hidden = () if args.linear else offer_probe.PROBE_HIDDEN

    report = {}
    print(f"\nSonde {'linear' if args.linear else 'MLP ' + str(hidden)}"
          f" - Paar-F1, kein Dekoder:")
    for name, matrix in variants.items():
        scores = offer_probe.fit_and_score(
            matrix[~test], labels[~test], matrix[test], hidden, args.seed)
        auc = offer_probe.roc_auc(list(labels[test]), list(scores))
        f1, threshold = offer_probe.best_f1(list(labels[test]), list(scores))
        report[name] = {"auc": auc, "pair_f1": f1, "threshold": threshold,
                        "columns": int(matrix.shape[1])}
        print(f"  {name:28s} AUC {auc:.3f}   Paar-F1 {f1:.3f} "
              f"bei Schwelle {threshold:.2f}")

    payload = {
        "encoder": args.encoder,
        "checkpoint": str(checkpoint),
        "source": source,
        "reference": f"data/offer_groups/{config.model_slug(args.reference_from)}",
        "pages": len(pages),
        "clusters": clusters,
        "holdout_pages": len(holdout),
        "pairs": int(len(labels)),
        "positive": int(labels.sum()),
        "hidden": list(hidden),
        "variants": report,
    }
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out = config.EVAL_DIR / (
        f"offers_probe_{args.encoder}{'_linear' if args.linear else ''}.json")
    with open(out, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nReport: {out}")
    print("Die Sonde kennt keinen Dekoder. Gruppen-F1 misst `magda offers-grid`.")
