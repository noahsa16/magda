"""API-Weg der Demo: Upload eines fremden PDFs.

Der Runner selbst wird hier nicht gestartet - `POST /api/run` mit dem Job
"extract-pdf" ist bereits über test_jobs.py und test_runner.py abgedeckt.
Diese Datei prüft, was an der API-Grenze rund um den Upload passiert.
"""

import fitz
import pytest
from fastapi.testclient import TestClient

from magda import api, config, uploads


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
