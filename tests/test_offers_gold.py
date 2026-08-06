"""Die handannotierte Gruppierungsreferenz und ihre Metriken.

Das Clustering laesst sich per Ablation gegen die Arithmetik pruefen
(`magda offers-report`), aber nur dort, wo ein Grundpreis steht. Ueber die
Haelfte der Urteile lautet deshalb "nicht beurteilbar", und das deckt sich
fast mit Non-Food. Diese Luecke schliesst keine Heuristik, sondern nur eine
Referenz von Hand.

Sie gruppiert *Wortindizes*, nicht Entity-Spans: Spans gehoeren einem
Labelordner, Woerter der Seite. So beurteilt dieselbe Referenz die Heuristik
auf sonnet-5-Labels, ein LLM als Gruppierungs-Teacher und spaeter einen
OFFER-Kopf auf GBERT.
"""

import json

import pytest

from magda import config, offers_gold
from magda.gold import words_hash
from magda.offers import cluster_page


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """Verlegt gold/offers/ und data/words/ ins tmp-Verzeichnis.

    Gepatcht wird auf config, nicht auf offers_gold - das Modul liest die
    Pfade zur Laufzeit, genau wie gold.py und api.py.
    """
    words_dir = tmp_path / "words"
    gold_dir = tmp_path / "gold"
    words_dir.mkdir()
    gold_dir.mkdir()
    monkeypatch.setattr(config, "WORDS_DIR", words_dir)
    monkeypatch.setattr(config, "GOLD_DIR", gold_dir)
    return words_dir, gold_dir


def _write(dirs, page_id, texts, groups, status="done", hash_override=None):
    words_dir, gold_dir = dirs
    words = [{"text": t, "bbox": [0, 0, 1, 1]} for t in texts]
    with open(words_dir / f"{page_id}.json", "w") as f:
        json.dump({"page_id": page_id, "width": 100, "height": 200, "words": words}, f)
    target = gold_dir / "offers"
    target.mkdir(exist_ok=True)
    with open(target / f"{page_id}.json", "w") as f:
        json.dump(
            {
                "page_id": page_id,
                "words_hash": hash_override or words_hash(words),
                "status": status,
                "annotator": "",
                "groups": groups,
            },
            f,
        )


# ------------------------------------------------------------------ Laden


def test_laedt_gruppen_als_zuordnung_wort_zu_angebot(dirs):
    _write(dirs, "p1", ["Landliebe", "Milch", "1.29", "Ja!", "Butter", "2.49"],
           [[0, 1, 2], [3, 4, 5]])

    reference = offers_gold.load_reference()

    assert reference.assignments["p1"] == {0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1}


def test_ungruppierte_woerter_fehlen_in_der_zuordnung(dirs):
    """Kleingedrucktes gehoert zu keinem Angebot - das ist eine Aussage, kein Loch."""
    _write(dirs, "p1", ["Milch", "1.29", "Abgabe", "haushaltsueblich"], [[0, 1]])

    reference = offers_gold.load_reference()

    assert set(reference.assignments["p1"]) == {0, 1}


def test_halb_annotierte_seite_wird_nicht_gemessen(dirs):
    """Wie bei gold/: eine unfertige Seite erzeugt Falsch-Negative fuer alle Arme."""
    _write(dirs, "p1", ["Milch", "1.29"], [[0, 1]], status="in_progress")

    reference = offers_gold.load_reference()

    assert reference.assignments == {}
    assert reference.in_progress == ["p1"]


def test_verschobene_wortliste_entwertet_die_annotation(dirs):
    """Genau wogegen der words_hash existiert - Indizes zeigen auf andere Woerter."""
    _write(dirs, "p1", ["Milch", "1.29"], [[0, 1]], hash_override="veraltet")

    reference = offers_gold.load_reference()

    assert reference.assignments == {}
    assert reference.stale == ["p1"]


def test_wort_in_zwei_gruppen_ist_ein_fehler_und_kein_stiller_gewinner(dirs):
    """Ein Wort gehoert zu hoechstens einem Angebot. Sonst ist die Referenz kaputt."""
    _write(dirs, "p1", ["Milch", "1.29"], [[0, 1], [1]])

    reference = offers_gold.load_reference()

    assert reference.assignments == {}
    assert reference.broken == ["p1"]


