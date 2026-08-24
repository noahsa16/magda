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


def _fill(entry: dict, per_page, clusters, seed: int) -> dict:
    """Traegt Zaehlungen und Intervalle je Auswertungsbereich ein."""
    from magda import offer_grid

    for scope in ("total", "blind", "checkable"):
        entry[scope] = offer_grid.total_of(per_page, scope).to_dict()
        entry[scope]["pair_ci"] = offer_grid.bootstrap(
            per_page, clusters, scope, "pair_f1", seed=seed)
        entry[scope]["group_ci"] = offer_grid.bootstrap(
            per_page, clusters, scope, "group_f1", seed=seed)
    return entry


def _note_capping(entry: dict, decoder: str) -> dict:
    """Wie oft das ILP nicht optimiert, sondern durchgereicht hat.

    Wo die Kappung greift, *ist* das ILP Union-Find - und zwar an genau der
    Stelle, an der es seinen Vorteil ausspielen sollte. Eine Zahl ohne diese
    Angabe sieht aus wie ein ILP-Ergebnis und ist teilweise keines.
    """
    if decoder != "ilp":
        return entry
    from magda import offer_ilp

    entry["ilp"] = dict(offer_ilp.LAST_RUN)
    return entry


def report_name(args) -> str:
    """Dateiname des Reports - die Entity-Quelle gehoert hinein.

    Der Lehrerlauf und der Vorhersagelauf messen beide `dev` und
    beantworten trotzdem verschiedene Fragen. Unter einem Namen
    ueberschreibt der zweite den ersten, ohne dass jemand es sieht.

    Aus demselben Grund steht der Dekoder im Namen: Ein ILP-Lauf und ein
    Union-Find-Lauf ueber dieselben Seiten sind zwei Messungen, und der
    Vergleich braucht beide nebeneinander.
    """
    suffix = f"_{config.model_slug(args.predictions)}" if args.predictions else ""
    if getattr(args, "cross_validate", False):
        suffix += "_cv"
    decoder = getattr(args, "decoder", "union") or "union"
    if decoder != "union":
        suffix += "_" + decoder.replace(",", "-")
    # Und aus demselben Grund die Lernkurve: ihre Punkte tragen dieselben
    # Variantennamen nicht, sie ist eine andere Messung ueber dieselben
    # Seiten. Ohne das ueberschreibt ein Kurvenlauf den Variantenvergleich.
    if getattr(args, "curve", None):
        suffix += "_curve"
    return f"offers_grid_{args.splits.replace(',', '-')}{suffix}.json"


def train_namespace(args):
    """Argumente fuer die Trainingsseite des Gitters.

    Der Einsatzfall trennt beide Seiten: annotiert ist die Gruppierung ueber
    *Lehrer*-Entities, angewandt wird das Paarmodell auf denen des Schuelers.
    Ohne `--train-labels-from` traineirte ein Vorhersagelauf auf null Seiten,
    denn fuer den Trainingssplit existieren keine Vorhersagen.
    """
    overrides = {"splits": args.train_splits}
    if args.predictions and getattr(args, "train_labels_from", None):
        overrides |= {"predictions": None, "labels_from": args.train_labels_from}
    return argparse.Namespace(**{**vars(args), **overrides})


