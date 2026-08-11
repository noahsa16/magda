"""Der Agenten-Pfad muss dieselben Labels erzeugen wie der API-Pfad.

Eine neue Woche, die einen anderen Guard-Pfad durchlaeuft, ist kein
zusaetzlicher Datensatz, sondern ein zweiter mit anderen Konventionen -
und der Wochenvergleich haengt daran.
"""

import json

import pytest

from magda import label_teacher, labeling


def _words(texts):
    return [{"text": t, "bbox": [0.0, 0.0, 1.0, 1.0]} for t in texts]


# Die Legende macht `app_footnote_markers` erst scharf: ohne sie ist die
# Markermenge leer und die Regel schweigt bauartbedingt.
LEGEND = ["1", "Nur", "für", "registrierte", "PENNY", "App", "Nutzer."]


def test_der_prompt_ist_derselbe_wie_fuer_die_api():
    """Zwei Prompts fuer dieselbe Aufgabe driften auseinander."""
    words = _words(["MARATHON", "Fitnessdrink", "1.49"])
    task = label_teacher.build_task({"page_id": "x_p1", "words": words})
    expected = labeling._PROMPT.format(
        word_list="\n".join(f"{i}: {w['text']}" for i, w in enumerate(words))
    )
    assert task["prompt"] == expected


def test_die_aufgabe_nennt_das_seitenbild():
    task = label_teacher.build_task({"page_id": "1355990_p3", "words": _words(["a"])})
    assert task["image"].endswith("data/images/1355990_p3.png")
    assert task["words"] == 1


def test_finish_spans_kuerzt_ueber_oder():
    """`trim_spans` laeuft mit - sonst spannt ein Angebot ueber zwei."""
    words = _words(["Waschmittel", "oder", "Pods"])
    tags = label_teacher.finish_spans(
        [{"start": 0, "end": 3, "label": "PRODUCT"}], words)
    assert tags == ["B-PRODUCT", "O", "O"]


def test_finish_spans_widmet_den_fussnotenpreis_um():
    """`apply_app_price_rule` laeuft mit."""
    words = _words(["1.99", "1"] + LEGEND)
    tags = label_teacher.finish_spans(
        [{"start": 0, "end": 1, "label": "PRICE"}], words)
    assert tags[0] == "B-APP_PRICE"


def test_die_fussnotenregel_kommt_nach_dem_kuerzen():
    """Reihenfolge, nicht nur Anwesenheit: erst kuerzen, dann umwidmen.

    Der Span laeuft ueber „oder" hinweg bis zu einem zweiten Preis, dahinter
    steht die Fussnote. Vor dem Kuerzen sieht die Regel `2.99` als letztes
    Wort und die Fussnote dahinter - sie wuerde umwidmen. Nach dem Kuerzen
    endet der Span vor „oder", und die Fussnote steht nicht mehr dahinter.
    """
    words = _words(["1.99", "oder", "2.99", "1"] + LEGEND)
    span = {"start": 0, "end": 3, "label": "PRICE"}

    assert label_teacher.finish_spans([span], words)[0] == "B-PRICE"
    # Die verkehrte Reihenfolge gaebe ein anderes Ergebnis - genau deshalb
    # steht sie in `finish_spans` fest.
    verkehrt = labeling.trim_spans(
        labeling.apply_app_price_rule([span], words), words)
    assert verkehrt[0]["label"] == "APP_PRICE"


@pytest.mark.parametrize("span, grund", [
    ({"start": 0, "end": 1, "label": "GEMUESE"}, "Label unbekannt"),
    ({"start": 0, "end": 99, "label": "PRICE"}, "liegt nicht in"),
    ({"start": 1, "end": 1, "label": "PRICE"}, "liegt nicht in"),
    ({"start": "0", "end": 1, "label": "PRICE"}, "nicht ganzzahlig"),
    ({"start": 0, "label": "PRICE"}, "fehlt end"),
    ("kein Objekt", "kein Objekt"),
])
def test_kaputte_spans_werden_mit_begruendung_verworfen(span, grund):
    kept, rejected = label_teacher.valid_spans([span], _words(["a", "b"]))
    assert kept == []
    assert grund in rejected[0]


def test_ein_span_ueber_das_letzte_wort_ueberlebt():
    """`end` ist exklusiv. Eine Grenze `end < len(words)` wirft ihn still weg."""
    kept, rejected = label_teacher.valid_spans(
        [{"start": 1, "end": 2, "label": "PRICE"}], _words(["x", "1.99"]))
    assert kept and not rejected


def test_brauchbare_spans_ueberleben_neben_kaputten():
    """Eine kaputte Angabe darf nicht die ganze Seite kosten."""
    kept, rejected = label_teacher.valid_spans(
        [{"start": 0, "end": 1, "label": "PRICE"},
         {"start": 0, "end": 1, "label": "QUATSCH"}],
        _words(["1.99", "x"]))
    assert kept == [{"start": 0, "end": 1, "label": "PRICE"}]
    assert len(rejected) == 1


def test_pending_meldet_was_der_labelordner_nicht_hat(tmp_path, monkeypatch):
    monkeypatch.setattr(label_teacher.config, "WORDS_DIR", tmp_path / "words")
    (tmp_path / "words").mkdir()
    for name in ("a_p1", "a_p2"):
        (tmp_path / "words" / f"{name}.json").write_text("{}")
    labeled = tmp_path / "labeled" / "sonnet-5"
    labeled.mkdir(parents=True)
    (labeled / "a_p1.json").write_text("{}")
    monkeypatch.setattr(label_teacher.config, "labeled_dir", lambda model: labeled)

    assert label_teacher.pending("sonnet-5") == ["a_p2"]


