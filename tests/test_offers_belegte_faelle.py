"""Regressionspins fuer die in `offers.py` belegten Einzelfaelle.

Die Docstrings im Clustering begruenden fast jede Konstante mit einem
konkreten Fall ("belegter Fall: FREIXENET/HARIBO auf 1351497_p1"). Ohne Test
schuetzt so eine Begruendung nichts: wer `dy * 2.8` auf `2.5` setzt oder die
2-%-Schwelle in `_same_block` anfasst, macht den Fall still kaputt, und die
ganze Suite bleibt gruen. Genau das haelt die Projektkonvention fest.

Zwei Dinge zur Einordnung, damit diese Datei nicht falsch gelesen wird:

- **Es sind Pins, keine Qualitaetsbelege.** Die Tests frieren dokumentiertes
  Verhalten ein und berichten keine Zahl. Was das Clustering wirklich taugt,
  misst `magda offers-report` auf Train + Dev.
- **Die Seiten liegen im Testsplit.** Das ist hier vertretbar, weil kein Modell
  sie sieht - `offers.py` laeuft erst nach der Vorhersage - und weil ein Pin
  nichts optimiert. Es gilt aber die Umkehrung: Nie eine Konstante nachziehen,
  damit einer dieser Tests gruen wird. Ein Test, der hier rot wird, ist ein
  Befund ueber die Heuristik, kein Grund, die Erwartung anzupassen.
"""

import json

import pytest

from magda import config
from magda.offers import cluster_page

LABELS = "sonnet-5"

pytestmark = pytest.mark.skipif(
    not config.labeled_dir(LABELS).is_dir(),
    reason=f"data/labeled/{LABELS}/ nicht vorhanden (z.B. im Trainings-Bundle)",
)


def _offers(page_id: str):
    path = config.labeled_dir(LABELS) / f"{page_id}.json"
    if not path.is_file():
        pytest.skip(f"{path} nicht vorhanden")
    with open(path) as f:
        page = json.load(f)
    return cluster_page(page)


def _offer_with(offers, needle: str):
    """Das eine Angebot, in dem `needle` vorkommt - sonst schlaegt der Test fehl."""
    matches = [o for o in offers if any(needle in e.text for e in o.entities)]
    assert len(matches) == 1, (
        f"{needle!r} steht in {len(matches)} Angeboten, erwartet genau eines"
    )
    return matches[0]


def test_freixenet_und_haribo_landen_nicht_im_selben_angebot():
    """Der Fall aus dem Modul-Docstring: die Abstimmung je Entity konnte die
    Marke an einen anderen Preis andocken als das Produkt direkt daneben."""
    offers = _offers("1351497_p1")

    freixenet = _offer_with(offers, "FREIXENET")
    haribo = _offer_with(offers, "HARIBO")

    assert freixenet is not haribo
    assert freixenet.values()["price"] == "3.89"
    assert haribo.values()["price"] == "0.69"


def test_goldbaeren_und_pico_balla_bleiben_ein_angebot():
    """Gegenprobe zur Legenden-Zerlegung (`_segment_legend`): die Suesswarenzeile
    hat ihre Preise ausserhalb des Blocks und darf nicht ueber die
    Lesereihenfolge zerschnitten werden - beide Sorten teilen sich einen Preis."""
    offers = _offers("1351497_p1")

    goldbaeren = _offer_with(offers, "Goldbären")

    assert any("Pico-Balla" in e.text for e in goldbaeren.entities)
    assert goldbaeren.values()["price"] == "0.69"
    assert goldbaeren.values()["quantity"] == "205 g | 190 g"


def test_fanta_und_coca_cola_teilen_sich_menge_und_grundpreis():
    """Ein Angebot mit zwei Markennamen und einer gemeinsamen Menge. Zugleich
    der Fall aus `_attach_orphan_descriptions`: "2 l" und "(1 l = 0.65)" stehen
    im Textlayer getrennt vom Markennamen und muessen wieder andocken."""
    offers = _offers("1351497_p1")

    fanta = _offer_with(offers, "FANTA")

    assert any("COCA-COLA" in e.text for e in fanta.entities)
    assert fanta.values()["quantity"] == "2 l"
    assert fanta.values()["unit_price"] == "(1 l = 0.65)"


