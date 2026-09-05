"""Die LLM-Blackbox gegen die eigene Pipeline stellen - Produkt gegen Produkt.

    magda blackbox-eval --pages <dev-liste> --dry-run   # nur Verdrahtung
    magda blackbox-eval --pages data/eval/test_cluster_pages.txt

Der Vergleich ist dreispaltig, weil zwei Zahlen die falsche Frage
beantworten wuerden:

    Blackbox        gegen Referenz
    eigene Pipeline gegen Referenz
    Blackbox        gegen eigene Pipeline

Referenz sind die Angebote, die aus den Lehrer-Labels gebaut werden. Sie ist
**selbst LLM-erzeugt** - die ersten beiden Zeilen messen also Naehe zur
Lehrerausgabe, nicht Richtigkeit, dieselbe Einschraenkung wie bei `magda
agreement`. Die dritte Zeile kommt ohne Referenz aus und ist reine
Uebereinstimmung. Wer eine der Zahlen berichtet, nennt die Einschraenkung
mit, sonst behauptet er mehr als der Aufbau hergibt.

Der eigentliche Nebengewinn ist die **Zeit**: die 170x-Zahl des Projekts
vergleicht bisher Labeling gegen Inferenz, also einen Zwischenschritt gegen
einen anderen. Hier laufen beide Wege bis zum fertigen Angebot.

`--dry-run` macht alles ausser dem LLM-Aufruf und gibt **keine Quoten** aus.
Damit laesst sich die Verdrahtung pruefen, ohne Kontingent zu verbrennen.
Dass der Probelauf schweigt, ist kein Schoenheitsfehler: er rechnet
"eigene Pipeline gegen Referenz" auch ohne die Blackbox, und wer ihn auf
`test_cluster_pages.txt` laufen liesse, haette den Testsplit angefasst,
bevor der Schlussbatch ueberhaupt beginnt.

Was "Referenz" heisst, entscheidet `--reference-groups`. Der Default
`heuristic` bildet `cluster_page`-Angebote aus den Lehrer-Labels - also
**dieselbe Gruppierungsheuristik**, die mit `--grouper heuristic` auch auf
der eigenen Seite laeuft. Die Zeile "eigene gegen Referenz" vergleicht damit
die Heuristik weitgehend mit sich selbst und faellt entsprechend hoch aus.
Gemessen am 03.09.2026 (`scripts/blackbox_decompose.py`): Heuristik gegen
Heuristik-Referenz 0.839, Paarmodell gegen dieselbe Referenz 0.695 - obwohl
das Paarmodell auf dem vollen Testsplit Gruppen-F1 0.778 gegen 0.439
erreicht. Gegen die Teacher-Gruppierung (`--reference-groups teacher`)
dreht sich das Bild: 0.811 gegen 0.708. Wer den Grouper wechselt, muss die
Referenz mitwechseln, sonst misst er die Selbstaehnlichkeit der Heuristik.
Die Blackbox-Antworten liegen als `blackbox_deals` im Report; ein Wechsel
von Grouper oder Referenz braucht deshalb keinen neuen API-Lauf -
`--blackbox-from <report.json>` liest sie wieder ein, statt die API zu rufen.

`--reference-groups gold` ist die einzige Einstellung, bei der die ersten
beiden Zeilen **Richtigkeit** messen statt Naehe zum Lehrer: Entities aus
den handannotierten Spans in `gold/`, Angebote aus `gold/offers/`. Beides
muss fuer eine Seite `status: done` tragen, sonst wird sie nicht gemessen -
eine halb annotierte Seite als leere Referenz zu werten hiesse "alles
falsch" statt "nicht gemessen". Die Seitenliste schrumpft dabei auf die
fertig annotierten Seiten, und der Report nennt, welche fehlen.
"""

from __future__ import annotations

import argparse
import json
import time

