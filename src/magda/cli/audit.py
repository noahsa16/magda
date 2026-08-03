"""Kandidaten für die Handprüfung eines Labels sammeln.

    magda audit APP_PRICE --labels-from sonnet-5

Schreibt `data/audit/<label>.json`: alle Spans mit diesem Label plus die, die
es farblich tragen müssten, aber nicht haben. Geurteilt wird danach in der
Oberfläche unter /audit, nicht hier – die Farbe sortiert vor, ein Mensch
entscheidet.

Der Schritt ist eigenständig, weil er 296 Seitenbilder öffnet. Aus einem
API-Request heraus wäre das eine Wartezeit von Sekunden bei jedem Aufruf;
so liegt das Ergebnis auf der Platte wie bei jedem anderen Pipeline-Schritt.

Bereits gefällte Urteile bleiben beim erneuten Sammeln erhalten, solange der
Span an derselben Wortposition steht. Sonst wäre ein zweiter Lauf das Ende
jeder angefangenen Durchsicht.
"""

import argparse
import sys

from magda import config
from magda.label_audit import collect, load_audit, save_audit, summarize
from magda.labels import ENTITY_TYPES


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("label", help="Entity-Typ, z. B. APP_PRICE")
    parser.add_argument(
        "--labels-from",
        help="Modellordner unter data/labeled/. Ohne Angabe der größte.",
    )
    parser.add_argument(
        "--siblings",
        nargs="*",
        default=["PRICE", "OLD_PRICE"],
        help="Labels, mit denen verwechselt werden kann (Vorschlagsquelle).",
    )
    args = parser.parse_args(argv)

    label = args.label.upper()
    if label not in ENTITY_TYPES:
        sys.exit(f"Unbekanntes Label '{label}'. Bekannt: {', '.join(ENTITY_TYPES)}")

    model = args.labels_from or config.default_labeled_model()
    if not config.labeled_dir(model).is_dir():
        sys.exit(f"Keine Labels unter {config.labeled_dir(model)}.")

    print(f"Sammle '{label}' aus data/labeled/{config.model_slug(model)} …")
    candidates = collect(label, model, tuple(args.siblings))

    previous = load_audit(label)
    data = {
        "label": label,
        "labels_from": model,
        "candidates": candidates,
        # Urteile überleben ein erneutes Sammeln, sofern der Span noch da ist.
        "verdicts": {
            key: verdict
            for key, verdict in previous.get("verdicts", {}).items()
            if any(c["key"] == key for c in candidates)
        },
    }
    path = save_audit(data)

    counts = summarize(data)
    dropped = len(previous.get("verdicts", {})) - len(data["verdicts"])
    print(f"{counts['total']} Kandidaten: {counts['labeled']} tragen '{label}', "
          f"{counts['candidate']} sitzen auf passendem Grund ohne es.")
    if counts["judged"]:
        print(f"Bereits beurteilt: {counts['judged']}"
              + (f" ({dropped} Urteile ohne Span verworfen)" if dropped else ""))
    print(f"Gespeichert: {path}")
    print("Durchsehen unter /audit in der Oberfläche (magda serve --frontend).")


if __name__ == "__main__":
    main()
