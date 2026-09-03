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

from magda import offer_pairs, offers


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


# --------------------------------------------------------------- Bloecke


def _value(pairs, pair, name):
    """Ein einzelnes Merkmal eines Paares, ueber seinen Namen."""
    return pairs.features[pairs.index_pairs.index(pair)][pairs.feature_names.index(name)]


def test_default_bloecke_ergeben_die_bisherigen_dreissig():
    """Bestehende Aufrufer und Checkpoints duerfen sich nicht verschieben."""
    names = offer_pairs.feature_names(offer_pairs.DEFAULT_BLOCKS)

    assert len(names) == 30
    assert names[:18] == [f"type_i_{t}" for t in offer_pairs.TYPES] + [
        f"type_j_{t}" for t in offer_pairs.TYPES
    ]


def test_bloecke_haengen_hinten_an_statt_sich_dazwischenzuschieben():
    """Sonst zeigt jedes gelernte Gewicht auf eine andere Spalte."""
    base = offer_pairs.feature_names(offer_pairs.DEFAULT_BLOCKS)
    full = offer_pairs.feature_names(offer_pairs.ALL_BLOCKS)

    assert full[: len(base)] == base


def test_unbekannter_block_bricht_ab():
    with pytest.raises(ValueError, match="unbekannt"):
        offer_pairs.feature_names(("types", "gibtsnicht"))


# ------------------------------------------------- Kontextmerkmale (Geometrie)


def _legend_page():
    """Zwei Produkte ueber zwei Preisen - die Form einer Non-Food-Legende.

    Nachgebaut nach `1347387_p31`: Jeder Preis greift zum naechstgelegenen
    Namen, und wenn der Abstand einmal kippt, kippt die ganze Spalte mit.
    Hier liegt Produkt 1 naeher an Preis 0 als Produkt 0 - reine Naehe
    ordnet also falsch zu.
    """
    texts = ["Pflanztopf-Set", "Fensterdoppelrollo", "8.99", "9.99"]
    boxes = [
        [10, 10, 60, 20],
        [10, 30, 60, 40],
        [10, 50, 60, 60],
        [10, 70, 60, 80],
    ]
    return {
        "page_id": "legende",
        "width": 100,
        "height": 200,
        "words": [{"text": t, "bbox": b} for t, b in zip(texts, boxes)],
        "tags": ["B-PRODUCT", "B-PRODUCT", "B-PRICE", "B-PRICE"],
    }


def test_ein_zweiter_produktanker_dazwischen_trennt():
    """`products_between` ist das staerkste Trennsignal ohne Bild.

    Ein Angebot ist ein Stern um genau einen Produktanker. Zwischen Produkt 0
    und Preis 0 liegt Produkt 1 - zwischen Produkt 1 und Preis 0 liegt keiner.
    """
    pairs = offer_pairs.page_pairs(_legend_page(), blocks=offer_pairs.GEOMETRY_BLOCKS)

    assert _value(pairs, (0, 2), "products_between") > 0
    assert _value(pairs, (1, 2), "products_between") == 0


def test_entities_between_kann_das_nicht_unterscheiden():
    """Der Grund, warum `products_between` nicht redundant ist.

    Typblind gezaehlt liegt in beiden Faellen etwas dazwischen - nur der
    Ankertyp sagt, ob es trennt.
    """
    pairs = offer_pairs.page_pairs(_legend_page(), blocks=offer_pairs.GEOMETRY_BLOCKS)

    assert _value(pairs, (0, 2), "entities_between") > 0
    assert _value(pairs, (0, 3), "entities_between") > 0


def test_naeherer_rivale_gleichen_typs_wird_gezaehlt():
    """Der Legendenversatz ist ein Margenproblem, kein Abstandsproblem."""
    pairs = offer_pairs.page_pairs(_legend_page(), blocks=offer_pairs.GEOMETRY_BLOCKS)

    # Zu Preis 0 liegt Produkt 1 naeher als Produkt 0.
    assert _value(pairs, (0, 2), "closer_rivals_i") > 0
    assert _value(pairs, (1, 2), "closer_rivals_i") == 0


