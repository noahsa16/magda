"""Download von Penny-Prospektseiten.

Penny stellt seine Prospekte als "Blätterkatalog" bereit. Praktischerweise
liegt dort jede Seite als eigenes einseitiges PDF, das sich direkt über eine
vorhersagbare URL ziehen lässt – kein Browser-Scraping nötig.
"""

import re

import requests

PDF_BASE = "https://penny-publish.blaetterkatalog.de/frontend/catalogs"
CATALOG_BASE = "https://penny-publish.blaetterkatalog.de/frontend/getcatalog.do"


def extract_catalog_id(flipping_book_url: str) -> str:
    match = re.search(r"catalogId=(\d+)", flipping_book_url)
    if not match:
        raise ValueError(f"Keine catalogId in URL gefunden: {flipping_book_url}")
    return match.group(1)


def get_catalog_version(catalog_id: str, session: requests.Session) -> str:
    """Ermittelt die Katalog-Version aus der getcatalog-Seite.

    Die Version steckt je nach Katalog an unterschiedlichen Stellen im HTML,
    daher zwei Regex-Versuche. Fallback "1" hat bisher immer funktioniert,
    wenn beide nichts finden.
    """
    url = f"{CATALOG_BASE}?catalogId={catalog_id}"
    resp = session.get(url, timeout=15)
    resp.raise_for_status()

    match = re.search(r"catalogVersion\s*[=:]\s*['\"]?(\d+)['\"]?", resp.text)
    if match:
        return match.group(1)

    match = re.search(rf"/catalogs/{catalog_id}/(\d+)/pdf/", resp.text)
    if match:
        return match.group(1)

    return "1"


def fetch_page_pdf(
    catalog_id: str, version: str, page: int, session: requests.Session
) -> bytes | None:
    """Lädt eine einzelne Prospektseite als PDF. None bei 404 = Katalogende."""
    url = f"{PDF_BASE}/{catalog_id}/{version}/pdf/save/bk_{page}.pdf"
    resp = session.get(url, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content


def download_catalog(
    flipping_book_url: str,
    session: requests.Session,
    max_pages: int = 40,
):
    """Generator über alle Seiten eines Katalogs: liefert (seitennr, pdf_bytes).

    Bricht ab, sobald eine Seite 404 liefert – so müssen wir die Seitenzahl
    nicht vorher kennen.
    """
    catalog_id = extract_catalog_id(flipping_book_url)
    version = get_catalog_version(catalog_id, session)

    for page in range(1, max_pages + 1):
        pdf_bytes = fetch_page_pdf(catalog_id, version, page, session)
        if pdf_bytes is None:
            break
        yield page, pdf_bytes
