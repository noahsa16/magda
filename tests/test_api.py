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
    for name in ("RAW_DIR", "WORDS_DIR", "IMAGES_DIR", "LABELED_DIR", "EVAL_DIR", "CHECKPOINTS_DIR", "GOLD_DIR", "RUNS_DIR"):
        d = tmp_path / name.lower()
        d.mkdir()
        monkeypatch.setattr(config, name, d)
    # Ohne das schreiben die Tests das echte catalogs.json im Repo um.
    monkeypatch.setattr(config, "CATALOGS_FILE", tmp_path / "catalogs.json")
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
    assert body == {
        "catalogs": [],
        "totals": {
            "raw": 0, "words": 0, "images": 0, "labeled": 0,
            "gold_done": 0, "gold_in_progress": 0,
        },
    }


def test_status_zaehlt_pro_katalog(client):
    (config.RAW_DIR / "462828").mkdir()
    (config.RAW_DIR / "462828" / "bk_1.pdf").write_bytes(b"x")
    (config.RAW_DIR / "462828" / "bk_2.pdf").write_bytes(b"x")
    _write_words("462828_p1")

    body = client.get("/api/status").json()

    assert len(body["catalogs"]) == 1
    # Der Vergleich gegen das ganze Dict ist Absicht: Das Frontend-Interface
    # CatalogStatus spiegelt genau diese Schlüsselmenge, ein stillschweigend
    # dazugekommenes Feld soll hier auffallen. Das Ladedatum hängt an der Uhr
    # und wird in test_status_liefert_ladedatum_je_katalog eigens geprüft.
    entry = dict(body["catalogs"][0])
    assert entry.pop("downloaded") is not None
    assert entry == {"id": "462828", "raw": 2, "words": 1, "images": 0, "labeled": 0}
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
    import time

    from magda import runner

    runner.reset()
    yield
    runner.stop()
    # Auf den Pump-Thread warten, bevor die Fixture die Pfade zurückdreht -
    # sonst schreibt er die Metadaten ins echte data/runs/.
    deadline = time.time() + 10
    while runner.status()["running"] and time.time() < deadline:
        time.sleep(0.05)
    runner.reset()


def test_run_lehnt_unbekannten_schritt_ab(client, clean_runner):
    resp = client.post("/api/run", json={"job": "rm -rf /"})

    assert resp.status_code == 400
    assert "Unbekannter Schritt" in resp.json()["detail"]


def test_run_lehnt_ungueltige_variante_ab(client, clean_runner):
    resp = client.post("/api/run", json={"job": "04_train", "args": {"variant": "bash"}})

    assert resp.status_code == 400
    assert "nicht erlaubt" in resp.json()["detail"]


def test_run_verlangt_variante_wo_noetig(client, clean_runner):
    resp = client.post("/api/run", json={"job": "05_evaluate", "args": {}})

    assert resp.status_code == 400


def test_run_lehnt_unbekannten_parameter_ab(client, clean_runner):
    resp = client.post(
        "/api/run", json={"job": "02_extract_words", "args": {"outfile": "/etc/passwd"}}
    )

    assert resp.status_code == 400
    assert "Unbekannter Parameter" in resp.json()["detail"]


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
         "annotator": "", "num_spans": 0, "stale": False},
        {"page_id": "462828_p2", "catalog": "462828", "status": "done",
         "annotator": "kjell", "num_spans": 1, "stale": False},
    ]


def test_gold_uebersicht_meldet_veraltete_wortliste(client):
    # Ohne diesen Vergleich meldet die Übersicht nach einem erneuten Schritt 02
    # weiter "fertig" - der Schaden fiele genau dort zuerst auf, wo man ihn
    # bisher nicht sah.
    _write_words("462828_p1")
    client.put("/api/gold/462828_p1", json={
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "done",
        "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}],
    })
    assert client.get("/api/gold").json()[0]["stale"] is False

    _write_words("462828_p1", {
        "page_id": "462828_p1", "width": 595.28, "height": 841.89,
        "words": [{"text": "Anders", "bbox": [1, 2, 3, 4]}],
    })

    row = client.get("/api/gold").json()[0]
    assert row["status"] == "done"
    assert row["stale"] is True