def test_abstandsverhaeltnis_ist_eins_beim_naechsten_kandidaten():
    """Nicht "wie weit", sondern "wie weit im Vergleich zu den Alternativen".

    Die Erwartungen stehen als Zahl da, nicht als `1/RATIO_CAP`: Wer die
    Konstante in die Erwartung schreibt, baut einen Test, der sich selbst
    bestaetigt und die Kappung nicht schuetzt.
    """
    pairs = offer_pairs.page_pairs(_legend_page(), blocks=offer_pairs.GEOMETRY_BLOCKS)

    # Preis 2 ist der naechste Preis zu Produkt 0 -> Verhaeltnis 1.0, /5 = 0.2.
    assert _value(pairs, (0, 2), "distance_ratio") == pytest.approx(0.2)
    # Preis 3 liegt 60 statt 40 entfernt -> 1.5, /5 = 0.3.
    assert _value(pairs, (0, 3), "distance_ratio") == pytest.approx(0.3)


def test_ungelabelte_woerter_dazwischen_werden_gezaehlt():
    """54,5 % aller Woerter sind O - fuer die alten Merkmale unsichtbar.

    Das Kleingedruckte steht raeumlich zwischen den Angeboten und zieht
    jede Nachbarschaftsheuristik schief.
    """
    pairs = offer_pairs.page_pairs(_page(), blocks=offer_pairs.GEOMETRY_BLOCKS)

    assert _value(pairs, (2, 3), "words_between") > 0   # "zzgl" liegt dazwischen
    assert _value(pairs, (0, 1), "words_between") == 0


# ------------------------------------------------------------ Farbmerkmale


def _painted(page, tiles):
    """Seitengrosses RGB-Array, weiss, mit eingemalten Kacheln."""
    import numpy as np

    pixels = np.full((int(page["height"]), int(page["width"]), 3), 255, dtype=np.uint8)
    for x0, y0, x1, y1, color in tiles:
        pixels[y0:y1, x0:x1] = color
    return pixels


GELB = (255, 212, 0)
BLAU = (0, 124, 132)


def test_gleiche_kachel_heisst_kleiner_farbabstand_und_durchgehender_pfad():
    page = _page()
    pixels = _painted(page, [(5, 5, 99, 145, GELB)])   # eine Kachel ueber beide

    pairs = offer_pairs.page_pairs(page, pixels=pixels, blocks=offer_pairs.ALL_BLOCKS)

    assert _value(pairs, (0, 3), "bg_distance") == pytest.approx(0.0, abs=1e-6)
    assert _value(pairs, (0, 3), "path_same_bg") == pytest.approx(1.0)


def test_verschiedene_kacheln_heissen_grosser_farbabstand():
    """Das Merkmal, das die Wortkoordinaten nicht hergeben.

    Der Farbabstand steht als ausgerechnete Zahl da, damit die Normierung
    auf sqrt(3*255^2) mitgeschuetzt ist: Blau (0,124,132) zu Weiss hat den
    RGB-Abstand 311.95, geteilt durch 441.67 sind das 0.706.
    """
    page = _spread_page()
    pixels = _painted(page, [(5, 45, 65, 65, BLAU)])   # nur Entity 1 auf Kachel

    pairs = offer_pairs.page_pairs(page, pixels=pixels, blocks=offer_pairs.ALL_BLOCKS)

    assert _value(pairs, (0, 1), "bg_distance") == pytest.approx(0.706, abs=0.005)
    # Der Pfad verlaesst den Hintergrund von Entity 0 (Weiss), sobald er die
    # blaue Kachel erreicht.
    assert _value(pairs, (0, 1), "path_same_bg") < 1.0


