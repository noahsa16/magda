"""API-Weg der Demo: PDF hochladen oder aus einer Katalog-URL importieren.

Der Runner selbst wird hier nicht gestartet - `POST /api/run` mit dem Job
"extract-pdf" ist bereits über test_jobs.py und test_runner.py abgedeckt.
Diese Datei prüft, was an der API-Grenze rund um Upload und URL-Import passiert.
"""

import fitz
import pytest
from fastapi.testclient import TestClient

from magda import api, config, scraping, uploads


@pytest.fixture
def client(tmp_path, monkeypatch):
    d = tmp_path / "uploads"
    monkeypatch.setattr(config, "UPLOADS_DIR", d)
    return TestClient(api.app)


def _tiny_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.insert_text((10, 30), "Testseite", fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def test_upload_speichert_ein_pdf_und_liefert_seine_id(client):
    resp = client.post(
        "/api/demo/upload",
        files={"file": ("prospekt.pdf", _tiny_pdf(), "application/pdf")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert uploads.is_valid_id(body["upload_id"])
    assert body["pages"] == 1
    # Der vom Nutzer gewählte Dateiname "prospekt.pdf" landet nirgends im Pfad.
    assert (config.UPLOADS_DIR / f"{body['upload_id']}.pdf").is_file()
    assert not (config.UPLOADS_DIR / "prospekt.pdf").exists()


def test_upload_lehnt_falschen_content_type_ab(client):
    resp = client.post(
        "/api/demo/upload",
        files={"file": ("bild.png", b"\x89PNG\r\n", "image/png")},
    )

    assert resp.status_code == 400


def test_upload_lehnt_kein_echtes_pdf_ab(client):
    resp = client.post(
        "/api/demo/upload",
        files={"file": ("fake.pdf", b"nicht wirklich ein pdf", "application/pdf")},
    )

    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# URL-Import
# ---------------------------------------------------------------------------


def _single_page_pdf(text: str) -> bytes:
    doc = fitz.open()
    doc.new_page(width=100, height=100).insert_text((10, 30), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def _fake_download_catalog(pages: int):
    def fake(url, session, max_pages):
        for i in range(1, pages + 1):
            yield i, _single_page_pdf(f"Seite {i}")
    return fake


def test_from_url_liefert_dieselbe_form_wie_ein_upload(client, monkeypatch):
    monkeypatch.setattr(scraping, "download_catalog", _fake_download_catalog(3))

    resp = client.post("/api/demo/from-url", json={"url": "https://x/?catalogId=1"})

    assert resp.status_code == 200
    body = resp.json()
    assert uploads.is_valid_id(body["upload_id"])
    assert body["pages"] == 3


def test_from_url_ohne_catalog_id_ist_400(client):
    resp = client.post("/api/demo/from-url", json={"url": "https://x/ohne-id"})

    assert resp.status_code == 400


def test_from_url_netzfehler_wird_zu_400(client, monkeypatch):
    """Wie bei /api/catalogs/probe: ein unerreichbarer Katalog ist für den
    Nutzer eine fehlerhafte Eingabe, kein Serverfehler."""
    def kaputt(url, session, max_pages):
        raise ConnectionError("Netzwerk weg")
        yield  # pragma: no cover - macht kaputt() zum Generator

    monkeypatch.setattr(scraping, "download_catalog", kaputt)

    resp = client.post("/api/demo/from-url", json={"url": "https://x/?catalogId=1"})

    assert resp.status_code == 400
