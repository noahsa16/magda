"""Tests für die Span-zu-BIO-Konvertierung.

Die Spans kommen vom LLM und sind entsprechend unzuverlässig – hier wird
vor allem geprüft, dass kaputter Input verworfen wird statt zu crashen.
"""

from magda.labels import LABELS, label2id, spans_to_bio


def test_einfacher_span():
    tags = spans_to_bio(5, [{"start": 1, "end": 3, "label": "PRODUCT"}])
    assert tags == ["O", "B-PRODUCT", "I-PRODUCT", "O", "O"]


def test_span_mit_einem_wort():
    tags = spans_to_bio(3, [{"start": 0, "end": 1, "label": "PRICE"}])
    assert tags == ["B-PRICE", "O", "O"]


def test_unbekanntes_label_wird_verworfen():
    tags = spans_to_bio(3, [{"start": 0, "end": 2, "label": "QUATSCH"}])
    assert tags == ["O", "O", "O"]


def test_span_ausserhalb_wird_verworfen():
    tags = spans_to_bio(3, [{"start": 1, "end": 7, "label": "PRODUCT"}])
    assert tags == ["O", "O", "O"]


def test_ueberlappung_erster_gewinnt():
    tags = spans_to_bio(
        4,
        [
            {"start": 0, "end": 2, "label": "PRODUCT"},
            {"start": 1, "end": 3, "label": "BRAND"},  # überlappt -> fliegt raus
        ],
    )
    assert tags == ["B-PRODUCT", "I-PRODUCT", "O", "O"]


def test_kaputte_indizes_crashen_nicht():
    tags = spans_to_bio(3, [{"start": "a", "end": None, "label": "PRICE"}, {"label": "PRICE"}])
    assert tags == ["O", "O", "O"]


def test_label_ids_sind_konsistent():
    # id2label/label2id müssen exakt invers sein, sonst knallt es erst beim Training
    assert len(LABELS) == len(set(LABELS))
    assert all(label2id[label] == i for i, label in enumerate(LABELS))