def test_der_pfadanteil_saettigt_nicht_bei_vielen_farbwechseln():
    """Der Grund, warum das Zaehlen von Wechseln ersetzt wurde.

    Auf echten Prospektseiten waren 92 % aller Paare am Anschlag von fuenf
    Wechseln, bei vervierfachter Toleranz noch 80 % - eine Seite ist
    visuell dicht, jede Linie kreuzt Fotos, Text und Kacheln. Ein Anteil
    bleibt dagegen aussagekraeftig: hier liegt er strikt zwischen 0 und 1.
    """
    page = _page()
    einfarbig = _painted(page, [(5, 5, 99, 145, GELB)])
    stripes = [(5, 5 + 6 * i, 99, 8 + 6 * i, GELB if i % 2 else BLAU) for i in range(24)]

    ruhig = _value(offer_pairs.page_pairs(
        page, pixels=einfarbig, blocks=offer_pairs.ALL_BLOCKS), (0, 3), "path_same_bg")
    unruhig = _value(offer_pairs.page_pairs(
        page, pixels=_painted(page, stripes), blocks=offer_pairs.ALL_BLOCKS),
        (0, 3), "path_same_bg")

    # Der Vorgaenger stand in beiden Faellen bei 1.0 und unterschied nichts.
    # Gefordert ist deshalb ein deutlicher Abstand, keine feste Schwelle:
    # Wo der Wert der unruhigen Seite genau landet, haengt an der
    # Glaettungsgroesse - dass er weit unter der ruhigen liegt, nicht.
    assert ruhig == pytest.approx(1.0)
    assert ruhig - unruhig > 0.4


def test_eine_fremde_flaeche_dazwischen_senkt_den_pfadanteil():
    """Zwei Entities auf gleicher Kachelfarbe, aber durch Fremdfarbe getrennt."""
    page = _spread_page()
    zusammen = _painted(page, [(5, 5, 65, 65, GELB)])
    getrennt = _painted(page, [(5, 5, 65, 25, GELB), (5, 45, 65, 65, GELB),
                               (5, 28, 65, 42, BLAU)])

    a = _value(offer_pairs.page_pairs(page, pixels=zusammen,
                                      blocks=offer_pairs.ALL_BLOCKS), (0, 1), "path_same_bg")
    b = _value(offer_pairs.page_pairs(page, pixels=getrennt,
                                      blocks=offer_pairs.ALL_BLOCKS), (0, 1), "path_same_bg")

    assert a == pytest.approx(1.0)
    assert b < 0.7


def _spread_page():
    """Vier weit auseinanderliegende Entities - je Rand einzeln bemalbar."""
    boxes = [[10, 10, 60, 20], [10, 50, 60, 60], [10, 90, 60, 100], [10, 130, 60, 140]]
    return {
        "page_id": "spread",
        "width": 100,
        "height": 200,
        "words": [{"text": t, "bbox": b} for t, b in zip("abcd", boxes)],
        "tags": ["B-PRODUCT", "B-PRICE", "B-PRODUCT", "B-PRICE"],
    }


def test_abstand_zum_seitenueblichen_hintergrund():
    """Trennt "steht auf einer Kachel" von "steht auf dem Seitengrund".

    Das Merkmal misst gegen den Median der Entity-Hintergruende. Liegt genau
    die Haelfte auf Kachel, ist der Median die Mitte und das Merkmal stumpf -
    deshalb hier eine Seite mit einer einzelnen Kachel.
    """
    page = _spread_page()
    pixels = _painted(page, [(5, 5, 65, 25, BLAU)])   # nur Entity 0

    pairs = offer_pairs.page_pairs(page, pixels=pixels, blocks=offer_pairs.ALL_BLOCKS)

    assert _value(pairs, (0, 1), "bg_offpage_i") > 0.3
    assert _value(pairs, (0, 1), "bg_offpage_j") == pytest.approx(0.0, abs=1e-6)


