"""Die Rechnung urteilt ueber eine Gruppierung, die sie nicht erzeugt hat.

`0,25 kg x 4,00 EUR/kg = 1,00 EUR` stimmt oder stimmt nicht. Das ist
Arithmetik und braucht keine Handannotation - und es ist genau die Kontrolle,
die einer LLM-Gruppierung fehlt, solange sie nur gegen sich selbst gehalten
wird.

Der Unterschied zu `magda offers-report` ist wichtig genug fuer einen eigenen
Test: Dort *ordnet* die Heuristik teilweise selbst arithmetisch zu, weshalb
der Report erst per Ablation (`arithmetic=False`) die Rechnung abschalten
muss, bevor sie richten darf. Ein Modell, das nach dem Seitenbild gruppiert,
hat nie gerechnet - hier ist die Arithmetik von sich aus unbeteiligt.
"""

from magda import offers_verify
from magda.offers_gold import offers_from_reference

WIDTH, HEIGHT = 1000.0, 1000.0


def _word(text, x0, y0):
    return {"text": text, "bbox": [x0, y0, x0 + 40, y0 + 12]}


# Zwei Angebote, beide mit Grundpreis: Butter 250 g zu 4.00/kg macht 1.00,
# Milch 500 g zu 4.00/kg macht 2.00. Damit ist jeder Preis genau einer
# Gruppe zuzuordnen - und eine Fehlzuordnung nachweisbar, nicht nur unbelegt.
SEITE = {
    "page_id": "p1",
    "width": WIDTH,
    "height": HEIGHT,
    "words": [
        _word("Butter", 100, 100),          # 0
        _word("250 g", 100, 120),           # 1
        _word("(1 kg = 4.00)", 200, 120),   # 2
        _word("1.00", 100, 140),            # 3
        _word("Milch", 100, 500),           # 4
        _word("500 g", 100, 520),           # 5
        _word("(1 kg = 4.00)", 200, 520),   # 6
        _word("2.00", 100, 540),            # 7
    ],
    "tags": [
        "B-PRODUCT", "B-QUANTITY", "B-UNIT_PRICE", "B-PRICE",
        "B-PRODUCT", "B-QUANTITY", "B-UNIT_PRICE", "B-PRICE",
    ],
}

RICHTIG = {0: 0, 1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1, 7: 1}
VERTAUSCHT = {0: 0, 1: 0, 2: 0, 7: 0, 4: 1, 5: 1, 6: 1, 3: 1}


def test_aufgehende_rechnung_bestaetigt_die_gruppe():
    verdict = offers_verify.judge_page(SEITE, RICHTIG)

    assert verdict.confirmed == 2
    assert verdict.contradicted == 0


def test_vertauschte_preise_werden_widerlegt():
    """Der Preis passt rechnerisch zur anderen Gruppe - das ist der Beleg."""
    verdict = offers_verify.judge_page(SEITE, VERTAUSCHT)

    assert verdict.confirmed == 0
    assert verdict.contradicted == 2


def test_ohne_grundpreis_gibt_es_kein_urteil():
    """Non-Food traegt keinen Grundpreis - dort schweigt die Rechnung."""
    page = dict(SEITE, tags=[
        "B-PRODUCT", "B-QUANTITY", "O", "B-PRICE",
        "B-PRODUCT", "B-QUANTITY", "O", "B-PRICE",
    ])

    verdict = offers_verify.judge_page(page, RICHTIG)

    assert verdict.confirmed == 0
    assert verdict.contradicted == 0
    assert verdict.unjudgeable == 2


def test_ein_preis_der_nirgends_aufgeht_gilt_nicht_als_widerlegt():
    """Sonst zaehlte jeder Labelfehler als Gruppierungsfehler.

    Die Rechnung kann nur richten, wenn sie eine Alternative benennt. Ein
    Preis, der zu keiner Gruppe der Seite passt, ist ein Befund ueber die
    Labels oder ueber Mehrfachpackungen - kein Beleg gegen die Zuordnung.
    """
    page = dict(SEITE, words=list(SEITE["words"]))
    page["words"][3] = _word("7.77", 100, 140)

    verdict = offers_verify.judge_page(page, RICHTIG)

    assert verdict.contradicted == 0
    assert verdict.unresolved == 1


