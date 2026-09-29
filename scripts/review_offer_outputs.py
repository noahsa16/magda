"""Zeigt und speichert eine visuelle Einzelfallprüfung der Angebotsausgaben.

Die Reihenfolge der Ausgaben ist durch die gespeicherten Quelldateien fixiert.
Ein Urteilscode gilt genau für die Ausgabe mit demselben nullbasierten Index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from magda import blackbox_eval


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "data/eval/study-2026-09-16/study.json"
RUNTIME = ROOT / "data/eval/runtime_thl_qwen3.8-27b_2026-09-24.json"
AUDIT = ROOT / "data/audit/offer_output_review_2026-09-24.json"
REPORT = ROOT / "reports/offer_output_visual_review_2026-09-24.md"
CODES = {
    "C": "Produkt und Preis auf der Seite korrekt zugeordnet",
    "I": "Produkt und Preis erkennbar, Name, Gruppierung oder Bedingung ungenau",
    "W": "Produkt sichtbar, aber falscher Preis oder falsche Bedingung",
    "D": "Dublette eines anderen ausgegebenen Angebots",
    "S": "Kein entsprechendes Angebot auf der Seite",
    "U": "Anhand des Seitenbildes nicht sicher entscheidbar",
}


def outputs() -> tuple[list[str], dict[str, dict[str, list[dict]]]]:
    study = json.loads(STUDY.read_text())
    runtime = json.loads(RUNTIME.read_text())
    qwen = {}
    for row in runtime["per_page"]:
        deals = []
        for record in row["records"] or []:
            if not isinstance(record, dict):
                continue
            name = " ".join(str(part).strip() for part in
                            (record.get("brand"), record.get("product")) if part)
            price = blackbox_eval.parse_price(record.get("price"))
            if name and price is not None:
                deals.append({"name": name, "price": price})
        qwen[row["page_id"]] = deals
    pages = study["pages"]
    if pages != [row["page_id"] for row in runtime["per_page"]]:
        raise ValueError("Seitenlisten stimmen nicht überein")
    return pages, {page: {"magda": study["own_deals"][page], "qwen": qwen[page]}
                   for page in pages}


def load_audit() -> dict:
    if AUDIT.exists():
        audit = json.loads(AUDIT.read_text())
        if audit["study_sha256"] != hashlib.sha256(STUDY.read_bytes()).hexdigest():
            raise ValueError("Studienquelle hat sich geändert")
        if audit["runtime_sha256"] != hashlib.sha256(RUNTIME.read_bytes()).hexdigest():
            raise ValueError("Laufzeitquelle hat sich geändert")
        return audit
    return {
        "protocol": "visual-offer-pair-review-v1",
        "reviewer": "Codex, visuelle Einzelfallprüfung; keine unabhängige Humanannotation",
        "criterion": "Gedrucktes Produkt mit regulärem Preis auf derselben Seite. App- und Vergleichspreise zählen nicht als regulärer Preis. Echte Preis- oder Produktvarianten dürfen getrennte Angebote sein. Nach dem ersten Eintrag sind identische Ausgaben Dubletten.",
        "codes": CODES,
        "study_sha256": hashlib.sha256(STUDY.read_bytes()).hexdigest(),
        "runtime_sha256": hashlib.sha256(RUNTIME.read_bytes()).hexdigest(),
        "pages": {},
    }


def report_text(pages: list[str], deals: dict, audit: dict) -> str:
    if set(audit["pages"]) != set(pages):
        raise ValueError("Für den Bericht müssen alle Seiten geprüft sein")
    lines = [
        "# Visuelle Prüfung der ausgegebenen Angebote",
        "",
        "42 PENNY-Seiten. Jede der 281 Magda- und 349 Qwen-Ausgaben wurde "
        "einzeln mit dem jeweiligen Seitenbild verglichen. Die Reihenfolge "
        "und Wortlaute stammen aus den gespeicherten Ausgabedateien.",
        "",
        "Dies ist eine visuelle Einzelprüfung durch Codex, keine unabhängige "
        "menschliche Goldannotation. Geprüft wurden ausgegebene Angebote, "
        "nicht sämtliche auf den Seiten sichtbaren Angebote. Die Zahlen "
        "messen daher keine Vollständigkeit und sind kein neuer F1-Wert.",
        "",
        "Ein regulärer Preis gilt als korrekt, wenn er dem Produkt auf der "
        "Seite zugeordnet ist. App- und Vergleichspreise zählen nicht als "
        "regulärer Preis. Echte Varianten können getrennte Angebote sein. "
        "Identische wiederholte Ausgaben zählen ab der zweiten als Dublette.",
        "",
        "| Code | Bedeutung |",
        "| --- | --- |",
    ]
    lines.extend(f"| {code} | {meaning} |" for code, meaning in CODES.items())
    lines.extend(["", "## Auszählung", "", "| System | Gesamt | C | I | W | D | S | U | C-Anteil |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for system in ("magda", "qwen"):
        counts = Counter(code for page in pages for code in audit["pages"][page][system])
        total = sum(counts.values())
        values = " | ".join(str(counts[code]) for code in CODES)
        lines.append(f"| {system} | {total} | {values} | {counts['C'] / total:.1%} |")
    lines.extend(["", "## Einzelurteile", ""])
    for page in pages:
        entry = audit["pages"][page]
        lines.extend([
            f"### {page}",
            "",
            f"[Seitenbild](../data/images/{page}.png)",
            "",
            entry.get("note", "") or "Keine zusätzliche Notiz.",
            "",
            "| System | Nr. | Preis (€) | Produkt | Code |",
            "| --- | ---: | ---: | --- | --- |",
        ])
        for system in ("magda", "qwen"):
            for index, offer in enumerate(deals[page][system]):
                name = offer["name"].replace("|", "\\|").replace("\n", " ")
                code = entry[system][index]
                lines.append(f"| {system} | {index:02d} | {offer['price']:.2f} | {name} | {code} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    show = sub.add_parser("show")
    show.add_argument("page_id")
    mark = sub.add_parser("mark")
    mark.add_argument("page_id")
    mark.add_argument("--magda", required=True)
    mark.add_argument("--qwen", required=True)
    mark.add_argument("--note", default="")
    sub.add_parser("summary")
    sub.add_parser("report")
    args = parser.parse_args()

    pages, deals = outputs()
    audit = load_audit()
    if args.command in ("show", "mark") and args.page_id not in deals:
        parser.error("Seite ist nicht Teil der 42 Testseiten")

    if args.command == "show":
        page = args.page_id
        existing = audit["pages"].get(page, {})
        print(f"{page} | Bild: {ROOT / 'data/images' / (page + '.png')}")
        for system in ("magda", "qwen"):
            print(f"\n{system.upper()} ({len(deals[page][system])})")
            codes = existing.get(system, "")
            for index, offer in enumerate(deals[page][system]):
                status = codes[index] if index < len(codes) else "."
                print(f"{index:02d} {status} {offer['price']:>6.2f} {offer['name']}")
        if existing.get("note"):
            print("\nNotiz:", existing["note"])
    elif args.command == "mark":
        page = args.page_id
        for system in ("magda", "qwen"):
            codes = getattr(args, system).upper()
            if len(codes) != len(deals[page][system]) or set(codes) - set(CODES):
                parser.error(f"{system}: {len(deals[page][system])} gültige Codes nötig")
        audit["pages"][page] = {"magda": args.magda.upper(),
                                "qwen": args.qwen.upper(), "note": args.note}
        AUDIT.parent.mkdir(parents=True, exist_ok=True)
        AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
        print(f"Gespeichert: {page}")
    elif args.command == "summary":
        for system in ("magda", "qwen"):
            counts = Counter(code for page in audit["pages"].values()
                             for code in page[system])
            print(system, "reviewed", sum(len(deals[p][system]) for p in audit["pages"]),
                  "of", sum(len(deals[p][system]) for p in pages), dict(counts))
        print("pages", len(audit["pages"]), "of", len(pages))
        print("missing", " ".join(page for page in pages if page not in audit["pages"]))
    else:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report_text(pages, deals, audit))
        print(f"Bericht gespeichert: {REPORT}")


if __name__ == "__main__":
    main()