def test_gold_uebersicht_ueberlebt_kaputte_datei(client):
    # gold/ wird gemergt: ein Konfliktmarker in einer Datei darf nicht die
    # Übersicht aller anderen Seiten mitnehmen.
    _write_words("462828_p1")
    _write_words("462828_p2")
    with open(config.GOLD_DIR / "462828_p1.json", "w") as f:
        f.write("<<<<<<< HEAD\n{}\n")

    body = client.get("/api/gold").json()

    assert body[0]["status"] == "broken"
    assert body[1]["status"] == "untouched"


def test_gold_antwortet_beim_speichern_formgleich_zum_lesen(client):
    # Das Frontend legt die PUT-Antwort direkt in seinen Cache - fehlt dort
    # stale, wandert ein undefined in den Konfliktzustand.
    _write_words("462828_p1")
    payload = {
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "in_progress",
        "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}],
    }

    saved = client.put("/api/gold/462828_p1", json=payload).json()

    assert saved["stale"] is False
    assert set(saved) == set(client.get("/api/gold/462828_p1").json())
    with open(config.GOLD_DIR / "462828_p1.json") as f:
        assert "stale" not in json.load(f)


def test_gold_antwortet_mit_der_angefragten_page_id(client):
    # Kopierte Gold-Datei: maßgeblich ist die angefragte Seite, nicht der Inhalt.
    _write_words("462828_p1")
    with open(config.GOLD_DIR / "462828_p1.json", "w") as f:
        json.dump({"page_id": "999999_p7", "words_hash": "x", "status": "done",
                   "annotator": "", "spans": []}, f)

    assert client.get("/api/gold/462828_p1").json()["page_id"] == "462828_p1"


def test_gold_schreiben_laesst_keinen_torso_zurueck(client, monkeypatch):
    # Die Gold-Datei ist das einzige Artefakt, das sich nicht neu erzeugen
    # lässt. Bricht das Schreiben ab, muss die vorherige Fassung stehen bleiben.
    _write_words("462828_p1")
    hash_ = _hash_of(client, "462828_p1")
    client.put("/api/gold/462828_p1", json={
        "words_hash": hash_, "status": "in_progress", "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}],
    })

    def boom(*args, **kwargs):
        raise OSError("Platte voll")

    # Eigener Kontext: monkeypatch.undo() würde auch die Pfade der Fixture
    # zurückdrehen und den Rest des Tests gegen das echte gold/ laufen lassen.
    with monkeypatch.context() as m:
        m.setattr(api.json, "dump", boom)
        with pytest.raises(OSError):
            client.put("/api/gold/462828_p1", json={
                "words_hash": hash_, "status": "done", "annotator": "noah",
                "spans": [{"start": 1, "end": 2, "label": "PRICE"}],
            })

    body = client.get("/api/gold/462828_p1").json()
    assert body["spans"] == [{"start": 0, "end": 1, "label": "PRODUCT"}]
    assert [f.name for f in config.GOLD_DIR.iterdir()] == ["462828_p1.json"]
    # Die Temp-Datei von mkstemp kommt mit 0600; gold/ wird aber geteilt.
    assert (config.GOLD_DIR / "462828_p1.json").stat().st_mode & 0o777 == 0o644


def test_status_liefert_ladedatum_je_katalog(client):
    (config.RAW_DIR / "462828").mkdir()
    (config.RAW_DIR / "462828" / "bk_1.pdf").write_bytes(b"x")
    _write_words("462828_p1")

    row = client.get("/api/status").json()["catalogs"][0]

    assert row["downloaded"] is not None
    assert len(row["downloaded"]) == 10  # YYYY-MM-DD


def test_status_ohne_rohdaten_hat_kein_ladedatum(client):
    # Wörter da, aber data/raw/ geleert: der Katalog existiert weiter,
    # das Datum ist nicht mehr ableitbar.
    _write_words("462828_p1")

    row = client.get("/api/status").json()["catalogs"][0]

    assert row["downloaded"] is None


def test_status_totals_enthalten_kein_ladedatum(client):
    _write_words("462828_p1")

    totals = client.get("/api/status").json()["totals"]

    assert set(totals) == {
        "raw", "words", "images", "labeled", "gold_done", "gold_in_progress",
    }


