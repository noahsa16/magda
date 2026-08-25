"""Die Variantenregistry und die Box-Ausbreitung fuer LiLT.

Vier Arme statt zwei, und drei davon brauchen Boxen auf verschiedenen Wegen:
LayoutXLMs Tokenizer nimmt `boxes=` selbst entgegen, LiLTs XLM-R-Tokenizer
kennt das Argument nicht. Wer das verwechselt, bekommt keinen Fehler, sondern
ein Modell ohne Positionsinformation - also genau den Arm, gegen den es
antreten soll.
"""

import pytest

from magda import jobs
from magda.alignment import subword_boxes
from magda.config import VARIANTS, variant_spec


def test_subword_boxen_folgen_den_wortindizes():
    """Jedes Subword traegt die Box seines Ursprungsworts, auch das zweite."""
    boxes = [[10, 20, 30, 40], [50, 60, 70, 80]]
    # "Rinderhack" zerfaellt in zwei Subwords, "1.99" bleibt eines
    assert subword_boxes([0, 0, 1], boxes) == [
        [10, 20, 30, 40],
        [10, 20, 30, 40],
        [50, 60, 70, 80],
    ]


def test_sondertokens_bekommen_die_nullbox():
    """word_id None ist <s>, </s> oder Padding - die haben keine Position."""
    boxes = [[10, 20, 30, 40]]
    assert subword_boxes([None, 0, None, None], boxes) == [
        [0, 0, 0, 0],
        [10, 20, 30, 40],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ]


def test_es_gibt_genau_eine_box_je_token():
    """Die bbox-Spalte muss so lang sein wie input_ids, sonst bricht der
    Vorwaertsdurchlauf erst im Modell und mit unverstaendlicher Meldung."""
    word_ids = [None, 0, 0, 0, 1, 2, 2, None, None, None]
    boxes = [[1, 1, 1, 1], [2, 2, 2, 2], [3, 3, 3, 3]]
    assert len(subword_boxes(word_ids, boxes)) == len(word_ids)


def test_lilt_braucht_boxen_aber_kein_seitenbild():
    """Der ganze Grund fuer den Arm: Layout ohne visuellen Backbone."""
    lilt = variant_spec("lilt")
    assert lilt.boxes == "manual"
    assert lilt.image is False


def test_layoutxlm_laesst_den_tokenizer_die_boxen_ausbreiten():
    """LayoutXLMTokenizerFast nimmt `boxes=` - dort waere manuelles
    Ausbreiten doppelt gemoppelt und die Spalte doppelt so lang."""
    layoutxlm = variant_spec("layoutxlm")
    assert layoutxlm.boxes == "tokenizer"
    assert layoutxlm.image is True


def test_die_beiden_textarme_bekommen_keine_boxen():
    for name in ("gbert", "xlmr"):
        assert variant_spec(name).boxes == "none"
        assert variant_spec(name).image is False


def test_lilt_und_layoutxlm_teilen_den_textencoder():
    """Der Vergleich haengt daran: nur so ist die Differenz zwischen beiden
    der visuelle Backbone und nicht zusaetzlich ein anderer Encoder."""
    assert "xlm-roberta" in variant_spec("lilt").model_name
    assert "xlm-roberta" in variant_spec("xlmr").model_name


def test_unbekannte_variante_wird_abgelehnt():
    with pytest.raises(KeyError):
        variant_spec("layoutlmv3")


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_der_runner_startet_jeden_arm(variant):
    """`jobs.build_command` ist die einzige Stelle, an der aus einer
    Nutzereingabe ein Kommando wird, und sie validiert gegen ihre eigene
    Variantenliste. Driftet die von der Registry ab, bietet das Frontend einen
    Arm an, den es nicht starten kann - oder verweigert einen, den es gibt."""
    argv = jobs.build_command("train", {"variant": variant})

    assert variant in argv
