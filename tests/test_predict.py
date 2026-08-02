"""Der Prediction-Export ist die Übergabe an die Angebots-Rekonstruktion.

Zwei Eigenschaften tragen diesen Schritt: Koordinaten müssen mitkommen, und
ein abgeschnittenes Wort darf nicht wie eine Entscheidung gegen ein Entity
aussehen.
"""

import json

import numpy as np

from magda.labels import label2id
from magda.predict import (
    bounding_box,
    merge_windows,
    page_output,
    word_predictions,
    write_pages,
)

SEITE = {
    "page_id": "1351497_p10",
    "width": 595.0,
    "height": 842.0,
    "words": [
        {"text": "Rinderhack", "bbox": [10.0, 20.0, 60.0, 30.0]},
        {"text": "frisch", "bbox": [62.0, 20.0, 90.0, 30.0]},
        {"text": "3.99", "bbox": [10.0, 40.0, 40.0, 55.0]},
    ],
}


def logits_fuer(tags):
    """Ein-Subword-je-Wort-Logits, die genau diese Tags erzwingen."""
    logits = np.zeros((len(tags) + 2, len(label2id)))
    for position, tag in enumerate(tags, start=1):
        logits[position][label2id[tag]] = 10.0
    return logits


# [CLS] Wort0 Wort1 Wort2 [SEP]  ->  drei Wörter, je ein Subword
WORD_IDS = [None, 0, 1, 2, None]


def test_bounding_box_umschliesst_alle_woerter():
    assert bounding_box([[10.0, 20.0, 60.0, 30.0], [62.0, 20.0, 90.0, 35.0]]) == [
        10.0, 20.0, 90.0, 35.0,
    ]


def test_faltet_subwords_auf_wortebene_zurueck():
    tags, scores = word_predictions(
        logits_fuer(["B-PRODUCT", "I-PRODUCT", "B-PRICE"]), WORD_IDS, 3
    )

    assert tags == ["B-PRODUCT", "I-PRODUCT", "B-PRICE"]
    assert all(0.0 < s <= 1.0 for s in scores)


def test_nur_das_erste_subword_eines_wortes_zaehlt():
    """Dieselbe Konvention, mit der align_word_labels die Labels hinlegt."""
    word_ids = [None, 0, 0, 0, 1, None]
    logits = np.zeros((6, len(label2id)))
    logits[1][label2id["B-PRODUCT"]] = 10.0
    logits[2][label2id["B-PRICE"]] = 10.0  # Fortsetzung, muss ignoriert werden
    logits[3][label2id["B-BRAND"]] = 10.0
    logits[4][label2id["O"]] = 10.0

    tags, _ = word_predictions(logits, word_ids, 2)

    assert tags == ["B-PRODUCT", "O"]


def test_abgeschnittene_woerter_bleiben_none_statt_O():
    """Sonst sieht Truncation aus wie "hier ist kein Entity" und verschluckt Angebote."""
    tags, scores = word_predictions(logits_fuer(["B-PRODUCT"]), [None, 0, None], 3)

    assert tags == ["B-PRODUCT", None, None]
    assert scores[1] is None and scores[2] is None


def test_seite_meldet_truncation_und_zaehlt_woerter():
    tags, scores = word_predictions(logits_fuer(["B-PRODUCT"]), [None, 0, None], 3)

    out = page_output(SEITE, tags, scores, "gbert", "sonnet-5")

    assert out["truncated"] is True
    assert out["num_words"] == 3
    assert out["num_words_predicted"] == 1
    assert out["words"][2]["label"] is None


def test_entities_tragen_text_und_huellbox():
    tags, scores = word_predictions(
        logits_fuer(["B-PRODUCT", "I-PRODUCT", "B-PRICE"]), WORD_IDS, 3
    )

    out = page_output(SEITE, tags, scores, "gbert", "sonnet-5")

    produkt, preis = out["entities"]
    assert produkt["label"] == "PRODUCT"
    assert produkt["text"] == "Rinderhack frisch"
    assert produkt["bbox"] == [10.0, 20.0, 90.0, 30.0]
    assert preis["text"] == "3.99"
    assert 0.0 < produkt["confidence"] <= 1.0


def test_jedes_wort_behaelt_seine_koordinaten():
    """Ohne Boxen kann die nächste Stufe kein Angebot räumlich gruppieren."""
    tags, scores = word_predictions(logits_fuer(["O", "O", "O"]), WORD_IDS, 3)

    out = page_output(SEITE, tags, scores, "gbert", "sonnet-5")

    assert [w["bbox"] for w in out["words"]] == [w["bbox"] for w in SEITE["words"]]
    assert [w["i"] for w in out["words"]] == [0, 1, 2]


