"""Eine LLM-Gruppierung als Referenzersatz - und was sie von Gold unterscheidet.

Die Handannotation sprengt den Projektrahmen (Teamentscheidung, 06.08.2026),
also gruppiert ein Vision-Modell. Das darf nur nicht so aussehen wie
`gold/offers/`: eine Referenz, die selbst aus einem Modell kommt, misst
Uebereinstimmung, nicht Richtigkeit. Deshalb ein eigener Ordner, und
`provenance` in jeder Datei.

Der Teacher antwortet in *Entity*-Nummern, gespeichert werden *Wortindizes*.
Beides zusammen: Entities sind die Einheit, in der auch der Annotator klickt
(ein Angebot hat schnell zwoelf Woerter), Wortindizes die Einheit, die den
naechsten Labeling-Lauf ueberlebt.
"""

import json

import pytest

from magda import config, offer_teacher, offers_gold
from magda.gold import words_hash


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """Verlegt data/words/ und data/offer_groups/ ins tmp-Verzeichnis."""
    words_dir = tmp_path / "words"
    groups_dir = tmp_path / "offer_groups"
    words_dir.mkdir()
    monkeypatch.setattr(config, "WORDS_DIR", words_dir)
    monkeypatch.setattr(config, "OFFER_GROUPS_DIR", groups_dir)
    return words_dir, groups_dir


def _page(page_id="p1"):
    texts = ["Landliebe", "Butter", "1.29", "zzgl", "Ja!", "Milch", "0.99"]
    return {
        "page_id": page_id,
        "width": 100,
        "height": 200,
        "words": [{"text": t, "bbox": [0, 0, 1, 1]} for t in texts],
        "tags": ["B-BRAND", "B-PRODUCT", "B-PRICE", "O", "B-BRAND", "B-PRODUCT", "B-PRICE"],
    }


def _write_words(words_dir, page):
    with open(words_dir / f"{page['page_id']}.json", "w") as f:
        json.dump({k: v for k, v in page.items() if k != "tags"}, f)


# ------------------------------------------------------------------ Aufgabe


def test_die_aufgabe_listet_entities_statt_einzelner_woerter():
    """Der Teacher gruppiert dieselbe Einheit, die im Annotator ein Klick ist."""
    task = offer_teacher.build_task(_page())

    assert [e["type"] for e in task["entities"]] == [
        "BRAND", "PRODUCT", "PRICE", "BRAND", "PRODUCT", "PRICE"
    ]
    assert task["entities"][0]["text"] == "Landliebe"
    assert task["entities"][0]["index"] == 0


def test_die_aufgabe_nennt_das_seitenbild():
    """Ohne Bild sieht der Teacher genau das, was auch die Heuristik sieht."""
    task = offer_teacher.build_task(_page())

    assert task["image"].endswith("p1.png")


# ------------------------------------------------- Entity-Nummern zu Woertern


def test_entity_gruppen_werden_zu_wortindizes_aufgeloest():
    groups = offer_teacher.expand_entity_groups(_page(), [[0, 1, 2], [3, 4, 5]])

    assert groups == [[0, 1, 2], [4, 5, 6]]


def test_ungelabelte_woerter_bleiben_ausserhalb_jedes_angebots():
    """"zzgl" (Index 3) gehoert keiner Entity - und damit keinem Angebot."""
    groups = offer_teacher.expand_entity_groups(_page(), [[0, 1, 2], [3, 4, 5]])

    assert 3 not in [w for group in groups for w in group]


def test_unbekannte_entity_nummer_wird_abgelehnt():
    """Ein Modell verzaehlt sich; still zu ignorieren verfaelscht die Referenz."""
    with pytest.raises(ValueError, match="99"):
        offer_teacher.expand_entity_groups(_page(), [[0, 99]])


def test_dieselbe_entity_in_zwei_angeboten_wird_abgelehnt():
    with pytest.raises(ValueError, match="zwei"):
        offer_teacher.expand_entity_groups(_page(), [[0, 1], [1, 2]])


# ------------------------------------------------------------------ Speichern


def test_gespeicherte_gruppierung_ist_ueber_load_reference_lesbar(dirs):
    words_dir, groups_dir = dirs
    page = _page()
    _write_words(words_dir, page)

    offer_teacher.save_grouping(page, [[0, 1, 2], [4, 5, 6]], source="sonnet-5")
    reference = offers_gold.load_reference(offer_teacher.teacher_dir("sonnet-5"))

    assert reference.assignments["p1"] == {0: 0, 1: 0, 2: 0, 4: 1, 5: 1, 6: 1}


def test_die_datei_haelt_fest_dass_sie_nicht_von_hand_kommt(dirs):
    words_dir, groups_dir = dirs
    page = _page()
    _write_words(words_dir, page)

    path = offer_teacher.save_grouping(page, [[0, 1, 2]], source="sonnet-5")

    with open(path) as f:
        stored = json.load(f)
    assert stored["provenance"]["kind"] == "llm"
    assert stored["provenance"]["source"] == "sonnet-5"
    assert stored["words_hash"] == words_hash(page["words"])


def test_kaputte_gruppierung_wird_nicht_gespeichert(dirs):
    """Ein Wort in zwei Angeboten ist keine Grenzfrage, sondern kaputt."""
    words_dir, groups_dir = dirs
    page = _page()
    _write_words(words_dir, page)

    with pytest.raises(ValueError):
        offer_teacher.save_grouping(page, [[0, 1], [1, 2]], source="sonnet-5")

    assert not list(groups_dir.rglob("*.json"))


def test_die_herkunft_steht_im_geladenen_referenzobjekt(dirs):
    """Wer eine Zahl gegen diese Referenz berichtet, muss die Herkunft sehen."""
    words_dir, _ = dirs
    page = _page()
    _write_words(words_dir, page)
    offer_teacher.save_grouping(page, [[0, 1, 2]], source="sonnet-5")

    reference = offers_gold.load_reference(offer_teacher.teacher_dir("sonnet-5"))

    assert reference.provenance["p1"] == "llm"


def test_handannotation_bleibt_der_default(dirs, monkeypatch, tmp_path):
    """`load_reference()` ohne Argument liest weiter gold/offers/."""
    gold_dir = tmp_path / "gold"
    (gold_dir / "offers").mkdir(parents=True)
    monkeypatch.setattr(config, "GOLD_DIR", gold_dir)
    words_dir, _ = dirs
    page = _page()
    _write_words(words_dir, page)
    offer_teacher.save_grouping(page, [[0, 1, 2]], source="sonnet-5")

    assert offers_gold.load_reference().assignments == {}


def test_gruppierte_seiten_lassen_sich_auflisten(dirs):
    """Damit `magda offers-report` an genau denselben Seiten messen kann.

    Ohne diese Einschraenkung stuende die Genauigkeit der LLM-Gruppierung
    (wenige Seiten) neben der Genauigkeit der Heuristik (alle 196) - zwei
    Zahlen ueber verschiedene Grundmengen, nebeneinandergestellt als waeren
    sie vergleichbar.
    """
    words_dir, _ = dirs
    for page_id in ("p1", "p2"):
        page = _page(page_id)
        _write_words(words_dir, page)
        offer_teacher.save_grouping(page, [[0, 1, 2]], source="sonnet-5")

    assert offer_teacher.grouped_page_ids("sonnet-5") == {"p1", "p2"}


def test_unbekannte_quelle_ist_leer_statt_ein_fehler(dirs):
    assert offer_teacher.grouped_page_ids("gibtsnicht") == set()
