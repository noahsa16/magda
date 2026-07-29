"""Katalog-Entdeckung: welche Penny-Prospekte gibt es gerade, und welche Seiten
davon sind verschieden?

Penny veröffentlicht je Woche 44 Regionalausgaben. Die Katalog-IDs stehen nicht
irgendwo versteckt, sondern in Penny's eigener Markt-API: `/.rest/market`
liefert alle 2121 Märkte, jeder mit `flippingBookURL`. Raten oder Suchen im
ID-Raum ist unnötig — und für ältere Wochen auch aussichtslos, siehe unten.

Zwei Messungen vom 29.07.2026, die das Vorgehen bestimmen:

**Die Regionalausgaben sind zu 91 % identisch.** Über alle 44 Regionen einer
Woche liegen 2004 Seiten, davon nur ~171 verschiedene; je Seitenposition gibt es
2 bis 6 Fassungen, nicht 44. Wer alles herunterlädt, holt 4 GB für 340 MB
Information — und schlimmer: dieselbe Seite landet in Train- und Testsplit.
Deshalb wird vor dem Download dedupliziert, nicht danach.

**Es gibt kein Archiv.** Penny hält ungefähr zwei Wochen online, ältere Kataloge
sind gelöscht. Ein feiner Scan des ID-Gitters (Schrittweite 99 bei 132 IDs
Blockbreite, kann also keinen Block überspringen) über 1.325.000–1.347.600 fand
genau zwei lebende Penny-Blöcke: die laufende und die vorige Woche. Die Stelle
der Woche davor ist tot. Wer eine Woche verpasst, bekommt sie nicht zurück.
"""

import re
import time
from collections import defaultdict

import requests

MARKET_API = "https://www.penny.de/.rest/market"
PDF_BASE = "https://penny-publish.blaetterkatalog.de/frontend/catalogs"

# Die IDs einer Woche liegen auf einem Gitter mit Schrittweite 3.
ID_STRIDE = 3

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = _UA
    return session


def _pdf_url(catalog_id: str, page: int, version: str = "1") -> str:
    return f"{PDF_BASE}/{catalog_id}/{version}/pdf/save/bk_{page}.pdf"


def current_week_ids(session: requests.Session) -> list[str]:
    """Die Katalog-IDs der laufenden Woche, aus Penny's Markt-API.

    `nextWeekFlippingBookURL` ist unter der Woche leer und füllt sich erst
    freitags – deshalb wird es hier nicht ausgewertet, sondern beim nächsten
    Lauf ohnehin zur laufenden Woche.
    """
    resp = session.get(MARKET_API, headers={"Accept": "application/json"}, timeout=60)
    resp.raise_for_status()
    ids = set()
    for market in resp.json():
        match = re.search(r"catalogId=(\d+)", market.get("flippingBookURL") or "")
        if match:
            ids.add(match.group(1))
    return sorted(ids)


def page_exists(catalog_id: str, page: int, session: requests.Session) -> int | None:
    """Größe der Seite in Bytes, None wenn es sie nicht gibt.

    HEAD statt GET: die Antwort kostet 141 ms statt 190 ms und überträgt keine
    Nutzlast. Bei ein paar tausend Proben ist das der Unterschied zwischen
    Minuten und Gigabytes.
    """
    try:
        resp = session.head(_pdf_url(catalog_id, page), timeout=15)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    return int(resp.headers.get("Content-Length", 0))


def expand_block(seed: str, session: requests.Session, limit: int = 60) -> list[str]:
    """Alle IDs des Blocks, in dem `seed` liegt – gitterweise nach beiden Seiten.

    Für eine vergangene Woche gibt es keine Markt-API mehr; die Regionen einer
    Woche liegen aber lückenlos auf dem Dreiergitter, also lässt sich der Block
    von einer bekannten ID aus ablaufen.
    """
    found = [seed] if page_exists(seed, 1, session) is not None else []
    if not found:
        return []
    for direction in (-1, 1):
        step = 1
        while step <= limit:
            candidate = str(int(seed) + direction * step * ID_STRIDE)
            if page_exists(candidate, 1, session) is None:
                break
            found.append(candidate)
            step += 1
    return sorted(found, key=int)


def page_sizes(catalog_id: str, session: requests.Session, max_pages: int = 80) -> list[int]:
    """Größe jeder Seite, bis die erste fehlt. Länge = Seitenzahl des Katalogs."""
    sizes = []
    for page in range(1, max_pages + 1):
        size = page_exists(catalog_id, page, session)
        if size is None:
            break
        sizes.append(size)
    return sizes


def dedupe_plan(
    catalog_ids: list[str], session: requests.Session, pause: float = 0.0
) -> tuple[list[tuple[str, int]], dict]:
    """Welche (Katalog, Seite) muss man laden, um jede verschiedene Seite genau
    einmal zu haben?

    Gruppiert nach (Seitenposition, Dateigröße). Gleiche Größe an gleicher
    Position heißt in dieser Quelle gleicher Inhalt – auf den Seiten 1 bis 8
    wortweise nachgeprüft. Die Annahme ist bewusst konservativ nur hier: die
    endgültige Entdopplung passiert später über `words_hash` auf der
    extrahierten Wortliste, wo sie exakt ist. Diese Vorauswahl spart nur den
    Download.
    """
    gruppen: dict[tuple[int, int], list[tuple[str, int]]] = defaultdict(list)
    seiten_gesamt = 0
    for catalog_id in catalog_ids:
        for position, size in enumerate(page_sizes(catalog_id, session), start=1):
            gruppen[(position, size)].append((catalog_id, position))
            seiten_gesamt += 1
        if pause:
            time.sleep(pause)

    plan = sorted((eintraege[0] for eintraege in gruppen.values()), key=lambda x: (int(x[0]), x[1]))
    statistik = {
        "kataloge": len(catalog_ids),
        "seiten_gesamt": seiten_gesamt,
        "seiten_verschieden": len(plan),
        "dubletten": seiten_gesamt - len(plan),
    }
    return plan, statistik


def fetch_page(catalog_id: str, page: int, session: requests.Session) -> bytes | None:
    try:
        resp = session.get(_pdf_url(catalog_id, page), timeout=40)
    except requests.RequestException:
        return None
    return resp.content if resp.status_code == 200 else None
