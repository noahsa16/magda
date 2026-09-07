"""Blackbox gegen eigene Pipeline: Name und Aktionspreis je Preisvariante.

Default: LayoutXLM-Vorhersagen, Paarmodell, menschliche Spans und Gruppen.
Die vollständige angeforderte Gold-Seitenliste muss fertig sein; Teilmessungen
brauchen --allow-partial. --blackbox-from verwendet gespeicherte Antworten
ohne API-Aufruf. Alte Reports bleiben erhalten; das Bewertungsprotokoll v2
trägt einen eigenen Dateinamen. Altpreis und Zusatzfelder werden aufbewahrt,
aber nicht durch den Haupt-F1 bewertet.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from magda import blackbox_eval, config, provenance


def _pdf_path(page_id: str):
    """`1342881_p22` -> data/raw/1342881/bk_22.pdf."""
    catalog, _, page = page_id.rpartition("_p")
    if not catalog or not page.isdigit():
        raise ValueError(f"Unlesbare page_id: {page_id}")
    return config.RAW_DIR / catalog / f"bk_{int(page)}.pdf"


def _offers_of(page: dict, grouper: str, model=None):
    """Angebote einer Seite nach der gewaehlten Gruppierungsmethode.

    "heuristic" ist `offers.cluster_page` - reine Abstands-/Preisregeln,
    kein Training. "pair-model" ist das trainierte Paarmodell samt
    ILP-Dekoder (`checkpoints/offer_pairs/model.pt`).
    """
    if grouper == "heuristic":
        from magda import offers
        return offers.cluster_page(page)

    from magda import offers_gold
    assignment = {
        word: group_id
        for group_id, group in enumerate(model.group_page_words(page, model.threshold))
        for word in group
    }
    return offers_gold.offers_from_reference(page, assignment)


def _deals_by_page(pages: list[dict], grouper: str = "heuristic", model=None) -> dict[str, list[dict]]:
    """Angebote der eigenen Pipeline, auf die gemeinsame Feldmenge projiziert."""
    result: dict[str, list[dict]] = {}
    fragments = 0
    for page in pages:
        deals = []
        for offer in _offers_of(page, grouper, model):
            projected = blackbox_eval.deals_from_offer(offer)
            if not projected:
                fragments += 1
            else:
                deals.extend(projected)
        result[page["page_id"]] = deals
    result["__fragments__"] = fragments  # type: ignore[assignment]
    return result


def _teacher_deals_by_page(pages: list[dict], reference_from: str) -> dict[str, list[dict]]:
    """Angebote aus der tatsaechlichen Teacher-Gruppierung (data/offer_groups/),
    statt aus `cluster_page` auf den Lehrer-Labels neu gebaut.

    Der Unterschied ist real: `cluster_page` auf Lehrer-Labels ist dieselbe
    Heuristik wie auf der eigenen Seite und damit teilweise ein Vergleich der
    Heuristik mit sich selbst (siehe Moduldocstring). data/offer_groups/
    ist die tatsaechlich vom Teacher gebildete Gruppierung.
    """
    from magda import offer_teacher, offers_gold

    reference = offers_gold.load_reference(offer_teacher.teacher_dir(reference_from))
    result: dict[str, list[dict]] = {}
    fragments = 0
    for page in pages:
        assignment = reference.assignments.get(page["page_id"])
        if assignment is None:
            raise ValueError(f"Fertige Teacher-Gruppierung fehlt: {page['page_id']}")
        deals = []
        for offer in offers_gold.offers_from_reference(page, assignment):
            projected = blackbox_eval.deals_from_offer(offer)
            if not projected:
                fragments += 1
            else:
                deals.extend(projected)
        result[page["page_id"]] = deals
    result["__fragments__"] = fragments  # type: ignore[assignment]
    return result


def _gold_deals_by_page(page_ids: list[str]) -> tuple[dict[str, list[dict]], list[str]]:
    """Angebote aus der Handannotation: Spans aus gold/, Gruppen aus gold/offers/.

    Die Entities kommen bewusst aus den Gold-Spans und nicht aus den
    Lehrer-Labels. Sonst waere die Referenz ein Zwitter - richtige Gruppen
    ueber LLM-Entities - und die Zeile "gegen Referenz" misst wieder
    teilweise den Lehrer. Zurueck kommen die Angebote und die Seiten, fuer
    die eine der beiden Haelften fehlt oder nicht fertig ist.
    """
    from magda import gold, offers_gold

    spans_by_page = {p["page_id"]: p for p in gold.load_gold_pages().pages}
    groups = offers_gold.load_reference()
    result: dict[str, list[dict]] = {}
    fragments = 0
    missing: list[str] = []
    for page_id in page_ids:
        page = spans_by_page.get(page_id)
        assignment = groups.assignments.get(page_id)
        if page is None or assignment is None:
            missing.append(page_id)
            continue
        deals = []
        for offer in offers_gold.offers_from_reference(page, assignment):
            projected = blackbox_eval.deals_from_offer(offer)
            if not projected:
                fragments += 1
            else:
                deals.extend(projected)
        result[page_id] = deals
    result["__fragments__"] = fragments  # type: ignore[assignment]
    return result, missing


def _row(title: str, counts: dict) -> str:
    def rate(value):
        return "  -  " if value is None else f"{value:.3f}"
    return (f"  {title:<34} {counts['matched']:>7} {counts['system']:>8} "
            f"{counts['reference']:>9} {rate(counts['precision']):>10} "
            f"{rate(counts['recall']):>8} {rate(counts['f1']):>7}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="magda blackbox-eval",
        description="LLM-Blackbox gegen die eigene Pipeline messen.")
    parser.add_argument("--pages", required=True,
                        help="Datei mit page_ids, eine je Zeile")
    parser.add_argument("--labels-from", default="sonnet-5",
                        help="Labelquelle der Referenzangebote")
    parser.add_argument("--predictions", default="layoutxlm",
                        help="Vorhersagevariante der eigenen Pipeline")
    parser.add_argument("--grouper", default="pair-model",
                        choices=("heuristic", "pair-model"),
                        help="Wie die eigene Seite Entities zu Angeboten gruppiert.\n"
                             "heuristic = offers.cluster_page (untrainiert).\n"
                             "pair-model = trainiertes Paarmodell + ILP-Dekoder (Default)")
    parser.add_argument("--checkpoint", default=None,
                        help="Checkpoint fuer --grouper pair-model "
                             "(Default: checkpoints/offer_pairs/model.pt)")
    parser.add_argument("--reference-groups", default="gold",
                        choices=("heuristic", "teacher", "gold"),
                        help="Wie die Referenzangebote gebildet werden.\n"
                             "heuristic = offers.cluster_page auf den Lehrer-Labels\n"
                             "  (Achtung, das ist dieselbe Heuristik wie\n"
                             "  --grouper heuristic und vergleicht sich teilweise\n"
                             "  selbst, siehe Moduldocstring).\n"
                             "teacher = data/offer_groups/<--reference-from>, die\n"
                             "  tatsaechlich vom Teacher gebildete Gruppierung.\n"
                             "gold = Handannotation (Default; Spans aus gold/, Gruppen aus\n"
                             "  gold/offers/) - die einzige Referenz, die\n"
                             "  Richtigkeit misst; nur fertige Seiten zaehlen")
    parser.add_argument("--reference-from", default="claude-sonnet-5",
                        help="Gruppierung unter data/offer_groups/ fuer "
                             "--reference-groups teacher")
    parser.add_argument("--model", default=config.CHAT_AI_VISION_MODEL,
                        help="Vision-Modell fuer die Blackbox")
    parser.add_argument("--dry-run", action="store_true",
                        help="alles ausser dem LLM-Aufruf")
    parser.add_argument("--blackbox-from", default=None,
                        help="Blackbox-Antworten (`blackbox_deals`) aus einem frueheren\n"
                             "Report unter data/eval/ wiederverwenden statt die API zu\n"
                             "rufen - fuer einen Referenz- oder Grouper-Wechsel ohne\n"
                             "neuen Lauf. --model wird aus dem Report uebernommen.")
    parser.add_argument("--limit", type=int,
                        help="nur die ersten N Seiten (Probelauf)")
    parser.add_argument("--allow-partial", action="store_true",
                        help="Unfertige Gold-Seiten ausdrücklich auslassen (explorative Teilmessung).")
    args = parser.parse_args(argv)

    from magda.cli.evaluate import read_page_ids
    from magda.cli.offers import _load_labeled_pages, _load_predicted_pages

    page_ids = read_page_ids(args.pages)
    requested_pages = list(page_ids)
    if args.limit:
        page_ids = page_ids[:args.limit]

    replay = None
    if args.blackbox_from:
        replay = json.loads(open(args.blackbox_from).read())
        args.model = replay["model"]

    gold_missing: list[str] = []
    gold_reference = None
    if args.reference_groups == "gold":
        gold_reference, gold_missing = _gold_deals_by_page(page_ids)
        if gold_missing and not args.allow_partial:
            parser.exit(1, "Handannotation unvollständig. Alle Seiten brauchen fertige Spans und Gruppen. "
                           "Für eine Teilmessung ausdrücklich --allow-partial setzen.\n")
        page_ids = [p for p in page_ids if p not in set(gold_missing)]
        if not page_ids:
            parser.exit(1, "Keine der Seiten ist in gold/ und gold/offers/ fertig "
                           "annotiert (status: done in beiden). Nichts zu messen.\n")

    wanted = set(page_ids)
    reference_pages = ([] if args.reference_groups == "gold" else
                       [p for p in _load_labeled_pages(args.labels_from) if p.get("page_id") in wanted])
    predicted_pages = [p for p in _load_predicted_pages(args.predictions)
                       if p.get("page_id") in wanted]

    missing = wanted - {p["page_id"] for p in predicted_pages}
    if missing:
        parser.exit(1, f"Fuer {len(missing)} Seite(n) fehlt eine Vorhersage, "
                       f"z. B. {sorted(missing)[0]}. Erst `magda predict "
                       f"{args.predictions}` auf diesen Seiten laufen lassen.\n")

    for page in predicted_pages:
        current = json.loads((config.WORDS_DIR / f"{page['page_id']}.json").read_text())
        if [w["text"] for w in current["words"]] != [w["text"] for w in page["words"]]:
            parser.exit(1, f"Vorhersage passt nicht zur Wortliste: {page['page_id']}.\n")
    if replay is not None:
        attempted = set(replay.get("pages", replay["blackbox_deals"]))
        if wanted - attempted:
            parser.exit(1, "Der gespeicherte Blackbox-Lauf enthält nicht alle angeforderten Seiten.\n")

    grouper_model = None
    if args.grouper == "pair-model":
        from magda import offer_model
        from magda.cli.offers_model import DEFAULT_CHECKPOINT
        grouper_model = offer_model.load(args.checkpoint or DEFAULT_CHECKPOINT)

    if args.reference_groups == "gold":
        reference = gold_reference
    elif args.reference_groups == "teacher":
        reference = _teacher_deals_by_page(reference_pages, args.reference_from)
    else:
        reference = _deals_by_page(reference_pages)
    started = time.perf_counter()
    if wanted - set(reference):
        parser.exit(1, "Referenz fehlt für angeforderte Seiten.\n")
    own = _deals_by_page(predicted_pages, args.grouper, grouper_model)
    own_fragments = own.pop("__fragments__")
    reference_fragments = reference.pop("__fragments__")
    own_seconds = time.perf_counter() - started

    reference_is_llm = args.reference_groups != "gold"
    if args.reference_groups == "gold":
        ref_source = "gold/ + gold/offers/ (Handannotation - die Zahlen messen Richtigkeit)"
    elif args.reference_groups == "teacher":
        ref_source = (f"data/offer_groups/{config.model_slug(args.reference_from)} "
                      f"(LLM-erzeugt - die Zahlen messen Naehe, nicht Richtigkeit)")
    else:
        ref_source = (f"data/labeled/{config.model_slug(args.labels_from)} "
                      f"(cluster_page auf Lehrer-Labels; LLM-erzeugt - die Zahlen "
                      f"messen Naehe, nicht Richtigkeit)")
    print(f"Seiten:     {len(page_ids)}"
          + (f" ({len(gold_missing)} ohne fertige Handannotation ausgelassen)"
             if gold_missing else ""))
    print(f"Referenz:   Angebote aus {ref_source}")
    print(f"Eigene:     data/predictions/{config.model_slug(args.predictions)} "
          f"+ --grouper {args.grouper}, "
          f"{own_fragments} Fragmente ohne Produkt-und-Preis verworfen")
    print()

    blackbox_deals: dict[str, list[dict]] = {}
    blackbox_seconds = 0.0
    errors: list[str] = []
    if args.dry_run:
        print("Probelauf: die Blackbox wird nicht aufgerufen.\n")
    elif replay is not None:
        blackbox_deals = {p: replay["blackbox_deals"][p] for p in page_ids
                          if p in replay["blackbox_deals"]}
        not_replayed = [p for p in page_ids if p not in blackbox_deals]
        if not_replayed:
            errors.append(f"{len(not_replayed)} Seite(n) ohne Blackbox-Antwort im "
                          f"Report, z. B. {not_replayed[0]}")
        blackbox_seconds = None
        errors.extend(error for error in replay.get("errors", [])
                      if any(error.startswith(page_id + ":") for page_id in page_ids))
        print(f"Blackbox-Antworten aus {args.blackbox_from} wiederverwendet "
              f"({len(blackbox_deals)} Seiten, kein API-Aufruf).\n")
    else:
        from magda import blackbox

        client = config.make_llm_client()
        started = time.perf_counter()
        for number, page_id in enumerate(page_ids, 1):
            path = _pdf_path(page_id)
            if not path.is_file():
                errors.append(f"{page_id}: {path} fehlt (data/raw aus dem Drive-Archiv)")
                continue
            try:
                raw = blackbox.extract_deals_from_page_with_retry(
                    path.read_bytes(), client, args.model)
                blackbox_page = [
                    {"name": " ".join(
                        part for part in (deal.get("brand"), deal.get("product")) if part
                     ).strip(),
                     "price": blackbox_eval.parse_price(deal.get("price")),
                     "original_price": blackbox_eval.parse_price(deal.get("old_price")),
                     # Noch nicht Teil des Vergleichs (compare_pages kennt nur
                     # COMMON_FIELDS) - bleiben im Report fuer eine spaetere
                     # arithmetische Gegenprobe erhalten.
                     "quantity": deal.get("quantity"),
                     "unit_price": deal.get("unit_price"),
                     "app_price": blackbox_eval.parse_price(deal.get("app_price")),
                     "discount_pct": deal.get("discount_pct")}
                    for deal in raw if isinstance(deal, dict)
                ]
                blackbox_deals[page_id] = blackbox_page
            except Exception as error:                      # noqa: BLE001
                errors.append(f"{page_id}: {type(error).__name__}: {error}")
            print(f"  {number}/{len(page_ids)} {page_id}"
                  f"  {len(blackbox_deals.get(page_id, [])):>3} Angebote", flush=True)
        blackbox_seconds = time.perf_counter() - started

    raw_blackbox_deals = blackbox_deals
    blackbox_deals = {
        page_id: [deal for deal in deals if deal.get("name") and deal.get("price") is not None]
        for page_id, deals in raw_blackbox_deals.items()
    }
    blackbox_fragments = sum(len(deals) for deals in raw_blackbox_deals.values()) - sum(len(deals) for deals in blackbox_deals.values())

    def paired(a: dict, b: dict) -> dict:
        return blackbox_eval.compare_pages(
            {p: (a.get(p) or [], b.get(p) or []) for p in page_ids})

    if args.dry_run:
        # Bewusst keine Quote: sie waere eine Zahl ueber die uebergebenen
        # Seiten, und die koennen Testseiten sein.
        print(f"Probelauf beendet. {sum(len(v) for v in own.values())} eigene "
              f"und {sum(len(v) for v in reference.values())} Referenzangebote "
              f"gebildet - Verdrahtung steht, keine Quote berechnet.")
        return

    comparisons = {
        "eigene_vs_referenz": paired(own, reference),
        "blackbox_vs_referenz": paired(blackbox_deals, reference),
        "blackbox_vs_eigene": paired(blackbox_deals, own),
    }

    print()
    print(f"  {'Vergleich':<34} {'Treffer':>7} {'System':>8} "
          f"{'Referenz':>9} {'Praezis.':>10} {'Recall':>8} {'F1':>7}")
    titles = {"eigene_vs_referenz": "eigene Pipeline gegen Referenz",
              "blackbox_vs_referenz": "Blackbox gegen Referenz",
              "blackbox_vs_eigene": "Blackbox gegen eigene Pipeline"}
    for key, counts in comparisons.items():
        print(_row(titles[key], counts))

    print()
    print(f"  eigene Pipeline: {own_seconds / max(len(page_ids), 1):.3f} s je Seite "
          f"(Gruppierung, ohne Modellinferenz)")
    if blackbox_deals and replay is None:
        print(f"  Blackbox:        {blackbox_seconds / max(len(page_ids), 1):.1f} s je Seite")
    elif blackbox_deals:
        print("  Blackbox:        Replay ohne API-Aufruf; keine neue Laufzeitmessung")
    for line in errors:
        print(f"  ! {line}")

    payload = {
        "evaluation_version": blackbox_eval.EVALUATION_VERSION,
        "matching_fields": list(blackbox_eval.COMMON_FIELDS),
        "name_similarity": blackbox_eval.NAME_SIMILARITY,
        "price_tolerance": 0.0,
        "requested_pages": requested_pages,
        "pages": page_ids,
        "model": args.model,
        "prompt_version": (replay.get("prompt_version") if replay is not None
                           else None if args.dry_run else blackbox.PROMPT_VERSION),
        "blackbox_from": args.blackbox_from,
        "replay_sha256": provenance.file_digest(Path(args.blackbox_from)) if replay is not None else None,
        "labels_from": config.model_slug(args.labels_from),
        "predictions": config.model_slug(args.predictions),
        "grouper": args.grouper,
        "reference_groups": args.reference_groups,
        "reference_from": config.model_slug(args.reference_from)
                          if args.reference_groups == "teacher" else None,
        "reference_is_llm": reference_is_llm,
        "gold_missing": gold_missing,
        "own_fragments": own_fragments,
        "reference_fragments": reference_fragments,
        "own_deals": own,
        "reference_deals": reference,
        "reference_sha256": provenance.digest(reference),
        "prediction_sha256": provenance.prediction_identity(
            config.DATA_DIR / "predictions" / config.model_slug(args.predictions), page_ids),
        "checkpoint_sha256": provenance.checkpoint_digest(
            Path(args.checkpoint or DEFAULT_CHECKPOINT)) if grouper_model else None,
        "code": provenance.code_version(),
        "seconds": {"own_grouping": round(own_seconds, 3),
                    "blackbox": round(blackbox_seconds, 1) if blackbox_seconds is not None else None},
        "comparisons": comparisons,
        "blackbox_deals": raw_blackbox_deals,
        "blackbox_fragments": blackbox_fragments,
        "errors": errors,
    }
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    # Modell, Grouper und Referenzquelle gehoeren alle in den Dateinamen wie
    # ueberall sonst im Projekt (offers_model_*, offers_variants_*, ...):
    # ohne das ueberschreibt ein zweiter Lauf mit anderem --grouper oder
    # --reference-groups den vorigen Report still, obwohl er eine andere
    # Frage beantwortet.
    suffix = f"_{args.grouper}" if args.grouper != "heuristic" else ""
    suffix += f"_ref-{args.reference_groups}" if args.reference_groups != "heuristic" else ""
    out_path = config.EVAL_DIR / f"blackbox_test_{config.model_slug(args.model)}{suffix}_{blackbox_eval.EVALUATION_VERSION}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nReport: {out_path}")