# ---------------------------------------------------------------------------
# Job-Katalog, Lauf-Historie, Katalog-Verzeichnis
# ---------------------------------------------------------------------------


def test_jobs_liefert_den_katalog(client):
    body = client.get("/api/jobs").json()

    jobs_by_name = {j["job"]: j for j in body}
    assert "07_flair_baseline" in jobs_by_name
    url_param = next(p for p in jobs_by_name["01_download_flyers"]["params"] if p["key"] == "url")
    assert url_param["required"] is True


def test_runs_ist_leer_ohne_laeufe(client):
    assert client.get("/api/runs").json() == []


def test_runs_liefert_historie_und_detail(client):
    from magda import runs

    runs.write_meta("20260729-120000_04_train", {
        "run_id": "20260729-120000_04_train", "job": "04_train", "args": {"variant": "gbert"},
        "command": ["python", "04_train.py"], "started": "2026-07-29T12:00:00",
        "finished": "2026-07-29T12:08:00", "exit_code": 0, "duration": 480.0,
    })
    runs.log_path("20260729-120000_04_train").write_text("Epoch 1/10")

    listing = client.get("/api/runs").json()
    assert listing[0]["job"] == "04_train"

    detail = client.get("/api/runs/20260729-120000_04_train").json()
    assert detail["log"] == "Epoch 1/10"


def test_run_detail_lehnt_pfadangabe_ab(client):
    assert client.get("/api/runs/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_catalogs_anlegen_listen_entfernen(client):
    created = client.post("/api/catalogs", json={
        "id": "1342881", "url": "https://x/?catalogId=1342881", "title": "KW30", "version": "1",
    })
    assert created.status_code == 200

    body = client.get("/api/catalogs").json()
    assert body["error"] is None
    assert body["entries"][0]["id"] == "1342881"

    assert client.delete("/api/catalogs/1342881").status_code == 200
    assert client.get("/api/catalogs").json()["entries"] == []


def test_catalogs_lehnt_duplikat_ab(client):
    payload = {"id": "1342881", "url": "https://x", "title": "KW30", "version": "1"}
    client.post("/api/catalogs", json=payload)

    assert client.post("/api/catalogs", json=payload).status_code == 409


def test_catalogs_zaehlt_lokale_seiten(client):
    (config.RAW_DIR / "1342881").mkdir()
    (config.RAW_DIR / "1342881" / "bk_1.pdf").write_bytes(b"x")
    client.post("/api/catalogs", json={"id": "1342881", "url": "https://x", "title": "KW30"})

    assert client.get("/api/catalogs").json()["entries"][0]["local_pages"] == 1


def test_probe_meldet_fehler_lesbar(client, monkeypatch):
    def boom(url, session):
        raise ValueError("Keine catalogId in URL gefunden: kaputt")

    monkeypatch.setattr(api.scraping, "probe_catalog", boom)

    resp = client.post("/api/catalogs/probe", json={"url": "kaputt"})

    assert resp.status_code == 400
    assert "catalogId" in resp.json()["detail"]


def test_status_zaehlt_gold(client):
    _write_words("462828_p1")
    with open(config.GOLD_DIR / "462828_p1.json", "w") as f:
        json.dump({"page_id": "462828_p1", "status": "done", "spans": []}, f)
    with open(config.GOLD_DIR / "462828_p2.json", "w") as f:
        json.dump({"page_id": "462828_p2", "status": "in_progress", "spans": []}, f)

    totals = client.get("/api/status").json()["totals"]

    assert totals["gold_done"] == 1
    assert totals["gold_in_progress"] == 1


def test_label_verteilung_zaehlt_entities(client):
    with open(config.LABELED_DIR / "462828_p1.json", "w") as f:
        json.dump({"tags": ["B-PRODUCT", "I-PRODUCT", "B-PRICE", "O", "B-PRODUCT"]}, f)

    body = client.get("/api/labels/distribution").json()

    assert body["pages"] == 1
    assert body["counts"]["PRODUCT"] == 2
    assert body["counts"]["PRICE"] == 1
    assert body["total"] == 3
