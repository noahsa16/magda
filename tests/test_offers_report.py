"""Tests fuer die Ablationsmessung (`magda.offers_report`) und die dafuer
noetigen Erweiterungen in `magda.offers` (`arithmetic`, `trace`).

Gegen synthetische Seiten, weil hier Verhalten *neu* entsteht - anders als
in `test_offers_belegte_faelle.py`, das dokumentiertes Verhalten auf echten
Seiten einfriert.
"""

from magda.offers import cluster_page
from magda.offers_report import collect, judge_page


def _word(text, x0, y0, x1, y1):
    return {"text": text, "bbox": [x0, y0, x1, y1]}


def _page_burger_fall(page_id="1_p1"):
    """Nachbau des belegten Falls (1351497_p10): der Preis sitzt geometrisch
    naeher an einem Nachbarprodukt als an dem Block, zu dem er rechnerisch
    gehoert (0,5 kg x 4.00 EUR/kg = 2.00)."""
    return {
        "page_id": page_id,
        "width": 500,
        "height": 800,
        "words": [
            _word("Wurst", 40, 100, 90, 112),
            _word("500", 40, 116, 60, 128),
            _word("g", 62, 116, 70, 128),
            _word("(1", 85, 116, 95, 128),
            _word("kg", 96, 116, 115, 128),
            _word("=", 116, 116, 122, 128),
            _word("4.00)", 123, 116, 150, 128),
            _word("Kaese", 300, 100, 350, 112),
            _word("2.00", 310, 100, 360, 140),
        ],
        "tags": [
            "B-PRODUCT",
            "B-QUANTITY", "I-QUANTITY",
            "B-UNIT_PRICE", "I-UNIT_PRICE", "I-UNIT_PRICE", "I-UNIT_PRICE",
            "B-PRODUCT",
            "B-PRICE",
        ],
    }


def test_arithmetic_true_liefert_das_bisherige_ergebnis():
    """Ohne die neuen Parameter - und mit `arithmetic=True` explizit - haengt
    der Preis am Block mit der passenden Grundpreis-Rechnung, nicht am
    geometrisch naeheren Nachbarn."""
    page = _page_burger_fall()

    offers = cluster_page(page)
    offers_explicit = cluster_page(page, arithmetic=True, trace=None)

    assert [o.values() for o in offers] == [o.values() for o in offers_explicit]
    wurst = next(o for o in offers if o.values()["product"] == "Wurst")
    kaese = next(o for o in offers if o.values()["product"] == "Kaese")
    assert wurst.values()["price"] == "2.00"
    assert kaese.values()["price"] is None


def test_ablation_ordnet_den_preis_dem_geometrisch_naeheren_block_zu():
    """`arithmetic=False` ueberspringt die Grundpreis-Rechnung: derselbe
    Preis landet jetzt bei Kaese, dem geometrisch naeheren Block."""
    page = _page_burger_fall()

    offers = cluster_page(page, arithmetic=False)

    wurst = next(o for o in offers if o.values()["product"] == "Wurst")
    kaese = next(o for o in offers if o.values()["product"] == "Kaese")
    assert wurst.values()["price"] is None
    assert kaese.values()["price"] == "2.00"


def test_trace_protokolliert_pfad_und_urteil_je_zuordnung():
    """`trace` haelt fest, dass die Zuordnung geometrisch geschah und dass die
    Arithmetik ihr widerspricht - der Preis passt rechnerisch zu Wurst, nicht
    zu dem Block, den die Geometrie tatsaechlich gewaehlt hat (Kaese)."""
    page = _page_burger_fall()
    trace = []

    cluster_page(page, arithmetic=False, trace=trace)

    assert len(trace) == 1
    match = trace[0]
    assert match.path == "geometric"
    assert match.price_type == "PRICE"
    assert match.value == 2.0
    assert match.target_block.values()["product"] == "Kaese"
    assert match.confirmed is False