def test_der_hintergrund_wird_neben_der_box_gemessen_nicht_darin():
    """`BORDER_PAD` ist der Grund, warum die Schrift die Farbe nicht faelscht.

    Entity 0 ist ganz schwarz uebermalt, Entity 1 nicht. Wer innerhalb der
    Box misst, bekommt fuer 0 Schriftschwarz statt Kachelblau - und
    `bg_distance` zwischen zwei Entities *derselben* Kachel waere gross
    statt null. Waeren beide uebermalt, laese man innen wie aussen
    dasselbe und der Test unterschiede nichts.
    """
    page = _spread_page()
    pixels = _painted(page, [
        (5, 5, 65, 65, BLAU),          # eine Kachel ueber Entity 0 und 1
        (10, 10, 60, 20, (0, 0, 0)),   # nur Entity 0 komplett "beschriftet"
    ])

    pairs = offer_pairs.page_pairs(page, pixels=pixels, blocks=offer_pairs.ALL_BLOCKS)

    # Beide sitzen auf derselben Kachel - der Abstand ist null, sofern
    # neben der Box gemessen wird.
    assert _value(pairs, (0, 1), "bg_distance") == pytest.approx(0.0, abs=1e-6)


def test_farbmerkmale_ohne_bild_brechen_ab():
    """Kein Sentinel: der waere seitenkonstant und damit Vorlagen-Memorieren.

    In der echten Pipeline schreibt `cli/extract.py` das Bild immer - ein
    Abbruch kostet betrieblich nichts und nennt die Abhilfe.
    """
    with pytest.raises(ValueError, match="magda extract"):
        offer_pairs.page_pairs(_page(), blocks=offer_pairs.ALL_BLOCKS)


def test_ohne_farbblock_wird_kein_bild_verlangt():
    """Die 30 alten Merkmale kommen weiter ohne Platte aus."""
    pairs = offer_pairs.page_pairs(_page(), blocks=offer_pairs.GEOMETRY_BLOCKS)

    assert pairs.features and all(len(row) == len(pairs.feature_names) for row in pairs.features)


def test_auch_die_neuen_merkmale_heissen_nicht_nach_der_rechnung():
    """Der Verboten-Test deckt den erweiterten Vektor mit ab."""
    verboten = ("unit_price", "arithmetic", "quantity_times", "rechnung")
    for name in offer_pairs.feature_names(offer_pairs.ALL_BLOCKS):
        assert not any(wort in name for wort in verboten), name


# ------------------------------------------------------------------- Anker


def _variantenblock():
    """Ein Produktname, zwei Preise darunter - die Form aus Issue #6.

    Der zweite Preis steht weiter weg als der fremde Produktname unten;
    genau deshalb trennt die Geometrie hier falsch.
    """
    texts = ["Pfanne", "9.99", "14.99", "Topf"]
    boxes = [
        [10, 10, 60, 20],     # Pfanne   - der gemeinsame Anker
        [10, 40, 40, 55],     # 9.99
        [10, 90, 40, 105],    # 14.99    - weit unten
        [10, 108, 60, 118],   # Topf     - naeher an 14.99 als Pfanne
    ]
    return {
        "page_id": "vb",
        "width": 100,
        "height": 200,
        "words": [{"text": t, "bbox": b} for t, b in zip(texts, boxes)],
        "tags": ["B-PRODUCT", "B-PRICE", "B-PRICE", "B-PRODUCT"],
    }


ANKER = offer_pairs.ANCHOR_BLOCKS


def test_zwei_preise_unter_einem_namen_teilen_ihren_anker():
    """Das Zielmerkmal: die Geschwisterkante eines Variantenblocks."""
    page = _page()
    pairs = offer_pairs.page_pairs(page, blocks=ANKER)
    shared = pairs.feature_names.index("shared_anchor")
    von = dict(zip(pairs.index_pairs, pairs.features))

    # Preis 2 und Produkt 1 gehoeren zusammen, Preis 2 und Produkt 4 nicht.
    assert von[(1, 2)][shared] == 1.0
    assert von[(2, 4)][shared] == 0.0


