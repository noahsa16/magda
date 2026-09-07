"""Name und Aktionspreis je Preisvariante, symmetrisch für beide Systeme."""

import pytest

from magda import blackbox_eval


# ---------------------------------------------------------------- Matching


def test_gleicher_preis_und_aehnlicher_name_gilt_als_treffer():
    system = [{"name": "Landliebe Butter 250g", "price": 1.29}]
    reference = [{"name": "Landliebe Butter", "price": 1.29}]

    result = blackbox_eval.match_deals(system, reference)

    assert result["matched"] == 1
    assert result["only_system"] == 0


def test_ein_anderer_preis_ist_kein_treffer():
    """Der Preis ist der harte Anker - Namen variieren, Preise nicht."""
    system = [{"name": "Landliebe Butter", "price": 1.49}]
    reference = [{"name": "Landliebe Butter", "price": 1.29}]

    assert blackbox_eval.match_deals(system, reference)["matched"] == 0


def test_jedes_angebot_wird_hoechstens_einmal_gepaart():
    """Sonst treibt ein System seinen Recall mit Duplikaten hoch."""
    system = [{"name": "Butter", "price": 1.29}, {"name": "Butter", "price": 1.29}]
    reference = [{"name": "Butter", "price": 1.29}]

    result = blackbox_eval.match_deals(system, reference)

    assert result["matched"] == 1
    assert result["only_system"] == 1


def test_leere_seiten_auf_beiden_seiten_ergeben_keine_quote():
    assert blackbox_eval.match_deals([], [])["f1"] is None


def test_die_gemeinsame_feldmenge_ignoriert_app_preise():
    """Zusatzfelder sind nicht Teil des vorab festgelegten Haupt-F1."""
    system = [{"name": "Butter", "price": 1.29, "app_price": 0.99}]
    reference = [{"name": "Butter", "price": 1.29}]

    assert blackbox_eval.match_deals(system, reference)["matched"] == 1


def test_ein_voellig_anderer_name_beim_selben_preis_ist_kein_treffer():
    """Sonst reichte auf einer Seite mit vielen 0.99-Angeboten der Preis."""
    system = [{"name": "Zahnpasta", "price": 0.99}]
    reference = [{"name": "Kiwi Gold", "price": 0.99}]

    assert blackbox_eval.match_deals(system, reference)["matched"] == 0


def test_das_matching_ist_symmetrisch_in_der_trefferzahl():
    """Wer die eine Seite unscharf und die andere exakt matcht, verzerrt in
    unbekannte Richtung - deshalb dieselbe Funktion fuer beide Richtungen."""
    a = [{"name": "Butter", "price": 1.29}, {"name": "Milch", "price": 0.99}]
    b = [{"name": "Butter 250 g", "price": 1.29}]

    assert (blackbox_eval.match_deals(a, b)["matched"]
            == blackbox_eval.match_deals(b, a)["matched"])


# ------------------------------------------------------------- Preisparsen


@pytest.mark.parametrize("text,expected", [
    ("1.59", 1.59),
    ("1,59", 1.59),          # deutsche Schreibweise kommt im Textlayer vor
    ("1.59 | 2.49", 1.59),   # values() joint Varianten, die erste gilt
    ("nur 0.99 €", 0.99),
    (None, None),
    ("", None),
    ("ohne Ziffer", None),
])
def test_preise_werden_aus_dem_textfeld_gelesen(text, expected):
    assert blackbox_eval.parse_price(text) == expected


# ------------------------------------------------ Projektion eines Angebots


def _offer(**values):
    class Fake:
        def values(self):
            return values
    return Fake()


def test_ein_angebot_ohne_preis_ist_kein_vergleichbares_angebot():
    """Fragmente sind kein Extraktionsergebnis - sie wuerden die Praezision
    der eigenen Pipeline druecken, ohne dass die Blackbox ein Gegenstueck
    haette. Sie werden gezaehlt und getrennt ausgewiesen."""
    assert blackbox_eval.deals_from_offer(_offer(product="Butter", price=None)) == []


def test_ein_angebot_ohne_namen_ist_kein_vergleichbares_angebot():
    assert blackbox_eval.deals_from_offer(_offer(product=None, price="1.29")) == []


def test_marke_und_produkt_ergeben_zusammen_den_namen():
    """Die Blackbox liefert einen Fliesstext-Namen; unsere Pipeline trennt
    BRAND und PRODUCT. Getrennt verglichen waere der Name systematisch kuerzer."""
    [deal] = blackbox_eval.deals_from_offer(
        _offer(brand="Landliebe", product="Butter", price="1.29"))

    assert deal["name"] == "Landliebe Butter"
    assert deal["price"] == 1.29


def test_der_streichpreis_wird_mitgefuehrt_aber_nicht_bewertet():
    [deal] = blackbox_eval.deals_from_offer(
        _offer(product="Butter", price="1.29", old_price="1.99"))

    assert deal["original_price"] == 1.99
    assert "original_price" not in blackbox_eval.COMMON_FIELDS


def test_der_app_preis_taucht_in_der_projektion_nicht_auf():
    """Die Blackbox kann APP_PRICE nicht ausdruecken - er gehoert nicht in den Vergleich."""
    [deal] = blackbox_eval.deals_from_offer(
        _offer(product="Butter", price="1.29", app_price="0.99"))

    assert "app_price" not in deal


# ------------------------------------------------------ Aggregation je Lauf


def test_die_seitenweisen_zahlen_werden_aufsummiert_nicht_gemittelt():
    """Ein Mittel ueber Seiten gewichtet eine Seite mit zwei Angeboten so
    stark wie eine mit dreissig."""
    pages = {
        "p1": ([{"name": "A", "price": 1.0}], [{"name": "A", "price": 1.0}]),
        "p2": ([], [{"name": "B", "price": 2.0}] * 9),
    }
    result = blackbox_eval.compare_pages(pages)

    assert result["matched"] == 1
    assert result["only_reference"] == 9
    assert result["recall"] == pytest.approx(0.1)


def test_preisvarianten_werden_auf_beiden_seiten_gleich_gezaehlt():
    reference = blackbox_eval.deals_from_offer(_offer(product="Pfanne", price="9.99 | 14.99"))
    system = [{"name": "Pfanne", "price": 9.99}, {"name": "Pfanne", "price": 14.99}]
    assert blackbox_eval.match_deals(system, reference)["f1"] == 1.0


def test_maximalmatching_bleibt_bei_vertauschter_reihenfolge_gleich():
    from itertools import permutations
    system = [{"name": name, "price": 1} for name in ("Butter", "Landliebe Butter mild")]
    reference = [{"name": name, "price": 1} for name in ("Butter mild", "Kerrygold Butter mild")]
    for own in permutations(system):
        for other in permutations(reference):
            assert blackbox_eval.match_deals(own, other)["matched"] == 2
            assert blackbox_eval.match_deals(other, own)["matched"] == 2


def test_altpreise_sind_ausdruecklich_nicht_im_haupt_f1():
    assert blackbox_eval.COMMON_FIELDS == ("name", "price")
