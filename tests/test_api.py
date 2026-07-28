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
    for name in ("RAW_DIR", "WORDS_DIR", "IMAGES_DIR", "LABELED_DIR", "EVAL_DIR", "CHECKPOINTS_DIR", "GOLD_DIR"):
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


def test_evaluation_leer(client):
    assert client.get("/api/evaluation").json() == []


def test_evaluation_liefert_reports(client):
    report = {
        "variant": "layoutxlm",
        "split": "test",
        "num_pages": 12,
        "created": "2026-07-23T12:00:00",
        "report": {"PRODUCT": {"precision": 0.9, "recall": 0.8, "f1-score": 0.85, "support": 40}},
    }
    with open(config.EVAL_DIR / "layoutxlm_test.json", "w") as f:
        json.dump(report, f)

    body = client.get("/api/evaluation").json()

    assert len(body) == 1
    assert body[0]["variant"] == "layoutxlm"


@pytest.fixture
def clean_model_cache(monkeypatch):
    monkeypatch.setattr(api, "_MODEL_CACHE", {})


def test_inference_ohne_checkpoint_ist_503(client, clean_model_cache):
    resp = client.post(
        "/api/inference",
        files={"file": ("seite.pdf", b"%PDF-fake", "application/pdf")},
    )
    assert resp.status_code == 503
    assert "04_train" in resp.json()["detail"]


def test_inference_lehnt_nicht_pdf_ab(client, clean_model_cache):
    resp = client.post(
        "/api/inference",
        files={"file": ("bild.png", b"\x89PNG", "image/png")},
    )
    assert resp.status_code == 400


# --- Modellstatus ----------------------------------------------------------


def test_model_status_ohne_checkpoints(client):
    body = client.get("/api/model").json()

    assert [e["variant"] for e in body] == ["layoutxlm", "gbert"]
    assert all(e["trained"] is False for e in body)


def test_model_status_liest_trainingsverlauf(client):
    ckpt = config.CHECKPOINTS_DIR / "layoutxlm" / "checkpoint-120"
    ckpt.mkdir(parents=True)
    (config.CHECKPOINTS_DIR / "layoutxlm" / "best").mkdir()
    state = {
        "epoch": 3.0,
        "global_step": 120,
        "max_steps": 400,
        "best_metric": 0.83,
        "log_history": [
            {"epoch": 1.0, "loss": 0.9},
            {"epoch": 1.0, "eval_f1": 0.71},
            {"epoch": 2.0, "eval_f1": 0.83},
        ],
    }
    with open(ckpt / "trainer_state.json", "w") as f:
        json.dump(state, f)

    entry = client.get("/api/model").json()[0]

    assert entry["trained"] is True
    assert entry["steps"] == 120
    assert entry["best_f1"] == 0.83
    # Nur Zeilen mit eval_f1 landen im Verlauf, die reinen Loss-Logs nicht.
    assert entry["history"] == [{"epoch": 1.0, "f1": 0.71}, {"epoch": 2.0, "f1": 0.83}]


# --- Pipeline-Runner -------------------------------------------------------


@pytest.fixture
def clean_runner():
    from magda import runner

    runner.reset()
    yield
    runner.stop()
    runner.reset()


def test_run_lehnt_unbekannten_schritt_ab(client, clean_runner):
    resp = client.post("/api/run", json={"job": "rm -rf /"})

    assert resp.status_code == 400
    assert "Unbekannter Schritt" in resp.json()["detail"]


def test_run_lehnt_ungueltige_variante_ab(client, clean_runner):
    resp = client.post("/api/run", json={"job": "04_train", "variant": "bash"})

    assert resp.status_code == 400
    assert "Ungültige Variante" in resp.json()["detail"]


def test_run_verlangt_variante_wo_noetig(client, clean_runner):
    resp = client.post("/api/run", json={"job": "05_evaluate"})

    assert resp.status_code == 400


def test_run_status_ist_leer_ohne_lauf(client, clean_runner):
    body = client.get("/api/run").json()

    assert body["running"] is False
    assert body["job"] is None
    assert body["lines"] == []


# --- Gold-Annotationen (handgelabelt) -----------------------------------------------


def _hash_of(client, page_id: str) -> str:
    return client.get(f"/api/gold/{page_id}").json()["words_hash"]


