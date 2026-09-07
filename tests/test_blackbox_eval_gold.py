"""`magda blackbox-eval --reference-groups gold`: die Handannotation als Referenz.

Alle bisherigen Blackbox-Zahlen messen Naehe zu claude-sonnet-5. Die
Gold-Referenz ist die einzige, die Richtigkeit misst - und sie ist aus zwei
Haelften gebaut (Spans in gold/, Gruppen in gold/offers/), die beide fertig
sein muessen. Der Fall, der leise brechen wuerde: eine Seite, der eine
Haelfte fehlt, als leere Referenz mitzaehlen. Das hiesse "alles falsch"
statt "nicht gemessen".
"""

import json

import pytest

from magda import config
from magda.cli import blackbox_eval as cli
from magda.gold import words_hash


WORDS = [
    {"text": "Landliebe", "bbox": [40, 100, 90, 112]},
    {"text": "Milch", "bbox": [40, 116, 90, 128]},
    {"text": "1.29", "bbox": [40, 132, 90, 148]},
    {"text": "Ja!", "bbox": [40, 600, 90, 612]},
    {"text": "Butter", "bbox": [40, 616, 90, 628]},
    {"text": "2.49", "bbox": [40, 632, 90, 648]},
]
# Gold sagt: zwei Angebote. Der Lehrer hat die Marke des zweiten uebersehen.
GOLD_SPANS = [{"start": 0, "end": 1, "label": "BRAND"}, {"start": 1, "end": 2, "label": "PRODUCT"},
              {"start": 2, "end": 3, "label": "PRICE"}, {"start": 3, "end": 4, "label": "BRAND"},
              {"start": 4, "end": 5, "label": "PRODUCT"}, {"start": 5, "end": 6, "label": "PRICE"}]
TEACHER_TAGS = ["B-BRAND", "B-PRODUCT", "B-PRICE", "O", "B-PRODUCT", "B-PRICE"]
GROUPS = [[0, 1, 2], [3, 4, 5]]


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


@pytest.fixture
def projekt(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORDS_DIR", tmp_path / "words")
    monkeypatch.setattr(config, "GOLD_DIR", tmp_path / "gold")
    monkeypatch.setattr(config, "LABELED_DIR", tmp_path / "labeled")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "EVAL_DIR", tmp_path / "eval")
    for page_id in ("p_done", "p_half", "p_none"):
        _write(tmp_path / "words" / f"{page_id}.json",
               {"width": 600, "height": 800, "words": WORDS})
        _write(tmp_path / "labeled" / "sonnet-5" / f"{page_id}.json",
               {"page_id": page_id, "words": WORDS, "tags": TEACHER_TAGS})
        _write(tmp_path / "predictions" / "gbert" / f"{page_id}.json",
               {"page_id": page_id, "words": WORDS, "entities": GOLD_SPANS})
    done = {"status": "done", "words_hash": words_hash(WORDS)}
    _write(tmp_path / "gold" / "p_done.json", {**done, "spans": GOLD_SPANS})
    _write(tmp_path / "gold" / "offers" / "p_done.json", {**done, "groups": GROUPS})
    # p_half: Spans fertig, Gruppierung erst begonnen.
    _write(tmp_path / "gold" / "p_half.json", {**done, "spans": GOLD_SPANS})
    _write(tmp_path / "gold" / "offers" / "p_half.json",
           {**done, "status": "in_progress", "groups": GROUPS})
    (tmp_path / "pages.txt").write_text("p_done\np_half\np_none\n")
    return tmp_path


def test_nur_seiten_mit_beiden_fertigen_haelften_bilden_die_referenz(projekt):
    deals, missing = cli._gold_deals_by_page(["p_done", "p_half", "p_none"])
    deals.pop("__fragments__")

    assert sorted(missing) == ["p_half", "p_none"]
    assert set(deals) == {"p_done"}
    assert sorted(d["price"] for d in deals["p_done"]) == [1.29, 2.49]


def test_die_entities_kommen_aus_den_gold_spans_nicht_vom_lehrer(projekt):
    """Sonst waere die Referenz ein Zwitter: richtige Gruppen ueber
    LLM-Entities - und misst wieder teilweise den Lehrer."""
    deals, _ = cli._gold_deals_by_page(["p_done"])

    assert {d["name"] for d in deals["p_done"]} == {"Landliebe Milch", "Ja! Butter"}


def test_replay_misst_gegen_gold_ohne_api_und_laesst_unfertige_seiten_aus(projekt, capsys):
    report = {"model": "irgendein-vision-modell", "prompt_version": 1,
              "seconds": {"blackbox": 12.0},
              "blackbox_deals": {p: [{"name": "Landliebe Milch", "price": 1.29,
                                      "original_price": None}]
                                 for p in ("p_done", "p_half", "p_none")}}
    (projekt / "old_report.json").write_text(json.dumps(report))

    cli.main(["--pages", str(projekt / "pages.txt"), "--reference-groups", "gold",
              "--blackbox-from", str(projekt / "old_report.json"),
              "--predictions", "gbert", "--grouper", "heuristic", "--allow-partial"])

    out = capsys.readouterr().out
    assert "Seiten:     1 (2 ohne fertige Handannotation ausgelassen)" in out
    assert "Richtigkeit" in out
    written = json.loads((projekt / "eval" /
                          "blackbox_test_irgendein-vision-modell_ref-gold_offer-price-v2.json").read_text())
    assert written["pages"] == ["p_done"]
    assert written["reference_is_llm"] is False
    assert sorted(written["gold_missing"]) == ["p_half", "p_none"]
    # Die Blackbox fand eines der zwei Gold-Angebote; wie die Heuristik der
    # eigenen Seite gruppiert, ist hier nicht Gegenstand - nur, dass sie
    # gegen dieselben zwei Referenzangebote gemessen wird.
    assert written["comparisons"]["blackbox_vs_referenz"]["recall"] == 0.5
    assert written["comparisons"]["eigene_vs_referenz"]["reference"] == 2


def test_abschlussmessung_verlangt_die_ganze_seitenliste(projekt):
    with pytest.raises(SystemExit, match="1"):
        cli.main(["--pages", str(projekt / "pages.txt"), "--reference-groups", "gold"])
