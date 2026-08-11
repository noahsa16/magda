"""Ein Paarmodell auf einer vorhandenen Gruppierung trainieren und messen.

Aufruf:
    magda offers-model train                       # lernt auf den Train-Seiten
    magda offers-model eval                        # misst auf den Dev-Seiten
    magda offers-model eval --splits dev --threshold 0.6
    magda offers-model predict --splits dev        # Gruppierung als Dateien ablegen

Gelernt wird aus `data/offer_groups/<quelle>/`, und das faerbt ab: Ein
Schueler kann nicht besser werden als der Lehrer, aus dem er lernt - wie
GBERT an der Konsistenzgrenze von sonnet-5 haengt. Die Herkunft steht
deshalb im Checkpoint und in jedem Report.

**Zwei Zahlen, die verschiedene Fragen beantworten.** `offers-gold` misst
die *Uebereinstimmung* mit dem Lehrer - dieselbe Quelle wie das Training,
nur andere Seiten. `offers-verify` rechnet Menge x Grundpreis nach und ist
die einzige Instanz, die weder am Training noch am Lehrer beteiligt war.
Deshalb steht die Rechnung auch nicht unter den Merkmalen; Begruendung in
`offer_pairs`.

Trainings- und Messseiten kommen aus `data/splits/split.json`, nicht aus
einer eigenen Aufteilung. Der Testsplit ist auch hier zum Messen am Ende da.
"""

import argparse
import json

from magda import config, offer_teacher, offers_gold
from magda.cli.offers import _load_labeled_pages, _load_predicted_pages

SPLIT_FILE = config.DATA_DIR / "splits" / "split.json"
DEFAULT_CHECKPOINT = config.PROJECT_ROOT / "checkpoints" / "offer_pairs" / "model.pt"


def _split_ids(names: list[str], parser) -> set[str]:
    if not SPLIT_FILE.is_file():
        parser.exit(1, f"{SPLIT_FILE} fehlt. Erst `magda split` laufen lassen.\n")
    with open(SPLIT_FILE) as f:
        split = json.load(f)
    unknown = [n for n in names if n not in split]
    if unknown:
        parser.error(f"Unbekannte Splits: {', '.join(unknown)}. Bekannt: {', '.join(sorted(split))}")
    return {page_id for name in names for page_id in split[name]}


def _pages(args, parser):
    if args.predictions:
        return args.predictions, _load_predicted_pages(args.predictions)
    source = args.labels_from or config.default_labeled_model()
    if source is None:
        parser.exit(1, "Keine Labelquelle gefunden. Erst `magda label` laufen lassen.\n")
    if not config.labeled_dir(source).is_dir():
        parser.error(f"Labelquelle nicht gefunden: {source}")
    return source, _load_labeled_pages(source)


def _selected(args, parser):
    """Seiten des gewaehlten Splits, fuer die auch eine Gruppierung vorliegt."""
    source, pages = _pages(args, parser)
    reference = offers_gold.load_reference(offer_teacher.teacher_dir(args.reference_from))
    if not reference.assignments:
        parser.exit(1, f"Keine Gruppierung unter data/offer_groups/"
                       f"{config.model_slug(args.reference_from)}.\n")
    wanted = _split_ids([s.strip() for s in args.splits.split(",") if s.strip()], parser)
    selected = [p for p in pages
                if p.get("page_id") in wanted and p.get("page_id") in reference.assignments]
    if not selected:
        parser.exit(1, f"Keine Seite aus {args.splits} ist gruppiert. "
                       "`magda offers-teacher pages` sagt, was fehlt.\n")
    return source, selected, reference