# ------------------------------------------------------------------ Metrik


def _page(page_id, words, tags):
    return {
        "page_id": page_id,
        "width": 500,
        "height": 800,
        "words": words,
        "tags": tags,
    }


def _word(text, x0, y0, x1, y1):
    return {"text": text, "bbox": [x0, y0, x1, y1]}


def _zwei_angebote():
    """Zwei Produkte mit je eigenem Preis, weit auseinander."""
    return _page(
        "1_p1",
        [
            _word("Landliebe", 40, 100, 90, 112),
            _word("Milch", 40, 116, 90, 128),
            _word("1.29", 40, 132, 90, 148),
            _word("Ja!", 40, 600, 90, 612),
            _word("Butter", 40, 616, 90, 628),
            _word("2.49", 40, 632, 90, 648),
        ],
        ["B-BRAND", "B-PRODUCT", "B-PRICE", "B-BRAND", "B-PRODUCT", "B-PRICE"],
    )


REFERENZ_ZWEI_ANGEBOTE = {0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1}


def test_perfekte_gruppierung_erreicht_paar_f1_eins():
    page = _zwei_angebote()

    score = offers_gold.judge_page(page, REFERENZ_ZWEI_ANGEBOTE, cluster_page(page))

    assert score.shared_pairs == score.ref_pairs == score.sys_pairs
    assert score.ref_pairs == 6  # je Angebot 3 Entities, also 3 Paare


def test_zusammengeworfene_angebote_senken_die_precision():
    """Ein System, das alles in ein Angebot wirft, findet jedes echte Paar - und erfindet Paare dazu."""
    page = _zwei_angebote()
    alles_in_einem = [_angebot_ueber(page, range(6))]

    score = offers_gold.judge_page(page, REFERENZ_ZWEI_ANGEBOTE, alles_in_einem)

    assert score.shared_pairs == 6, "beide echten Angebote sind enthalten"
    assert score.sys_pairs == 15, "6 Entities in einer Gruppe = 15 Paare"


def test_zerrissenes_angebot_senkt_den_recall():
    """Jede Entity als eigenes Angebot: kein einziges Paar, also Recall null."""
    page = _zwei_angebote()
    alles_einzeln = [_angebot_ueber(page, [i]) for i in range(6)]

    score = offers_gold.judge_page(page, REFERENZ_ZWEI_ANGEBOTE, alles_einzeln)

    assert score.sys_pairs == 0
    assert score.shared_pairs == 0
    assert score.ref_pairs == 6


def test_entity_ohne_referenzgruppe_wird_ausgewiesen_statt_gewertet():
    """Was der Mensch keinem Angebot zugeordnet hat, darf keine Zahl bewegen."""
    page = _zwei_angebote()
    ohne_letztes = {k: v for k, v in REFERENZ_ZWEI_ANGEBOTE.items() if k != 5}

    score = offers_gold.judge_page(page, ohne_letztes, cluster_page(page))

    assert score.unassignable == 1
    assert score.ref_pairs == 4, "das zweite Angebot hat nur noch zwei Entities"


def test_entity_ueber_der_angebotsgrenze_folgt_der_mehrheit_ihrer_woerter():
    """Ein Span kann ueber die Grenze reichen - dann entscheidet die Mehrheit.

    Hier gehoert "Landliebe Milch" zu Angebot 0, aber der Annotator hat das
    zweite Wort dem Nachbarn zugeschlagen. Zwei zu eins fuer Angebot 0.
    """
    page = _page(
        "1_p3",
        [
            _word("Landliebe", 40, 100, 90, 112),
            _word("Milch", 92, 100, 130, 112),
            _word("Bio", 132, 100, 160, 112),
            _word("1.29", 40, 116, 90, 132),
        ],
        ["B-PRODUCT", "I-PRODUCT", "I-PRODUCT", "B-PRICE"],
    )

    # Der Preis liegt eindeutig in Angebot 0. Zaehlt die Entity zur Mehrheit,
    # bilden beide ein Paar; folgte sie dem letzten Wort, waeren es null.
    score = offers_gold.judge_page(page, {0: 0, 1: 0, 2: 1, 3: 0}, cluster_page(page))

    assert score.unassignable == 0
    assert score.ref_pairs == 1, "die Entity zaehlt ganz zu Angebot 0"