def main(argv=None):
    from magda import offer_grid, offer_model, offer_pairs

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
    parser.add_argument("--train-labels-from",
                        help="Entity-Quelle fuers Training, wenn --predictions "
                             "nur die Messseite ersetzen soll")
    parser.add_argument("--splits", default="dev", help="worauf gemessen wird")
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--objective", default="group_f1",
                        choices=("pair_f1", "group_f1"),
                        help="Kriterium der Schwellenkalibrierung")
    parser.add_argument("--variants", default=",".join(offer_grid.VARIANTS),
                        help="Teilmenge der Varianten, kommagetrennt")
    parser.add_argument("--cross-validate", action="store_true",
                        help="jede Referenzseite out-of-fold auswerten statt "
                             "nur den Messsplit - mehr unabhaengige Einheiten")
    parser.add_argument("--curve", default=None,
                        help="Lernkurve: Seitengrenzen fuer das Training, "
                             "kommagetrennt, 0 = alle. Beschnitten wird "
                             "clusterweise und nur die Trainingsmenge; "
                             "gemessen wird immer gegen dieselbe Referenz.\n"
                             "Beispiel: --curve 10,20,30,0")
    parser.add_argument("--decoder", default="union",
                        help="wie aus Kanten Gruppen werden, kommagetrennt fuer "
                             "den Vergleich. union = Zusammenhangskomponenten, "
                             "ilp = Correlation Clustering mit Transitivitaet "
                             "(braucht pulp). Mehrere ergeben eine gepaarte "
                             f"Differenz. Bekannt: {', '.join(offer_model.DECODERS)}")
    args = parser.parse_args(argv)

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    unknown = [v for v in variants if v not in offer_grid.VARIANTS]
    if unknown:
        parser.error(f"Unbekannte Variante(n): {', '.join(unknown)}. "
                     f"Bekannt: {', '.join(offer_grid.VARIANTS)}")

    decoders = [d.strip() for d in args.decoder.split(",") if d.strip()]
    unknown = [d for d in decoders if d not in offer_model.DECODERS]
    if unknown:
        parser.error(f"Unbekannte(r) Dekoder: {', '.join(unknown)}. "
                     f"Bekannt: {', '.join(offer_model.DECODERS)}")

    # Dritte Achse: die Lernkurve. `0` heisst "alle Trainingsseiten" und
    # gehoert als Endpunkt dazu - ohne ihn fehlt der Kurve die Referenz,
    # gegen die "saettigt sie?" ueberhaupt beantwortbar ist.
    limits = [int(p) for p in args.curve.split(",") if p.strip()] if args.curve else [0]
    if any(limit < 0 for limit in limits):
        parser.error("--curve nimmt nur nichtnegative Seitenzahlen (0 = alle).")

    # Ein Lauf je Kombination. Alle Achsen in *einem* Lauf, weil der
    # gepaarte Bootstrap die Zaehlungen je Seite braucht - aus zwei
    # Reportdateien laesst er sich nicht nachtraeglich bilden.
    def _label(variant, decoder, limit):
        parts = [variant] if len(variants) > 1 or not args.curve else []
        if len(decoders) > 1:
            parts.append(decoder)
        if args.curve:
            parts.append(f"p{limit}" if limit else "alle")
        return "/".join(parts) or variant

    runs = [(_label(v, d, limit), v, d, limit)
            for limit in limits for v in variants for d in decoders]
    wanted = [label for label, _, _, _ in runs]

    # Erst die Messseiten (setzt args.splits voraus), dann die Trainingsseiten.
    source, eval_pages, reference = _selected(args, parser)
    train_args = train_namespace(args)
    train_source, train_pages, _ = _selected(train_args, parser)

    if args.cross_validate:
        # Ausgewertet wird die *ganze* Referenz, jede Seite aus einem Modell,
        # das sie nicht gesehen hat. Die Trennung Training/Messung wandert
        # damit von den Splits in die Folds.
        seen = {p["page_id"] for p in eval_pages}
        eval_pages = eval_pages + [p for p in train_pages if p["page_id"] not in seen]
        train_pages = eval_pages

    assignments = reference.assignments
    clusters = offer_grid.clusters_of(eval_pages)
    print(f"Entities:    {source}" + ("  (Vorhersagen)" if args.predictions else "  (Labels)"))
    print(f"Referenz:    data/offer_groups/{config.model_slug(args.reference_from)}"
          f"  ({', '.join(sorted(set(reference.provenance.values())))})")
    print(f"Training:    {args.train_splits}, {len(train_pages)} Seiten "
          f"aus {train_source}")
    modus = ("out-of-fold ueber die ganze Referenz"
             if args.cross_validate else f"Split {args.splits}")
    print(f"Messung:     {modus}, {len(eval_pages)} Seiten "
          f"in {len(clusters)} Duplikat-Clustern")
    print()

    results: dict[str, dict] = {}
    counts_by_variant: dict[str, list] = {}
    for label, name, decoder, limit in runs:
        blocks = offer_grid.VARIANTS[name]
        started = time.perf_counter()
        if decoder == "ilp":
            from magda import offer_ilp
            offer_ilp.reset_counters()

        if args.cross_validate:
            per_page, thresholds, trained_on = offer_grid.cross_validate(
                eval_pages, assignments, blocks, folds=args.folds,
                epochs=args.epochs, seed=args.seed, objective=args.objective,
                decoder=decoder, limit=limit)
            entry = {
                "blocks": list(blocks),
                "decoder": decoder,
                "limit": limit,
                "features": len(offer_pairs.feature_names(blocks)),
                "threshold": round(sum(thresholds) / len(thresholds), 3),
                "thresholds_per_fold": thresholds,
                "seconds": round(time.perf_counter() - started, 1),
            }
            # Zum Kurvenpunkt gehoert die Clusterzahl, nicht die Seitenzahl:
            # elf Regionalfassungen einer Vorlage sind eine Beobachtung.
            # Gemittelt ueber die Folds, weil jeder eine eigene innere Menge hat.
            by_id = {p["page_id"]: p for p in eval_pages}
            sizes = [len(ids) for ids in trained_on]
            fold_clusters = [len(offer_grid.clusters_of([by_id[i] for i in ids]))
                             for ids in trained_on]
            entry["train_pages"] = round(sum(sizes) / len(sizes), 1)
            entry["train_clusters"] = round(sum(fold_clusters) / len(fold_clusters), 1)
            _fill(entry, per_page, clusters, args.seed)
            _note_capping(entry, decoder)
            counts_by_variant[label] = per_page
            results[label] = entry
            print(f"  {label:<16} {entry['features']:>3} Merkmale, "
                  f"{entry['train_pages']:>5.1f} Seiten in "
                  f"{entry['train_clusters']:>4.1f} Clustern, "
                  f"Schwellen {thresholds}, {entry['seconds']:>5.1f} s")
            continue

        calibration = offer_model.calibrate(
            train_pages, assignments, folds=args.folds, epochs=args.epochs,
            seed=args.seed, objective=args.objective, blocks=blocks,
            decoder=decoder)
        threshold = calibration["threshold"]
        model = offer_model.train(
            train_pages, assignments, epochs=args.epochs, seed=args.seed,
            blocks=blocks, decoder=decoder,
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
            "decoder": decoder,
            "features": len(model.feature_names),
            "threshold": threshold,
            "seconds": round(time.perf_counter() - started, 1),
        }
        _fill(entry, per_page, clusters, args.seed)
        _note_capping(entry, decoder)
        counts_by_variant[label] = per_page
        results[label] = entry
        print(f"  {label:<16} {entry['features']:>3} Merkmale, "
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

    comparisons: dict[str, dict] = {}
    baseline = wanted[0]
    if len(wanted) > 1:
        print(f"Gepaarte Differenz gegen '{baseline}' (Gruppen-F1, dieselben Seiten):")
        print(f"  {'Variante':<12}{'Differenz':>11}{'Intervall':>20}{'p':>8}   Bereich")
        for scope in ("total", "blind", "checkable"):
            for name in wanted[1:]:
                paired = offer_grid.paired_bootstrap(
                    counts_by_variant[name], counts_by_variant[baseline],
                    clusters, scope, "group_f1", seed=args.seed)
                comparisons[f"{name}_vs_{baseline}_{scope}"] = paired
                if paired["difference"] is None:
                    continue
                spanne = f"[{paired['low']:+.3f}, {paired['high']:+.3f}]"
                print(f"  {name:<12}{paired['difference']:>+11.3f}{spanne:>20}"
                      f"{paired['p_two_sided']:>8.3f}   {scope}")
        print()

    print("Die Intervalle sind 95 % ueber Duplikat-Cluster gebootstrappt, nicht")
    print("ueber Seiten. Ohne Intervall ist eine Differenz keine Behauptung.")
    print("Zwei ueberlappende Einzelintervalle heissen dabei NICHT 'kein")
    print("Unterschied' - dafuer ist die gepaarte Differenz zustaendig.")

    payload = {
        "source": source,
        "source_kind": "predictions" if args.predictions else "labels",
        "train_source": train_source,
        "reference": f"data/offer_groups/{config.model_slug(args.reference_from)}",
        "provenance": sorted(set(reference.provenance.values())),
        "train_splits": args.train_splits,
        "splits": args.splits,
        "cross_validated": bool(args.cross_validate),
        "decoders": decoders,
        "objective": args.objective,
        "train_pages": len(train_pages),
        "eval_pages": len(eval_pages),
        "eval_clusters": len(clusters),
        "variants": results,
        "paired_vs_baseline": comparisons,
    }
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.EVAL_DIR / report_name(args)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nReport: {out_path}")
