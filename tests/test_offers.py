import argparse
import json
import sqlite3

import pytest

from magda.offers import (
    Entity,
    Offer,
    Variant,
    _quantity_in_unit,
    cluster_page,
    entities_from_page,
    write_sqlite,
)


def _word(text, x0, y0, x1, y1):
    return {"text": text, "bbox": [x0, y0, x1, y1]}


def _entity(entity_type, text, start):
    return Entity(id=start, type=entity_type, text=text, bbox=(0.0, 0.0, 1.0, 1.0),
                  start=start, end=start + 1, context_before="", context_after="")


def test_mehrfachpackung_multipliziert_menge_mit_multiplikator():
    """"2 x 350 g" ist 0.7 kg, nicht 0.35 - der belegte Fall aus CLAUDE.md."""
    assert _quantity_in_unit("2 x 350 g", "kg") == 0.7
    assert _quantity_in_unit("6x1,5 l", "l") == 9.0
    assert _quantity_in_unit("2 × 350 g", "kg") == 0.7


def test_menge_ohne_multiplikator_bleibt_unveraendert():
    assert _quantity_in_unit("800-g-Packung", "kg") == 0.8
    assert _quantity_in_unit("250 g", "kg") == 0.25
    assert _quantity_in_unit("kein Zahlwort hier", "kg") is None


def test_entities_enthalten_text_box_und_kontext():
    page = {
        "page_id": "1_p1",
        "words": [
            _word("vorher", 0, 0, 10, 10),
            _word("Coca", 10, 0, 20, 10),
            _word("Cola", 21, 0, 31, 10),
            _word("nachher", 32, 0, 42, 10),
        ],
        "tags": ["O", "B-BRAND", "I-BRAND", "O"],
    }

    entities = entities_from_page(page, context_window=1)

    assert len(entities) == 1
    assert entities[0].text == "Coca Cola"
    assert entities[0].bbox == (10, 0, 31, 10)
    assert entities[0].context_before == "vorher"
    assert entities[0].context_after == "nachher"


def test_cluster_ordnen_preis_produkt_und_marke_ueber_layout_zu():
    page = {
        "page_id": "1_p1",
        "width": 500,
        "height": 800,
        "words": [
            _word("COCA-COLA", 40, 100, 110, 112),
            _word("Getränk", 40, 116, 90, 128),
            _word("0.99", 400, 105, 450, 145),
            _word("BARILLA", 40, 500, 90, 512),
            _word("Pasta", 40, 516, 80, 528),
            _word("1.29", 400, 505, 450, 545),
        ],
        "tags": [
            "B-BRAND",
            "B-PRODUCT",
            "B-PRICE",
            "B-BRAND",
            "B-PRODUCT",
            "B-PRICE",
        ],
    }

    offers = cluster_page(page)

    assert len(offers) == 2
    assert offers[0].values()["brand"] == "COCA-COLA"
    assert offers[0].values()["product"] == "Getränk"
    assert offers[0].values()["price"] == "0.99"
    assert offers[1].values()["brand"] == "BARILLA"
    assert offers[1].values()["product"] == "Pasta"
    assert offers[1].values()["price"] == "1.29"


def test_variants_paart_mengen_und_preise_positionsweise():
    """Pfanne: 20 cm 9.99 / 24 cm 14.99 / 28 cm 17.99 - drei Groessen, drei
    Preise, je positionsweise in Lesereihenfolge gepaart (belegter Fall aus
    CLAUDE.md: 26 von 26 aufloesbaren Faellen gehen positionsweise auf, 0 nur
    in anderer Reihenfolge). Die Entities stehen absichtlich nicht in
    Lesereihenfolge in der Liste - `variants()` sortiert nach Wortindex, nicht
    nach Listenposition."""
    entities = [
        _entity("PRICE", "17.99", 6),
        _entity("QUANTITY", "20 cm", 1),
        _entity("PRICE", "9.99", 2),
        _entity("PRODUCT", "Pfanne", 0),
        _entity("QUANTITY", "28 cm", 5),
        _entity("QUANTITY", "24 cm", 3),
        _entity("PRICE", "14.99", 4),
    ]
    offer = Offer(id=0, page_id="p1", bbox=(0, 0, 1, 1), entities=entities)

    variants = offer.variants()

    assert [v.position for v in variants] == [0, 1, 2]
    assert [(v.quantity, v.price) for v in variants] == [
        ("20 cm", "9.99"), ("24 cm", "14.99"), ("28 cm", "17.99"),
    ]


