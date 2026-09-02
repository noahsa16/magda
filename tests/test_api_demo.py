"""API-Weg der Demo: Upload/Import, Ergebnis lesen, Seitenbild, Export.

Der Runner selbst wird hier nicht gestartet - `POST /api/run` mit dem Job
"extract-pdf" ist bereits über test_jobs.py und test_runner.py abgedeckt.
Diese Datei prüft, was an der API-Grenze drumherum passiert: Upload/Import,
ID-Prüfung, und dass ein bereits vorliegendes Ergebnis-JSON korrekt gelesen
und in die drei Exportformate umgewandelt wird.
"""

import csv
import io
import json
import sqlite3

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


# ---------------------------------------------------------------------------
# ID-Validierung (gilt für alle Lese-Endpunkte)
# ---------------------------------------------------------------------------


def test_id_mit_pfadtrenner_erreicht_den_handler_nie(client):
    """Starlette erlaubt "/" nicht innerhalb eines einzelnen Pfadsegments -
    die Route matcht solche IDs also gar nicht erst. 404 statt 400, aber in
    keinem Fall wird ein Datei- oder Verzeichniszugriff mit diesem Wert
    versucht, mittelbar auch nicht ueber "..". """
    for bad_id in ("../../etc/passwd", "a/b"):
        for suffix in ("", "/page/1.png", "/export?format=json"):
            assert client.get(f"/api/demo/{bad_id}{suffix}").status_code == 404


def test_ungueltige_aber_pfadfreie_id_wird_mit_400_abgelehnt(client):
    for suffix in ("", "/page/1.png", "/export?format=json"):
        assert client.get(f"/api/demo/zu-kurz{suffix}").status_code == 400


def test_unbekannte_aber_gueltige_id_ist_404(client):
    unbekannt = uploads.new_id()
    assert client.get(f"/api/demo/{unbekannt}").status_code == 404


# ---------------------------------------------------------------------------
# Ergebnis lesen, Seitenbild, Export
# ---------------------------------------------------------------------------

# Ein Ergebnis, wie es `magda extract-pdf --out .../<id>.json --no-embed-images`
# tatsächlich schreiben würde - schlank genug für den Test, aber mit allen
# Feldern, die to_csv/to_sqlite über pipeline.from_json brauchen.
def _sample_result(doc_id: str = "abc123") -> dict:
    offer = {
        "page_index": 0, "bbox": [0, 0, 30, 10],
        "product": "Butter", "brand": None, "price": "1.29", "old_price": None,
        "quantity": None, "unit_price": None, "app_price": None, "discount": None,
        "valid": None,
        "variants": [{"position": 0, "quantity": None, "price": "1.29",
                      "old_price": None, "unit_price": None, "app_price": None}],
        "confidence": 0.9, "arithmetic": "unverifiable",
        "entity_word_ranges": [
            {"type": "PRODUCT", "start": 0, "end": 1},
            {"type": "PRICE", "start": 1, "end": 2},
        ],
    }
    return {
        "doc_id": doc_id,
        "models": {
            "variant": "gbert", "checkpoint": "fake/best",
            "pairs_checkpoint": "fake/pairs.pt", "pair_threshold": 0.68,
        },
        "timing": {"extract": 0.1, "ner": 0.2, "grouping": 0.05},
        "pages_without_text": [],
        "pages": [
            {
                "page_index": 0, "width": 100, "height": 100, "png_base64": None,
                "words": [
                    {"text": "Butter", "bbox": [0, 0, 10, 10]},
                    {"text": "1.29", "bbox": [20, 0, 30, 10]},
                ],
                "entities": [
                    {"id": 0, "type": "PRODUCT", "text": "Butter", "bbox": [0, 0, 10, 10],
                     "start": 0, "end": 1, "context_before": "", "context_after": "1.29"},
                    {"id": 1, "type": "PRICE", "text": "1.29", "bbox": [20, 0, 30, 10],
                     "start": 1, "end": 2, "context_before": "Butter", "context_after": ""},
                ],
                "offers": [offer],
            },
        ],
        "offers": [offer],
    }


def _write_result(upload_id: str, payload: dict | None = None) -> None:
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with open(uploads.result_path(upload_id), "w") as f:
        json.dump(payload or _sample_result(), f)


def test_ergebnis_liefert_das_gespeicherte_json(client):
    upload_id = uploads.new_id()
    _write_result(upload_id)

    body = client.get(f"/api/demo/{upload_id}").json()

    assert body["doc_id"] == "abc123"
    assert len(body["offers"]) == 1
    assert body["offers"][0]["product"] == "Butter"


def test_seitenbild_liefert_die_datei_mit_doc_id_praefix(client):
    """extract_pdf.py --images-dir schreibt <doc_id>_p<n>.png - der Endpunkt
    muss diesen Namen finden, ohne ihn selbst zu kennen."""
    upload_id = uploads.new_id()
    directory = uploads.images_dir(upload_id)
    directory.mkdir(parents=True)
    (directory / "abc123_p1.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    resp = client.get(f"/api/demo/{upload_id}/page/1.png")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_seitenbild_ohne_datei_ist_404(client):
    upload_id = uploads.new_id()
    _write_result(upload_id)  # Ergebnis liegt vor, Bilder aber nicht

    assert client.get(f"/api/demo/{upload_id}/page/1.png").status_code == 404


def test_export_ohne_ergebnis_ist_404(client):
    upload_id = uploads.new_id()
    assert client.get(f"/api/demo/{upload_id}/export?format=csv").status_code == 404


def test_export_json_ist_ein_download_mit_passendem_content_type(client):
    upload_id = uploads.new_id()
    _write_result(upload_id)

    resp = client.get(f"/api/demo/{upload_id}/export?format=json")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.json()["doc_id"] == "abc123"


def test_export_csv_hat_eine_zeile_je_variante(client):
    upload_id = uploads.new_id()
    _write_result(upload_id)

    resp = client.get(f"/api/demo/{upload_id}/export?format=csv")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert len(rows) == 1
    assert rows[0]["product"] == "Butter"
    assert rows[0]["price"] == "1.29"


def test_export_sqlite_ist_eine_gueltige_datenbank(client, tmp_path):
    upload_id = uploads.new_id()
    _write_result(upload_id)

    resp = client.get(f"/api/demo/{upload_id}/export?format=sqlite")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/x-sqlite3"
    db_path = tmp_path / "export.sqlite"
    db_path.write_bytes(resp.content)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("select product, price from offers").fetchall()
    assert rows == [("Butter", "1.29")]


def test_export_ohne_format_ist_ein_klarer_fehler(client):
    upload_id = uploads.new_id()
    _write_result(upload_id)

    resp = client.get(f"/api/demo/{upload_id}/export")

    assert resp.status_code == 422
