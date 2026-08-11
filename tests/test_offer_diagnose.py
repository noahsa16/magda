"""Trennt die Frage "wer deckelt?" in Kantenqualitaet und Dekodierverlust.

Gruppen-F1 allein sagt nicht, woran es liegt. Ein Paarmodell mit perfekten
Wahrscheinlichkeiten und ein Dekoder, der sie verschenkt, sehen von aussen
genauso aus wie gute Dekodierung schlechter Kanten - die Konsequenzen sind
aber entgegengesetzt: bessere Merkmale gegen besseres Dekodieren.

Dieselbe Denkfigur wie die Ablation in `offers_report`: eine Groesse
isolieren, indem man die andere festhaelt.
"""

import pytest

from magda import offer_grid


def test_perfekte_trennung_ergibt_auc_eins():
    """Alle positiven Paare ueber allen negativen."""
    assert offer_grid.edge_auc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) == 1.0


def test_umgekehrte_ordnung_ergibt_auc_null():
    assert offer_grid.edge_auc([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]) == 0.0


def test_raten_ergibt_auc_eine_halbe():
    """Der Bezugspunkt: 0.5 heisst, die Kanten tragen keine Information."""
    assert offer_grid.edge_auc([1, 0, 1, 0], [0.5, 0.5, 0.5, 0.5]) == 0.5


def test_gleichstaende_zaehlen_halb():
    """Sonst haengt die Zahl daran, wie das Modell rundet.

    Ein Modell, das viele Paare exakt gleich bewertet, bekaeme sonst je
    nach Sortierreihenfolge 0 oder 1 - also eine Zahl ohne Bedeutung.
    """
    assert offer_grid.edge_auc([1, 0], [0.7, 0.7]) == 0.5


def test_ohne_beide_klassen_gibt_es_keine_auc():
    """None statt 0.5: "nicht messbar" ist etwas anderes als "raet"."""
    assert offer_grid.edge_auc([1, 1, 1], [0.9, 0.8, 0.7]) is None
    assert offer_grid.edge_auc([], []) is None


def test_die_auc_haengt_nur_an_der_reihenfolge():
    """Eine monotone Umskalierung darf nichts aendern - genau das macht die
    Zahl schwellenfrei und damit unabhaengig von der Kalibrierung."""
    labels = [1, 0, 1, 0, 1]
    roh = [0.9, 0.4, 0.6, 0.1, 0.8]
    gestaucht = [0.5 + s / 10 for s in roh]

    assert offer_grid.edge_auc(labels, roh) == offer_grid.edge_auc(labels, gestaucht)


torch = pytest.importorskip("torch")

from magda import offer_model  # noqa: E402
from test_offer_model import _training_set  # noqa: E402


def test_perfekte_kanten_ergeben_perfekte_gruppen():
    """Das Orakel prueft den Dekoder, nicht das Modell.

    Bekommt der Dekoder die wahre Zugehoerigkeit als Wahrscheinlichkeit,
    muss er sie reproduzieren. Tut er das nicht, verliert er Information
    unabhaengig vom Paarmodell - und dann waere jede Diagnose ueber die
    Kantenqualitaet gegenstandslos, weil der Massstab selbst leckt.
    """
    pages, reference = _training_set()
    model = offer_model.train(pages, reference, epochs=5)

    result = offer_grid.diagnose(pages, reference, model, thresholds=[0.5, 0.9])

    assert result["oracle"] == 1.0


def test_die_obergrenze_liegt_nie_unter_dem_erreichten():
    """`ceiling` faehrt alle Schwellen ab, `achieved` nimmt eine davon."""
    pages, reference = _training_set()
    model = offer_model.train(pages, reference, epochs=5)
    model.threshold = 0.9

    result = offer_grid.diagnose(pages, reference, model,
                                 thresholds=[0.5, 0.7, 0.9])

    assert result["ceiling"] >= result["achieved"]


def test_zerfall_und_verschmelzung_werden_unterschieden():
    """Die beiden Fehlerarten verlangen gegenlaeufige Massnahmen.

    Zerfall heisst, dem System fehlen Kanten - es braucht mehr Recall.
    Verschmelzung heisst, es hat zu viele. Aus einer Gruppen-F1-Zahl ist
    das nicht ablesbar, und wer sich vertut, dreht an der falschen
    Schraube.
    """
    pages, reference = _training_set()
    model = offer_model.train(pages, reference, epochs=5)
    # Schwelle ganz oben: nichts wird verbunden, also muss alles zerfallen.
    model.threshold = 0.9999

    kinds = offer_grid.failure_kinds(pages, reference, model)["kinds"]

    assert kinds.get("zerfallen", 0) + kinds.get("entity_fehlt", 0) > 0
    assert kinds.get("verschmolzen", 0) == 0


def test_alles_in_einer_gruppe_zaehlt_als_verschmolzen():
    """Die Gegenprobe - sonst koennte 'zerfallen' immer herauskommen."""
    pages, reference = _training_set()
    model = offer_model.train(pages, reference, epochs=5)
    model.threshold = 0.0        # jede Kante zaehlt, die Seite wird eine Gruppe

    kinds = offer_grid.failure_kinds(pages, reference, model)["kinds"]

    assert kinds.get("verschmolzen", 0) > 0
    assert kinds.get("zerfallen", 0) == 0