def test_der_anker_verbindet_ueber_die_geometrie_hinweg():
    """Der Fall, den die vorhandenen Merkmale nicht loesen.

    "14.99" liegt naeher an "Topf" als an "Pfanne". Trotzdem muss es
    denselben Anker haben wie "9.99" - sonst trennt die Naehe wieder, und
    das Merkmal traegt nichts bei, was `distance` nicht schon sagt.
    """
    pairs = offer_pairs.page_pairs(_variantenblock(), blocks=ANKER)
    shared = pairs.feature_names.index("shared_anchor")
    von = dict(zip(pairs.index_pairs, pairs.features))

    assert von[(1, 2)][shared] == 0.0     # 14.99 ankert am naeheren "Topf"
    # Die Speiche stimmt trotzdem: jeder Preis teilt den Anker mit *seinem*
    # naechsten Produktnamen.
    assert von[(0, 1)][shared] == 1.0     # Pfanne - 9.99
    assert von[(2, 3)][shared] == 1.0     # 14.99 - Topf


def test_zwei_produktnamen_teilen_nie_einen_anker():
    """Die dokumentierte Grenze - jeder Anker ist sein eigener.

    Bloecke mit mehreren Produktnamen loest dieses Merkmal nicht. Steht so
    im Docstring; hier festgehalten, damit die Grenze nicht spaeter fuer
    einen Fehler gehalten wird.
    """
    pairs = offer_pairs.page_pairs(_variantenblock(), blocks=ANKER)
    shared = pairs.feature_names.index("shared_anchor")
    von = dict(zip(pairs.index_pairs, pairs.features))

    assert von[(0, 3)][shared] == 0.0


def test_ohne_produktnamen_bleiben_die_ankermerkmale_null():
    """Kein Sentinel: der waere seitenkonstant und damit selbst ein Merkmal."""
    page = _variantenblock()
    page["tags"] = ["B-PRICE", "B-PRICE", "B-PRICE", "B-PRICE"]

    pairs = offer_pairs.page_pairs(page, blocks=ANKER)

    erste = pairs.feature_names.index("shared_anchor")
    for row in pairs.features:
        assert row[erste:erste + 3] == [0.0, 0.0, 0.0]


def test_der_ankerblock_haengt_hinten_an():
    """Sonst zeigt jedes gelernte Gewicht eines Checkpoints auf eine andere
    Spalte, und das faellt durch keine Pruefung auf."""
    mit = offer_pairs.feature_names(ANKER)
    ohne = offer_pairs.feature_names(offer_pairs.GEOMETRY_BLOCKS)

    assert mit[:len(ohne)] == ohne
    assert mit[len(ohne):] == offer_pairs.ANCHOR_NAMES


def test_die_variante_beide_waechst_nicht_mit_neuen_bloecken():
    """`ALL_BLOCKS = BLOCK_ORDER` haette "beide" still um den Ankerblock
    erweitert - und jeder Vergleich gegen eine aeltere Zahl meinte dann
    etwas anderes."""
    assert "anchor" not in offer_pairs.ALL_BLOCKS
    assert len(offer_pairs.feature_names(offer_pairs.ALL_BLOCKS)) == 39


def test_kein_ankermerkmal_heisst_nach_der_rechnung():
    """Dieselbe Zusicherung wie fuer die Grundmerkmale, fuer den neuen Block."""
    verboten = ("unit_price", "arithmetic", "quantity_times", "rechnung")
    for name in offer_pairs.ANCHOR_NAMES:
        assert not any(wort in name for wort in verboten), name


