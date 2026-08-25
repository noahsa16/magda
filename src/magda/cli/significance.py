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

from magda.config import DATA_DIR, EVAL_DIR, VARIANTS, WORDS_DIR, labeled_dir
from magda.dataset import get_or_create_splits, load_labeled_pages
from magda.dedupe import group
from magda.significance import bootstrap_f1, paired_bootstrap

CLUSTER_THRESHOLD = 0.7


def shared_test_pages(
    a: dict[str, list[str]], b: dict[str, list[str]], test: set[str],
) -> tuple[list[str], int]:
    """Seiten, die beide Modelle vorhergesagt haben *und* im Testsplit liegen.

    Die blosse Schnittmenge der beiden Ordner reicht nicht. `data/predictions/`
    ist ein Archiv, kein Abbild des aktuellen Splits: Ein Ordner behaelt die
    Vorhersagen frueherer Laeufe, und nach einem neuen Split sind deren Seiten
    womoeglich Trainingsdaten.

    Belegter Fall (25.08.2026): nach dem Wechsel der Testwoche von KW32 auf
    KW35 lagen in `gbert` noch 101 und in `layoutxlm` noch 100 Seiten des
    Vorlaufs. Die Schnittmenge war 216 statt 116, und 100 davon hatte das
    Modell inzwischen im Training gesehen. Der Bootstrap haette daraus ein
    Konfidenzintervall gebaut, ohne dass irgendetwas darauf hingewiesen
    haette - die Zahl waere schlicht zu gut gewesen.

    Gibt die genommenen Seiten und die Zahl der verworfenen zurueck; das
    Verwerfen gehoert in die Ausgabe, nicht in die Stille.
    """
    gemeinsam = set(a) & set(b)
    genommen = sorted(gemeinsam & test)
    return genommen, len(gemeinsam) - len(genommen)


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
    """Duplikat-Cluster als Positionen in `page_ids`.

    Fehlt auch nur eine Wortliste, wird abgebrochen statt geschätzt. Der
    frühere Fallback fasste die fehlenden Seiten zu einem Sammel-Cluster
    zusammen – und lief auf einer Maschine ohne `data/words` (etwa dem
    Trainings-Bundle) klaglos mit *einem* Cluster über alle 100 Seiten durch.
    Das Ergebnis war ein Intervall der Breite null und p = 0.0, also die
    Optik eines hochsignifikanten Befunds an genau der Stelle, an der die
    Unsicherheit herkommen soll.
    """
    words, missing = {}, []
    for pid in page_ids:
        path = WORDS_DIR / f"{pid}.json"
        if path.exists():
            words[pid] = [w["text"] for w in json.loads(path.read_text())["words"]]
        else:
            missing.append(pid)
    if missing:
        sys.exit(
            f"{len(missing)} von {len(page_ids)} Wortlisten fehlen unter {WORDS_DIR} "
            f"(z. B. {', '.join(missing[:3])}). Ohne sie lassen sich die "
            f"Duplikat-Cluster nicht bilden, und über Seiten statt Cluster "
            f"gezogen wäre das Konfidenzintervall zu eng.\n"
            f"Diesen Schritt dort laufen lassen, wo data/words vollständig ist."
        )
    position = {pid: i for i, pid in enumerate(page_ids)}
    clusters = [[position[p] for p in c] for c in group(words, threshold=CLUSTER_THRESHOLD)]
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

    # Gegen den Split, nicht gegen die blosse Schnittmenge der Ordner: siehe
    # shared_test_pages.
    splits = get_or_create_splits(load_labeled_pages(args.labels_from))
    shared, verworfen = shared_test_pages(
        predictions[a], predictions[b], set(splits["test"]))
    if not shared:
        sys.exit(
            f"Keine gemeinsame Seite von {a} und {b} liegt im Testsplit. "
            f"Erst `magda predict <variante> --split test` laufen lassen."
        )
    if verworfen:
        print(f"{verworfen} gemeinsame Seiten liegen ausserhalb des Testsplits "
              f"und bleiben draussen (Vorhersagen frueherer Laeufe).")

    reference = []
    for pid in shared:
        path = labeled_dir(args.labels_from) / f"{pid}.json"
        if not path.exists():
            sys.exit(f"Referenz fehlt: {path}")
        reference.append(json.loads(path.read_text())["tags"])

    clusters = test_clusters(shared)
    print(f"{len(shared)} Seiten in {len(clusters)} Clustern "
          f"(Jaccard {CLUSTER_THRESHOLD}), {args.resamples} Resamples.\n")

    result = {}
    for name in (a, b):
        tags = [predictions[name][pid] for pid in shared]
        result[name] = bootstrap_f1(reference, tags, clusters, args.resamples)
        r = result[name]
        print(f"{name:<12} F1 {r['f1']:.4f}  95%-KI [{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}]")

    comparison = paired_bootstrap(
        reference,
        [predictions[a][pid] for pid in shared],
        [predictions[b][pid] for pid in shared],
        clusters,
        args.resamples,
    )
    print(f"\n{a} − {b}: {comparison['difference']:+.4f}  "
          f"95%-KI [{comparison['ci95'][0]:+.4f}, {comparison['ci95'][1]:+.4f}]  "
          f"p = {comparison['p_value']:.4f}")
    if comparison["significant"]:
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
                "pages": len(shared),
                "clusters": len(clusters),
                "cluster_threshold": CLUSTER_THRESHOLD,
                "per_model": result,
                "paired": comparison,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nGespeichert: {out_file}")