def _cmd_train(args, parser):
    from magda import offer_model

    source, pages, reference = _selected(args, parser)
    stats = offer_model.training_stats(pages, reference.assignments)
    hidden = tuple(int(h) for h in args.hidden.split(","))
    decoder = args.decoder or "union"

    calibration = None
    if args.folds > 1:
        calibration = offer_model.calibrate(
            pages, reference.assignments, folds=args.folds,
            epochs=args.epochs, seed=args.seed, hidden=hidden,
            objective=args.objective, decoder=decoder,
        )

    model = offer_model.train(
        pages, reference.assignments, epochs=args.epochs, seed=args.seed,
        hidden=hidden, decoder=decoder,
        provenance={
            "reference": args.reference_from,
            "kind": sorted(set(reference.provenance.values())),
            "labels": source,
            "splits": args.splits,
            "pages": stats["pages"],
            "decoder": decoder,
        },
    )
    if calibration:
        model.threshold = calibration["threshold"]
    path = model.save(args.out)

    print(f"Lehrer: data/offer_groups/{config.model_slug(args.reference_from)}"
          f"   Labels: {source}   Splits: {args.splits}   Dekoder: {decoder}")
    if "llm" in set(reference.provenance.values()):
        print("  Maschinell erzeugte Gruppierung: das Modell lernt Uebereinstimmung,")
        print("  nicht Richtigkeit. Gegenprobe: `magda offers-model eval`.")
    print()
    print(f"  Seiten            {stats['pages']}")
    print(f"  Paare             {stats['pairs']}")
    print(f"    zusammen        {stats['positive']}")
    print(f"    getrennt        {stats['negative']}")
    print(f"    ohne Urteil     {stats['skipped']}   (Referenz schweigt, kein Negativbeispiel)")
    print()
    if calibration:
        curve_path = config.EVAL_DIR / "offers_model_calibration.json"
        config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
        with open(curve_path, "w") as f:
            json.dump({"source": source, "splits": args.splits, "folds": args.folds,
                       "hidden": list(hidden), "epochs": args.epochs,
                       **calibration}, f, indent=2, ensure_ascii=False)

        print(f"Schwelle out-of-fold ueber {calibration['pages']} Seiten "
              f"(Kriterium {calibration['objective']}): {calibration['threshold']}")
        print()
        print(f"  {'Kriterium':<12} {'Schwelle':>9} {'Paar-F1':>9} {'Gruppen-F1':>11} {'Angebote':>9}")
        for name, row in (("Paar-F1", calibration["best_pair_f1"]),
                          ("Gruppen-F1", calibration["best_group_f1"])):
            print(f"  {name:<12} {row['threshold']:>9} {(row['pair_f1'] or 0):>9.3f} "
                  f"{(row['group_f1'] or 0):>11.3f} {row['groups']:>9}")
        print(f"  {'Referenz':<12} {'':>9} {'':>9} {'':>11} "
              f"{calibration['best_pair_f1']['reference_groups']:>9}")
        print()
        print("  Die beiden Kriterien waehlen verschiedene Schwellen. Paar-F1 belohnt")
        print("  Vorsicht, Gruppen-F1 verlangt das ganze Angebot - welche Zahl das")
        print("  Projekt tragen soll, ist eine Teamentscheidung.")
        print(f"  Kurve: {curve_path}")
    else:
        print(f"Nicht kalibriert (--folds {args.folds}), Schwelle bleibt {model.threshold}")
    print()
    print(f"Checkpoint: {path}")


def _cmd_eval(args, parser):
    from magda import offer_model, offers_verify
    from magda.offers import cluster_page

    source, pages, reference = _selected(args, parser)
    model = offer_model.load(args.checkpoint)
    # Ohne Angabe die Schwelle des Checkpoints: sie wurde out-of-fold
    # gewaehlt und gehoert zum Modell. Wer sie hier neu setzt, misst nicht
    # mehr das System, das trainiert wurde. Fuer den Dekoder gilt dasselbe,
    # und zwar staerker: Die Schwelle wurde *fuer ihn* gewaehlt.
    threshold = args.threshold if args.threshold is not None else model.threshold
    if args.decoder:
        model.decoder = args.decoder

    def grouping(page):
        return offers_gold.offers_from_reference(page, _assignment(model, page, threshold))

    agreement = offers_gold.collect(pages, reference, grouping=grouping)
    verdict = offers_verify.collect(
        pages, {p["page_id"]: _assignment(model, p, threshold) for p in pages}
    )
    heuristic = offers_gold.collect(pages, reference)
    # Dieselbe Gegenprobe fuer die Heuristik, sonst stuende die Genauigkeit
    # des Modells ohne Massstab da. Achtung beim Lesen: `cluster_page` ordnet
    # teilweise selbst arithmetisch zu, ihre Zahl ist also *nicht* die eines
    # unbeteiligten Richters - dafuer gibt es `magda offers-report`.
    heuristic_verdict = offers_verify.collect(pages, {
        p["page_id"]: {word: index
                       for index, offer in enumerate(cluster_page(p))
                       for entity in offer.entities
                       for word in range(entity.start, entity.end)}
        for p in pages
    })

    payload = {
        "source": source,
        "reference": f"data/offer_groups/{config.model_slug(args.reference_from)}",
        "provenance": sorted(set(reference.provenance.values())),
        "splits": args.splits,
        "threshold": threshold,
        "decoder": model.decoder,
        "checkpoint": str(args.checkpoint),
        "model_provenance": model.provenance,
        "agreement": agreement.to_dict(),
        "heuristic": heuristic.to_dict(),
        "arithmetic": verdict.to_dict(),
        "arithmetic_heuristic": heuristic_verdict.to_dict(),
    }
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "" if model.decoder == "union" else f"_{model.decoder}"
    out_path = config.EVAL_DIR / (
        f"offers_model_{args.splits.replace(',', '-')}{suffix}.json")
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    def _rate(value):
        return "nicht messbar" if value is None else f"{value:.3f}"

    print(f"Splits: {args.splits}   Seiten: {agreement.pages}   "
          f"Schwelle: {threshold}   Dekoder: {model.decoder}")
    print(f"Lehrer: data/offer_groups/{config.model_slug(args.reference_from)}")
    print()
    print("Uebereinstimmung mit dem Lehrer (andere Seiten als im Training):")
    print(f"  {'':<12} {'Paar-F1':>10} {'Gruppen-F1':>12} {'Angebote':>10}")
    print(f"  {'Paarmodell':<12} {_rate(agreement.pair_f1):>10} "
          f"{_rate(agreement.group_f1):>12} {agreement.sys_groups:>10}")
    print(f"  {'Heuristik':<12} {_rate(heuristic.pair_f1):>10} "
          f"{_rate(heuristic.group_f1):>12} {heuristic.sys_groups:>10}")
    print(f"  {'Lehrer':<12} {'-':>10} {'-':>12} {agreement.ref_groups:>10}")
    print()
    print("Unabhaengige Gegenprobe (Menge x Grundpreis, kein Merkmal des Modells):")
    print(f"  bestaetigt        {verdict.confirmed}")
    print(f"  widerlegt         {verdict.contradicted}")
    print(f"  ohne Treffer      {verdict.unresolved}   (Mehrfachpackung oder fehlendes Label)")
    print(f"  unbeurteilbar     {verdict.unjudgeable}   (kein Grundpreis - meist Non-Food)")
    print(f"  Genauigkeit       {_rate(verdict.accuracy)}   bei Abdeckung {_rate(verdict.coverage)}")
    print(f"  zum Vergleich Heuristik: {_rate(heuristic_verdict.accuracy)} "
          f"bei Abdeckung {_rate(heuristic_verdict.coverage)}")
    print("  (deren Zahl ist milder zu lesen: `cluster_page` ordnet teils selbst")
    print("   arithmetisch zu, der Richter ist dort also nicht unbeteiligt)")
    print()
    print(f"Report: {out_path}")


