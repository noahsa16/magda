"""Welche Seiten die Gruppierungsreferenz zuerst braucht.

Von Hand annotiert werden 30 bis 50 Seiten, nicht 196. Welche 30, entscheidet
ueber den Wert der Messung - und die Antwort steht diesmal in der Messung
selbst: `magda offers-report` kann dort nicht urteilen, wo kein Grundpreis
steht. Genau diese Seiten muss die Handarbeit abdecken, sonst annotiert man
nach, was die Rechnung ohnehin schon prueft.

Gegengewicht ist die Clustergroesse: Penny druckt 44 fast gleiche
Regionalausgaben, und eine Vorlage, die fuer elf Seiten steht, ist mehr wert
als eine Einzelseite. Beide Ranglisten kommen abwechselnd zum Zug.
"""

import json

import pytest

from magda import config, review


@pytest.fixture
def daten(tmp_path, monkeypatch):
    for name in ("gold", "splits"):
        (tmp_path / name).mkdir()
    (tmp_path / "gold" / "offers").mkdir()
    monkeypatch.setattr(config, "GOLD_DIR", tmp_path / "gold")
    monkeypatch.setattr(config, "SPLITS_DIR", tmp_path / "splits")
    return tmp_path


def splits(basis, **rollen):
    with open(basis / "splits" / "split.json", "w") as f:
        json.dump(rollen, f)


def annotiert(basis, page_id):
    with open(basis / "gold" / "offers" / f"{page_id}.json", "w") as f:
        json.dump({"page_id": page_id, "words_hash": "x", "status": "done",
                   "annotator": "test", "groups": [[0]]}, f)


def _word(text, x0, y0, x1, y1):
    return {"text": text, "bbox": [x0, y0, x1, y1]}


def food(page_id, marke="Landliebe"):
    """Menge und Grundpreis vorhanden - die Rechnung kann urteilen."""
    return {
        "page_id": page_id,
        "width": 500,
        "height": 800,
        "words": [
            _word(marke, 40, 100, 90, 112),
            _word("Butter", 40, 116, 90, 128),
            _word("250 g", 40, 132, 90, 144),
            _word("(1 kg = 8.00)", 40, 148, 140, 160),
            _word("2.00", 200, 100, 250, 140),
        ],
        "tags": ["B-BRAND", "B-PRODUCT", "B-QUANTITY", "B-UNIT_PRICE", "B-PRICE"],
    }


def nonfood(page_id, artikel="Bohrmaschine"):
    """Kein Grundpreis - die Rechnung kann hier grundsaetzlich nicht urteilen."""
    return {
        "page_id": page_id,
        "width": 500,
        "height": 800,
        "words": [
            _word(artikel, 40, 100, 120, 112),
            _word("Akkuschrauber", 40, 116, 130, 128),
            _word("Zange", 40, 132, 90, 144),
            _word("Bitsatz", 40, 148, 90, 160),
            _word("49.99", 200, 100, 250, 140),
        ],
        "tags": ["B-PRODUCT", "B-PRODUCT", "B-PRODUCT", "B-PRODUCT", "B-PRICE"],
    }


def test_der_blinde_fleck_steht_an_erster_stelle(daten):
    """Wo die Rechnung nicht urteilen kann, ist Handarbeit alternativlos."""
    splits(daten, train=["f1", "n1"], dev=[], test=[])

    vorschlaege = review.offer_queue([food("f1"), nonfood("n1")])

    assert vorschlaege[0]["page_id"] == "n1"
    assert vorschlaege[0]["reason"] == "luecke"


def test_grosse_vorlagen_kommen_trotzdem_dran(daten):
    """Nur nach der Luecke sortiert, deckte die Referenz kein einziges Lebensmittel ab."""
    splits(daten, train=["f1", "f2", "f3", "n1", "n2"], dev=[], test=[])
    pages = [food("f1"), food("f2", "Landliebe"), food("f3", "Landliebe"),
             nonfood("n1"), nonfood("n2", "Stichsaege")]

    vorschlaege = review.offer_queue(pages, limit=2)

    assert {v["reason"] for v in vorschlaege} == {"luecke", "masse"}


def test_je_duplikat_cluster_nur_eine_seite(daten):
    """Sonst annotiert man dreimal dieselbe Regionalausgabe."""
    splits(daten, train=["n1", "n2"], dev=[], test=[])

    vorschlaege = review.offer_queue([nonfood("n1"), nonfood("n2")])

    assert len(vorschlaege) == 1
    assert vorschlaege[0]["represents"] == ["n2"]
    assert vorschlaege[0]["cluster_size"] == 2


def test_testseiten_bleiben_aussen_vor(daten):
    """Der Testsplit ist zum Messen am Ende da, nicht zum Entwickeln."""
    splits(daten, train=["f1"], dev=[], test=["n1"])

    vorschlaege = review.offer_queue([food("f1"), nonfood("n1")])

    assert [v["page_id"] for v in vorschlaege] == ["f1"]


def test_bereits_annotierter_cluster_faellt_weg(daten):
    """Eine fertige Seite vertritt ihren Cluster schon."""
    splits(daten, train=["n1", "n2", "f1"], dev=[], test=[])
    annotiert(daten, "n1")

    vorschlaege = review.offer_queue([nonfood("n1"), nonfood("n2"), food("f1")])

    assert [v["page_id"] for v in vorschlaege] == ["f1"]


def test_ohne_split_wird_nicht_geraten(daten):
    """Ohne split.json ist "nur Train und Dev" nicht durchsetzbar."""
    with pytest.raises(FileNotFoundError):
        review.offer_queue([food("f1")])
