"""Holt eine komplette Prospektwoche über alle 44 Regionalausgaben.

Aufruf:
    magda harvest                 # laufende Woche
    magda harvest --seed 1342881  # ältere Woche über eine bekannte ID

Warum ein eigener Schritt neben `magda download`: der lädt einen einzelnen
Katalog über seine URL. Hier geht es um die Woche als Ganzes – 44 Regionen, die
zu über 90 % identisch sind. Geladen wird alles, gespeichert nur, was neu ist:
der Text lässt sich nur im PDF ablesen, also muss jede Seite einmal durch die
Leitung, aber nicht auf die Platte.

Penny hält ungefähr zwei Wochen online. Wer eine Woche verpasst, bekommt sie
nicht zurück – die nächste Woche erscheint freitags, `--seed` greift für die
vorige.
"""

import argparse
import hashlib
import sys

from tqdm import tqdm

from magda import catalog_meta, discovery
from magda.config import RAW_DIR
from magda.ocr import extract_words


def _word_hash(pdf_bytes: bytes) -> str | None:
    words = [w["text"] for w in extract_words(pdf_bytes)["words"]]
    if not words:
        return None
    return hashlib.sha256("\x00".join(words).encode()).hexdigest()


def _known_hashes() -> dict[str, str]:
    """Was schon auf der Platte liegt, zählt als gesehen – der Lauf ist idempotent."""
    seen = {}
    for pdf in sorted(RAW_DIR.glob("*/bk_*.pdf")):
        try:
            h = _word_hash(pdf.read_bytes())
        except Exception:
            continue
        if h:
            seen.setdefault(h, f"{pdf.parent.name}/{pdf.name}")
    return seen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", help="Bekannte Katalog-ID einer älteren Woche")
    parser.add_argument("--max-pages", type=int, default=80)
    args = parser.parse_args(argv)

    session = discovery.make_session()

    if args.seed:
        ids = discovery.expand_block(args.seed, session)
        if not ids:
            sys.exit(f"Katalog {args.seed} ist nicht mehr abrufbar – die Woche ist gelöscht.")
        origin = f"Gitterlauf ab {args.seed}"
    else:
        ids = discovery.current_week_ids(session)
        if not ids:
            sys.exit("Penny's Markt-API liefert gerade keine Katalog-URLs.")
        origin = "Markt-API"

    print(f"{len(ids)} Regionen ({origin}): {ids[0]}..{ids[-1]}")

    # Regionszuordnung festhalten, solange sie abrufbar ist. Nach einer Woche
    # kennt die Markt-API diese Kataloge nicht mehr.
    current = discovery.market_metadata(session)
    inferred = discovery.infer_older_block(current, ids, ids[0]) if args.seed else {}
    catalog_meta.merge({**current, **inferred})
    print(f"Regionen notiert: {len(current)} bestätigt, {len(inferred)} vermutet")

    seen = _known_hashes()
    print(f"schon vorhanden: {len(seen)} verschiedene Seiten\n")

    added = duplicate_count = empty_count = 0
    for catalog_id in tqdm(ids, desc="Regionen", unit="Katalog"):
        for page in range(1, args.max_pages + 1):
            pdf_bytes = discovery.fetch_page(catalog_id, page, session)
            if pdf_bytes is None:
                break
            try:
                h = _word_hash(pdf_bytes)
            except Exception:
                empty_count += 1
                continue
            if h is None:
                empty_count += 1
                continue
            if h in seen:
                duplicate_count += 1
                continue
            seen[h] = f"{catalog_id}/bk_{page}.pdf"
            out_dir = RAW_DIR / catalog_id
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"bk_{page}.pdf").write_bytes(pdf_bytes)
            added += 1

    print(f"\n{added} neue Seiten, {duplicate_count} Duplikate verworfen, {empty_count} ohne Textlayer")
    print(f"{len(seen)} verschiedene Seiten in data/raw/")
    print("Weiter mit: magda extract")

