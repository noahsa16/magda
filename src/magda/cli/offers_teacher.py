"""Angebote von einem Vision-Modell gruppieren lassen, Seite fuer Seite.

Aufruf:
    magda offers-teacher pages --limit 40          # was zu tun ist
    magda offers-teacher task 1342815_p21          # die Aufgabe einer Seite
    magda offers-teacher save 1342815_p21 --from antwort.json

Drei Schritte statt einem, weil der Teacher hier kein API-Client ist, sondern
ein Agent mit Bildzugriff: `pages` sagt, welche Seiten drankommen, `task`
liefert die nummerierten Entities samt Pfad zum Seitenbild, `save` nimmt die
Antwort entgegen und validiert sie, bevor sie auf der Platte landet.

Die Antwortdatei nennt *Entity-Nummern* aus `task`, nicht Wortindizes:

    {"groups": [[0, 1, 2], [3, 4, 5]], "notes": "p21: Legende links"}

`save` uebersetzt sie in Wortindizes, lehnt unbekannte und doppelt vergebene
Nummern ab und schreibt nach data/offer_groups/<quelle>/. **Nicht nach
gold/offers/** - was ein Modell erzeugt hat, darf nicht als Handannotation
auftreten, sonst misst die naechste Zahl Uebereinstimmung statt Richtigkeit.
"""

import argparse
import json
from pathlib import Path

from magda import config, offer_teacher, review
from magda.cli.offers import _load_labeled_pages


def _pages(args, parser):
    source = args.labels_from or config.default_labeled_model()
    if source is None:
        parser.exit(1, "Keine Labelquelle gefunden. Erst `magda label` laufen lassen.\n")
    if not config.labeled_dir(source).is_dir():
        parser.error(f"Labelquelle nicht gefunden: {source}")
    return source, _load_labeled_pages(source)


def _one_page(args, parser):
    _, pages = _pages(args, parser)
    for page in pages:
        if page.get("page_id") == args.page_id:
            return page
    parser.exit(1, f"Seite {args.page_id} nicht in der Labelquelle gefunden.\n")


def _cmd_pages(args, parser):
    _, pages = _pages(args, parser)
    done = {f.stem for f in offer_teacher.teacher_dir(args.source).glob("*.json")}
    try:
        queue = review.offer_queue(pages, limit=args.limit, annotated=done)
    except FileNotFoundError as error:
        parser.exit(1, f"{error}\n")

    if args.json:
        print(json.dumps([c["page_id"] for c in queue]))
        return
    print(f"Quelle: {args.source}   schon gruppiert: {len(done)}   offen: {len(queue)}")
    for candidate in queue:
        print(f"  {candidate['page_id']:<16} {candidate['split']:<6} "
              f"{candidate['reason']:<7} Cluster {candidate['cluster_size']:>2}   "
              f"unbeurteilbar {candidate['unjudgeable']}")


def _cmd_task(args, parser):
    page = _one_page(args, parser)
    print(json.dumps(offer_teacher.build_task(page), indent=2, ensure_ascii=False))


def _cmd_save(args, parser):
    page = _one_page(args, parser)
    with open(args.answer) as f:
        answer = json.load(f)
    if not isinstance(answer.get("groups"), list):
        parser.exit(1, 'Die Antwortdatei braucht ein Feld "groups" mit einer Liste von Listen.\n')

    try:
        groups = offer_teacher.expand_entity_groups(page, answer["groups"])
        path = offer_teacher.save_grouping(
            page, groups, source=args.source,
            model=args.model or args.source, notes=answer.get("notes", ""),
        )
    except ValueError as error:
        # Exit-Code 2, damit ein Agent den Unterschied zwischen "kaputte
        # Antwort, nochmal versuchen" und "Datei fehlt" sieht.
        parser.exit(2, f"Abgelehnt: {error}\n")

    print(f"{args.page_id}: {len(groups)} Angebote gespeichert -> {path}")


def _cmd_view(args, parser):
    from magda import offer_view

    page_ids = [p.strip() for p in args.pages.split(",") if p.strip()] if args.pages else None
    entries = offer_view.load(args.source, page_ids, limit=args.limit)
    if not entries:
        parser.exit(1, f"Keine Gruppierung unter data/offer_groups/"
                       f"{config.model_slug(args.source)} gefunden.\n")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(offer_view.render(entries, args.source), encoding="utf-8")
    offers = sum(len(a.get("groups") or []) for _, a in entries)
    print(f"{len(entries)} Seiten, {offers} Angebote -> {out}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default="claude-sonnet-5",
                        help="Ordnername unter data/offer_groups/. Default claude-sonnet-5")
    parser.add_argument("--labels-from", dest="labels_from", default=None,
                        help="Labelordner unter data/labeled/. Default: konfiguriertes/groesstes Modell")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pages = subparsers.add_parser("pages", help="Welche Seiten als Naechstes drankommen")
    pages.add_argument("--limit", type=int, default=40)
    pages.add_argument("--json", action="store_true", help="Nur die page_ids als JSON-Liste")

    task = subparsers.add_parser("task", help="Die Aufgabe einer Seite als JSON")
    task.add_argument("page_id")

    save = subparsers.add_parser("save", help="Eine Antwort validieren und ablegen")
    save.add_argument("page_id")
    save.add_argument("--from", dest="answer", required=True,
                      help="JSON-Datei mit {\"groups\": [[Entity-Nummern], ...]}")
    save.add_argument("--model", default=None, help="Modellname fuer die provenance")

    view = subparsers.add_parser(
        "view", help="Gruppierungen als HTML ansehen (Seitenbild mit Farben)")
    view.add_argument("--pages", default=None,
                      help="Seiten, komma-getrennt. Ohne Angabe die ersten --limit")
    view.add_argument("--limit", type=int, default=8)
    view.add_argument("--out", default="offer_groups.html")

    args = parser.parse_args(argv)
    return {"pages": _cmd_pages, "task": _cmd_task, "save": _cmd_save,
            "view": _cmd_view}[args.command](args, parser)
