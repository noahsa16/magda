"""API-Weg für die Gruppierungsreferenz unter gold/offers/.

Fünfte Schreibstelle der API und dieselbe enge Beschränkung wie die anderen
vier: nur gold/offers/, nur mit passendem `words_hash`, nur geprüfte Indizes.
Nach `data/labeled/` schreibt auch dieser Weg nicht - dort liegt die Referenz,
gegen die anschließend gemessen wird.
"""

import json

import pytest
from fastapi.testclient import TestClient

from magda import api, config
from magda.gold import words_hash

SEITE = {
    "page_id": "1_p1",
    "width": 595.28,
    "height": 841.89,
    "words": [
        {"text": "Landliebe", "bbox": [72.4, 310.2, 198.6, 324.8]},
        {"text": "Butter", "bbox": [72.4, 326.0, 198.6, 340.0]},
        {"text": "1.29", "bbox": [210.5, 305.0, 265.3, 348.1]},
    ],
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("WORDS_DIR", "GOLD_DIR", "LABELED_DIR", "IMAGES_DIR"):
        d = tmp_path / name.lower()
        d.mkdir()
        monkeypatch.setattr(config, name, d)
    monkeypatch.setattr(config, "CATALOGS_FILE", tmp_path / "catalogs.json")
    with open(config.WORDS_DIR / "1_p1.json", "w") as f:
        json.dump(SEITE, f)
    return TestClient(api.app)


def _hash():
    return words_hash(SEITE["words"])


def test_unberuehrte_seite_liefert_leere_gruppen(client):
    antwort = client.get("/api/offer-gold/1_p1")

    assert antwort.status_code == 200
    assert antwort.json()["groups"] == []
    assert antwort.json()["status"] == "untouched"
    assert antwort.json()["words_hash"] == _hash()


def test_speichert_und_liest_gruppen_zurueck(client):
    client.put("/api/offer-gold/1_p1", json={
        "words_hash": _hash(), "status": "done", "annotator": "noah",
        "groups": [[0, 1, 2]],
    })

    antwort = client.get("/api/offer-gold/1_p1")

    assert antwort.json()["groups"] == [[0, 1, 2]]
    assert antwort.json()["status"] == "done"


def test_speichert_unter_gold_offers_nicht_neben_die_span_annotation(client):
    """Sonst überschreibt die Gruppierung die handannotierten Spans derselben Seite."""
    client.put("/api/offer-gold/1_p1", json={
        "words_hash": _hash(), "status": "done", "annotator": "", "groups": [[0]],
    })

    assert (config.GOLD_DIR / "offers" / "1_p1.json").exists()
    assert not (config.GOLD_DIR / "1_p1.json").exists()


def test_veraltete_wortliste_wird_abgelehnt(client):
    """Derselbe 409 wie bei den Spans - die Indizes zeigen sonst woanders hin."""
    antwort = client.put("/api/offer-gold/1_p1", json={
        "words_hash": "veraltet", "status": "done", "annotator": "", "groups": [[0]],
    })

    assert antwort.status_code == 409


def test_wortindex_ausserhalb_der_seite_wird_abgelehnt(client):
    antwort = client.put("/api/offer-gold/1_p1", json={
        "words_hash": _hash(), "status": "done", "annotator": "", "groups": [[0, 99]],
    })

    assert antwort.status_code == 422


def test_wort_in_zwei_angeboten_wird_abgelehnt(client):
    """Die Prüfung gehört hierher, nicht erst in den Ladepfad der Messung."""
    antwort = client.put("/api/offer-gold/1_p1", json={
        "words_hash": _hash(), "status": "done", "annotator": "", "groups": [[0, 1], [1]],
    })

    assert antwort.status_code == 422
    assert "zwei" in antwort.json()["detail"].lower() or "doppelt" in antwort.json()["detail"].lower()


def test_leeres_angebot_wird_abgelehnt(client):
    antwort = client.put("/api/offer-gold/1_p1", json={
        "words_hash": _hash(), "status": "done", "annotator": "", "groups": [[]],
    })

    assert antwort.status_code == 422


def test_uebersicht_nennt_stand_und_veraltung(client):
    client.put("/api/offer-gold/1_p1", json={
        "words_hash": _hash(), "status": "done", "annotator": "noah", "groups": [[0, 1]],
    })

    zeilen = client.get("/api/offer-gold").json()

    assert len(zeilen) == 1
    assert zeilen[0]["page_id"] == "1_p1"
    assert zeilen[0]["status"] == "done"
    assert zeilen[0]["num_offers"] == 1
    assert zeilen[0]["stale"] is False


def test_unbekannte_seite_ist_ein_404(client):
    assert client.get("/api/offer-gold/gibtsnicht").status_code == 404