def _cmd_diagnose(args, parser):
    """Wer deckelt - das Paarmodell oder das Dekodieren?"""
    from magda import offer_grid, offer_model

    source, pages, reference = _selected(args, parser)
    model = offer_model.load(args.checkpoint)
    if args.decoder:
        model.decoder = args.decoder
    result = offer_grid.diagnose(pages, reference.assignments, model)
    result |= {"source": source, "splits": args.splits,
               "reference": config.model_slug(args.reference_from),
               "checkpoint": str(args.checkpoint)}

    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    # Die Entity-Quelle gehoert in den Namen, nicht nur der Dekoder: Der
    # Lehrerlauf und der Vorhersagelauf messen beide `dev` und beantworten
    # verschiedene Fragen. Derselbe Fehler wie einst bei `offers_grid`.
    out_path = config.EVAL_DIR / (
        f"offers_diagnose_{args.splits.replace(',', '-')}"
        f"_{config.model_slug(source)}_{model.decoder}.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Entities: {source}   Splits: {args.splits}   Dekoder: {model.decoder}")
    print(f"{result['pages']} Seiten, {result['pairs']} beurteilbare Paare, "
          f"davon {result['positive']} zusammengehoerig")
    print()
    print(f"  Kantenqualitaet (AUC)        {result['auc']:.3f}")
    print("    Trennschaerfe ohne Schwelle. 0.5 hiesse: die Kanten tragen nichts.")
    print()
    print(f"  erreicht  (Schwelle {result['threshold']:.2f})   {result['achieved']:.3f}")
    print(f"  Obergrenze (Schwelle {result['ceiling_threshold']:.2f})   {result['ceiling']:.3f}")
    print("    Die Obergrenze ist post-hoc auf den Messseiten gewaehlt, also")
    print("    keine erreichbare Leistung - der Abstand ist der Preis der")
    print("    Schwellenwahl, nicht ein Versaeumnis.")
    print()
    print(f"  mit perfekten Kanten         {result['oracle']:.3f}")
    print("    Muss 1.000 sein. Sonst verliert der Dekoder selbst Information,")
    print("    unabhaengig vom Modell - und die Diagnose haette keinen Massstab.")
    print()
    if result["auc"] is not None:
        if result["ceiling"] and result["ceiling"] < 0.8 and result["auc"] > 0.95:
            print("  Lesart: gute Kanten, verlustreiches Dekodieren.")
        elif result["auc"] < 0.9:
            print("  Lesart: die Kanten selbst begrenzen - bessere Merkmale oder")
            print("  eine bessere Referenz, kein anderes Dekodierverfahren.")
    f = result["failures"]
    print()
    print(f"  Verfehlte Gruppen: {f['miss']} von {f['hit'] + f['miss']}")
    for kind, count in sorted(f["kinds"].items(), key=lambda kv: -kv[1]):
        print(f"    {kind:28s} {count:3d}  ({count / f['miss']:.0%})")
    print(f"    Groesse getroffen {f['mean_size_hit']:.2f} Entities, "
          f"verfehlt {f['mean_size_miss']:.2f}")
    print(f"    ohne Grundpreis: {f['blind_share_hit']:.0%} der getroffenen, "
          f"{f['blind_share_miss']:.0%} der verfehlten")
    print("    Zerfall heisst: es fehlen Kanten. Verschmelzung: es sind zu viele.")
    print("    Die Massnahmen sind gegenlaeufig - deshalb die Unterscheidung.")
    print(f"\nReport: {out_path}")