def test_judge_page_zaehlt_den_burger_fall_als_contradicted():
    verdict = judge_page(_page_burger_fall())

    assert verdict.confirmed == 0
    assert verdict.contradicted == 1
    assert verdict.unjudgeable == 0


def test_ohne_grundpreis_ist_das_urteil_unjudgeable_nicht_confirmed():
    """Ein Preis ohne jede Menge-/Grundpreis-Angabe auf der Seite laesst sich
    nicht pruefen - das Urteil ist `unjudgeable`, kein `confirmed`."""
    page = {
        "page_id": "2_p1",
        "width": 500,
        "height": 800,
        "words": [
            _word("Kaese", 300, 100, 350, 112),
            _word("2.00", 310, 100, 360, 140),
        ],
        "tags": ["B-PRODUCT", "B-PRICE"],
    }

    verdict = judge_page(page)

    assert verdict.confirmed == 0
    assert verdict.contradicted == 0
    assert verdict.unjudgeable == 1


def test_block_mit_widersprechender_grundpreisrechnung_zaehlt_als_ohne_passende_paarung():
    """Der Fall aus CLAUDE.md (1351497_p20): ein Block mit Menge und
    Grundpreis, dessen tatsaechlicher Preis zu keiner Rechnung passt -
    0,5 kg x 4.00 EUR/kg = 2.00, aber der Preis lautet 9.99."""
    page = {
        "page_id": "3_p1",
        "width": 500,
        "height": 800,
        "words": [
            _word("Wurst", 40, 100, 90, 112),
            _word("500", 40, 116, 60, 128),
            _word("g", 62, 116, 70, 128),
            _word("(1", 85, 116, 95, 128),
            _word("kg", 96, 116, 115, 128),
            _word("=", 116, 116, 122, 128),
            _word("4.00)", 123, 116, 150, 128),
            _word("9.99", 40, 130, 90, 145),
        ],
        "tags": [
            "B-PRODUCT",
            "B-QUANTITY", "I-QUANTITY",
            "B-UNIT_PRICE", "I-UNIT_PRICE", "I-UNIT_PRICE", "I-UNIT_PRICE",
            "B-PRICE",
        ],
    }

    verdict = judge_page(page)

    assert verdict.offers_total == 1
    assert verdict.blocks_without_matching_pairing == 1


def test_block_mit_passender_grundpreisrechnung_zaehlt_nicht_als_ohne_passende_paarung():
    """Gegenprobe: passt die Rechnung, ist der Block unauffaellig."""
    page = _page_burger_fall()
    page["words"][-1] = _word("2.00", 40, 130, 90, 145)  # Preis direkt am eigenen Block

    verdict = judge_page(page)

    assert verdict.blocks_without_matching_pairing == 0


def test_collect_ueberspringt_seiten_ohne_wortliste_und_zaehlt_sie():
    report = collect([{"page_id": "ohne-worte"}])

    assert report.pages == 0
    assert report.pages_skipped == 1


def test_leerer_report_weist_fehlende_beurteilbare_zuordnungen_aus():
    """0 beurteilbare Zuordnungen sind kein 0-%- oder 100-%-Befund, sondern
    keiner - `confirmation_rate` ist dann None, nicht 0.0."""
    report = collect([])

    assert report.judged == 0
    assert report.confirmation_rate is None


def test_collect_aggregiert_ueber_mehrere_seiten():
    contradicted_page = _page_burger_fall("1_p1")
    unjudgeable_page = {
        "page_id": "2_p1",
        "width": 500,
        "height": 800,
        "words": [
            _word("Kaese", 300, 100, 350, 112),
            _word("2.00", 310, 100, 360, 140),
        ],
        "tags": ["B-PRODUCT", "B-PRICE"],
    }

    report = collect([contradicted_page, unjudgeable_page])

    assert report.pages == 2
    assert report.contradicted == 1
    assert report.unjudgeable == 1
    assert report.judged == 1
    assert report.confirmation_rate == 0.0
