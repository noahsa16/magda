"""Das 2x2-Gitter - Merkmalsbloecke einzeln messen.

Die Aufschluesselung nach blindem Fleck ist die eigentliche Kennzahl des
Vorhabens: Farbmerkmale sind fuer den Bereich gebaut, in dem die Arithmetik
schweigt. Eine Gesamtzahl kann steigen, weil das Modell in der ohnehin
prueffbaren Haelfte besser wird - deshalb wird getrennt ausgewiesen.
"""

import pytest

from magda import offer_grid


def _page(tags, texts=None):
    """Vier Entities untereinander, je ein Wort."""
    texts = texts or ["Butter", "1.29", "Milch", "0.99"]
    boxes = [[10, 10 + 30 * i, 60, 20 + 30 * i] for i in range(len(tags))]
    return {
        "page_id": "p1",
        "width": 100,
        "height": 200,
        "words": [{"text": t, "bbox": b} for t, b in zip(texts, boxes)],
        "tags": tags,
    }


MIT_GRUNDPREIS = ["B-PRODUCT", "B-PRICE", "B-UNIT_PRICE", "B-PRODUCT"]
OHNE_GRUNDPREIS = ["B-PRODUCT", "B-PRICE", "B-PRODUCT", "B-PRICE"]


# ------------------------------------------------------------- Bewertung


def test_eine_perfekte_gruppierung_trifft_alles():
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 1, 3: 1}

    counts = offer_grid.judge_page(page, assignment, [[0, 1], [2, 3]])

    assert counts.total.pair_f1 == pytest.approx(1.0)
    assert counts.total.group_f1 == pytest.approx(1.0)
    assert counts.total.exact_groups == 2


def test_alles_in_eine_gruppe_zu_werfen_trifft_keine_gruppe_genau():
    """Gruppen-F1 zaehlt nur exakte Treffer - "die Zeile stimmt"."""
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 1, 3: 1}

    counts = offer_grid.judge_page(page, assignment, [[0, 1, 2, 3]])

    assert counts.total.exact_groups == 0
    assert counts.total.group_f1 == pytest.approx(0.0)
    # Paarweise bleibt trotzdem etwas uebrig: die beiden echten Paare
    # stecken in der grossen Gruppe mit drin.
    assert counts.total.shared_pairs == 2


def test_entities_ausserhalb_der_referenz_bewegen_keine_zahl():
    """Wo der Mensch geschwiegen hat, ist kein Negativbeleg."""
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0}          # die zweite Haelfte fehlt

    counts = offer_grid.judge_page(page, assignment, [[0, 1], [2, 3]])

    assert counts.total.ref_groups == 1
    assert counts.total.ref_pairs == 1


# --------------------------------------------------------- Blinder Fleck


def test_ohne_grundpreis_gilt_das_paar_als_blind():
    """Ohne UNIT_PRICE in der Gruppe kann die Rechnung nicht urteilen."""
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 1, 3: 1}

    counts = offer_grid.judge_page(page, assignment, [[0, 1], [2, 3]])

    assert counts.blind.ref_pairs == 2
    assert counts.checkable.ref_pairs == 0


def test_mit_grundpreis_gilt_das_paar_als_pruefbar():
    page = _page(MIT_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 0, 3: 1}   # Grundpreis in Gruppe 0

    counts = offer_grid.judge_page(page, assignment, [[0, 1, 2], [3]])

    assert counts.checkable.ref_pairs == 3   # drei Paare in Gruppe 0
    assert counts.blind.ref_pairs == 0


def test_blind_und_pruefbar_ergeben_zusammen_das_ganze():
    """Sonst verschwaende eine Teilmenge unbemerkt aus der Auswertung."""
    page = _page(MIT_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 0, 3: 1}

    counts = offer_grid.judge_page(page, assignment, [[0, 1], [2], [3]])

    assert counts.blind.ref_pairs + counts.checkable.ref_pairs == counts.total.ref_pairs
    assert counts.blind.ref_groups + counts.checkable.ref_groups == counts.total.ref_groups


def test_blind_haengt_an_der_referenz_nicht_an_der_vorhersage():
    """Sonst haenge die Einteilung an dem System, das beurteilt werden soll.

    Dieselbe Referenz, zwei verschiedene Systemausgaben - die Zahl der
    blinden Referenzpaare darf sich nicht bewegen.
    """
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 1, 3: 1}

    gut = offer_grid.judge_page(page, assignment, [[0, 1], [2, 3]])
    schlecht = offer_grid.judge_page(page, assignment, [[0, 2], [1, 3]])

    assert gut.blind.ref_pairs == schlecht.blind.ref_pairs


# ------------------------------------------------------------- Bootstrap


def _counts(page_id, ref, sys, shared):
    page = offer_grid.PageCounts(page_id=page_id)
    for scope in (page.total, page.blind):
        scope.ref_pairs, scope.sys_pairs, scope.shared_pairs = ref, sys, shared
    return page


def test_bootstrap_resampelt_cluster_nicht_seiten():
    """Elf Regionalfassungen einer Vorlage sind eine Beobachtung, nicht elf.

    Ueber Seiten resampelt waere das Intervall zu eng - genau der Fehler,
    den `magda significance` fuer die Labelmetriken vermeidet.
    """
    per_page = [_counts("a", 10, 10, 10), _counts("b", 10, 10, 10),
                _counts("c", 10, 10, 0)]

    eng = offer_grid.bootstrap(per_page, [["a"], ["b"], ["c"]], rounds=200)
    weit = offer_grid.bootstrap(per_page, [["a", "b"], ["c"]], rounds=200)

    assert eng["clusters"] == 3
    assert weit["clusters"] == 2
    # Weniger unabhaengige Einheiten -> breiteres Intervall.
    assert (weit["high"] - weit["low"]) > (eng["high"] - eng["low"])


def test_bootstrap_braucht_mindestens_zwei_cluster():
    """Ein einziger Cluster ergibt ein Intervall der Breite null - also keines."""
    result = offer_grid.bootstrap([_counts("a", 10, 10, 10)], [["a"]], rounds=50)

    assert result["low"] is None


def test_bootstrap_ist_bei_gleichem_seed_reproduzierbar():
    per_page = [_counts("a", 10, 10, 9), _counts("b", 10, 10, 4)]
    clusters = [["a"], ["b"]]

    first = offer_grid.bootstrap(per_page, clusters, rounds=100, seed=7)
    second = offer_grid.bootstrap(per_page, clusters, rounds=100, seed=7)

    assert first == second


def test_alle_varianten_bauen_auf_denselben_grundmerkmalen_auf():
    """Ein Gitter vergleicht Zusaetze, keine verschiedenen Systeme."""
    from magda import offer_pairs

    basis = offer_pairs.feature_names(offer_grid.VARIANTS["basis"])
    for name, blocks in offer_grid.VARIANTS.items():
        assert offer_pairs.feature_names(blocks)[:len(basis)] == basis, name
