"""Tests für den Modell-gegen-Modell-Vergleich.

Pfade werden wie überall als config.X zur Laufzeit gelesen, damit die
Fixtures sie auf ein Temp-Verzeichnis umbiegen können.
"""

import json

import pytest

from magda import agreement, config


@pytest.fixture
def labels(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LABELED_DIR", tmp_path / "labeled")

    def write(model: str, page_id: str, tags: list[str]):
        directory = config.labeled_dir(model)
        directory.mkdir(parents=True, exist_ok=True)
        words = [{"text": f"w{i}", "bbox": [0, 0, 1, 1]} for i in range(len(tags))]
        with open(directory / f"{page_id}.json", "w") as f:
            json.dump({"page_id": page_id, "words": words, "tags": tags}, f)

    return write


def test_seiten_ohne_gegenstueck_zaehlen_nicht_mit(labels):
    labels("alpha", "1_p1", ["O"])
    labels("alpha", "1_p2", ["O"])
    labels("beta", "1_p1", ["O"])

    assert agreement.common_pages("alpha", "beta") == ["1_p1"]


def test_einigkeit_wird_getrennt_von_gemeinsamem_schweigen_gezaehlt():
    """Auf einer Prospektseite trägt jedes dritte Wort kein Label. Zählt man
    "beide sagen O" als Übereinstimmung, sieht jedes Modellpaar einig aus."""
    a = ["B-PRICE", "O", "O", "O"]
    b = ["B-OLD_PRICE", "O", "O", "O"]

    result = agreement.compare_page(a, b)

    assert result["agreement"] == 0.75
    # Auf den Wörtern, um die es geht, sind sie sich zu 0 % einig.
    assert result["agreement_on_labeled"] == 0.0
    assert result["labeled_words"] == 1


def test_unterschiedlich_lange_taglisten_werden_nicht_verglichen():
    """Dann zeigen die Indizes auf verschiedene Wörter – jeder Vergleich wäre
    ausgedacht. Derselbe Grund, aus dem Gold-Dateien einen words_hash tragen."""
    assert agreement.compare_page(["O", "O"], ["O"]) is None


def test_verwechslungsmatrix_trennt_typfehler_von_ausgelassenem_label(labels):
    labels("alpha", "1_p1", ["B-BRAND", "B-PRICE", "O"])
    labels("beta", "1_p1", ["B-PRODUCT", "O", "O"])

    result = agreement.compare_models("alpha", "beta")

    # BRAND gegen PRODUCT ist ein Typfehler ...
    assert result["confusion"] == {"BRAND": {"PRODUCT": 1}}
    # ... "alpha labelt, beta nicht" ist etwas anderes und steht separat.
    assert result["only_a"] == {"PRICE": 1}
    assert result["only_b"] == {}


def test_uneinigste_seite_steht_oben(labels):
    """Die Reihenfolge ist der Zweck: sie sagt, welche Seite als Nächstes von
    Hand annotiert gehört."""
    labels("alpha", "1_p1", ["B-PRICE", "B-PRICE"])
    labels("beta", "1_p1", ["B-PRICE", "B-PRICE"])
    labels("alpha", "1_p2", ["B-PRICE", "B-PRICE"])
    labels("beta", "1_p2", ["B-BRAND", "B-BRAND"])

    ranking = agreement.disagreement_ranking("alpha", "beta")

    assert [p["page_id"] for p in ranking] == ["1_p2", "1_p1"]
    assert ranking[0]["agreement"] == 0.0
    assert ranking[1]["agreement"] == 1.0


def test_einigkeit_je_label_zeigt_wo_die_unsicherheit_sitzt(labels):
    labels("alpha", "1_p1", ["B-PRICE", "B-PRICE", "B-PRODUCT", "B-PRODUCT"])
    labels("beta", "1_p1", ["B-PRICE", "B-PRICE", "B-PRODUCT", "B-BRAND"])

    scores = agreement.label_agreement("alpha", "beta")

    assert scores["PRICE"] == 1.0
    assert scores["PRODUCT"] < 1.0
    # Labels ohne ein einziges Vorkommen tauchen nicht auf – eine Zeile
    # "QUANTITY 0 %" wäre irreführend, wenn es keine gibt.
    assert "QUANTITY" not in scores
