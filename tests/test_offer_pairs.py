"""Merkmale je Entity-Paar - die Eingabe der Relationsklassifikation.

Gruppieren ist eine Relation, keine Klassifikation: BIO-Tags koennen sagen
"dieses Wort ist ein Preis", aber nicht "dieser Preis gehoert zu jenem
Produkt". Die Literatur loest das paarweise (DocILE arXiv:2302.05658, LiLT
arXiv:2202.13669) - eine Kante je Entity-Paar, danach
Zusammenhangskomponenten.

**Die Rechnung Menge x Grundpreis ist hier kein Merkmal.** Sie ist der
einzige Richter im System, der sich selbst beweist; gibt man sie dem Modell
als Eingabe, misst `magda offers-verify` hinterher die Rechnung gegen sich
selbst. Dasselbe Muster wie die Ablation in `offers_report`: das Merkmal
zurueckhalten, mit dem hinterher gerichtet wird.
"""

import pytest

from magda import offer_pairs


def _page(page_id="p1"):
    """Zwei Angebote untereinander, dazu ein ungelabeltes Wort."""
    texts = ["Landliebe", "Butter", "1.29", "zzgl", "Ja!", "Milch", "0.99"]
    boxes = [
        [10, 10, 60, 20],    # Landliebe
        [10, 22, 60, 32],    # Butter
        [70, 10, 95, 40],    # 1.29   - gross gesetzt, rechts daneben
        [10, 40, 30, 48],    # zzgl
        [10, 110, 60, 120],  # Ja!
        [10, 122, 60, 132],  # Milch
        [70, 110, 95, 140],  # 0.99
    ]
    return {
        "page_id": page_id,
        "width": 100,
        "height": 200,
        "words": [{"text": t, "bbox": b} for t, b in zip(texts, boxes)],
        "tags": ["B-BRAND", "B-PRODUCT", "B-PRICE", "O", "B-BRAND", "B-PRODUCT", "B-PRICE"],
    }


# Entities der Seite: 0 Landliebe, 1 Butter, 2 "1.29", 3 Ja!, 4 Milch, 5 "0.99"
OBEN = {0, 1, 2}
UNTEN = {3, 4, 5}


def _assignment(page):
    """Referenz: Woerter 0-2 sind Angebot 0, Woerter 4-6 Angebot 1."""
    return {0: 0, 1: 0, 2: 0, 4: 1, 5: 1, 6: 1}


# ------------------------------------------------------------------- Paare


def test_jedes_entity_paar_kommt_genau_einmal_vor():
    """Sechs Entities ergeben 15 ungeordnete Paare - keines doppelt."""
    pairs = offer_pairs.page_pairs(_page())

    assert len(pairs.index_pairs) == 15
    assert len(set(pairs.index_pairs)) == 15


def test_paare_stehen_in_lesereihenfolge():
    """Erst dadurch duerfen die Deltas ein Vorzeichen tragen.

    Ungeordnet muesste jedes Merkmal symmetrisch sein und "der Preis steht
    *unter* dem Produkt" waere nicht ausdrueckbar - genau die Information,
    die den gelben Kasten von seinem Nachbarn trennt.
    """
    pairs = offer_pairs.page_pairs(_page())

    assert all(i < j for i, j in pairs.index_pairs)


def test_jedes_paar_hat_einen_merkmalsvektor_fester_laenge():
    pairs = offer_pairs.page_pairs(_page())

    assert len(pairs.features) == len(pairs.index_pairs)
    assert all(len(row) == len(offer_pairs.FEATURE_NAMES) for row in pairs.features)


def test_kein_merkmal_heisst_nach_der_rechnung():
    """Menge x Grundpreis bleibt der Richter, nicht die Eingabe.

    Wer hier ein Merkmal ergaenzt, das den Grundpreis auswertet, macht
    `magda offers-verify` zur Messung der Rechnung gegen sich selbst.
    """
    verboten = ("unit_price", "arithmetic", "quantity_times", "rechnung")
    for name in offer_pairs.FEATURE_NAMES:
        assert not any(wort in name for wort in verboten), name


# ------------------------------------------------------------------ Merkmale


def test_der_preis_steht_rechts_neben_seinem_produkt():
    """dx traegt ein Vorzeichen, sonst waere links und rechts dasselbe."""
    pairs = offer_pairs.page_pairs(_page())
    dx = offer_pairs.FEATURE_NAMES.index("dx")

    butter_preis = pairs.index_pairs.index((1, 2))
    assert pairs.features[butter_preis][dx] > 0