def test_haehnchen_und_trauben_werden_trotz_gemeinsamem_foto_getrennt():
    """Zweite Ebene von `_split_multi_product`: zwei Produkte unter einem Foto,
    nur das Haehnchen mit eigener Marke. Ueber BRAND allein nicht trennbar."""
    offers = _offers("1351497_p1")

    haehnchen = _offer_with(offers, "Minutenschnitzel")
    trauben = _offer_with(offers, "Tafeltrauben")

    assert haehnchen is not trauben
    assert haehnchen.values()["price"] == "6.99"
    assert trauben.values()["price"] == "1.39"


def test_schwartau_und_nutella_bleiben_getrennt():
    """Der Fall aus `_same_block`: kleine y-Luecke, grosse x-Luecke. Eine
    hoehenlastige Gewichtung wie in der Ankersuche wuerde beide zusammenziehen."""
    offers = _offers("1351497_p18")

    schwartau = _offer_with(offers, "SCHWARTAU")
    nutella = _offer_with(offers, "NUTELLA")

    assert schwartau is not nutella
    assert schwartau.values()["price"] == "2.29"
    assert nutella.values()["price"] == "6.49"


def test_solvel_varianten_werden_je_eigener_menge_getrennt():
    """Acht Produkte einer Marke auf einer Seite. Trennkriterium ist die eigene
    Menge je Anker, nicht der Preis - Sonnenblumenmargarine (500 g) und Rapsoel
    (1 l) kosten beide 1.59, und das ist ein echter Zufall im Sortiment."""
    offers = _offers("1351497_p13")

    solvel = [o for o in offers if any("SOLVEL" in e.text for e in o.entities)]

    assert len(solvel) == 8
    products = [o.values()["product"] for o in solvel]
    assert len(set(products)) == 8, f"Produkte nicht paarweise verschieden: {products}"
    assert all(o.values()["quantity"] for o in solvel), "Angebot ohne eigene Menge"


def test_burger_patties_und_lammspiesse_folgen_der_rechnung_statt_der_naehe():
    """Der Kernfall von `_match_badges`: der Preis sitzt geometrisch naeher am
    Nachbarprodukt als am eigenen. Menge x Grundpreis loest es eindeutig -
    0,8 kg x 11.24 EUR/kg = 8.99 und 0,26 kg x 23.03 EUR/kg = 5.99."""
    offers = _offers("1351497_p10")

    patties = _offer_with(offers, "Burger Patties")
    lammspiesse = _offer_with(offers, "Lammspieße")

    assert patties is not lammspiesse
    assert patties.values()["price"] == "8.99"
    assert patties.values()["app_price"] == "7.99"
    assert lammspiesse.values()["price"] == "5.99"


def test_legende_zerfaellt_spaltenweise_in_einzelne_angebote():
    """Non-Food-Sammellegende: `_segment_legend` schneidet spaltenweise ueber die
    Lesereihenfolge, weil Non-Food-Artikel keine Menge zum Trennen tragen.

    Gemessen auf dieser Seite: ohne den Pfad kollabieren Waeschepflege, BH und
    Damen-Slips in einen Block, und von 15 Angeboten tragen nur 3 Produkt *und*
    Preis - der Rest bleibt preisloses Fragment. Nicht `1351497_p28` aus dem
    Docstring von `_reading_order_groups`: dort liefert `_segment_legend` None,
    die Lesereihenfolge laeuft also gar nicht.
    """
    offers = _offers("1351518_p30")

    waeschepflege = _offer_with(offers, "Wäschepflege")
    bh = _offer_with(offers, "BH ohne Bügel")

    assert waeschepflege is not bh
    assert waeschepflege.values()["price"] == "2.00,"
    assert bh.values()["price"] == "5.00,"

    complete = [o for o in offers if o.values()["product"] and o.values()["price"]]
    assert len(complete) >= 10, (
        f"nur {len(complete)} Angebote mit Produkt und Preis - "
        "die Legende wurde vermutlich nicht zerlegt"
    )
