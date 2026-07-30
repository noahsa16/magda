"""Tests für den Flair-Vergleichsarm.

Laufen ohne installiertes flair: die Modellanbindung ist bewusst von der
Mapping-Logik getrennt, damit die Testsuite nicht an einer optionalen
Abhängigkeit hängt.
"""

import pytest

import magda.flair_baseline as fb
from magda.flair_baseline import (
    REPORTED_LABELS,
    check_tagset,
    predict_pages,
    restrict_to,
    spans_to_project_tags,
)


# --- Mapping und Einschränkung ---------------------------------------------


def test_restrict_to_behaelt_nur_das_gewuenschte_label():
    tags = ["B-BRAND", "I-BRAND", "B-PRICE", "O", "B-PRODUCT"]

    assert restrict_to(tags, REPORTED_LABELS) == ["B-BRAND", "I-BRAND", "O", "O", "O"]


def test_restrict_to_laesst_reines_O_unberuehrt():
    assert restrict_to(["O", "O"], REPORTED_LABELS) == ["O", "O"]


def test_spans_to_project_tags_mappt_org_auf_brand():
    # 4 Wörter, ORG über Wortindex 1-2 (end exklusiv).
    assert spans_to_project_tags(4, [(1, 3, "ORG")]) == ["O", "B-BRAND", "I-BRAND", "O"]


def test_spans_to_project_tags_verwirft_nicht_gemappte_label():
    """PER, LOC und MISC haben im Projekt-Schema keine Entsprechung."""
    spans = [(0, 1, "PER"), (1, 2, "LOC"), (2, 3, "MISC")]

    assert spans_to_project_tags(3, spans) == ["O", "O", "O"]


def test_spans_to_project_tags_ohne_spans():
    assert spans_to_project_tags(3, []) == ["O", "O", "O"]


# --- Tagset-Prüfung ---------------------------------------------------------


def test_check_tagset_akzeptiert_conll_labels():
    check_tagset({"PER", "LOC", "ORG", "MISC"})


def test_check_tagset_wirft_ohne_org():
    with pytest.raises(RuntimeError, match="ORG"):
        check_tagset({"PER", "LOC", "MISC"})


# --- Vorhersage (mit Doubles statt flair) -----------------------------------


class _FakeToken:
    def __init__(self, idx):
        self.idx = idx


class _FakeLabel:
    def __init__(self, value):
        self.value = value


class _FakeSpan:
    """flair zählt Token ab 1 und meint das Ende inklusiv."""

    def __init__(self, start_idx, end_idx, value):
        self.tokens = [_FakeToken(i) for i in range(start_idx, end_idx + 1)]
        self._value = value

    def get_label(self, _name):
        return _FakeLabel(self._value)


class _FakeSentence:
    def __init__(self, words):
        self.words = words
        self._spans = []

    def get_spans(self, _name):
        return self._spans


class _FakeTagger:
    """Steht für den SequenceTagger, ohne flair zu installieren."""

    def __init__(self, spans_per_call):
        self.spans_per_call = list(spans_per_call)
        self.seen = []

    def predict(self, sentence):
        sentence._spans = self.spans_per_call.pop(0)
        self.seen.append(sentence)


@pytest.fixture
def fake_sentence(monkeypatch):
    monkeypatch.setattr(fb, "_make_sentence", _FakeSentence)


def test_predict_pages_setzt_tags_auf_die_richtigen_wortindizes(fake_sentence):
    page = {"words": [{"text": t} for t in ["Angebot", "Landliebe", "Vollmilch", "1.29"]]}
    # ORG über flair-Token 2-3 (1-basiert, inklusiv) = Wortindex 1-2.
    tagger = _FakeTagger([[_FakeSpan(2, 3, "ORG")]])

    assert predict_pages([page], tagger) == [["O", "B-BRAND", "I-BRAND", "O"]]


def test_predict_pages_verwirft_nicht_gemappte_label(fake_sentence):
    page = {"words": [{"text": t} for t in ["Berlin", "Aldi"]]}
    tagger = _FakeTagger([[_FakeSpan(1, 1, "LOC")]])

    assert predict_pages([page], tagger) == [["O", "O"]]


def test_predict_pages_uebergibt_die_wortliste_vorsegmentiert(fake_sentence):
    """Ansatz A: flairs eigener Tokenizer bleibt aus, sonst verschieben sich
    die Indizes gegenüber der Wortliste aus Schritt 02."""
    page = {"words": [{"text": t} for t in ["(1", "kg", "=", "24.95)"]]}
    tagger = _FakeTagger([[]])

    predict_pages([page], tagger)

    assert tagger.seen[0].words == ["(1", "kg", "=", "24.95)"]


def test_predict_pages_liefert_ein_tag_je_wort(fake_sentence):
    """Absicherung gegen stilles Abschneiden langer Seiten."""
    page = {"words": [{"text": str(i)} for i in range(600)]}
    tagger = _FakeTagger([[]])

    tags = predict_pages([page], tagger)

    assert len(tags[0]) == 600


def test_predict_pages_bei_leerer_seite(fake_sentence):
    assert predict_pages([{"words": []}], _FakeTagger([])) == [[]]