def _assignment(model, page: dict, threshold: float) -> dict[int, int]:
    """Wortindex -> Angebotsnummer, wie das Modell die Seite sieht."""
    return {
        word: group_id
        for group_id, group in enumerate(model.group_page_words(page, threshold))
        for word in group
    }


def _cmd_predict(args, parser):
    from magda import offer_model, offer_pairs

    from_model = offer_model.load(args.checkpoint)
    threshold = args.threshold if args.threshold is not None else from_model.threshold
    if args.decoder:
        from_model.decoder = args.decoder
    _, pages, _ = _selected(args, parser)
    written = 0
    for page in pages:
        groups = from_model.group_page_words(page, threshold)
        offer_teacher.save_grouping(page, groups, source=args.target,
                                    model=str(args.checkpoint),
                                    notes=f"Schwelle {threshold}, "
                                          f"Dekoder {from_model.decoder}, "
                                          f"{len(offer_pairs.FEATURE_NAMES)} Merkmale")
        written += 1
    print(f"{written} Seiten -> data/offer_groups/{config.model_slug(args.target)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    # Als Elternparser statt am Hauptparser: sonst muesste `--labels-from` vor
    # dem Unterbefehl stehen, und genau dort sucht es niemand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--reference-from", dest="reference_from", default="claude-sonnet-5",
                        help="Gruppierung unter data/offer_groups/ als Lehrer")
    common.add_argument("--labels-from", dest="labels_from", default=None,
                        help="Labelordner unter data/labeled/")
    common.add_argument("--predictions", default=None,
                        help="Variante unter data/predictions/ statt data/labeled/")
    common.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT)
    common.add_argument("--decoder", default=None,
                        choices=("union", "ilp"),
                        help="wie aus Kanten Gruppen werden. Ohne Angabe beim Messen\n"
                             "der Dekoder des Checkpoints, beim Training union.\n"
                             "ilp = Correlation Clustering (braucht pulp)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train = subparsers.add_parser("train", help="Paarmodell trainieren", parents=[common])
    train.add_argument("--splits", default="train")
    train.add_argument("--epochs", type=int, default=300)
    train.add_argument("--seed", type=int, default=0)
    train.add_argument("--hidden", default="64,32",
                       help="Groesse der verdeckten Schichten, komma-getrennt")
    train.add_argument("--out", default=DEFAULT_CHECKPOINT)
    train.add_argument("--objective", default="group_f1",
                       choices=("pair_f1", "group_f1"),
                       help="Wonach die Schwelle gewaehlt wird. Default group_f1")
    train.add_argument("--folds", type=int, default=5,
                       help="Folds fuer die Schwellenwahl. 1 schaltet sie ab")

    evaluate = subparsers.add_parser("eval", help="Gegen Lehrer und Arithmetik messen",
                                     parents=[common])
    evaluate.add_argument("--splits", default="dev")
    evaluate.add_argument("--threshold", type=float, default=None,
                          help="Ueberschreibt die kalibrierte Schwelle des Checkpoints")

    diagnose = subparsers.add_parser(
        "diagnose", help="Kantenqualitaet gegen Dekodierverlust trennen",
        parents=[common])
    diagnose.add_argument("--splits", default="dev")

    predict = subparsers.add_parser("predict", help="Gruppierung als Dateien ablegen",
                                    parents=[common])
    predict.add_argument("--splits", default="dev")
    predict.add_argument("--threshold", type=float, default=None)
    predict.add_argument("--target", default="pair-model",
                         help="Zielordner unter data/offer_groups/")

    args = parser.parse_args(argv)
    return {"train": _cmd_train, "eval": _cmd_eval, "predict": _cmd_predict,
            "diagnose": _cmd_diagnose}[args.command](args, parser)