def test_variants_mit_je_einer_entity_ergibt_genau_eine_variante():
    entities = [
        _entity("PRODUCT", "Marke", 0),
        _entity("QUANTITY", "250 g", 1),
        _entity("PRICE", "1.99", 2),
    ]
    offer = Offer(id=0, page_id="p1", bbox=(0, 0, 1, 1), entities=entities)

    assert offer.variants() == [
        Variant(position=0, quantity="250 g", price="1.99",
                old_price=None, unit_price=None, app_price=None)
    ]


def test_variants_ohne_relevante_typen_ist_leer():
    offer = Offer(id=0, page_id="p1", bbox=(0, 0, 1, 1),
                  entities=[_entity("BRAND", "Marke", 0)])

    assert offer.variants() == []


def test_sqlite_export_schreibt_angebote_und_entity_context(tmp_path):
    page = {
        "page_id": "1_p1",
        "width": 500,
        "height": 800,
        "words": [
            _word("Marke", 40, 100, 80, 112),
            _word("Produkt", 40, 116, 90, 128),
            _word("1.99", 400, 105, 450, 145),
        ],
        "tags": ["B-BRAND", "B-PRODUCT", "B-PRICE"],
    }
    db = tmp_path / "offers.sqlite"

    stats = write_sqlite([page], db, source="test-model")

    assert stats == {"pages": 1, "offers": 1, "entities": 3, "variants": 1}
    with sqlite3.connect(db) as conn:
        offer = conn.execute(
            "select source, page_id, brand, product, price from offers"
        ).fetchone()
        entities = conn.execute(
            "select entity_type, text, bbox, context_before, context_after "
            "from offer_entities order by word_start"
        ).fetchall()
        variant = conn.execute(
            "select position, quantity, price, old_price, unit_price, app_price "
            "from offer_variants"
        ).fetchone()

    assert offer == ("test-model", "1_p1", "Marke", "Produkt", "1.99")
    assert variant == (0, None, "1.99", None, None, None)
    assert entities[0][0:2] == ("BRAND", "Marke")
    assert json.loads(entities[0][2]) == [40, 100, 80, 112]
    assert entities[0][4] == "Produkt 1.99"


def test_write_sqlite_nutzt_uebergebene_gruppierungsfunktion(tmp_path):
    """`write_sqlite` ruft nicht mehr fest `cluster_page` - jede Callable
    Seite -> list[Offer] muss durchgereicht werden, samt ihres Namens in der
    neuen Spalte `grouper`.

    Die Fake-Gruppierung liefert absichtlich ein anderes Ergebnis als
    `cluster_page` (0 statt 1 Angebot fuer diese Seite) - sonst waere der
    Test gruen, auch wenn `write_sqlite` den Parameter ignoriert und heimlich
    weiter `cluster_page` aufruft."""
    page = {
        "page_id": "1_p1",
        "width": 500,
        "height": 800,
        "words": [_word("Marke", 40, 100, 80, 112), _word("Produkt", 40, 116, 90, 128)],
        "tags": ["B-BRAND", "B-PRODUCT"],
    }
    db = tmp_path / "offers.sqlite"
    assert len(cluster_page(page)) == 1  # zur Kontrolle: die Heuristik faende hier ein Angebot

    def fake_grouping(page):
        return []

    stats = write_sqlite([page], db, source="test-model", grouping=fake_grouping, grouper="fake")

    assert stats["offers"] == 0
    with sqlite3.connect(db) as conn:
        rows = conn.execute("select source, grouper from offers").fetchall()
    assert rows == []


def test_write_sqlite_ohne_grouper_bleibt_bei_der_heuristik(tmp_path):
    """Rueckwaertskompatibilitaet: alte Aufrufe ohne `grouping`/`grouper`
    verhalten sich wie vor der Aenderung."""
    page = {
        "page_id": "1_p1",
        "width": 500,
        "height": 800,
        "words": [_word("Marke", 40, 100, 80, 112), _word("Produkt", 40, 116, 90, 128)],
        "tags": ["B-BRAND", "B-PRODUCT"],
    }
    db = tmp_path / "offers.sqlite"

    write_sqlite([page], db, source="test-model")

    with sqlite3.connect(db) as conn:
        row = conn.execute("select grouper from offers").fetchone()
    assert row == ("heuristic",)


def test_pair_model_grouper_bricht_bei_fehlendem_checkpoint_klar_ab(tmp_path, capsys):
    """Kein stiller Rueckfall auf die Heuristik - `magda offers --grouper
    pair-model` ohne Checkpoint muss abbrechen, nicht weiterlaufen."""
    from magda.cli.offers import _pair_model_grouping

    missing = tmp_path / "does-not-exist.pt"
    parser = argparse.ArgumentParser()

    with pytest.raises(SystemExit) as beendet:
        _pair_model_grouping(missing, parser)

    assert beendet.value.code == 1
    assert "Checkpoint fehlt" in capsys.readouterr().err