from magda import blackbox_eval, config


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
    ILP-Dekoder (`checkpoints/offer_pairs/model.pt`), das schwaechere von
    beiden ist bewusst der Default, um bestehende Laeufe nicht stillschweigend
    zu aendern - fuer die "beste lokale Konfiguration" explizit anfordern.
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
            deal = blackbox_eval.deal_from_offer(offer)
            if deal is None:
                fragments += 1
            else:
                deals.append(deal)
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
            result[page["page_id"]] = []
            continue
        deals = []
        for offer in offers_gold.offers_from_reference(page, assignment):
            deal = blackbox_eval.deal_from_offer(offer)
            if deal is None:
                fragments += 1
            else:
                deals.append(deal)
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
            deal = blackbox_eval.deal_from_offer(offer)
            if deal is None:
                fragments += 1
            else:
                deals.append(deal)
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
    parser.add_argument("--predictions", default="gbert",
                        help="Vorhersagevariante der eigenen Pipeline")
    parser.add_argument("--grouper", default="heuristic",
                        choices=("heuristic", "pair-model"),
                        help="Wie die eigene Seite Entities zu Angeboten gruppiert.\n"
                             "heuristic = offers.cluster_page (Default, ungetraint).\n"
                             "pair-model = trainiertes Paarmodell + ILP-Dekoder")
    parser.add_argument("--checkpoint", default=None,
                        help="Checkpoint fuer --grouper pair-model "
                             "(Default: checkpoints/offer_pairs/model.pt)")
    parser.add_argument("--reference-groups", default="heuristic",
                        choices=("heuristic", "teacher", "gold"),
                        help="Wie die Referenzangebote gebildet werden.\n"
                             "heuristic = offers.cluster_page auf den Lehrer-Labels\n"
                             "  (Default - Achtung, das ist dieselbe Heuristik wie\n"
                             "  --grouper heuristic und vergleicht sich teilweise\n"
                             "  selbst, siehe Moduldocstring).\n"
                             "teacher = data/offer_groups/<--reference-from>, die\n"
                             "  tatsaechlich vom Teacher gebildete Gruppierung.\n"
                             "gold = Handannotation (Spans aus gold/, Gruppen aus\n"
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
    args = parser.parse_args(argv)

    from magda.cli.evaluate import read_page_ids
    from magda.cli.offers import _load_labeled_pages, _load_predicted_pages

    page_ids = read_page_ids(args.pages)
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
        page_ids = [p for p in page_ids if p not in set(gold_missing)]
        if not page_ids:
            parser.exit(1, "Keine der Seiten ist in gold/ und gold/offers/ fertig "
                           "annotiert (status: done in beiden). Nichts zu messen.\n")

    wanted = set(page_ids)
    reference_pages = [p for p in _load_labeled_pages(args.labels_from)
                       if p.get("page_id") in wanted]
    predicted_pages = [p for p in _load_predicted_pages(args.predictions)
                       if p.get("page_id") in wanted]

    missing = wanted - {p["page_id"] for p in predicted_pages}
    if missing:
        parser.exit(1, f"Fuer {len(missing)} Seite(n) fehlt eine Vorhersage, "
                       f"z. B. {sorted(missing)[0]}. Erst `magda predict "
                       f"{args.predictions}` auf diesen Seiten laufen lassen.\n")

    grouper_model = None
    if args.grouper == "pair-model":
        from magda import offer_model
        from magda.cli.offers_model import DEFAULT_CHECKPOINT
        grouper_model = offer_model.load(args.checkpoint or DEFAULT_CHECKPOINT)

    started = time.perf_counter()
    if args.reference_groups == "gold":
        reference = gold_reference
    elif args.reference_groups == "teacher":
        reference = _teacher_deals_by_page(reference_pages, args.reference_from)
    else:
        reference = _deals_by_page(reference_pages)
    own = _deals_by_page(predicted_pages, args.grouper, grouper_model)
    own_fragments = own.pop("__fragments__")
    reference.pop("__fragments__")
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
        blackbox_seconds = replay.get("seconds", {}).get("blackbox", 0.0)
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

    comparisons = {"eigene_vs_referenz": paired(own, reference)}
    if blackbox_deals:
        comparisons["blackbox_vs_referenz"] = paired(blackbox_deals, reference)
        comparisons["blackbox_vs_eigene"] = paired(blackbox_deals, own)

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
        print("  Blackbox:        Zeit aus dem wiederverwendeten Report, nicht neu gemessen")
    for line in errors:
        print(f"  ! {line}")

    payload = {
        "pages": page_ids,
        "model": args.model,
        "prompt_version": (replay.get("prompt_version") if replay is not None
                           else None if args.dry_run else blackbox.PROMPT_VERSION),
        "blackbox_from": args.blackbox_from,
        "labels_from": config.model_slug(args.labels_from),
        "predictions": config.model_slug(args.predictions),
        "grouper": args.grouper,
        "reference_groups": args.reference_groups,
        "reference_from": config.model_slug(args.reference_from)
                          if args.reference_groups == "teacher" else None,
        "reference_is_llm": reference_is_llm,
        "gold_missing": gold_missing,
        "own_fragments": own_fragments,
        "seconds": {"own_grouping": round(own_seconds, 3),
                    "blackbox": round(blackbox_seconds, 1)},
        "comparisons": comparisons,
        "blackbox_deals": blackbox_deals,
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
    out_path = config.EVAL_DIR / f"blackbox_test_{config.model_slug(args.model)}{suffix}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nReport: {out_path}")
