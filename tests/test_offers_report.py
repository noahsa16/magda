"""Ablation und Messung des Angebots-Clusterings.

Die Zahlen auf `feature/db` messen ihr eigenes Zuordnungskriterium: `_match_badges`
ordnet bevorzugt ueber Menge x Grundpreis zu, und hinterher wurde gezaehlt, wie oft
ein Preis bei einem Produkt landet. Wer so misst, bekommt eine hohe Zahl und keine
Erkenntnis.

Der Ausweg ist eine Ablation: den arithmetischen Weg zum Messen abschalten, die
Geometrie allein zuordnen lassen und erst danach nachrechnen. Dann ist die
Arithmetik ein unbeteiligter Richter.
"""

from magda.offers import cluster_page


def _word(text, x0, y0, x1, y1):
    return {"text": text, "bbox": [x0, y0, x1, y1]}


def _zwei_bloecke_mit_fernem_preis():
    """Zwei Produkte, ein Preis - geometrisch beim falschen, rechnerisch beim richtigen.

    0,8 kg x 11.24 EUR/kg = 8.99 gehoert zu AAA oben; der Preis-Sticker sitzt
    aber auf Hoehe von BBB unten. Das ist der Fall aus dem Docstring von
    `_match_badges` (Burger Patties/Lammspiesse), auf das Noetigste eingedampft.
    """
    return {
        "page_id": "1_p1",
        "width": 500,
        "height": 800,
        "words": [
            _word("AAA", 40, 100, 90, 112),
            _word("800-g-Packung", 40, 116, 130, 128),
            _word("(1 kg = 11.24)", 40, 130, 140, 142),
            _word("BBB", 40, 500, 90, 512),
            _word("260 g", 40, 516, 90, 528),
            _word("(1 kg = 23.03)", 40, 530, 140, 542),
            _word("8.99", 400, 480, 450, 520),
        ],
        "tags": [
            "B-BRAND",
            "B-QUANTITY",
            "B-UNIT_PRICE",
            "B-BRAND",
            "B-QUANTITY",
            "B-UNIT_PRICE",
            "B-PRICE",
        ],
    }


def _offer_with(offers, needle):
    matches = [o for o in offers if any(needle in e.text for e in o.entities)]
    assert len(matches) == 1, f"{needle!r} in {len(matches)} Angeboten"
    return matches[0]


def test_die_rechnung_schlaegt_die_naehe():
    """Vorbedingung der Ablation: im Normalbetrieb gewinnt die Arithmetik."""
    offers = cluster_page(_zwei_bloecke_mit_fernem_preis())

    assert _offer_with(offers, "AAA").values()["price"] == "8.99"
    assert _offer_with(offers, "BBB").values()["price"] is None


def test_ohne_arithmetik_landet_der_preis_beim_falschen_produkt():
    """Genau dieser Unterschied ist die Messung: was die Geometrie allein anrichtet."""
    offers = cluster_page(_zwei_bloecke_mit_fernem_preis(), arithmetic=False)

    assert _offer_with(offers, "BBB").values()["price"] == "8.99"
    assert _offer_with(offers, "AAA").values()["price"] is None


def test_trace_haelt_den_zuordnungsweg_fest():
    trace = []

    cluster_page(_zwei_bloecke_mit_fernem_preis(), trace=trace)

    assert len(trace) == 1
    match = trace[0]
    assert match.path == "arithmetic"
    assert match.price_type == "PRICE"
    assert match.value == 8.99


def test_trace_kennt_die_rechnerischen_kandidaten_auch_ohne_arithmetik():
    """Damit der Report urteilen kann, muss der Trace beide Seiten kennen: wohin
    die Geometrie zugeordnet hat und wohin die Rechnung gezeigt haette."""
    trace = []

    cluster_page(_zwei_bloecke_mit_fernem_preis(), arithmetic=False, trace=trace)

    match = trace[0]
    assert match.path == "geometric"
    assert match.arithmetic_targets, "die Rechnung haette einen Block gefunden"
    assert match.target not in match.arithmetic_targets


# ----------------------------------------------------------------- Messmodul


def _ein_block_mit_passendem_preis():
    """Preis steht neben seinem eigenen Produkt - Geometrie und Rechnung einig."""
    page = _zwei_bloecke_mit_fernem_preis()
    page["words"][-1] = _word("8.99", 400, 100, 450, 140)
    return page


def _block_ohne_grundpreis():
    return {
        "page_id": "1_p2",
        "width": 500,
        "height": 800,
        "words": [
            _word("Hoodie", 40, 100, 90, 112),
            _word("8.00", 400, 100, 450, 140),
        ],
        "tags": ["B-PRODUCT", "B-PRICE"],
    }


