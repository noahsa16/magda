"""Zwei gespeicherte Gruppierungen gegeneinander messen (`--groups-from`).

Das ist die Deckenmessung: Zwei unabhaengige Annotatoren auf denselben
Seiten sagen, wie hoch Uebereinstimmung ueberhaupt ausfallen kann. Ohne
diese Zahl ist "das Modell erreicht 0.778" keine Einordnung, sondern nur
eine Zahl - es fehlt der Vergleichspunkt, gegen den sie gross oder klein
ist.

Der Fall, der leise brechen wuerde, ist die Seitenmenge: Wo nur eine der
beiden Seiten gruppiert hat, gibt es nichts zu vergleichen. Solche Seiten
als leere Systemausgabe zu werten hiesse "alles falsch" statt "nicht
gemessen" - genau der Fehler, den `load_reference` fuer die Referenz schon
vermeidet.
"""

import json

import pytest

from magda import config
from magda.cli import offers_gold as cli
from magda.gold import words_hash


WORDS = [
    {"text": "Landliebe", "bbox": [40, 100, 90, 112]},
    {"text": "Milch", "bbox": [40, 116, 90, 128]},
    {"text": "1.29", "bbox": [40, 132, 90, 148]},
    {"text": "Ja!", "bbox": [40, 600, 90, 612]},
    {"text": "Butter", "bbox": [40, 616, 90, 628]},
    {"text": "2.49", "bbox": [40, 632, 90, 648]},
]
TAGS = ["B-BRAND", "B-PRODUCT", "B-PRICE", "B-BRAND", "B-PRODUCT", "B-PRICE"]

# Zwei Angebote, sauber getrennt - und die Gegenlesart, die alles in eine
# Gruppe wirft. Zwischen beiden muss die Messung unterscheiden.
GETRENNT = [[0, 1, 2], [3, 4, 5]]
ZUSAMMEN = [[0, 1, 2, 3, 4, 5]]


@pytest.fixture
def projekt(tmp_path, monkeypatch):
    """Legt Woerter, Labels und zwei Gruppierungsquellen im tmp-Baum an."""
    for name in ("words", "labeled", "offer_groups", "eval"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(config, "WORDS_DIR", tmp_path / "words")
    monkeypatch.setattr(config, "LABELED_DIR", tmp_path / "labeled")
    monkeypatch.setattr(config, "OFFER_GROUPS_DIR", tmp_path / "offer_groups")
    monkeypatch.setattr(config, "EVAL_DIR", tmp_path / "eval")
    return tmp_path


def _seite(projekt, page_id):
    payload = {"page_id": page_id, "width": 500, "height": 800,
               "words": WORDS, "tags": TAGS}
    (projekt / "words" / f"{page_id}.json").write_text(json.dumps(payload))
    labels = projekt / "labeled" / "sonnet-5"
    labels.mkdir(exist_ok=True)
    (labels / f"{page_id}.json").write_text(json.dumps(payload))


def _gruppierung(projekt, source, page_id, groups):
    directory = projekt / "offer_groups" / source
    directory.mkdir(exist_ok=True)
    (directory / f"{page_id}.json").write_text(json.dumps({
        "page_id": page_id,
        "words_hash": words_hash(WORDS),
        "status": "done",
        "annotator": source,
        "provenance": {"kind": "llm", "source": source, "model": source,
                       "prompt_version": 1},
        "groups": groups,
    }))


def _report(projekt):
    path = next((projekt / "eval").glob("offers_gold_*.json"))
    return json.loads(path.read_text())


def test_zwei_gleiche_gruppierungen_ergeben_volle_uebereinstimmung(projekt):
    _seite(projekt, "1_p1")
    _gruppierung(projekt, "erster", "1_p1", GETRENNT)
    _gruppierung(projekt, "zweiter", "1_p1", GETRENNT)

    cli.main(["--labels-from", "sonnet-5",
              "--groups-from", "erster", "--reference-from", "zweiter"])

    report = _report(projekt)
    assert report["group_f1"] == 1.0
    assert report["pair_f1"] == 1.0
    assert report["groups_from"] == "erster"


def test_widersprechende_gruppierungen_fallen_unter_eins(projekt):
    """Sonst misst `--groups-from` gar nicht die uebergebene Gruppierung."""
    _seite(projekt, "1_p1")
    _gruppierung(projekt, "erster", "1_p1", ZUSAMMEN)
    _gruppierung(projekt, "zweiter", "1_p1", GETRENNT)

    cli.main(["--labels-from", "sonnet-5",
              "--groups-from", "erster", "--reference-from", "zweiter"])

    report = _report(projekt)
    assert report["group_f1"] == 0.0
    assert report["sys_groups"] == 1
    assert report["ref_groups"] == 2


def test_seite_ohne_gruppierung_des_systems_wird_uebersprungen(projekt):
    """Eine fehlende Seite heisst "nicht gemessen", nicht "alles falsch".

    Ohne die Einschraenkung zaehlte die zweite Seite als leere Ausgabe
    gegen zwei Referenzangebote - der Wert faellt, obwohl nichts falsch
    gruppiert wurde.
    """
    _seite(projekt, "1_p1")
    _seite(projekt, "2_p1")
    _gruppierung(projekt, "erster", "1_p1", GETRENNT)
    _gruppierung(projekt, "zweiter", "1_p1", GETRENNT)
    _gruppierung(projekt, "zweiter", "2_p1", GETRENNT)

    cli.main(["--labels-from", "sonnet-5",
              "--groups-from", "erster", "--reference-from", "zweiter"])

    report = _report(projekt)
    assert report["pages"] == 1
    assert report["group_f1"] == 1.0


def test_ohne_groups_from_wird_weiterhin_die_heuristik_gemessen(projekt):
    """Der Default darf sich durch die neue Option nicht verschieben."""
    _seite(projekt, "1_p1")
    _gruppierung(projekt, "zweiter", "1_p1", GETRENNT)

    cli.main(["--labels-from", "sonnet-5", "--reference-from", "zweiter"])

    report = _report(projekt)
    assert report["groups_from"] is None
    assert report["pages"] == 1
