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


def fetch_catalog_meta(catalog_id: str, session: requests.Session) -> dict:
    """Version und Titel aus der getcatalog-Seite.

    Ein 404 ist hier kein Fehler: geprüft am 29.07.2026 liefert die Seite für
    Katalog 1342881 längst 404, während dessen PDFs weiter abrufbar sind – die
    Metadatenseite läuft früher ab als der Inhalt. Fallback "1" hat bisher immer
    funktioniert. Bei 5xx wird dagegen geworfen: ein ausgefallener Server ist
    etwas anderes als eine abgelaufene Seite.

    Die Version steckt je nach Katalog an unterschiedlichen Stellen im HTML,
    daher zwei Regex-Versuche.
    """
    url = f"{CATALOG_BASE}?catalogId={catalog_id}"
    resp = session.get(url, timeout=15)
    if resp.status_code == 404:
        return {"found": False, "version": "1", "title": None}
    resp.raise_for_status()

    version = "1"
    match = re.search(r"catalogVersion\s*[=:]\s*['\"]?(\d+)['\"]?", resp.text)
    if match:
        version = match.group(1)
    else:
        match = re.search(rf"/catalogs/{catalog_id}/(\d+)/pdf/", resp.text)
        if match:
            version = match.group(1)

    title = re.search(r"<title>(.*?)</title>", resp.text, re.S)
    return {
        "found": True,
        "version": version,
        "title": title.group(1).strip() if title else None,
    }


def get_catalog_version(catalog_id: str, session: requests.Session) -> str:
    return fetch_catalog_meta(catalog_id, session)["version"]


def probe_catalog(url: str, session: requests.Session) -> dict:
    """Was bekäme man, wenn man diesen Katalog lädt?

    Prüft Metadaten und Seite 1, ohne etwas zu speichern – damit ein
    unerreichbarer Katalog vor dem Lauf auffällt statt als Exit-Code danach.
    """
    catalog_id = extract_catalog_id(url)
    meta = fetch_catalog_meta(catalog_id, session)
    pdf_url = f"{PDF_BASE}/{catalog_id}/{meta['version']}/pdf/save/bk_1.pdf"
    resp = session.get(pdf_url, timeout=30)
    return {
        "catalog_id": catalog_id,
        "version": meta["version"],
        "title": meta["title"],
        "meta_found": meta["found"],
        "page_1_status": resp.status_code,
        "page_1_bytes": len(resp.content) if resp.status_code == 200 else 0,
    }


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
