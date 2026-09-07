"""Menschliche Spans und Schülerausgaben bleiben getrennte Datenquellen."""

import json

import pytest

from magda import config, gold_evaluation, provenance
from magda.gold import words_hash


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    for name in ("GOLD_DIR", "WORDS_DIR"):
        directory = tmp_path / name
        directory.mkdir()
        monkeypatch.setattr(config, name, directory)
    words = [{"text": "Butter", "bbox": [0, 0, 1, 1]}, {"text": "1.29", "bbox": [1, 1, 2, 2]}]
    (config.WORDS_DIR / "p1.json").write_text(json.dumps({"width": 10, "height": 10, "words": words}))
    (config.GOLD_DIR / "p1.json").write_text(json.dumps({
        "words_hash": words_hash(words), "status": "done",
        "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}],
    }))
    directory = tmp_path / "predictions"
    directory.mkdir()
    (directory / "p1.json").write_text(json.dumps({
        "page_id": "p1", "words": [{**w, "label": tag} for w, tag in zip(words, ["B-PRODUCT", "B-PRICE"])],
    }))
    return directory


def test_falsche_student_entity_zaehlt_gegen_die_handreferenz(corpus):
    result = gold_evaluation.score_predictions(corpus, ["p1"])
    assert result["report"]["micro avg"]["precision"] == 0.5
    assert result["reference_is_llm"] is False
    assert result["page_ids"] == ["p1"]
    assert result["reference_sha256"]
    assert result["predictions_sha256"]


def test_fehlendes_gold_darf_die_abschlussmenge_nicht_verkleinern(corpus):
    with pytest.raises(ValueError, match="p2"):
        gold_evaluation.score_predictions(corpus, ["p1", "p2"])


def test_vertauschte_woerter_werden_trotz_gleicher_laenge_abgelehnt(corpus):
    path = corpus / "p1.json"
    payload = json.loads(path.read_text())
    payload["words"].reverse()
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Wortliste"):
        gold_evaluation.score_predictions(corpus, ["p1"])


def test_fingerabdruck_erkennt_geaenderte_gewichte(tmp_path):
    path = tmp_path / "model.pt"
    path.write_bytes(b"first")
    previous = provenance.checkpoint_digest(path)
    path.write_bytes(b"second")
    assert provenance.checkpoint_digest(path) != previous
