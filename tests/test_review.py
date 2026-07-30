"""Die Durchsicht-Reihenfolge entscheidet, was die Gold-Messung am Ende wert
ist. Dreissig Seiten aus demselben Duplikat-Cluster messen dreissigmal
dieselbe Vorlage."""

import json

import pytest

from magda import config, review


@pytest.fixture
def daten(tmp_path, monkeypatch):
    """Verlegt words/, gold/ und splits/ ins tmp-Verzeichnis.

    Gepatcht wird auf config, weil review.py die Pfade zur Laufzeit liest.
    """
    for name in ("words", "gold", "splits"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(config, "WORDS_DIR", tmp_path / "words")
    monkeypatch.setattr(config, "GOLD_DIR", tmp_path / "gold")
    monkeypatch.setattr(config, "SPLITS_DIR", tmp_path / "splits")
    return tmp_path


def seite(basis, page_id, woerter, status="in_progress"):
    with open(basis / "words" / f"{page_id}.json", "w") as f:
        json.dump({"page_id": page_id, "width": 100, "height": 100,
                   "words": [{"text": w, "bbox": [0, 0, 1, 1]} for w in woerter]}, f)
    with open(basis / "gold" / f"{page_id}.json", "w") as f:
        json.dump({"page_id": page_id, "words_hash": "x", "status": status,
                   "annotator": "test", "spans": []}, f)


def splits(basis, **rollen):
    with open(basis / "splits" / "split.json", "w") as f:
        json.dump(rollen, f)


# Zwei fast gleiche Seiten (ein Wort Unterschied) und eine deutlich andere.
GLEICH_A = ["Butter", "Milch", "Käse", "Brot", "Wurst", "Apfel"]
GLEICH_B = ["Butter", "Milch", "Käse", "Brot", "Wurst", "Birne"]
ANDERS = ["Bohrmaschine", "Akku", "Zange", "Hammer", "Säge", "Nagel"]


def test_je_cluster_nur_eine_seite(daten):
    seite(daten, "100_p1", GLEICH_A)
    seite(daten, "100_p2", GLEICH_B)
    seite(daten, "100_p3", ANDERS)
    splits(daten, train=[], dev=[], test=["100_p1", "100_p2", "100_p3"])

    ids = [v["page_id"] for v in review.queue(None, None)]

    assert len(ids) == 2, "die beiden fast gleichen Seiten zählen als eine"
    assert "100_p3" in ids


def test_cluster_mit_freigegebenem_vertreter_faellt_weg(daten):
    """Ist eine Seite des Clusters durchgesehen, bringt die Schwester nichts."""
    seite(daten, "100_p1", GLEICH_A, status="done")
    seite(daten, "100_p2", GLEICH_B)
    seite(daten, "100_p3", ANDERS)
    splits(daten, train=[], dev=[], test=["100_p1", "100_p2", "100_p3"])

    ids = [v["page_id"] for v in review.queue(None, None)]

    assert ids == ["100_p3"]


def test_testseiten_kommen_zuerst(daten):
    seite(daten, "100_p1", ANDERS)
    seite(daten, "200_p1", ["Zelt", "Schlafsack", "Isomatte", "Lampe"])
    splits(daten, train=["100_p1"], dev=[], test=["200_p1"])

    vorschlaege = review.queue(None, None)

    assert vorschlaege[0]["page_id"] == "200_p1"
    assert vorschlaege[0]["split"] == "test"


def test_ohne_offene_seiten_ist_die_liste_leer(daten):
    seite(daten, "100_p1", ANDERS, status="done")
    splits(daten, train=[], dev=[], test=["100_p1"])

    assert review.queue(None, None) == []


def test_limit_wird_eingehalten(daten):
    for i in range(5):
        seite(daten, f"100_p{i}", [f"Ware{i}", f"Sorte{i}", f"Preis{i}"])
    splits(daten, train=[], dev=[], test=[f"100_p{i}" for i in range(5)])

    assert len(review.queue(None, None, limit=3)) == 3


def test_abdeckung_zaehlt_cluster_nicht_seiten(daten):
    seite(daten, "100_p1", GLEICH_A, status="done")
    seite(daten, "100_p2", GLEICH_B)
    seite(daten, "100_p3", ANDERS)
    splits(daten, train=[], dev=[], test=["100_p1", "100_p2", "100_p3"])

    deckung = review.abdeckung()

    assert deckung["test_seiten"] == 3
    assert deckung["cluster"] == 2
    assert deckung["abgedeckt"] == 1


def test_default_pair_meidet_denselben_arm(monkeypatch, tmp_path):
    """mistral-…-promptv1 ist dasselbe Modell mit dem alten Prompt. Als zweite
    Meinung taugt es nicht – die Uneinigkeit misst dann die Prompt-Änderung."""
    labeled = tmp_path / "labeled"
    for name, anzahl in [("mistral-x", 10), ("mistral-x-promptv1", 10), ("qwen", 8)]:
        (labeled / name).mkdir(parents=True)
        for i in range(anzahl):
            (labeled / name / f"s{i}.json").write_text("{}")
    monkeypatch.setattr(config, "LABELED_DIR", labeled)

    a, b = review.default_pair()

    assert a == "mistral-x-promptv1" or a == "mistral-x"
    assert b == "qwen"
