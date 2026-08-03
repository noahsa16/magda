import json
import sqlite3

from magda.offers import cluster_page, entities_from_page, write_sqlite


def _word(text, x0, y0, x1, y1):
    return {"text": text, "bbox": [x0, y0, x1, y1]}


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

    assert stats == {"pages": 1, "offers": 1, "entities": 3}
    with sqlite3.connect(db) as conn:
        offer = conn.execute(
            "select source, page_id, brand, product, price from offers"
        ).fetchone()
        entities = conn.execute(
            "select entity_type, text, bbox, context_before, context_after "
            "from offer_entities order by word_start"
        ).fetchall()

    assert offer == ("test-model", "1_p1", "Marke", "Produkt", "1.99")
    assert entities[0][0:2] == ("BRAND", "Marke")
    assert json.loads(entities[0][2]) == [40, 100, 80, 112]
    assert entities[0][4] == "Produkt 1.99"
