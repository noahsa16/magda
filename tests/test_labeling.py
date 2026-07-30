"""Tests für das Herausschneiden des JSON-Arrays aus LLM-Antworten.

Alle Fälle hier sind echte Antworten aus dem ersten Labeling-Lauf über
einen Penny-Prospekt – das Modell hält sich nur meistens an "nur JSON".
"""

import pytest

from magda import labeling
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


# ---------------------------------------------------------------------------
# Span-Guard
# ---------------------------------------------------------------------------


def _words(*texts):
    return [{"text": t, "bbox": [0, 0, 1, 1]} for t in texts]


def test_guard_trennt_zwei_angebote_am_oder():
    """Das Modell zog "Waschmittel* ... oder All in 1 Color Pods* ..." in einen
    Span. "oder" trennt zwei Angebote und darf in keiner Entität stehen."""
    words = _words("Waschmittel*", "Aprilfrisch,", "oder", "All", "in", "1")
    spans = [{"start": 0, "end": 6, "label": "PRODUCT"}]

    assert labeling.trim_spans(spans, words) == [
        {"start": 0, "end": 2, "label": "PRODUCT"}
    ]


def test_guard_schneidet_den_grundpreis_aus_der_menge():
    """QUANTITY="g (1 kg = 11.98)" war der häufigste Einzelfehler."""
    words = _words("500", "g", "(1", "kg", "=", "11.98)")
    spans = [{"start": 0, "end": 6, "label": "QUANTITY"}]

    assert labeling.trim_spans(spans, words) == [
        {"start": 0, "end": 2, "label": "QUANTITY"}
    ]


def test_guard_laesst_den_grundpreis_selbst_in_ruhe():
    """UNIT_PRICE beginnt mit der Klammer – dort ist sie kein Abbruchgrund."""
    words = _words("(1", "kg", "=", "11.98)")
    spans = [{"start": 0, "end": 4, "label": "UNIT_PRICE"}]

    assert labeling.trim_spans(spans, words) == spans


def test_guard_verwirft_einen_span_der_mit_oder_beginnt():
    """"oder MEZZO MIX ..." – bleibt nach dem Kürzen nichts übrig, fällt der
    Span ganz weg statt als leerer Span durchzurutschen."""
    words = _words("oder", "MEZZO", "MIX")
    spans = [{"start": 0, "end": 3, "label": "PRODUCT"}]

    assert labeling.trim_spans(spans, words) == []


def test_guard_ruehrt_saubere_spans_nicht_an():
    words = _words("Löslicher", "Kaffee", "Classic,")
    spans = [{"start": 0, "end": 3, "label": "PRODUCT"}]

    assert labeling.trim_spans(spans, words) == spans


def test_rate_limit_wird_geduldiger_wiederholt_als_ein_serverfehler(monkeypatch):
    """Ein Lauf über 196 Seiten verlor 176 davon an 429ern, weil der Backoff
    nach acht Sekunden aufgab. Ein Kontingentfenster ist keine Sekundenfrage."""
    waits = []
    monkeypatch.setattr(labeling.time, "sleep", waits.append)

    class RateLimit(Exception):
        status_code = 429

    calls = []

    def failing(*args):
        calls.append(1)
        if len(calls) < 3:
            raise RateLimit("API rate limit exceeded")
        return ["O"]

    monkeypatch.setattr(labeling, "label_page", failing)
    assert labeling.label_page_with_retry([], b"", None, "m") == ["O"]
    # 20s, dann 40s – nicht 2s und 4s.
    assert waits == [20.0, 40.0]


def test_parse_fehler_wird_nicht_wiederholt(monkeypatch):
    """Das Modell hat geantwortet, nur unbrauchbar. Ein zweiter Versuch mit
    identischer Eingabe kostet nur Zeit."""
    calls = []

    def failing(*args):
        calls.append(1)
        raise ValueError("Kein JSON-Array in der Antwort")

    monkeypatch.setattr(labeling, "label_page", failing)
    with pytest.raises(ValueError):
        labeling.label_page_with_retry([], b"", None, "m")
    assert len(calls) == 1
