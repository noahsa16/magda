"""Grenzen, Typverwechslungen und leere Seiten nach dem SemEval-Vertrag."""

import pytest

from magda import semeval


def span(start, end, label="PRODUCT"):
    return {"start": start, "end": end, "label": label}


@pytest.mark.parametrize("predicted, expected", [
    ([span(0, 2)], (1, 1, 1, 1)),
    ([span(0, 2, "BRAND")], (0, 1, 1, 0)),
    ([span(0, 1)], (0, 0, 0.5, 1)),
    ([span(0, 1, "BRAND")], (0, 0, 0.5, 0)),
    ([span(2, 3)], (0, 0, 0, 0)),
    ([], (0, 0, 0, 0)),
])
def test_sechs_faelle_unterscheiden_grenze_und_typ(predicted, expected):
    result = semeval.evaluate([[span(0, 2)]], [predicted])
    assert tuple(result["matching_schemes"][scheme]["f1"] for scheme in semeval.SCHEMES) == expected


def test_benachbarte_einwortspans_ueberlappen_nicht():
    result = semeval.evaluate([[span(0, 1)]], [[span(1, 2)]])
    assert result["matching_schemes"]["partial"]["f1"] == 0


def test_ein_wort_ueberlappung_reicht_auch_bei_langen_spans():
    result = semeval.evaluate([[span(0, 150)]], [[span(149, 150)]])
    assert result["matching_schemes"]["type"]["f1"] == 1
    assert result["matching_schemes"]["partial"]["f1"] == 0.5


def test_nur_vorhergesagter_typ_wird_nicht_verschwiegen():
    result = semeval.evaluate([[span(0, 1)]], [[span(0, 1), span(2, 3, "PRICE")]])
    assert result["matching_schemes_per_label"]["PRICE"]["strict"]["spurious"] == 1
    assert result["matching_schemes"]["strict"]["precision"] == 0.5


def test_fehlende_seite_ist_keine_stille_schnittmenge():
    with pytest.raises(ValueError):
        semeval.evaluate([[], []], [[]])


def test_leere_seiten_erzeugen_keine_treffer():
    result = semeval.evaluate([[]], [[]])
    assert result["matching_schemes"]["strict"]["correct"] == 0
    assert result["matching_schemes"]["strict"]["possible"] == 0