def _labelordner(tmp_path, monkeypatch, seiten):
    """seiten: Liste von (woerter, tags)."""
    directory = tmp_path / "labeled"
    directory.mkdir()
    for number, (texts, tags) in enumerate(seiten):
        (directory / f"a_p{number}.json").write_text(json.dumps(
            {"page_id": f"a_p{number}", "words": _words(texts), "tags": tags}))
    monkeypatch.setattr(label_teacher.config, "labeled_dir", lambda model: directory)


def test_grenzwoerter_zaehlen_drin_und_draussen(tmp_path, monkeypatch):
    _labelordner(tmp_path, monkeypatch, [
        (["6", "Stück", "je", "500", "g"],
         ["B-QUANTITY", "I-QUANTITY", "O", "B-QUANTITY", "I-QUANTITY"]),
        (["2", "Stück", "x"],
         ["B-QUANTITY", "O", "O"]),
    ])
    counts = label_teacher.boundary_words("egal", "QUANTITY")

    assert counts["stück"] == (1, 1)
    assert counts["g"] == (1, 0)


def test_reine_zahlen_sind_keine_grenzwoerter(tmp_path, monkeypatch):
    """`500 g 1.99` wuerde sonst "1.99" als strittiges Grenzwort melden."""
    _labelordner(tmp_path, monkeypatch, [
        (["500", "g", "1.99"], ["B-QUANTITY", "I-QUANTITY", "O"]),
    ])
    assert "1.99" not in label_teacher.boundary_words("egal", "QUANTITY")


def test_interpunktion_faellt_beim_zaehlen_weg(tmp_path, monkeypatch):
    """Sonst stehen `Stück` und `Stück,` als zwei Woerter da, jedes zu selten."""
    _labelordner(tmp_path, monkeypatch, [
        (["6", "Stück,"], ["B-QUANTITY", "I-QUANTITY"]),
        (["2", "Stück"], ["B-QUANTITY", "I-QUANTITY"]),
    ])
    counts = label_teacher.boundary_words("egal", "QUANTITY")

    assert counts["stück"] == (2, 0)


def _cli_umgebung(tmp_path, monkeypatch, texts=("1.99",)):
    from magda.cli import label_teacher as cli

    words_dir = tmp_path / "words"
    words_dir.mkdir()
    (words_dir / "a_p1.json").write_text(
        json.dumps({"page_id": "a_p1", "words": _words(list(texts))}))
    labeled = tmp_path / "labeled"
    labeled.mkdir()
    monkeypatch.setattr(cli, "WORDS_DIR", words_dir)
    monkeypatch.setattr(cli.config, "labeled_dir", lambda model: labeled)
    return cli, labeled


def test_eine_seite_ganz_ohne_angebot_laesst_sich_speichern(tmp_path, monkeypatch):
    """Gewinnspiel, Imageanzeige, Rueckseite - es gibt Seiten ohne Entities.

    Vorher lehnte `save` die leere Antwort ab, und der Agent hat daraufhin
    zwei BRAND-Spans aus dem Fliesstext erfunden, um ueberhaupt speichern zu
    koennen (`1355990_p20`). Ein Werkzeug, das eine Entscheidung erzwingt,
    statt sie zuzulassen, schreibt die Referenz still voll.
    """
    cli, labeled = _cli_umgebung(tmp_path, monkeypatch, ("Gewinnspiel", "Teilnahme"))
    leer = tmp_path / "leer.json"
    leer.write_text("[]")

    cli.main(["save", "a_p1", "--from", str(leer)])

    assert json.loads((labeled / "a_p1.json").read_text())["tags"] == ["O", "O"]


def test_eine_komplett_kaputte_antwort_wird_weiter_abgelehnt(tmp_path, monkeypatch):
    """Die Gegenprobe: leer ist ein Ergebnis, durchgefallen ist ein Fehlschlag."""
    cli, labeled = _cli_umgebung(tmp_path, monkeypatch)
    kaputt = tmp_path / "kaputt.json"
    kaputt.write_text('[{"start": 0, "end": 1, "label": "QUATSCH"}]')

    with pytest.raises(SystemExit):
        cli.main(["save", "a_p1", "--from", str(kaputt)])
    assert not (labeled / "a_p1.json").exists()


def test_save_schreibt_nicht_ueber_eine_vorhandene_seite(tmp_path, monkeypatch, capsys):
    """Der Geist der Regel „nichts schreibt nach data/labeled/" ohne Not."""
    from magda.cli import label_teacher as cli

    words_dir = tmp_path / "words"
    words_dir.mkdir()
    page = {"page_id": "a_p1", "words": _words(["1.99"])}
    (words_dir / "a_p1.json").write_text(json.dumps(page))
    labeled = tmp_path / "labeled"
    labeled.mkdir()
    (labeled / "a_p1.json").write_text('{"tags": ["O"]}')
    answer = tmp_path / "antwort.json"
    answer.write_text('[{"start": 0, "end": 1, "label": "PRICE"}]')

    monkeypatch.setattr(cli, "WORDS_DIR", words_dir)
    monkeypatch.setattr(cli.config, "labeled_dir", lambda model: labeled)

    with pytest.raises(SystemExit):
        cli.main(["save", "a_p1", "--from", str(answer)])
    assert json.loads((labeled / "a_p1.json").read_text())["tags"] == ["O"]

    cli.main(["save", "a_p1", "--from", str(answer), "--force"])
    assert json.loads((labeled / "a_p1.json").read_text())["tags"] == ["B-PRICE"]