def test_index_fasst_den_lauf_zusammen(tmp_path):
    tags, scores = word_predictions(
        logits_fuer(["B-PRODUCT", "I-PRODUCT", "B-PRICE"]), WORD_IDS, 3
    )
    out = page_output(SEITE, tags, scores, "gbert", "sonnet-5")

    index = write_pages([out], tmp_path)

    assert index["num_pages"] == 1
    assert index["num_entities"] == 2
    assert index["entities_per_label"] == {"PRICE": 1, "PRODUCT": 1}
    assert index["catalogs"] == ["1351497"]
    geschrieben = json.loads((tmp_path / "1351497_p10.json").read_text())
    assert geschrieben["page_id"] == "1351497_p10"
    assert json.loads((tmp_path / "index.json").read_text())["num_pages"] == 1


def fenster_logits(zuordnung, laenge):
    """Logits eines Fensters: {position_im_fenster: tag}."""
    logits = np.zeros((laenge, len(label2id)))
    for position, tag in zuordnung.items():
        logits[position][label2id[tag]] = 10.0
    return logits


def test_fenster_decken_zusammen_die_ganze_seite_ab():
    """Der Punkt der Übung: kein Wort bleibt ohne Vorhersage."""
    # Fenster 0 sieht Wörter 0-2, Fenster 1 die Wörter 2-4.
    logits = [
        fenster_logits({1: "B-PRODUCT", 2: "I-PRODUCT", 3: "B-PRICE"}, 5),
        fenster_logits({1: "B-PRICE", 2: "B-BRAND", 3: "O"}, 5),
    ]
    word_ids = [[None, 0, 1, 2, None], [None, 2, 3, 4, None]]

    tags, scores = merge_windows(logits, word_ids, 5)

    assert None not in tags
    assert len(tags) == 5


def test_bei_ueberlappung_gewinnt_das_fenster_mit_mehr_kontext():
    """Wort 2 liegt in beiden Fenstern: am Rand von Fenster 0, mittig in Fenster 1."""
    logits = [
        fenster_logits({1: "O", 2: "O", 3: "B-PRODUCT"}, 5),   # Wort 2 ist hier Rand
        fenster_logits({1: "B-PRICE", 2: "O", 3: "O"}, 5),      # Wort 2 ist hier Rand
    ]
    # Fenster 0 deckt 0..2 (Wort 2 hat Abstand 0 zum Rand),
    # Fenster 1 deckt 2..4 (Wort 2 hat ebenfalls Abstand 0) -> erstes gewinnt.
    tags, _ = merge_windows(logits, [[None, 0, 1, 2, None], [None, 2, 3, 4, None]], 5)
    assert tags[2] == "B-PRODUCT"

    # Jetzt deckt Fenster 1 die Wörter 1..3 ab: Wort 2 sitzt dort mittig
    # (Abstand 1) und schlägt damit den Randtreffer aus Fenster 0.
    tags, _ = merge_windows(logits, [[None, 0, 1, 2, None], [None, 1, 2, 3, None]], 4)
    assert tags[2] == "O"


def test_leere_fenster_stoeren_nicht():
    logits = [fenster_logits({1: "B-PRODUCT"}, 3), fenster_logits({}, 3)]

    tags, _ = merge_windows(logits, [[None, 0, None], [None, None, None]], 2)

    assert tags[0] == "B-PRODUCT"
    assert tags[1] is None


def test_angeschnittenes_wort_am_fensteranfang_wird_uebergangen():
    """Fenstergrenzen liegen auf Subwords, nicht auf Wörtern.

    Beginnt ein Folgefenster mitten in einem Wort, hält `word_predictions`
    ein Fortsetzungs-Subword für das erste – eine Position, die im Training
    maskiert war. Solange ein anderes Fenster das Wort ganz sieht, gilt dessen
    Vorhersage.
    """
    # Fenster 0 sieht Wörter 0-2 ganz, Fenster 1 beginnt mitten in Wort 2.
    logits = [
        fenster_logits({1: "O", 2: "O", 3: "B-PRODUCT"}, 5),
        fenster_logits({1: "B-BRAND", 2: "O", 3: "O"}, 5),
    ]
    word_ids = [[None, 0, 1, 2, None], [None, 2, 3, 4, None]]

    tags, _ = merge_windows(logits, word_ids, 5)

    assert tags[2] == "B-PRODUCT", "Wort 2 muss aus dem Fenster kommen, das es ganz sieht"


def test_guard_verwirft_nichts_ohne_ersatz():
    """Deckt nur ein einziges Fenster das Wort ab, gilt dessen Vorhersage."""
    logits = [
        fenster_logits({1: "B-PRODUCT"}, 3),
        fenster_logits({1: "B-BRAND", 2: "B-PRICE"}, 3),
    ]
    # Wort 1 kommt nur in Fenster 1 vor und steht dort am Anfang.
    word_ids = [[None, 0, None], [None, 1, 2, None]]

    tags, _ = merge_windows(logits, word_ids, 3)

    assert tags[1] == "B-BRAND"
