"""Tests für die Span-zu-BIO-Konvertierung.

Die Spans kommen vom LLM und sind entsprechend unzuverlässig – hier wird
vor allem geprüft, dass kaputter Input verworfen wird statt zu crashen.
"""

from magda.labels import bio_to_spans, LABELS, label2id, spans_to_bio, validate_spans


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


def test_validate_spans_akzeptiert_gueltige_spans():
    spans = [
        {"start": 0, "end": 1, "label": "BRAND"},
        {"start": 1, "end": 4, "label": "PRODUCT"},
    ]
    assert validate_spans(spans, num_words=10) == []


def test_validate_spans_meldet_index_ausserhalb():
    errors = validate_spans([{"start": 8, "end": 12, "label": "PRICE"}], num_words=10)
    assert len(errors) == 1
    assert "8-12" in errors[0]


def test_validate_spans_meldet_leeren_oder_verdrehten_span():
    errors = validate_spans([{"start": 5, "end": 5, "label": "PRICE"}], num_words=10)
    assert len(errors) == 1


def test_validate_spans_meldet_unbekanntes_label():
    errors = validate_spans([{"start": 0, "end": 1, "label": "FARBE"}], num_words=10)
    assert len(errors) == 1
    assert "FARBE" in errors[0]


def test_validate_spans_meldet_ueberlappung():
    # BIO kann Überlappungen nicht darstellen - was hier durchrutscht, ginge
    # beim Konvertieren still verloren.
    spans = [
        {"start": 0, "end": 3, "label": "PRODUCT"},
        {"start": 2, "end": 5, "label": "QUANTITY"},
    ]
    errors = validate_spans(spans, num_words=10)
    assert len(errors) == 1
    assert "berlappen" in errors[0]


def test_validate_spans_erlaubt_direkt_angrenzende_spans():
    spans = [
        {"start": 0, "end": 2, "label": "BRAND"},
        {"start": 2, "end": 4, "label": "PRODUCT"},
    ]
    assert validate_spans(spans, num_words=10) == []


def test_validate_spans_sammelt_mehrere_fehler():
    spans = [
        {"start": -1, "end": 2, "label": "BRAND"},
        {"start": 3, "end": 4, "label": "UNSINN"},
    ]
    assert len(validate_spans(spans, num_words=10)) == 2


def test_bio_to_spans_ist_die_umkehrung_von_spans_to_bio():
    spans = [
        {"start": 0, "end": 1, "label": "BRAND"},
        {"start": 1, "end": 4, "label": "PRODUCT"},
        {"start": 5, "end": 7, "label": "QUANTITY"},
    ]
    tags = spans_to_bio(8, spans)
    assert bio_to_spans(tags) == spans


def test_bio_to_spans_trennt_zwei_gleiche_labels_nebeneinander():
    """B-PRODUCT direkt nach I-PRODUCT ist ein neuer Span, kein Anhängsel –
    sonst verschmelzen zwei Produkte einer Aufzählung zu einem."""
    tags = ["B-PRODUCT", "I-PRODUCT", "B-PRODUCT", "O"]

    assert bio_to_spans(tags) == [
        {"start": 0, "end": 2, "label": "PRODUCT"},
        {"start": 2, "end": 3, "label": "PRODUCT"},
    ]


def test_bio_to_spans_laesst_ein_verwaistes_i_tag_nicht_verschwinden():
    """Kaputte Tagfolgen sollen sichtbar bleiben, nicht still wegfallen."""
    assert bio_to_spans(["O", "I-PRICE"]) == [{"start": 1, "end": 2, "label": "PRICE"}]