def _block_dessen_rechnung_nicht_aufgeht():
    """Der Fall 1351497_p20: Menge und Grundpreis da, aber kein Preis passt dazu."""
    return {
        "page_id": "1_p3",
        "width": 500,
        "height": 800,
        "words": [
            _word("Aufstrich", 40, 100, 90, 112),
            _word("900 g", 40, 116, 90, 128),
            _word("(1 kg = 5.99)", 40, 130, 140, 142),
            _word("4.49", 400, 100, 450, 140),
        ],
        "tags": ["B-PRODUCT", "B-QUANTITY", "B-UNIT_PRICE", "B-PRICE"],
    }


def test_geometrie_wird_widerlegt_wenn_die_rechnung_woanders_hinzeigt():
    from magda.offers_report import judge_page

    verdict = judge_page(_zwei_bloecke_mit_fernem_preis())

    assert verdict.contradicted == 1
    assert verdict.confirmed == 0


def test_geometrie_wird_bestaetigt_wenn_sie_richtig_liegt():
    from magda.offers_report import judge_page

    verdict = judge_page(_ein_block_mit_passendem_preis())

    assert verdict.confirmed == 1
    assert verdict.contradicted == 0


def test_ohne_grundpreis_lautet_das_urteil_nicht_beurteilbar():
    """Kein Grundpreis heisst kein Urteil - nicht stillschweigend "richtig"."""
    from magda.offers_report import judge_page

    verdict = judge_page(_block_ohne_grundpreis())

    assert verdict.unjudgeable == 1
    assert verdict.confirmed == 0
    assert verdict.contradicted == 0


def test_block_ohne_stimmige_paarung_wird_gezaehlt():
    from magda.offers_report import judge_page

    verdict = judge_page(_block_dessen_rechnung_nicht_aufgeht())

    assert verdict.blocks_without_matching_pairing == 1


def test_leere_messung_wird_als_leer_ausgewiesen_statt_als_null_prozent():
    from magda.offers_report import collect

    report = collect([_block_ohne_grundpreis()])

    assert report.judged == 0
    assert report.geometric_accuracy is None


def test_collect_summiert_ueber_seiten():
    from magda.offers_report import collect

    report = collect([_zwei_bloecke_mit_fernem_preis(), _ein_block_mit_passendem_preis()])

    assert report.confirmed == 1
    assert report.contradicted == 1
    assert report.judged == 2
    assert report.geometric_accuracy == 0.5


# --------------------------------------------------- Die Grenze des Urteils


def _zweiter_preis_auf_belegten_block():
    """Zwei gleich teure Angebote, nur eines mit Grundpreis.

    0,5 kg x 4.00 EUR/kg = 2.00 passt rechnerisch zu AAA. AAA bekommt seinen
    eigenen Preis zuerst; der zweite 2.00 gehoert zu BBB, das gar keinen
    Grundpreis traegt. Ist das ein Widerspruch der Rechnung oder schlicht kein
    Urteil? Die Antwort haengt daran, ob ein bereits belegter Block noch als
    Alternative zaehlt - und genau darueber gehen zwei Lesarten auseinander.
    """
    return {
        "page_id": "1_p4",
        "width": 500,
        "height": 800,
        "words": [
            _word("AAA", 40, 100, 90, 112),
            _word("500 g", 40, 116, 90, 128),
            _word("(1 kg = 4.00)", 40, 130, 140, 142),
            _word("2.00", 200, 100, 250, 140),
            _word("BBB", 40, 600, 90, 612),
            _word("2.00", 200, 600, 250, 640),
        ],
        "tags": [
            "B-BRAND",
            "B-QUANTITY",
            "B-UNIT_PRICE",
            "B-PRICE",
            "B-BRAND",
            "B-PRICE",
        ],
    }


def test_belegter_block_zaehlt_streng_als_alternative_nachsichtig_nicht():
    """Beide Lesarten werden berichtet, statt eine zur richtigen zu erklaeren."""
    from magda.offers_report import judge_page

    verdict = judge_page(_zweiter_preis_auf_belegten_block())

    assert verdict.contradicted_strict == verdict.contradicted + 1
    assert verdict.unjudgeable_strict == verdict.unjudgeable - 1


def test_die_strenge_lesart_liefert_die_untere_schranke():
    from magda.offers_report import collect

    report = collect([_zweiter_preis_auf_belegten_block()])

    assert report.geometric_accuracy_strict <= report.geometric_accuracy
