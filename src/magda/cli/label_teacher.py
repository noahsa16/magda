"""Seiten von einem Agenten mit Bildzugriff labeln lassen.

Aufruf:
    magda label-teacher pages --limit 20           # was noch fehlt
    magda label-teacher task 1355990_p3            # Prompt und Bildpfad
    magda label-teacher save 1355990_p3 --from antwort.json

Drei Schritte statt einem, aus demselben Grund wie bei `offers-teacher`:
`sonnet-5` ist kein Modell hinter einer API, sondern ein Agent, der das
Seitenbild selbst oeffnet. `magda label` erreicht nur die GWDG-Modelle.

Die Antwortdatei traegt dieselben Spans, die auch die API liefern wuerde:

    [{"start": 12, "end": 14, "label": "PRODUCT"}, ...]

`save` schickt sie durch `trim_spans` und `apply_app_price_rule` - dieselbe
Kette wie `magda label --repair`. Ohne das haette eine neue Woche andere
Konventionen als KW30-32, und der Wochenvergleich waere hin.
"""

import argparse
import json
import sys

from magda import config, label_teacher

WORDS_DIR = config.WORDS_DIR


def _page(page_id: str, parser) -> dict:
    path = WORDS_DIR / f"{page_id}.json"
    if not path.is_file():
        parser.exit(1, f"Seite {page_id} nicht in {WORDS_DIR}.\n")
    with open(path) as f:
        return json.load(f)


def _cmd_pages(args, parser):
    model = args.model
    open_pages = label_teacher.pending(model)
    if args.json:
        print(json.dumps(open_pages[: args.limit] if args.limit else open_pages))
        return
    done = len(list(config.labeled_dir(model).glob("*.json"))) \
        if config.labeled_dir(model).is_dir() else 0
    print(f"Labelordner: {model}   fertig: {done}   offen: {len(open_pages)}")
    for page_id in open_pages[: args.limit] if args.limit else open_pages:
        print(f"  {page_id}")


def _cmd_task(args, parser):
    print(json.dumps(label_teacher.build_task(_page(args.page_id, parser)),
                     indent=2, ensure_ascii=False))


def _cmd_save(args, parser):
    page = _page(args.page_id, parser)
    words = page.get("words") or []

    with open(args.source) as f:
        answer = json.load(f)
    # Sowohl das nackte Array als auch {"spans": [...]} annehmen - beide
    # Formen kommen vor, und daran soll keine Antwort scheitern.
    spans = answer.get("spans") if isinstance(answer, dict) else answer
    if not isinstance(spans, list):
        parser.exit(1, f"{args.source} enthaelt kein Span-Array.\n")

    target = config.labeled_dir(args.model) / f"{args.page_id}.json"
    if target.exists() and not args.force:
        parser.exit(1, f"{target} gibt es schon. --force ueberschreibt.\n")

    kept, rejected = label_teacher.valid_spans(spans, words)
    if rejected:
        print(f"{len(rejected)} von {len(spans)} Spans verworfen:", file=sys.stderr)
        for reason in rejected[:10]:
            print(f"  {reason}", file=sys.stderr)
        if len(rejected) > 10:
            print(f"  ... und {len(rejected) - 10} weitere", file=sys.stderr)
    if not kept:
        parser.exit(1, "Kein einziger Span ist brauchbar - Seite nicht gespeichert.\n")

    tags = label_teacher.finish_spans(kept, words)
    page |= {"tags": tags, "model": args.model, "source": "annotation"}

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.tmp"
    with open(tmp, "w") as f:
        json.dump(page, f, ensure_ascii=False)
    tmp.replace(target)

    tagged = sum(1 for t in tags if t != "O")
    print(f"{target}   {len(kept)} Spans, {tagged}/{len(words)} Woerter getaggt")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="magda label-teacher",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--model", default=config.CANONICAL_LABELS,
                        help="Labelordner unter data/labeled/")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pages = subparsers.add_parser("pages", help="Welche Seiten noch kein Label haben",
                                  parents=[common])
    pages.add_argument("--limit", type=int, default=0)
    pages.add_argument("--json", action="store_true")

    task = subparsers.add_parser("task", help="Prompt und Bildpfad einer Seite",
                                 parents=[common])
    task.add_argument("page_id")

    save = subparsers.add_parser("save", help="Antwort pruefen und ablegen",
                                 parents=[common])
    save.add_argument("page_id")
    save.add_argument("--from", dest="source", required=True)
    save.add_argument("--force", action="store_true",
                      help="vorhandene Seite ueberschreiben")

    args = parser.parse_args(argv)
    return {"pages": _cmd_pages, "task": _cmd_task,
            "save": _cmd_save}[args.command](args, parser)
