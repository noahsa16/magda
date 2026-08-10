"""Die Fehler des Schülers ordnen und je Klasse die Lösbarkeit nennen.

    magda taxonomy --predictions gbert --labels-from sonnet-5 --split dev

Die Häufigkeiten sind das Beiwerk; die Spalte „womit lösbar" ist der Punkt.
Sie trennt behebbare von strukturellen Fehlern und sagt damit, was ein
weiterer Trainingslauf bringen würde und was nicht.

Standard ist **dev**. Der Testsplit wird genau einmal angefasst, gebündelt
am Ende – wer die Taxonomie zwischendurch auf Test rechnet, verbrennt eine
der Berührungen für eine Zahl, die auf Dev dieselbe Aussage trägt.
"""

from __future__ import annotations

import argparse
import json

from magda import config, error_taxonomy


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="magda taxonomy",
        description="Fehlerklassen des Schülers mit Lösbarkeits-Spalte.")
    parser.add_argument("--predictions", default="gbert",
                        help="Vorhersagevariante unter data/predictions/")
    parser.add_argument("--labels-from", default=config.CANONICAL_LABELS,
                        help="Referenzlabels unter data/labeled/")
    parser.add_argument("--split", default="dev", choices=["train", "dev", "test"])
    args = parser.parse_args(argv)

    from magda.cli.offers import _load_labeled_pages, _load_predicted_pages
    from magda.cli.offers_model import SPLIT_FILE

    if args.split == "test":
        print("! Testsplit: gehört in den gebündelten Schlussbatch.\n")

    wanted = set(json.loads(SPLIT_FILE.read_text())[args.split])
    reference = {p["page_id"]: p for p in _load_labeled_pages(args.labels_from)
                 if p["page_id"] in wanted}
    predicted = {p["page_id"]: p for p in _load_predicted_pages(args.predictions)
                 if p["page_id"] in wanted}
    shared = sorted(set(reference) & set(predicted))
    if not shared:
        parser.exit(1, f"Keine Seite aus {args.split} hat Labels *und* "
                       f"Vorhersagen. `magda predict {args.predictions} "
                       f"--split {args.split}` laufen lassen.\n")

    errors: list[dict] = []
    for page_id in shared:
        page = reference[page_id]
        words = [w["text"] for w in page["words"]]
        errors.extend(error_taxonomy.classify_page(
            words, page["tags"], predicted[page_id]["tags"]))

    summary = error_taxonomy.summarize(errors)
    print(f"{len(shared)} Seiten ({args.split}), Vorhersagen von "
          f"{args.predictions}, Referenz {args.labels_from}")
    print(f"{summary['total']} Fehler auf Span-Ebene\n")

    print(f"  {'Klasse':<24}{'Anzahl':>8}{'Anteil':>9}   womit lösbar")
    for name in error_taxonomy.CLASSES:
        entry = summary["classes"][name]
        share = "  -  " if entry["share"] is None else f"{entry['share']:.3f}"
        print(f"  {name:<24}{entry['count']:>8}{share:>9}   {entry['solvability']}")

    if summary["patterns"]:
        print("\n  Belegte Muster hinter den Lehrerlücken:")
        for pattern, count in sorted(summary["patterns"].items(),
                                     key=lambda kv: -kv[1]):
            print(f"    {pattern:<20}{count:>6}")

    print("\n  Fehler je Label (Zeile = Referenzlabel, sonst Vorhersage):")
    spalten = [n[:9] for n in error_taxonomy.CLASSES]
    print("    " + f"{'Label':<12}" + "".join(f"{c:>11}" for c in spalten))
    for label, counts in summary["per_label"].items():
        zeile = "".join(f"{counts.get(n, 0):>11}" for n in error_taxonomy.CLASSES)
        print(f"    {label:<12}{zeile}")

    print("\n  'lehrerluecke' ist konservativ gezählt: sie verlangt ein belegtes")
    print("  Muster im Text, nicht bloß 'die Referenz sagt O'. Die Zahl ist")
    print("  damit eine Untergrenze für den Lehrerfehleranteil.")

    payload = {
        "split": args.split,
        "predictions": config.model_slug(args.predictions),
        "labels_from": config.model_slug(args.labels_from),
        "pages": len(shared),
        "summary": summary,
    }
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.EVAL_DIR / f"error_taxonomy_{args.split}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nReport: {out_path}")