def test_leere_messung_ist_keine_null_prozent():
    assert offers_verify.Report().accuracy is None


def test_bericht_summiert_ueber_seiten():
    report = offers_verify.collect(
        [SEITE, dict(SEITE, page_id="p2")], {"p1": RICHTIG, "p2": VERTAUSCHT}
    )

    assert report.pages == 2
    assert report.confirmed == 2
    assert report.contradicted == 2
    assert report.accuracy == 0.5


def test_seiten_ohne_referenz_werden_uebersprungen():
    report = offers_verify.collect([SEITE], {"andere_seite": RICHTIG})

    assert report.pages == 0
    assert report.accuracy is None


def test_judge_offers_verdichtet_je_angebot():
    """0,205 kg x 3,37 EUR/kg = 0,69 EUR bestaetigt Angebot A; Angebot B
    traegt denselben Preis 0.69, obwohl sein eigener Grundpreis (500 g zu
    4.00/kg) 2.00 verlangt - die Rechnung zeigt auf Angebot A, also
    widerlegt."""
    page = {
        "page_id": "p1",
        "width": WIDTH,
        "height": HEIGHT,
        "words": [
            _word("Produkt A", 100, 100),        # 0
            _word("0,205 kg", 100, 120),          # 1
            _word("(1 kg = 3.37)", 200, 120),     # 2
            _word("0.69", 100, 140),              # 3
            _word("Produkt B", 100, 500),         # 4
            _word("500 g", 100, 520),             # 5
            _word("(1 kg = 4.00)", 200, 520),     # 6
            _word("0.69", 100, 540),              # 7 - falscher Preis fuer B
        ],
        "tags": [
            "B-PRODUCT", "B-QUANTITY", "B-UNIT_PRICE", "B-PRICE",
            "B-PRODUCT", "B-QUANTITY", "B-UNIT_PRICE", "B-PRICE",
        ],
    }
    assignment = {0: 0, 1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1, 7: 1}
    offers = offers_from_reference(page, assignment)

    assert offers_verify.judge_offers(page, offers) == ["confirmed", "contradicted"]


def test_judge_offers_contradicted_schlaegt_confirmed_im_selben_angebot():
    """Ein Angebot mit einem richtigen und einem falschen Preis gilt als
    widerlegt, nicht als halb bestaetigt - `contradicted` hat Vorrang vor
    `confirmed`, auch wenn beide Urteile im selben Angebot vorkommen."""
    page = {
        "page_id": "p1",
        "width": WIDTH,
        "height": HEIGHT,
        "words": [
            _word("Produkt A", 100, 100),        # 0
            _word("0,205 kg", 100, 120),          # 1
            _word("(1 kg = 3.37)", 200, 120),     # 2
            _word("0.69", 100, 140),              # 3 - korrekter Preis von A
            _word("2.00", 100, 160),              # 4 - gehoert eigentlich zu B
            _word("Produkt B", 100, 500),         # 5
            _word("500 g", 100, 520),             # 6
            _word("(1 kg = 4.00)", 200, 520),     # 7
        ],
        "tags": [
            "B-PRODUCT", "B-QUANTITY", "B-UNIT_PRICE", "B-PRICE", "B-APP_PRICE",
            "B-PRODUCT", "B-QUANTITY", "B-UNIT_PRICE",
        ],
    }
    assignment = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 1, 6: 1, 7: 1}
    offers = offers_from_reference(page, assignment)

    assert offers_verify.judge_offers(page, offers) == ["contradicted", "unverifiable"]


def test_judge_offers_ohne_preis_ist_unverifiable():
    page = dict(SEITE, tags=["B-PRODUCT", "B-QUANTITY", "O", "O",
                             "B-PRODUCT", "B-QUANTITY", "O", "O"])
    offers = offers_from_reference(page, RICHTIG)

    assert offers_verify.judge_offers(page, offers) == ["unverifiable", "unverifiable"]