def _ein_anker_zwei_abstaende():
    """Ein Produktname, ein Preis knapp darunter, einer sehr weit unten."""
    texts = ["Pfanne", "9.99", "14.99"]
    boxes = [[10, 10, 60, 20], [10, 25, 40, 40], [10, 900, 40, 915]]
    return {
        "page_id": "gap", "width": 100, "height": 1000,
        "words": [{"text": t, "bbox": b} for t, b in zip(texts, boxes)],
        "tags": ["B-PRODUCT", "B-PRICE", "B-PRICE"],
    }


def test_der_ankerabstand_waechst_mit_der_entfernung():
    """Sonst traegt das Merkmal nur "geteilt ja/nein" und nicht, wie sicher."""
    pairs = offer_pairs.page_pairs(_ein_anker_zwei_abstaende(), blocks=ANKER)
    gap_j = pairs.feature_names.index("anchor_gap_j")
    von = dict(zip(pairs.index_pairs, pairs.features))

    assert von[(0, 1)][gap_j] < von[(0, 2)][gap_j]


def test_der_ankerabstand_wird_gekappt():
    """Ungekappt dominiert eine Seite ohne nahen Namen die Skala, und die
    Unterschiede im relevanten Bereich - ein bis zwei Zeilen - fallen
    darunter zusammen."""
    pairs = offer_pairs.page_pairs(_ein_anker_zwei_abstaende(), blocks=ANKER)
    gap_j = pairs.feature_names.index("anchor_gap_j")
    von = dict(zip(pairs.index_pairs, pairs.features))

    assert von[(0, 2)][gap_j] == 1.0       # der ferne Preis liegt an der Kappe
    assert von[(0, 1)][gap_j] < 0.2        # der nahe deutlich darunter


def test_eine_entity_ohne_eigenen_namen_ankert_nicht_am_fremden():
    """Ein Produktname ist sein eigener Anker - nicht der naechste andere.

    Ohne das wanderte jeder Name zum Nachbarn und zwei benachbarte
    Angebote teilten sich einen Anker: das Merkmal sagte dann das
    Gegenteil dessen, wofuer es gebaut ist.
    """
    page = _variantenblock()
    entities = [e for e in offers.entities_from_page(page)
                if e.type in offers.VALUE_TYPES]

    of_index, gaps = offer_pairs._page_anchors(entities)

    assert of_index[0] == 0 and gaps[0] == 0.0     # "Pfanne" ankert an sich
    assert of_index[3] == 3 and gaps[3] == 0.0     # "Topf" ebenso


# ------------------------------------------------------- Lexikalischer Block

LEXIK = offer_pairs.LEXICAL_BLOCKS


def _lexik_page():
    """Zwei Angebote, getrennt durch "oder", das zweite mit Aktionspreis.

    Die drei Wortarten, um die es geht, tragen alle das Label `O`: "je",
    "Stueck", "oder" und "Aktion" fallen durchs Labeling und liegen bis
    hierher ungenutzt in der Wortliste.
    """
    texts = ["Landliebe", "Butter", "je", "Stück,", "1.29",
             "oder", "Ja!", "Milch", "Aktion", "0.99"]
    boxes = [[10, 10 + 12 * i, 60, 20 + 12 * i] for i in range(10)]
    return {
        "page_id": "lexik",
        "width": 100,
        "height": 200,
        "words": [{"text": t, "bbox": b} for t, b in zip(texts, boxes)],
        "tags": ["B-BRAND", "B-PRODUCT", "O", "O", "B-PRICE",
                 "O", "B-BRAND", "B-PRODUCT", "O", "B-PRICE"],
    }


def _lexik(pairs, i, j, name):
    """Ein einzelnes Lexikmerkmal des Paares (i, j)."""
    column = pairs.feature_names.index(name)
    return pairs.features[pairs.index_pairs.index((i, j))][column]


