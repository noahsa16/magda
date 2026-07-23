"""API-Tests gegen ein temporäres Datenverzeichnis.

Wichtig: magda/api.py greift auf Pfade als config.X-Attribute zur Laufzeit zu,
genau damit diese Fixtures sie umbiegen können.
"""

import json

import pytest
from fastapi.testclient import TestClient

from magda import api, config

SAMPLE_PAGE = {
    "page_id": "462828_p3",
    "width": 595.28,
    "height": 841.89,
    "words": [
        {"text": "Rinderhackfleisch", "bbox": [72.4, 310.2, 198.6, 324.8]},
        {"text": "3.99", "bbox": [210.5, 305.0, 265.3, 348.1]},
    ],
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("RAW_DIR", "WORDS_DIR", "IMAGES_DIR", "LABELED_DIR", "EVAL_DIR", "CHECKPOINTS_DIR"):
        d = tmp_path / name.lower()
        d.mkdir()
        monkeypatch.setattr(config, name, d)
    return TestClient(api.app)


def _write_words(page_id: str, page: dict | None = None):
    page = page or {**SAMPLE_PAGE, "page_id": page_id}
    with open(config.WORDS_DIR / f"{page_id}.json", "w") as f:
        json.dump(page, f)


def test_schema_liefert_entity_typen(client):
    body = client.get("/api/schema").json()
    assert body["entity_types"][0] == "PRODUCT"
    assert len(body["entity_types"]) >= 7


def test_status_mit_leeren_verzeichnissen(client):
    body = client.get("/api/status").json()
    assert body == {"catalogs": [], "totals": {"raw": 0, "words": 0, "images": 0, "labeled": 0}}


def test_status_zaehlt_pro_katalog(client):
    (config.RAW_DIR / "462828").mkdir()
    (config.RAW_DIR / "462828" / "bk_1.pdf").write_bytes(b"x")
    (config.RAW_DIR / "462828" / "bk_2.pdf").write_bytes(b"x")
    _write_words("462828_p1")

    body = client.get("/api/status").json()

    assert body["catalogs"] == [{"id": "462828", "raw": 2, "words": 1, "images": 0, "labeled": 0}]
    assert body["totals"]["raw"] == 2


def test_pages_sortiert_numerisch_und_markiert_gelabelte(client):
    _write_words("462828_p10")
    _write_words("462828_p2")
    with open(config.LABELED_DIR / "462828_p2.json", "w") as f:
        json.dump({**SAMPLE_PAGE, "tags": ["B-PRODUCT", "B-PRICE"]}, f)

    body = client.get("/api/pages").json()

    assert [p["page_id"] for p in body] == ["462828_p2", "462828_p10"]
    assert body[0]["labeled"] is True
    assert body[1]["labeled"] is False
    assert body[0]["catalog"] == "462828"


def test_page_detail_mit_tags(client):
    _write_words("462828_p3")
    with open(config.LABELED_DIR / "462828_p3.json", "w") as f:
        json.dump({**SAMPLE_PAGE, "tags": ["B-PRODUCT", "B-PRICE"]}, f)

    body = client.get("/api/pages/462828_p3").json()

    assert body["words"][0]["text"] == "Rinderhackfleisch"
    assert body["tags"] == ["B-PRODUCT", "B-PRICE"]


def test_page_detail_ohne_labels_hat_keine_tags(client):
    _write_words("462828_p3")
    body = client.get("/api/pages/462828_p3").json()
    assert "tags" not in body


def test_page_detail_404(client):
    assert client.get("/api/pages/nope_p1").status_code == 404


def test_page_image(client):
    (config.IMAGES_DIR / "462828_p3.png").write_bytes(b"\x89PNG-fake")
    resp = client.get("/api/pages/462828_p3/image")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_page_image_404(client):
    assert client.get("/api/pages/nope_p1/image").status_code == 404
