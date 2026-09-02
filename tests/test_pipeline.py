"""Der Pfad "fremdes PDF rein, Angebote raus" - ohne Modell, ohne data/.

Ersetzt in diesen Tests: ein Fake-NER (vorgegebene BIO-Tags je Seite statt
eines echten Forward-Pass) und ein Fake-Paarmodell (gruppiert probeweise alle
Entities einer Seite in ein Angebot). Beides reicht, um die Mechanik von
`magda.pipeline` zu pruefen - Seiten zerlegen, Sliding-Window-Aufruf
durchreichen, Gruppierung anwenden, Export in drei Formate. Ob eine
Gruppierung inhaltlich gut ist, decken `test_offer_model.py` und
`test_offers.py` ab.
"""

import csv
import io
import sqlite3

import fitz
import pytest

from magda import offers, pipeline
from magda.config import variant_spec

pytest.importorskip("torch")  # nur fuer Vollstaendigkeit des Envs, hier nicht direkt gebraucht


def _build_pdf() -> bytes:
    """Vier Seiten: zwei mit einem klaren Angebot, eine mit einer Entity ohne
    Preis (kein Variantentyp - prueft die CSV-Rueckfallzeile), eine ganz ohne
    Text (prueft `pages_without_text`)."""
    doc = fitz.open()

    page = doc.new_page(width=200, height=200)
    page.insert_text((10, 30), "Landliebe", fontsize=12)
    page.insert_text((10, 50), "Butter", fontsize=12)
    page.insert_text((100, 30), "1.29", fontsize=12)

    page = doc.new_page(width=200, height=200)
    page.insert_text((10, 30), "Milch", fontsize=12)
    page.insert_text((100, 30), "0.99", fontsize=12)

    page = doc.new_page(width=200, height=200)
    page.insert_text((10, 30), "Marke", fontsize=12)

    doc.new_page(width=200, height=200)  # leer, kein Textlayer

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# BIO-Tags je Seite, in Aufrufreihenfolge - die leere vierte Seite ruft das
# Fake-NER nie auf (0 Woerter fuehren zu einem fruehen `continue`).
_TAGS_BY_PAGE = [
    ["B-BRAND", "B-PRODUCT", "B-PRICE"],
    ["B-PRODUCT", "B-PRICE"],
    ["B-BRAND"],
]


def _make_fake_predict_pages(tag_sequences):
    calls = iter(tag_sequences)

    def fake(pages, model, tokenizer, spec, *, no_windows=False, images_dir=None,
             on_windows_built=None):
        assert len(pages) == 1, "extract_offers ruft predict_pages je Seite einzeln auf"
        tags = next(calls)
        words = pages[0]["words"]
        assert len(tags) == len(words), (
            f"Fake-NER erwartet {len(tags)} Woerter, Seite hat {len(words)}"
        )
        scores = [0.9] * len(tags)
        return [(tags, scores)]

    return fake


class _FakePairModel:
    """Gruppiert probeweise alle Entities einer Seite in ein Angebot.

    Fuer die Pipeline-Mechanik reicht das - die Gruppierungsqualitaet des
    echten Paarmodells deckt `test_offer_model.py` ab, nicht diese Datei.
    """

    threshold = 0.5
    blocks = ("types", "geometry_base")  # DEFAULT_BLOCKS, kein Farbmerkmal noetig

    def group_page(self, page, threshold):
        entities = [e for e in offers.entities_from_page(page) if e.type in offers.VALUE_TYPES]
        return [list(range(len(entities)))] if entities else []

    def score_page(self, page):
        entities = [e for e in offers.entities_from_page(page) if e.type in offers.VALUE_TYPES]
        return {
            (i, j): 0.8
            for i in range(len(entities))
            for j in range(i + 1, len(entities))
        }


def _fake_models() -> pipeline.LoadedModels:
    return pipeline.LoadedModels(
        variant="gbert",
        checkpoint="fake/checkpoint",
        ner_model=None,
        tokenizer=None,
        spec=variant_spec("gbert"),
        pair_model=_FakePairModel(),
        pairs_checkpoint="fake/pairs.pt",
    )


def _run(monkeypatch):
    import magda.predict as predict_module

    monkeypatch.setattr(predict_module, "predict_pages", _make_fake_predict_pages(_TAGS_BY_PAGE))
    result = pipeline.extract_offers(_build_pdf(), _fake_models(), progress=None)
    return result


def test_seiten_ohne_textlayer_werden_ausgewiesen_statt_uebersprungen(monkeypatch):
    result = _run(monkeypatch)

    assert len(result.pages) == 4
    assert result.pages_without_text == [f"{result.doc_id}_p4"]
    # Die leere Seite bleibt trotzdem im Ergebnis, nur ohne Inhalt.
    leere_seite = result.pages[3]
    assert leere_seite.words == []
    assert leere_seite.offers == []