def test_gold_unberuehrte_seite_liefert_leeren_entwurf(client):
    _write_words("462828_p1")

    body = client.get("/api/gold/462828_p1").json()

    assert body["status"] == "untouched"
    assert body["spans"] == []
    assert body["updated"] is None
    assert len(body["words_hash"]) == 64


def test_gold_unbekannte_seite_gibt_404(client):
    assert client.get("/api/gold/gibtsnicht_p1").status_code == 404


def test_gold_speichern_und_wiederlesen(client):
    _write_words("462828_p1")
    payload = {
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "in_progress",
        "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}],
    }

    assert client.put("/api/gold/462828_p1", json=payload).status_code == 200

    body = client.get("/api/gold/462828_p1").json()
    assert body["status"] == "in_progress"
    assert body["annotator"] == "noah"
    assert body["spans"] == [{"start": 0, "end": 1, "label": "PRODUCT"}]
    assert body["updated"] is not None


def test_gold_speichert_spans_nicht_als_tags(client):
    # Das Speicherformat ist Teil des Vertrags: Spans sind git-diffbar,
    # eine Liste aus 180 "O"-Einträgen ist es nicht.
    _write_words("462828_p1")
    client.put("/api/gold/462828_p1", json={
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "done",
        "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}],
    })

    with open(config.GOLD_DIR / "462828_p1.json") as f:
        stored = json.load(f)

    assert "tags" not in stored
    assert stored["spans"] == [{"start": 0, "end": 1, "label": "PRODUCT"}]


def test_gold_lehnt_ueberlappende_spans_ab(client):
    _write_words("462828_p1")
    resp = client.put("/api/gold/462828_p1", json={
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "in_progress",
        "annotator": "noah",
        "spans": [
            {"start": 0, "end": 2, "label": "PRODUCT"},
            {"start": 1, "end": 2, "label": "BRAND"},
        ],
    })
    assert resp.status_code == 422


def test_gold_lehnt_unbekanntes_label_ab(client):
    _write_words("462828_p1")
    resp = client.put("/api/gold/462828_p1", json={
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "in_progress",
        "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "FARBE"}],
    })
    assert resp.status_code == 422


def test_gold_lehnt_veralteten_hash_mit_409_ab(client):
    # Ändert sich Schritt 02, zeigen die Indizes auf andere Wörter. Der Hash
    # macht das laut, statt die Annotation still zu verfälschen.
    _write_words("462828_p1")
    resp = client.put("/api/gold/462828_p1", json={
        "words_hash": "0" * 64,
        "status": "in_progress",
        "annotator": "noah",
        "spans": [],
    })
    assert resp.status_code == 409


def test_gold_lehnt_ungueltigen_status_ab(client):
    # "untouched" ist ein server-berechneter Anzeigezustand, kein speicherbarer.
    _write_words("462828_p1")
    resp = client.put("/api/gold/462828_p1", json={
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "untouched",
        "annotator": "noah",
        "spans": [],
    })
    assert resp.status_code == 422


def test_gold_meldet_veraltete_wortliste_als_stale(client):
    _write_words("462828_p1")
    client.put("/api/gold/462828_p1", json={
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "done",
        "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}],
    })
    assert client.get("/api/gold/462828_p1").json()["stale"] is False

    # Schritt 02 lief erneut und die Wortliste hat sich geändert.
    _write_words("462828_p1", {
        "page_id": "462828_p1", "width": 595.28, "height": 841.89,
        "words": [{"text": "Anders", "bbox": [1, 2, 3, 4]}],
    })

    assert client.get("/api/gold/462828_p1").json()["stale"] is True


def test_gold_uebersicht_listet_auch_unberuehrte_seiten(client):
    _write_words("462828_p1")
    _write_words("462828_p2")
    client.put("/api/gold/462828_p2", json={
        "words_hash": _hash_of(client, "462828_p2"),
        "status": "done",
        "annotator": "kjell",
        "spans": [{"start": 0, "end": 1, "label": "PRICE"}],
    })

    body = client.get("/api/gold").json()

    assert body == [
        {"page_id": "462828_p1", "catalog": "462828", "status": "untouched",
         "annotator": "", "num_spans": 0},
        {"page_id": "462828_p2", "catalog": "462828", "status": "done",
         "annotator": "kjell", "num_spans": 1},
    ]