def test_der_lexikblock_haengt_hinten_an():
    """Dieselbe Zusicherung wie fuer den Ankerblock: ein Checkpoint, dessen
    Spalten sich verschieben, rechnet still falsch weiter."""
    mit = offer_pairs.feature_names(LEXIK)
    ohne = offer_pairs.feature_names(offer_pairs.GEOMETRY_BLOCKS)

    assert mit[:len(ohne)] == ohne
    assert mit[len(ohne):] == offer_pairs.LEXICAL_NAMES
    # Erst die gestapelte Variante prueft die *Stellung* im BLOCK_ORDER:
    # allein gemessen bliebe der Lexikblock auch dann hinten, wenn er sich
    # vor den Ankerblock schoebe - und genau das verschoebe die Spalten
    # eines Checkpoints, ohne dass etwas abstuerzt.
    gestapelt = offer_pairs.feature_names(offer_pairs.ANCHOR_LEXICAL_BLOCKS)
    assert gestapelt == ohne + offer_pairs.ANCHOR_NAMES + offer_pairs.LEXICAL_NAMES


def test_je_stueck_bindet_den_preis_an_die_beschreibung():
    """Der Textlayer sagt, was die Geometrie nur vermuten kann.

    Entities: 0 Landliebe, 1 Butter, 2 "1.29", 3 Ja!, 4 Milch, 5 "0.99".
    Vor dem Preis stehen "je" und "Stueck," - beide als `O` gelabelt.
    """
    pairs = offer_pairs.page_pairs(_lexik_page(), blocks=LEXIK)

    assert _lexik(pairs, 1, 2, "promo_before_j") == 1.0
    assert _lexik(pairs, 1, 2, "unit_before_j") == 1.0
    # Vor "Butter" steht nur die Marke - keine der beiden Wortarten.
    assert _lexik(pairs, 1, 2, "promo_before_i") == 0.0
    assert _lexik(pairs, 1, 2, "unit_before_i") == 0.0


def test_satzzeichen_stehen_der_wortliste_nicht_im_weg():
    """Der Textlayer haengt Kommas und Sternchen an: "Stueck," ist "Stueck"."""
    assert offer_pairs._normalise_token("Stück,") == "stück"
    assert offer_pairs._normalise_token("Filz*") == "filz"
    assert offer_pairs._normalise_token(" JE ") == "je"


def test_aktion_dazwischen_trennt():
    """"Aktion" oeffnet einen Preisblock - steht es zwischen zwei Entities,
    faengt dort ein neues Angebot an."""
    pairs = offer_pairs.page_pairs(_lexik_page(), blocks=LEXIK)

    assert _lexik(pairs, 4, 5, "action_between") == 1.0
    assert _lexik(pairs, 4, 5, "action_before_j") == 1.0
    assert _lexik(pairs, 1, 2, "action_between") == 0.0


def test_oder_dazwischen_trennt():
    """Dieselbe Grenze, die `labeling.trim_spans` schon beim Labeln zieht."""
    pairs = offer_pairs.page_pairs(_lexik_page(), blocks=LEXIK)

    assert _lexik(pairs, 2, 3, "separator_between") == 1.0
    assert _lexik(pairs, 0, 1, "separator_between") == 0.0


def test_ohne_lexikblock_wird_kein_wort_gelesen():
    """Der Block ist abschaltbar, sonst kann die Ablation ihn nicht messen."""
    ohne = offer_pairs.page_pairs(_lexik_page())

    assert len(ohne.features[0]) == len(offer_pairs.FEATURE_NAMES)
    assert not any(name in ohne.feature_names
                   for name in offer_pairs.LEXICAL_NAMES)


def test_kein_lexikmerkmal_heisst_nach_der_rechnung():
    """Dieselbe Zusicherung wie fuer die anderen Bloecke."""
    verboten = ("unit_price", "arithmetic", "quantity_times", "rechnung")
    for name in offer_pairs.LEXICAL_NAMES:
        assert not any(wort in name for wort in verboten), name