def test_grosse_schrift_faellt_als_merkmal_auf():
    """Der Preis im gelben Kasten ist hoeher gesetzt als der Produktname.

    Ohne dieses Merkmal unterscheidet das Modell den Sticker nicht vom
    Fliesstext - und der Sticker ist genau die Einheit, die `_match_badges`
    heute von Hand behandelt.
    """
    pairs = offer_pairs.page_pairs(_page())
    height_j = offer_pairs.FEATURE_NAMES.index("height_j")

    butter_preis = pairs.index_pairs.index((1, 2))
    butter_marke = pairs.index_pairs.index((0, 1))
    assert pairs.features[butter_preis][height_j] > pairs.features[butter_marke][height_j]


def test_entities_zwischen_den_beiden_werden_gezaehlt():
    """Was dazwischenliegt, trennt - das ist der Kern der Legenden-Fehler.

    Zwischen "Landliebe" und "0.99" liegen vier Entities; zwischen
    "Landliebe" und "Butter" keine.
    """
    pairs = offer_pairs.page_pairs(_page())
    between = offer_pairs.FEATURE_NAMES.index("entities_between")

    weit = pairs.features[pairs.index_pairs.index((0, 5))][between]
    nah = pairs.features[pairs.index_pairs.index((0, 1))][between]
    assert weit > nah
    assert nah == 0


def test_merkmale_sind_endlich():
    """Eine Seite ohne Ausdehnung darf keine Division durch null ausloesen."""
    page = _page()
    page["width"] = 0
    page["height"] = 0

    pairs = offer_pairs.page_pairs(page)

    assert all(all(v == v and abs(v) < 1e6 for v in row) for row in pairs.features)


# ------------------------------------------------------------------- Labels


def test_ein_paar_im_selben_referenzangebot_ist_positiv():
    page = _page()
    pairs = offer_pairs.page_pairs(page, _assignment(page))

    assert pairs.labels[pairs.index_pairs.index((0, 1))] == 1
    assert pairs.labels[pairs.index_pairs.index((1, 2))] == 1


def test_ein_paar_ueber_die_angebotsgrenze_ist_negativ():
    page = _page()
    pairs = offer_pairs.page_pairs(page, _assignment(page))

    assert pairs.labels[pairs.index_pairs.index((2, 3))] == 0


def test_ohne_referenz_gibt_es_keine_labels():
    """Beim Vorhersagen liegt keine Referenz vor - die Merkmale trotzdem."""
    pairs = offer_pairs.page_pairs(_page())

    assert pairs.labels is None


def test_eine_entity_ausserhalb_jedes_angebots_erzeugt_kein_trainingsbeispiel():
    """Der Teacher hat geschwiegen, nicht "gehoert nirgends hin" gesagt.

    Solche Paare als Negativ zu zaehlen brachte dem Modell bei, alles
    Nichtzugeordnete zu isolieren - das mag oft richtig sein, belegt ist es
    nicht. Sie fallen deshalb aus dem Training heraus statt hineinzufallen.
    """
    page = _page()
    assignment = {0: 0, 1: 0, 2: 0}      # das zweite Angebot fehlt in der Referenz
    pairs = offer_pairs.page_pairs(page, assignment)

    trainable = [p for p, label in zip(pairs.index_pairs, pairs.labels) if label is not None]
    assert (0, 1) in trainable
    assert (0, 3) not in trainable
    assert (3, 4) not in trainable


# ------------------------------------------------------ Gruppen aus Kanten


def test_kanten_werden_zu_zusammenhangskomponenten():
    edges = {(0, 1): 0.9, (1, 2): 0.8, (3, 4): 0.95, (0, 3): 0.1}

    groups = offer_pairs.groups_from_edges(6, edges, threshold=0.5)

    assert sorted(map(sorted, groups)) == [[0, 1, 2], [3, 4], [5]]


def test_eine_entity_ohne_kante_wird_ihr_eigenes_angebot():
    """Sonst verschwaende sie aus der Ausgabe und der Recall saehe besser aus."""
    groups = offer_pairs.groups_from_edges(3, {}, threshold=0.5)

    assert sorted(map(sorted, groups)) == [[0], [1], [2]]


def test_die_schwelle_wirkt():
    edges = {(0, 1): 0.6}

    assert len(offer_pairs.groups_from_edges(2, edges, threshold=0.5)) == 1
    assert len(offer_pairs.groups_from_edges(2, edges, threshold=0.7)) == 2


def test_gruppen_werden_zu_wortindizes():
    """Gespeichert wird, was den naechsten Labeling-Lauf ueberlebt."""
    page = _page()

    words = offer_pairs.entity_groups_to_words(page, [[0, 1, 2], [3, 4, 5]])

    assert words == [[0, 1, 2], [4, 5, 6]]


@pytest.mark.parametrize("threshold", [0.0, 1.0])
def test_extreme_schwellen_brechen_nicht(threshold):
    edges = {(0, 1): 0.5, (1, 2): 0.5}

    groups = offer_pairs.groups_from_edges(3, edges, threshold=threshold)

    assert sum(len(g) for g in groups) == 3
