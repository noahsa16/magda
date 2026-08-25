"""Ein Vorwaertsdurchlauf mit Batch 1 - vor dem Mieten einer GPU, nicht danach.

Der Anlass steht in CLAUDE.md: LayoutXLM starb ohne `image` an einem
nichtssagenden `'NoneType' object has no attribute 'tensor'` tief im
detectron2-Backbone, und zwar erst nach zehn Minuten Uebersetzungszeit auf dem
Pod. LiLT hat dieselbe Falle spiegelverkehrt - es braucht `bbox`, aber *kein*
Bild, und sein Tokenizer nimmt `boxes=` nicht entgegen.

Der Test laedt echte Gewichte. Ohne sie im HuggingFace-Cache wird er
uebersprungen statt rot: ein fehlendes Netz ist kein Fehler im Code.
"""

import pytest

from magda.config import MAX_SEQ_LENGTH, variant_spec
from magda.labels import LABELS

SEITE = {
    "page_id": "test_p1",
    "width": 476.22,
    "height": 841.89,
    "words": [
        {"text": "Rinderhackfleisch", "bbox": [50.0, 100.0, 200.0, 120.0]},
        {"text": "500", "bbox": [50.0, 130.0, 80.0, 145.0]},
        {"text": "g", "bbox": [85.0, 130.0, 95.0, 145.0]},
        {"text": "3.99", "bbox": [300.0, 200.0, 360.0, 240.0]},
    ],
    "tags": ["B-PRODUCT", "B-QUANTITY", "I-QUANTITY", "B-PRICE"],
}


@pytest.fixture(scope="module")
def lilt():
    """Tokenizer und Gewichte, oder ein sauberes Skip."""
    transformers = pytest.importorskip("transformers")
    spec = variant_spec("lilt")
    try:
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            spec.model_name, local_files_only=True
        )
        model = transformers.AutoModelForTokenClassification.from_pretrained(
            spec.model_name, num_labels=len(LABELS), local_files_only=True
        )
    except Exception as fehler:
        pytest.skip(f"LiLT nicht im Cache: {fehler}")
    return tokenizer, model


def test_lilt_baut_eine_box_je_subword(lilt):
    """Die bbox-Spalte muss die Laenge der Sequenz haben - sonst bricht es
    erst im Modell, und die Meldung nennt die Ursache nicht."""
    from magda.dataset import LiltDataset

    tokenizer, _ = lilt
    ds = LiltDataset([SEITE], tokenizer, MAX_SEQ_LENGTH)
    item = ds[0]

    assert item["bbox"].shape == (MAX_SEQ_LENGTH, 4)
    assert item["input_ids"].shape == (MAX_SEQ_LENGTH,)


def test_lilt_bekommt_kein_seitenbild(lilt):
    """Der ganze Sinn des Arms. Ein `image` im Batch waere ein unerwartetes
    Argument und flaechte den Vorwaertsdurchlauf."""
    from magda.dataset import LiltDataset

    tokenizer, _ = lilt
    item = LiltDataset([SEITE], tokenizer, MAX_SEQ_LENGTH)[0]

    assert "image" not in item


def test_die_boxen_stehen_nicht_alle_auf_null(lilt):
    """Ein LiLT ohne Positionen ist ein teureres GBERT und faellt an keiner
    Fehlermeldung auf - nur an einer Zahl, die man dann falsch deutet."""
    from magda.dataset import LiltDataset

    tokenizer, _ = lilt
    boxes = LiltDataset([SEITE], tokenizer, MAX_SEQ_LENGTH)[0]["bbox"]

    assert boxes.sum() > 0


def test_ein_vorwaertsdurchlauf_liefert_logits_je_wortposition(lilt):
    """Batch 1, echte Gewichte: findet in Sekunden, was auf dem Pod erst nach
    dem Aufsetzen der Umgebung auffiele."""
    from magda.dataset import LiltDataset

    tokenizer, model = lilt
    item = LiltDataset([SEITE], tokenizer, MAX_SEQ_LENGTH)[0]
    batch = {k: v.unsqueeze(0) for k, v in item.items()}

    out = model(**batch)

    assert out.logits.shape == (1, MAX_SEQ_LENGTH, len(LABELS))
    assert out.loss is not None, "labels waren im Batch, also muss ein Loss kommen"
