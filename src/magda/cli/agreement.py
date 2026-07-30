"""Vergleichsschritt: wo widersprechen sich zwei Labeling-Modelle?

    magda agreement qwen3.5-397b-a17b mistral-medium-3.5-128b
    magda agreement a b --top 40      # längere Annotationsliste

Der Gold-Vergleich (Schritt 08) misst gegen drei handannotierte Seiten. Das
ist die verlässlichste Zahl, aber eine schmale. Die Übereinstimmung zweier
Modelle lässt sich dagegen auf allen Seiten messen, ohne eine einzige davon
zu annotieren – und die uneinigsten Seiten sind genau die, deren Handarbeit
am meisten brächte.

Wichtig beim Berichten: Übereinstimmung ist keine Richtigkeit. Zwei Modelle
können sich einig und gemeinsam irren.
"""

import argparse
import json
import sys

from magda import agreement
from magda.config import EVAL_DIR, labeled_models


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_a", help="Erstes Modell (Ordner unter data/labeled/).")
    parser.add_argument("model_b", help="Zweites Modell.")
    parser.add_argument("--top", type=int, default=20, help="Wie viele Seiten auflisten.")
    args = parser.parse_args(argv)

    known = labeled_models()
    for model in (args.model_a, args.model_b):
        if model not in known:
            sys.exit(f"Keine Labels für {model}. Vorhanden: {', '.join(known) or 'nichts'}")

    result = agreement.compare_models(args.model_a, args.model_b)
    if not result["pages_compared"]:
        sys.exit("Keine gemeinsam gelabelte Seite – nichts zu vergleichen.")

    print(f"{args.model_a}  gegen  {args.model_b}")
    print(f"{result['pages_compared']} gemeinsame Seiten, "
          f"Übereinstimmung {result['agreement']:.1%}")
    if result["skipped"]:
        print(f"  übersprungen (Wortlisten passen nicht): {len(result['skipped'])}")

    print("\nEinigkeit je Label:")
    for entity, score in sorted(agreement.label_agreement(args.model_a, args.model_b).items(),
                                key=lambda kv: kv[1]):
        print(f"  {entity:<12}{score:6.1%}")

    if result["confusion"]:
        print("\nVerwechslungen (beide labeln, aber verschieden):")
        for type_a, others in sorted(result["confusion"].items()):
            for type_b, count in sorted(others.items(), key=lambda kv: -kv[1]):
                print(f"  {type_a:<12} -> {type_b:<12}{count:>5}")

    if result["only_a"] or result["only_b"]:
        print("\nNur ein Modell vergibt ein Label:")
        for label, counts in (("nur " + args.model_a, result["only_a"]),
                              ("nur " + args.model_b, result["only_b"])):
            if counts:
                items = ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
                print(f"  {label}: {items}")

    print(f"\nUneinigste Seiten – hier lohnt Handannotation am meisten:")
    print(f"{'Seite':<20}{'Wörter':>8}{'Konflikte':>11}{'Einigkeit':>11}")
    for page in result["pages"][: args.top]:
        print(f"{page['page_id']:<20}{page['words']:>8}{page['conflicts']:>11}"
              f"{page['agreement']:>10.1%}")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_file = EVAL_DIR / f"agreement_{args.model_a}_{args.model_b}.json"
    with open(out_file, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nReport geschrieben: {out_file}")
    print("Achtung beim Zitieren: Übereinstimmung ist keine Richtigkeit. Zwei "
          "Modelle können sich einig und gemeinsam irren.")

