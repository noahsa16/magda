"""Die Sonde vor dem Merkmalsblock - Rangmass, Mittelung, Paarbildung.

Die Sonde entscheidet, ob ein Embedding-Block ueberhaupt gebaut wird. Sie
rechnet ihr Rangmass selbst, weil sklearn hier nur als Weiterleitung von
seqeval mithaengt - also ist es auch selbst zu pruefen.
"""

import numpy as np
import pytest

from magda import offer_probe


# ------------------------------------------------------------------ Rangmass


def test_perfekte_trennung_ergibt_eins():
    assert offer_probe.roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0


def test_umgekehrte_trennung_ergibt_null():
    assert offer_probe.roc_auc([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]) == 0.0


def test_bindungen_zaehlen_halb():
    """Alle Punkte gleich heisst Muenzwurf, nicht perfekt.

    Ohne Bindungsmittelung haengt das Ergebnis an der Sortierreihenfolge -
    dieselbe Eingabe ergaebe 0.0 oder 1.0, je nach Zufall.
    """
    assert offer_probe.roc_auc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) == 0.5


def test_ohne_beide_klassen_ist_die_flaeche_undefiniert():
    """Nicht 0.0 zurueckgeben: eine Zahl ohne Bedeutung wandert sonst in
    einen Report und sieht dort wie eine Messung aus."""
    assert np.isnan(offer_probe.roc_auc([1, 1, 1], [0.2, 0.5, 0.9]))


# ------------------------------------------------------------------ Paar-F1


def test_die_beste_schwelle_wird_gesucht_nicht_gesetzt():
    """`pos_weight` verschiebt alle Wahrscheinlichkeiten nach oben - eine
    feste 0.5 verglaeche Schwellen statt Merkmale."""
    f1, threshold = offer_probe.best_f1([0, 0, 1, 1], [0.6, 0.65, 0.9, 0.95])

    assert f1 == 1.0
    assert threshold > 0.65


# --------------------------------------------------------------- Mittelung


def test_ein_wort_in_zwei_fenstern_wird_gemittelt():
    """Fenster ueberlappen um 128 Subwords; welches ein Wort besser sieht,
    ist nicht entscheidbar."""
    ersten = np.array([[0.0, 0.0], [2.0, 4.0]], dtype="float32")
    zweiten = np.array([[4.0, 8.0], [0.0, 0.0]], dtype="float32")

    vectors, seen = offer_probe.word_vectors(
        [ersten, zweiten], [[None, 0], [0, None]], count=1)

    assert seen.tolist() == [True]
    assert vectors[0].tolist() == [3.0, 6.0]


def test_ein_wort_ohne_fenster_gilt_als_ungesehen():
    """Sonst bekaeme es den Nullvektor und das Modell lernte, dass abgeschnittene
    Seiten anders aussehen - derselbe Grund, aus dem der Farbblock lieber
    abbricht."""
    hidden = np.array([[1.0, 1.0]], dtype="float32")

    vectors, seen = offer_probe.word_vectors([hidden], [[0]], count=2)

    assert seen.tolist() == [True, False]


# ------------------------------------------------------------ Paarbildung


def _page():
    texts = ["Landliebe", "Butter", "1.29", "Ja!"]
    boxes = [[10, 10 + 12 * i, 60, 20 + 12 * i] for i in range(4)]
    return {
        "page_id": "p1", "width": 100, "height": 200,
        "words": [{"text": t, "bbox": b} for t, b in zip(texts, boxes)],
        "tags": ["B-BRAND", "B-PRODUCT", "B-PRICE", "B-BRAND"],
    }


def _vectors(seen=(True, True, True, True)):
    words = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 2.0]],
                     dtype="float32")
    return words, np.array(seen)


def test_ein_paar_ohne_referenzurteil_wird_uebersprungen():
    """Wo die Referenz schweigt, gibt es kein Negativbeispiel - dieselbe
    Regel wie in `offer_pairs.page_pairs`."""
    from magda import offer_pairs

    rows = offer_probe.pair_rows(
        _page(), {0: 0, 1: 0, 2: 0}, _vectors(), offer_pairs.GEOMETRY_BLOCKS)

    # Entity 3 ("Ja!") steht in keinem Angebot, ihre drei Paare fallen weg.
    assert len(rows) == 3


def test_eine_entity_ohne_embedding_faellt_heraus():
    """Sonst stuenden zwei Merkmalsmengen auf verschiedenen Paarmengen und
    waeren nicht mehr vergleichbar."""
    from magda import offer_pairs

    rows = offer_probe.pair_rows(
        _page(), {0: 0, 1: 0, 2: 0}, _vectors(seen=(True, False, True, True)),
        offer_pairs.GEOMETRY_BLOCKS)

    assert len(rows) == 1


def test_das_paar_traegt_differenz_und_produkt():
    """`[|h_i - h_j|, h_i * h_j]` - die uebliche Paarbildung der
    Relationsliteratur, ohne h_i und h_j selbst."""
    from magda import offer_pairs

    rows = offer_probe.pair_rows(
        _page(), {0: 0, 1: 0, 2: 0}, _vectors(), offer_pairs.GEOMETRY_BLOCKS)
    _, embedding, _ = rows[0]

    assert embedding.tolist() == [1.0, 1.0, 0.0, 0.0]
