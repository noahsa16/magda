"""Die LLM-Blackbox gegen die eigene Pipeline stellen - Produkt gegen Produkt.

    magda blackbox-eval --pages data/eval/test_cluster_pages.txt --dry-run
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

`--dry-run` macht alles ausser dem LLM-Aufruf. Damit laesst sich die
Verdrahtung pruefen, ohne Kontingent zu verbrennen - und ohne den Testsplit
anzufassen, denn ohne Blackbox-Antwort entsteht keine Zahl.
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


def _deals_by_page(pages: list[dict]) -> dict[str, list[dict]]:
    """Angebote der eigenen Pipeline, auf die gemeinsame Feldmenge projiziert."""
    from magda import offers

    result: dict[str, list[dict]] = {}
    fragments = 0
    for page in pages:
        deals = []
        for offer in offers.cluster_page(page):
            deal = blackbox_eval.deal_from_offer(offer)
            if deal is None:
                fragments += 1
            else:
                deals.append(deal)
        result[page["page_id"]] = deals
    result["__fragments__"] = fragments  # type: ignore[assignment]
    return result


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
    parser.add_argument("--model", default=config.CHAT_AI_VISION_MODEL,
                        help="Vision-Modell fuer die Blackbox")
    parser.add_argument("--dry-run", action="store_true",
                        help="alles ausser dem LLM-Aufruf")
    parser.add_argument("--limit", type=int,
                        help="nur die ersten N Seiten (Probelauf)")
    args = parser.parse_args(argv)

    from magda.cli.evaluate import read_page_ids
    from magda.cli.offers import _load_labeled_pages, _load_predicted_pages

    page_ids = read_page_ids(args.pages)
    if args.limit:
        page_ids = page_ids[:args.limit]

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

    started = time.perf_counter()
    reference = _deals_by_page(reference_pages)
    own = _deals_by_page(predicted_pages)
    own_fragments = own.pop("__fragments__")
    reference.pop("__fragments__")
    own_seconds = time.perf_counter() - started

    print(f"Seiten:     {len(page_ids)}")
    print(f"Referenz:   Angebote aus data/labeled/{config.model_slug(args.labels_from)} "
          f"(LLM-erzeugt - die Zahlen messen Naehe, nicht Richtigkeit)")
    print(f"Eigene:     data/predictions/{config.model_slug(args.predictions)}, "
          f"{own_fragments} Fragmente ohne Produkt-und-Preis verworfen")
    print()

    blackbox_deals: dict[str, list[dict]] = {}
    blackbox_seconds = 0.0
    errors: list[str] = []
    if args.dry_run:
        print("Probelauf: die Blackbox wird nicht aufgerufen.\n")
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
                raw = blackbox.extract_deals_from_page(
                    path.read_bytes(), client, args.model)
                blackbox_page = [
                    {"name": deal.get("name"),
                     "price": blackbox_eval.parse_price(deal.get("price")),
                     "original_price": blackbox_eval.parse_price(
                         deal.get("original_price"))}
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
    if blackbox_deals:
        print(f"  Blackbox:        {blackbox_seconds / max(len(page_ids), 1):.1f} s je Seite")
    for line in errors:
        print(f"  ! {line}")

    payload = {
        "pages": page_ids,
        "model": args.model,
        "labels_from": config.model_slug(args.labels_from),
        "predictions": config.model_slug(args.predictions),
        "reference_is_llm": True,
        "own_fragments": own_fragments,
        "seconds": {"own_grouping": round(own_seconds, 3),
                    "blackbox": round(blackbox_seconds, 1)},
        "comparisons": comparisons,
        "errors": errors,
    }
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.EVAL_DIR / "blackbox_test.json"
    if args.dry_run:
        print("\nProbelauf - kein Report geschrieben.")
        return
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nReport: {out_path}")
