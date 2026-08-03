"""Die Handprüfung sortiert vor – sie entscheidet nichts.

Der Wert dieses Werkzeugs hängt an zwei Dingen: dass die Vorauswahl den
richtigen Ton trifft (ein grober Blau-Test fängt die hellblauen Kacheln neben
"ohne PENNY App" mit) und dass ein Urteil für alle 44 Regionalausgaben gilt.
"""

import json

import numpy as np
import pytest

from magda import config, label_audit


def test_app_ton_wird_erkannt_helles_blau_nicht():
    """(0, 124, 132) ist der verifizierte App-Kasten, (196, 227, 248) eine Kachel."""
    assert label_audit.on_app_background([0, 124, 132])
    assert label_audit.on_app_background([12, 118, 140])
    assert not label_audit.on_app_background([196, 227, 248])
    assert not label_audit.on_app_background([255, 212, 0])
    assert not label_audit.on_app_background(None)


def test_hintergrund_kommt_vom_rand_nicht_aus_der_mitte():
    """In der Wortbox steht Schrift; der Hintergrund liegt daneben."""
    pixels = np.zeros((100, 100, 3), dtype=np.uint8)
    pixels[:, :] = (0, 124, 132)       # Kasten
    pixels[40:60, 40:60] = (255, 255, 255)  # weiße Schrift mittendrin

    color = label_audit.background_color([40, 40, 60, 60], pixels, 100, 100)

    assert label_audit.on_app_background(color)


def test_streichpreis_im_kasten_hat_niedrige_prioritaet():
    """Im App-Kasten stehen zwei Preise – der durchgestrichene bleibt OLD_PRICE."""
    missing = {"source": "candidate", "current_label": "PRICE"}
    struck = {"source": "candidate", "current_label": "OLD_PRICE"}
    labeled = {"source": "labeled", "current_label": "APP_PRICE"}

    assert label_audit.priority_of(missing, "APP_PRICE") == "likely_missing"
    assert label_audit.priority_of(struck, "APP_PRICE") == "low"
    assert label_audit.priority_of(labeled, "APP_PRICE") == "check"


def test_gleicher_wortlaut_wird_zu_einer_vorlage_gebuendelt():
    """Sonst zählt dieselbe Seite aus 44 Regionen als 44 Entscheidungen."""
    candidates = [
        {"key": "a_p1:5", "context": "x «1.69» y", "current_label": "PRICE"},
        {"key": "b_p1:5", "context": "x «1.69» y", "current_label": "PRICE"},
        {"key": "c_p1:9", "context": "anders «2.99» z", "current_label": "PRICE"},
    ]

    result = label_audit._mark_duplicates(candidates)

    assert result[0]["duplicate_of"] is None
    assert result[1]["duplicate_of"] == "a_p1:5"
    assert result[0]["duplicates"] == 2
    assert result[2]["duplicate_of"] is None
    assert result[2]["duplicates"] == 1


def test_urteil_gilt_fuer_alle_regionalausgaben(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from magda.api import app

    monkeypatch.setattr(config, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(label_audit.config, "AUDIT_DIR", tmp_path)
    label_audit.save_audit({
        "label": "APP_PRICE",
        "labels_from": "sonnet-5",
        "candidates": [
            {"key": "a_p1:5", "context": "x «1.69» y", "current_label": "PRICE",
             "source": "candidate"},
            {"key": "b_p1:5", "context": "x «1.69» y", "current_label": "PRICE",
             "source": "candidate"},
        ],
        "verdicts": {},
    })

    client = TestClient(app)
    response = client.put("/api/audit/APP_PRICE/a_p1:5", json={"verdict": "wrong"})

    assert response.status_code == 200
    assert response.json()["applied_to"] == 2
    stored = json.loads((tmp_path / "APP_PRICE.json").read_text())
    assert stored["verdicts"]["b_p1:5"]["verdict"] == "wrong"


def test_urteile_fassen_die_labels_nicht_an(tmp_path, monkeypatch):
    """Ein Klick in der Oberfläche darf die Referenz nicht stillschweigend ändern."""
    from fastapi.testclient import TestClient

    from magda.api import app

    monkeypatch.setattr(config, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(label_audit.config, "AUDIT_DIR", tmp_path)
    label_audit.save_audit({
        "label": "APP_PRICE",
        "labels_from": "sonnet-5",
        "candidates": [{"key": "a_p1:5", "context": "x «1.69» y",
                        "current_label": "PRICE", "source": "candidate"}],
        "verdicts": {},
    })
    label_file = config.labeled_dir("sonnet-5") / "1342812_p3.json"
    before = label_file.read_bytes() if label_file.exists() else None

    TestClient(app).put("/api/audit/APP_PRICE/a_p1:5", json={"verdict": "wrong"})

    if before is not None:
        assert label_file.read_bytes() == before


def test_unbekanntes_ziel_label_wird_abgelehnt(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from magda.api import app

    monkeypatch.setattr(config, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(label_audit.config, "AUDIT_DIR", tmp_path)
    label_audit.save_audit({
        "label": "APP_PRICE",
        "labels_from": "sonnet-5",
        "candidates": [{"key": "a_p1:5", "context": "x «1.69» y",
                        "current_label": "PRICE", "source": "candidate"}],
        "verdicts": {},
    })

    response = TestClient(app).put(
        "/api/audit/APP_PRICE/a_p1:5", json={"verdict": "wrong", "should_be": "../gold"}
    )

    assert response.status_code == 422
