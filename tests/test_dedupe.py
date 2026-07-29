"""Entdopplung: Druckkennung raus, ähnliche Seiten zusammen."""

from magda import dedupe

# Am rechten Seitenrand steht senkrecht "<Seite>_<Region>-<Region>…".
SEITE_A = ["NATURGUT", "Bio-Möhren", "1.49", "Deutschland", "03_02-09-10"]
SEITE_B = ["NATURGUT", "Bio-Möhren", "1.49", "Deutschland", "03_01-11-12-13"]
SEITE_C = ["KROMBACHER", "Fassbrause", "4.99", "Aktion", "07_04-14"]


def test_print_marker_wird_gefunden():
    assert dedupe.print_marker(SEITE_A) == "03_02-09-10"
    assert dedupe.print_marker(["Milch", "1.09"]) is None


def test_normalize_entfernt_nur_die_druckkennung():
    assert dedupe.normalize(SEITE_A) == ["NATURGUT", "Bio-Möhren", "1.49", "Deutschland"]


def test_preise_werden_nicht_faelschlich_als_kennung_erkannt():
    """"1.49" und "25.7." dürfen die Kennung nicht auslösen – sonst
    verschwinden Preise und Datumsangaben aus dem Vergleich."""
    assert dedupe.normalize(["1.49", "25.7.", "20.7.", "1_2"]) == ["1.49", "25.7.", "20.7.", "1_2"]


def test_gleiche_seite_mit_anderer_kennung_faellt_zusammen():
    groups = dedupe.group({"a": SEITE_A, "b": SEITE_B, "c": SEITE_C})

    assert ["a", "b"] in groups
    assert ["c"] in groups


def test_schwelle_entscheidet():
    fast_gleich = {
        "a": ["Apfel", "Birne", "Kirsche", "Pflaume", "1.99"],
        "b": ["Apfel", "Birne", "Kirsche", "Pflaume", "2.99"],
    }
    # 4 von 6 gemeinsam -> Jaccard 0.67
    assert len(dedupe.group(fast_gleich, threshold=0.6)) == 1
    assert len(dedupe.group(fast_gleich, threshold=0.9)) == 2


def test_gruppierung_ist_transitiv():
    """A~B und B~C legt alle drei zusammen, auch wenn A und C auseinanderliegen.
    Eine Kette beinahe gleicher Regionalfassungen ist eine Seite, keine drei."""
    chain = {
        "a": ["w1", "w2", "w3", "w4", "w5", "w6", "w7", "w8", "w9", "x"],
        "b": ["w1", "w2", "w3", "w4", "w5", "w6", "w7", "w8", "w9", "y"],
        "c": ["w1", "w2", "w3", "w4", "w5", "w6", "w7", "w8", "w9", "z"],
    }
    assert dedupe.group(chain, threshold=0.8) == [["a", "b", "c"]]


def test_choose_bevorzugt_bearbeitete_seiten():
    """Eine gelabelte oder annotierte Seite wegzuwerfen hieße, die Arbeit
    daran wegzuwerfen."""
    assert dedupe.choose(["1342812_p2", "1342881_p4"], {"1342881_p4"}) == "1342881_p4"
    assert dedupe.choose(["1342812_p2", "1342881_p4"], set()) == "1342812_p2"
