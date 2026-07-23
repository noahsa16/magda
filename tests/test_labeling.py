"""Tests für das Herausschneiden des JSON-Arrays aus LLM-Antworten.

Alle Fälle hier sind echte Antworten aus dem ersten Labeling-Lauf über
einen Penny-Prospekt – das Modell hält sich nur meistens an "nur JSON".
"""

import pytest

from magda.labeling import _extract_json_array


def test_reines_array():
    assert _extract_json_array('[{"start": 0}]') == '[{"start": 0}]'


def test_code_fence():
    assert _extract_json_array('```json\n[{"start": 0}]\n```') == '[{"start": 0}]'


def test_einleitender_prosatext():
    # so passiert: das Modell antwortete auf Koreanisch mit Vorspann
    text = '지시하신 대로 반환하겠습니다.\n\n[{"start": 0, "end": 2}]'
    assert _extract_json_array(text) == '[{"start": 0, "end": 2}]'


def test_angehaengte_erklaerung_mit_klammern():
    # rfind("]") würde hier zu weit greifen – die Erklärung enthält selbst ]
    text = '[{"start": 0}]\n\n- **QUANTITY**: 200 g [siehe oben]'
    assert _extract_json_array(text) == '[{"start": 0}]'


def test_verschachtelte_klammern_bleiben_ganz():
    text = 'Hier:\n[{"a": [1, 2]}, {"b": [3]}]\nFertig.'
    assert _extract_json_array(text) == '[{"a": [1, 2]}, {"b": [3]}]'


def test_kein_array_wirft():
    with pytest.raises(ValueError, match="Kein JSON-Array"):
        _extract_json_array("Ich kann das leider nicht.")


def test_unvollstaendiges_array_wirft():
    with pytest.raises(ValueError, match="nicht geschlossen"):
        _extract_json_array('[{"start": 0}, {"start"')
