"""Konfidenzintervalle und Modellvergleich auf dem Test-Split.

    magda significance --labels-from sonnet-5
    magda significance --labels-from sonnet-5 --compare gbert layoutxlm

Liest die Exporte aus `data/predictions/<variante>/`, also das, was `magda
predict` ausliefert – nicht die Trainingsausgabe. Damit misst die Statistik
dasselbe Artefakt, das weiterverarbeitet wird.

Resampled wird über Duplikat-Cluster, nicht über Seiten: die 100 Testseiten
bilden bei Jaccard 0.7 nur rund 43 Cluster, weil Penny je Woche 44 fast
identische Regionalausgaben herausgibt. Über Seiten gezogen wäre das Intervall
zu eng und ein Unterschied zwischen zwei Modellen schnell "signifikant", der
in Wahrheit auf elf Kopien derselben Vorlage beruht.
"""

import argparse
import json
import sys
from datetime import datetime

from magda.config import DATA_DIR, EVAL_DIR, WORDS_DIR, labeled_dir
from magda.dedupe import group
from magda.significance import bootstrap_f1, paired_bootstrap

CLUSTER_THRESHOLD = 0.7


def load_predictions(variant: str) -> dict[str, list[str]]:
    """Wort-Tags je Seite aus dem Export. `null` (abgeschnitten) zählt als "O"."""
    folder = DATA_DIR / "predictions" / variant
    if not folder.exists():
        sys.exit(f"{folder} fehlt. Erst `magda predict {variant} --split test` laufen lassen.")
    pages = {}
    for path in sorted(folder.glob("*.json")):
        if path.name == "index.json":
            continue
        page = json.loads(path.read_text())
        pages[page["page_id"]] = [w["label"] or "O" for w in page["words"]]
    return pages


def test_clusters(page_ids: list[str]) -> list[list[int]]:
    """Duplikat-Cluster als Positionen in `page_ids`."""
    words = {}
    for pid in page_ids:
        path = WORDS_DIR / f"{pid}.json"
        if path.exists():
            words[pid] = [w["text"] for w in json.loads(path.read_text())["words"]]
    position = {pid: i for i, pid in enumerate(page_ids)}
    clusters = [[position[p] for p in c] for c in group(words, threshold=CLUSTER_THRESHOLD)]
    clusters += [[position[p] for p in page_ids if p not in words]] if len(words) < len(
        page_ids
    ) else []
    return [c for c in clusters if c]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--labels-from", required=True,
                        help="Referenzlabels, dieselben wie beim Training.")
    parser.add_argument("--compare", nargs=2, default=["gbert", "layoutxlm"],
                        metavar=("A", "B"))
    parser.add_argument("--resamples", type=int, default=10000)
    args = parser.parse_args(argv)

    a, b = args.compare
    predictions = {name: load_predictions(name) for name in (a, b)}
    gemeinsam = sorted(set(predictions[a]) & set(predictions[b]))
    if not gemeinsam:
        sys.exit(f"Keine Seiten, die in {a} und {b} beide vorliegen.")

    reference = []
    for pid in gemeinsam:
        path = labeled_dir(args.labels_from) / f"{pid}.json"
        if not path.exists():
            sys.exit(f"Referenz fehlt: {path}")
        reference.append(json.loads(path.read_text())["tags"])

    clusters = test_clusters(gemeinsam)
    print(f"{len(gemeinsam)} Seiten in {len(clusters)} Clustern "
          f"(Jaccard {CLUSTER_THRESHOLD}), {args.resamples} Resamples.\n")

    ergebnis = {}
    for name in (a, b):
        tags = [predictions[name][pid] for pid in gemeinsam]
        ergebnis[name] = bootstrap_f1(reference, tags, clusters, args.resamples)
        r = ergebnis[name]
        print(f"{name:<12} F1 {r['f1']:.4f}  95%-KI [{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}]")

    vergleich = paired_bootstrap(
        reference,
        [predictions[a][pid] for pid in gemeinsam],
        [predictions[b][pid] for pid in gemeinsam],
        clusters,
        args.resamples,
    )
    print(f"\n{a} − {b}: {vergleich['difference']:+.4f}  "
          f"95%-KI [{vergleich['ci95'][0]:+.4f}, {vergleich['ci95'][1]:+.4f}]  "
          f"p = {vergleich['p_value']:.4f}")
    if vergleich["significant"]:
        print(f"Der Unterschied ist mit diesen Daten belegbar.")
    else:
        print("Das Intervall überdeckt die Null: mit diesen Daten ist kein "
              "Unterschied belegbar. Das ist ein Befund, kein Versäumnis.")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_file = EVAL_DIR / f"significance_{a}_{b}.json"
    with open(out_file, "w") as f:
        json.dump(
            {
                "created": datetime.now().isoformat(timespec="seconds"),
                "labels_from": args.labels_from,
                "pages": len(gemeinsam),
                "clusters": len(clusters),
                "cluster_threshold": CLUSTER_THRESHOLD,
                "per_model": ergebnis,
                "paired": vergleich,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nGespeichert: {out_file}")