def test_referenzgruppe_ohne_entity_wird_gezaehlt_statt_verschwiegen():
    """Der Mensch sieht dort ein Angebot, die Labels geben keine Entity her.

    Das ist ein Labeling-Fehler, kein Gruppierungsfehler - er darf die
    Gruppenmetrik nicht belasten, aber auch nicht unsichtbar bleiben.
    """
    page = _zwei_angebote()
    mit_leerer_gruppe = dict(REFERENZ_ZWEI_ANGEBOTE)

    score = offers_gold.judge_page(page, mit_leerer_gruppe | {99: 7}, cluster_page(page))

    assert score.ref_groups == 2
    assert score.ref_groups_without_entities == 1


def _angebot_ueber(page, indices):
    """Baut ein Offer aus den Entities einer Seite - fuer erfundene Systemausgaben."""
    from magda.offers import _make_offer, entities_from_page

    entities = entities_from_page(page)
    return _make_offer(page["page_id"], 0, [entities[i] for i in indices])


# -------------------------------------------------------- Gruppen-Uebereinstimmung


def test_gruppen_f1_verlangt_die_exakte_menge():
    """Die Zahl, die "Zeile in der Datenbank stimmt" entspricht - kein Teilpunkt."""
    page = _zwei_angebote()
    fast_richtig = [
        _angebot_ueber(page, [0, 1, 2]),
        _angebot_ueber(page, [3, 4]),  # der Preis fehlt
    ]

    score = offers_gold.judge_page(page, REFERENZ_ZWEI_ANGEBOTE, fast_richtig)

    assert score.exact_groups == 1
    assert score.ref_groups == 2


def test_weggelassene_entity_wird_zur_eigenen_gruppe_statt_zu_verschwinden():
    """Sonst verbesserte ein System seinen Recall, indem es Entities unterschlaegt.

    Der Preis 2.49 steht in keinem der beiden Angebote. Er bildet deshalb eine
    dritte Systemgruppe - sein Paar mit "Ja! Butter" fehlt und kostet Recall.
    """
    page = _zwei_angebote()
    preis_unterschlagen = [
        _angebot_ueber(page, [0, 1, 2]),
        _angebot_ueber(page, [3, 4]),
    ]

    score = offers_gold.judge_page(page, REFERENZ_ZWEI_ANGEBOTE, preis_unterschlagen)

    assert score.sys_groups == 3
    assert score.ref_pairs == 6
    assert score.shared_pairs == 4


# --------------------------------------------------------------- Aggregation


def test_leere_messung_wird_als_leer_ausgewiesen_statt_als_null():
    """Wie bei offers_report: None heisst "nichts zu messen", 0.0 hiesse "alles falsch"."""
    report = offers_gold.Report()

    assert report.pair_f1 is None
    assert report.group_f1 is None


def test_einzelnes_angebot_erzeugt_kein_paar_und_bleibt_messbar():
    """Ein Angebot aus einer Entity traegt zur Paarmetrik nichts bei - ohne Absturz."""
    page = _page(
        "1_p2",
        [_word("Hoodie", 40, 100, 90, 112)],
        ["B-PRODUCT"],
    )

    score = offers_gold.judge_page(page, {0: 0}, cluster_page(page))

    assert score.ref_pairs == 0
    assert score.exact_groups == 1


def test_collect_summiert_ueber_seiten():
    page = _zwei_angebote()
    reference = offers_gold.Reference(assignments={"1_p1": REFERENZ_ZWEI_ANGEBOTE})

    report = offers_gold.collect([page], reference)

    assert report.pages == 1
    assert report.pair_f1 == 1.0
    assert report.group_f1 == 1.0


def test_seite_ohne_referenz_wird_uebergangen():
    """Gemessen wird nur, wo ein Mensch hingeschaut hat."""
    reference = offers_gold.Reference(assignments={})

    report = offers_gold.collect([_zwei_angebote()], reference)

    assert report.pages == 0
    assert report.pair_f1 is None
