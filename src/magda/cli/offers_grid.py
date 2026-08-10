"""Misst die Merkmalsbloecke des Paarmodells einzeln - Basis, Geometrie, Farbe.

Das Gitter beantwortet die Frage, die eine Gesamtzahl offen laesst: Wirkt
ein Merkmal dort, wo es gebaut wurde? Farbmerkmale sind fuer den blinden
Fleck gedacht - Non-Food ohne Grundpreis, wo die Arithmetik schweigt.
Deshalb wird jede Variante zusaetzlich getrennt nach blinden und
prueffbaren Paaren ausgewiesen, mit Cluster-Bootstrap.
"""

from __future__ import annotations

import argparse
import json
import time

from magda import config, offer_teacher, offers_gold
from magda.cli.offers_model import _selected


def _rate(value) -> str:
    return "  -  " if value is None else f"{value:.3f}"


def _interval(bounds) -> str:
    if bounds.get("low") is None:
        return ""
    return f"[{bounds['low']:.3f}, {bounds['high']:.3f}]"


def main(argv=None):
    from magda import offer_grid, offer_model

    parser = argparse.ArgumentParser(
        prog="magda offers-grid",
        description="Merkmalsbloecke des Paarmodells einzeln messen.",
    )
    parser.add_argument("--labels-from", help="Labelquelle, sonst die groesste")
    parser.add_argument("--predictions", help="statt Labels die Vorhersagen einer Variante")
    parser.add_argument("--reference-from", default="claude-sonnet-5",
                        help="Gruppierungsreferenz unter data/offer_groups/")
    parser.add_argument("--train-splits", default="train",
                        help="worauf trainiert und kalibriert wird")
    parser.add_argument("--splits", default="dev", help="worauf gemessen wird")
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--objective", default="group_f1",
                        choices=("pair_f1", "group_f1"),
                        help="Kriterium der Schwellenkalibrierung")
    parser.add_argument("--variants", default=",".join(offer_grid.VARIANTS),
                        help="Teilmenge der Varianten, kommagetrennt")
    args = parser.parse_args(argv)

    wanted = [v.strip() for v in args.variants.split(",") if v.strip()]
    unknown = [v for v in wanted if v not in offer_grid.VARIANTS]
    if unknown:
        parser.error(f"Unbekannte Variante(n): {', '.join(unknown)}. "
                     f"Bekannt: {', '.join(offer_grid.VARIANTS)}")

    # Erst die Messseiten (setzt args.splits voraus), dann die Trainingsseiten.
    source, eval_pages, reference = _selected(args, parser)
    train_args = argparse.Namespace(**{**vars(args), "splits": args.train_splits})
    _, train_pages, _ = _selected(train_args, parser)

    assignments = reference.assignments
    clusters = offer_grid.clusters_of(eval_pages)
    print(f"Labelquelle: {source}")
    print(f"Referenz:    data/offer_groups/{config.model_slug(args.reference_from)}"
          f"  ({', '.join(sorted(set(reference.provenance.values())))})")
    print(f"Training:    {args.train_splits}, {len(train_pages)} Seiten")
    print(f"Messung:     {args.splits}, {len(eval_pages)} Seiten "
          f"in {len(clusters)} Duplikat-Clustern")
    print()

    results: dict[str, dict] = {}
    for name in wanted:
        blocks = offer_grid.VARIANTS[name]
        started = time.perf_counter()
        calibration = offer_model.calibrate(
            train_pages, assignments, folds=args.folds, epochs=args.epochs,
            seed=args.seed, objective=args.objective, blocks=blocks)
        threshold = calibration["threshold"]
        model = offer_model.train(
            train_pages, assignments, epochs=args.epochs, seed=args.seed,
            blocks=blocks,
            provenance={"reference": args.reference_from, "labels": source,
                        "splits": args.train_splits, "pages": len(train_pages),
                        "blocks": list(blocks)})
        model.threshold = threshold

        per_page = [
            offer_grid.judge_page(page, assignments[page["page_id"]],
                                  model.group_page_words(page, threshold))
            for page in eval_pages
        ]
        entry = {
            "blocks": list(blocks),
            "features": len(model.feature_names),
            "threshold": threshold,
            "seconds": round(time.perf_counter() - started, 1),
        }
        for scope in ("total", "blind", "checkable"):
            counts = offer_grid.total_of(per_page, scope)
            entry[scope] = counts.to_dict()
            entry[scope]["pair_ci"] = offer_grid.bootstrap(
                per_page, clusters, scope, "pair_f1", seed=args.seed)
            entry[scope]["group_ci"] = offer_grid.bootstrap(
                per_page, clusters, scope, "group_f1", seed=args.seed)
        results[name] = entry
        print(f"  {name:<10} {entry['features']:>3} Merkmale, "
              f"Schwelle {threshold:.2f}, {entry['seconds']:>5.1f} s")

    print()
    header = f"  {'Variante':<10} {'Merkmale':>8} {'Paar-F1':>9} {'Gruppen-F1':>11} {'Angebote':>9}"
    for scope, title in (("total", "Alle Paare"),
                         ("blind", "Blinder Fleck (ohne Grundpreis)"),
                         ("checkable", "Prueffbar (mit Grundpreis)")):
        print(f"{title}:")
        print(header)
        for name in wanted:
            entry = results[name][scope]
            print(f"  {name:<10} {results[name]['features']:>8} "
                  f"{_rate(entry['pair_f1']):>9} {_rate(entry['group_f1']):>11} "
                  f"{entry['sys_groups']:>9}   "
                  f"{_interval(entry['pair_ci'])}")
        print()

    print("Die Intervalle sind 95 % ueber Duplikat-Cluster gebootstrappt, nicht")
    print("ueber Seiten. Ohne Intervall ist eine Differenz keine Behauptung.")

    payload = {
        "source": source,
        "reference": f"data/offer_groups/{config.model_slug(args.reference_from)}",
        "provenance": sorted(set(reference.provenance.values())),
        "train_splits": args.train_splits,
        "splits": args.splits,
        "objective": args.objective,
        "train_pages": len(train_pages),
        "eval_pages": len(eval_pages),
        "eval_clusters": len(clusters),
        "variants": results,
    }
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.EVAL_DIR / f"offers_grid_{args.splits.replace(',', '-')}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nReport: {out_path}")
