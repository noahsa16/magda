"""Urteile der Handprüfung als neuen Labelordner ablegen.

    magda audit-apply APP_PRICE --labels-from sonnet-5 --target sonnet-5-app

Der Zielordner ist Pflicht und darf nicht die Quelle sein. `data/labeled/`
ist die Referenz, gegen die gemessen wird – eine Korrektur an Ort und Stelle
verschöbe die Grundlage aller früheren Zahlen, ohne dass es jemand sieht.
Nebeneinander sind beide Stände dagegen vergleichbar, und genau das ist der
Sinn der Übung: erst die Übernahme macht messbar, was sie bringt.
"""

from __future__ import annotations

import argparse
import json

from magda import audit_apply, config


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="magda audit-apply",
        description="Urteile der Handprüfung auf einen Labelordner anwenden.",
    )
    parser.add_argument("label", help="z. B. APP_PRICE")
    parser.add_argument("--labels-from", required=True, help="Quellordner")
    parser.add_argument("--target", required=True,
                        help="Zielordner, NICHT die Quelle")
    args = parser.parse_args(argv)

    if config.model_slug(args.target) == config.model_slug(args.labels_from):
        parser.exit(1, "Ziel und Quelle sind derselbe Ordner. data/labeled/ "
                       "ist die Referenz und wird nicht überschrieben.\n")

    path = config.PROJECT_ROOT / "data" / "audit" / f"{args.label}.json"
    if not path.is_file():
        parser.exit(1, f"{path} fehlt. Erst `magda audit {args.label}` "
                       f"laufen lassen.\n")

    data = json.loads(path.read_text())
    # Die Auditdatei nennt ihre eigene Labelquelle. Weicht sie ab, zeigen die
    # Wortindizes auf andere Wörter – derselbe Vertragsbruch wie beim
    # `words_hash` in gold/.
    audited = data.get("labels_from")
    if audited and config.model_slug(audited) != config.model_slug(args.labels_from):
        parser.exit(1, f"Die Urteile wurden auf {audited} gefällt, angewandt "
                       f"werden sollen sie auf {args.labels_from}. Die "
                       f"Wortindizes gälten dann für andere Wörter.\n")

    result = audit_apply.apply_verdicts(
        data.get("verdicts") or {},
        config.labeled_dir(args.labels_from),
        config.labeled_dir(args.target),
    )
    print(f"{result['pages']} Seiten geschrieben, "
          f"{result['changed']} Span(s) geändert, "
          f"{result['confirmed']} Urteil(e) bestätigt.")
    if result["unresolved"]:
        print(f"\n{len(result['unresolved'])} Urteil(e) ohne Zielabel – das "
              f"alte Label bleibt stehen, weil ein Ersatz geraten wäre:")
        for key in result["unresolved"]:
            print(f"  {key}")
    print(f"\nZiel:   {config.labeled_dir(args.target)}")
    print(f"Quelle: {config.labeled_dir(args.labels_from)} (unverändert)")
