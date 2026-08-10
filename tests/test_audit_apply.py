"""Handurteile auf Labels anwenden - in einen neuen Ordner, nie in den alten.

`data/labeled/sonnet-5/` ist die Referenz, gegen die gemessen wird. Wer sie
in place korrigiert, verschiebt still die Grundlage aller frueheren Zahlen.
"""

import json

import pytest

from magda import audit_apply


def _labels(tmp_path, page_id, tags, ordner="quelle"):
    directory = tmp_path / "labeled" / ordner
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{page_id}.json").write_text(json.dumps({
        "page_id": page_id, "tags": tags,
        "words": [{"text": f"w{i}"} for i in range(len(tags))],
    }))
    return directory


def _tags(tmp_path, page_id="p1"):
    return json.loads((tmp_path / "ziel" / f"{page_id}.json").read_text())["tags"]


# ------------------------------------------------------------ Grundverhalten


def test_ein_wrong_urteil_setzt_das_neue_label(tmp_path):
    source = _labels(tmp_path, "p1", ["O", "B-PRICE", "O"])
    verdicts = {"p1:1": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    result = audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")

    assert _tags(tmp_path) == ["O", "B-APP_PRICE", "O"]
    assert result["changed"] == 1


def test_ein_correct_urteil_laesst_alles_stehen(tmp_path):
    source = _labels(tmp_path, "p1", ["O", "B-APP_PRICE", "O"])
    verdicts = {"p1:1": {"verdict": "correct", "should_be": "APP_PRICE"}}

    result = audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")

    assert _tags(tmp_path) == ["O", "B-APP_PRICE", "O"]
    assert result["changed"] == 0


def test_die_quelle_bleibt_unberuehrt(tmp_path):
    """Die Regel, wegen der es ueberhaupt einen zweiten Ordner gibt."""
    source = _labels(tmp_path, "p1", ["O", "B-PRICE", "O"])
    before = (source / "p1.json").read_text()
    verdicts = {"p1:1": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")

    assert (source / "p1.json").read_text() == before


def test_seiten_ohne_urteil_werden_unveraendert_kopiert(tmp_path):
    """Der Zielordner muss vollstaendig sein, sonst trainiert man auf weniger."""
    source = _labels(tmp_path, "p1", ["O", "B-PRICE"])
    _labels(tmp_path, "p2", ["B-PRODUCT", "O"])

    result = audit_apply.apply_verdicts({}, source, tmp_path / "ziel")

    assert (tmp_path / "ziel" / "p2.json").is_file()
    assert result["pages"] == 2


# ------------------------------------------------------- BIO bleibt gueltig


def test_ein_mehrwortiger_span_wird_ganz_umgetragen(tmp_path):
    """Beurteilt hat der Mensch die Entity, nicht das Token.

    Nur das erste Wort umzuschreiben ergaebe `B-APP_PRICE I-PRICE` - eine
    BIO-Folge, die kein Leser mehr als eine Entity liest und die
    `bio_to_spans` in zwei zerlegt.
    """
    source = _labels(tmp_path, "p1", ["O", "B-PRICE", "I-PRICE", "O"])
    verdicts = {"p1:1": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")

    assert _tags(tmp_path) == ["O", "B-APP_PRICE", "I-APP_PRICE", "O"]


def test_ein_urteil_auf_ein_folgewort_traegt_den_ganzen_span_um(tmp_path):
    """Der Auditkandidat kann auf jedem Wort des Spans sitzen."""
    source = _labels(tmp_path, "p1", ["B-PRICE", "I-PRICE", "O"])
    verdicts = {"p1:1": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")

    assert _tags(tmp_path) == ["B-APP_PRICE", "I-APP_PRICE", "O"]


def test_ein_urteil_auf_ein_o_wort_setzt_einen_neuen_span(tmp_path):
    """Der haeufigste Fall der Pruefung: der App-Preis fehlte ganz."""
    source = _labels(tmp_path, "p1", ["O", "O", "O"])
    verdicts = {"p1:1": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")

    assert _tags(tmp_path) == ["O", "B-APP_PRICE", "O"]


# ------------------------------------------------------------- Abbruchfaelle


def test_ein_urteil_auf_eine_unbekannte_seite_bricht_ab(tmp_path):
    """Halb angewandte Urteile machen den Ordner um genau den Betrag falsch,
    den niemand sieht - dieselbe Regel wie in `offer_teacher`."""
    source = _labels(tmp_path, "p1", ["O", "B-PRICE"])
    verdicts = {"gibtsnicht:0": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    with pytest.raises(ValueError, match="gibtsnicht"):
        audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")


def test_ein_urteil_hinter_dem_seitenende_bricht_ab(tmp_path):
    source = _labels(tmp_path, "p1", ["O", "B-PRICE"])
    verdicts = {"p1:99": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    with pytest.raises(ValueError, match="99"):
        audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")


def test_ein_unbekannter_labeltyp_bricht_ab(tmp_path):
    """Sonst entsteht ein Tag, das `labels.py` nicht kennt, und das Training
    faellt erst beim Aufbau des Klassifikationskopfs um."""
    source = _labels(tmp_path, "p1", ["O", "B-PRICE"])
    verdicts = {"p1:1": {"verdict": "wrong", "should_be": "GIBTSNICHT"}}

    with pytest.raises(ValueError, match="GIBTSNICHT"):
        audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")


def test_ein_wrong_ohne_zielabel_wird_nicht_geraten(tmp_path):
    """Belegter Fall: `1342881_p31:165` = "Aktion <<1.99>> 1 2 3". Der Mensch
    hat APP_PRICE verworfen und *nicht* gesagt, was stattdessen gilt.

    Ein `O` daraus zu machen behauptet, dort stehe kein Preis - dabei steht
    dort einer. Ein `PRICE` daraus zu machen ist eine Vermutung. Also bleibt
    das Tag stehen und der Fall wird ausgewiesen, statt still entschieden zu
    werden.
    """
    source = _labels(tmp_path, "p1", ["O", "B-APP_PRICE"])
    verdicts = {"p1:1": {"verdict": "wrong", "should_be": ""}}

    result = audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")

    assert _tags(tmp_path) == ["O", "B-APP_PRICE"]
    assert result["changed"] == 0
    assert result["unresolved"] == ["p1:1"]


def test_ziel_und_quelle_duerfen_nicht_derselbe_ordner_sein(tmp_path):
    """Die eine Regel, die dieses Modul ueberhaupt rechtfertigt."""
    source = _labels(tmp_path, "p1", ["O", "B-PRICE"])

    with pytest.raises(ValueError, match="derselbe"):
        audit_apply.apply_verdicts({}, source, source)