def test_zwei_seiten_ergeben_je_ein_angebot_aus_den_fake_tags(monkeypatch):
    result = _run(monkeypatch)

    assert len(result.pages[0].offers) == 1
    offer = result.pages[0].offers[0]
    assert offer.brand == "Landliebe"
    assert offer.product == "Butter"
    assert offer.price == "1.29"
    assert offer.page_index == 0

    assert len(result.pages[1].offers) == 1
    assert result.pages[1].offers[0].product == "Milch"
    assert result.pages[1].offers[0].price == "0.99"

    # Seite 3 hat nur eine BRAND-Entity, trotzdem ein (variantenloses) Angebot.
    assert len(result.pages[2].offers) == 1
    assert result.pages[2].offers[0].brand == "Marke"
    assert result.pages[2].offers[0].price is None

    assert len(result.offers) == 3  # ueber alle Seiten geflacht


def test_fortschritt_wird_je_seite_gemeldet(monkeypatch):
    calls = []
    import magda.predict as predict_module

    monkeypatch.setattr(predict_module, "predict_pages", _make_fake_predict_pages(_TAGS_BY_PAGE))
    result = pipeline.extract_offers(
        _build_pdf(), _fake_models(), progress=lambda i, n, s: calls.append((i, n, s))
    )

    assert [c[0] for c in calls] == [0, 1, 2, 3]
    assert all(c[1] == 4 for c in calls)
    assert all(c[2] >= 0 for c in calls)
    assert len(result.pages) == 4


def test_ner_bekommt_falsche_wortzahl_und_die_pruefung_schlaegt_an(monkeypatch):
    """Gegenprobe: eine absichtlich falsche Tag-Liste muss den Test rot machen,
    nicht still durchlaufen - sonst schuetzt die Assertion in der Fake-Funktion
    nichts."""
    import magda.predict as predict_module

    kaputte_tags = [["B-BRAND"], ["B-PRODUCT", "B-PRICE"], ["B-BRAND"]]  # erste Seite zu kurz
    monkeypatch.setattr(
        predict_module, "predict_pages", _make_fake_predict_pages(kaputte_tags)
    )
    with pytest.raises(AssertionError):
        pipeline.extract_offers(_build_pdf(), _fake_models(), progress=None)


def test_to_csv_hat_eine_zeile_je_variante_und_eine_fuer_variantenlose_angebote(monkeypatch):
    result = _run(monkeypatch)
    rows = list(csv.DictReader(io.StringIO(pipeline.to_csv(result))))

    # Zwei Angebote mit je einer Variante (PRICE gesetzt) plus ein
    # variantenloses Angebot (nur BRAND) - macht drei Zeilen, keine Angebote
    # verschwinden.
    assert len(rows) == 3
    prices = sorted(r["price"] or "" for r in rows)
    assert prices == ["", "0.99", "1.29"]
    variantenlose = [r for r in rows if r["brand"] == "Marke"]
    assert len(variantenlose) == 1
    assert variantenlose[0]["price"] == ""
    assert variantenlose[0]["position"] == "0"


def test_to_json_ist_ohne_binaerdaten_decodierbar(monkeypatch):
    import json

    result = _run(monkeypatch)
    payload = json.loads(pipeline.to_json(result))

    assert payload["doc_id"] == result.doc_id
    assert len(payload["pages"]) == 4
    assert payload["pages_without_text"] == [f"{result.doc_id}_p4"]
    assert payload["models"]["variant"] == "gbert"
    # gbert braucht kein Seitenbild - keine base64-Nutzlast im Export.
    assert all(p["png_base64"] is None for p in payload["pages"])


def test_to_sqlite_hat_dasselbe_schema_wie_write_sqlite(monkeypatch, tmp_path):
    result = _run(monkeypatch)
    pipeline_db = tmp_path / "pipeline.sqlite"
    totals = pipeline.to_sqlite(result, pipeline_db)

    assert totals["offers"] == 3
    assert totals["entities"] == 3 + 2 + 1  # Landliebe/Butter/1.29, Milch/0.99, Marke

    reference_db = tmp_path / "reference.sqlite"
    reference_page = {
        "page_id": "ref_p1",
        "width": 100,
        "height": 100,
        "words": [{"text": "Test", "bbox": [0, 0, 10, 10]}],
        "tags": ["O"],
    }
    offers.write_sqlite([reference_page], reference_db, source="ref", grouping=offers.cluster_page)

    with sqlite3.connect(pipeline_db) as conn_a, sqlite3.connect(reference_db) as conn_b:
        columns_a = {row[1] for row in conn_a.execute("pragma table_info(offers)")}
        columns_b = {row[1] for row in conn_b.execute("pragma table_info(offers)")}
        assert columns_a == columns_b

        variant_columns_a = {row[1] for row in conn_a.execute("pragma table_info(offer_variants)")}
        variant_columns_b = {row[1] for row in conn_b.execute("pragma table_info(offer_variants)")}
        assert variant_columns_a == variant_columns_b

        rows = conn_a.execute(
            "select source, grouper, product, brand, price from offers order by offer_index"
        ).fetchall()
    assert rows[0][0] == "pipeline:gbert"
    assert rows[0][1] == "pair-model"
    assert ("Landliebe", "Butter", "1.29") in [(r[3], r[2], r[4]) for r in rows]
