"""Tests für den Gold-Ladepfad (handannotierte Referenz unter gold/)."""

import json

import pytest

from magda import config, gold


@pytest.fixture
def gold_dirs(tmp_path, monkeypatch):
    """Verlegt gold/ und data/words/ in ein tmp-Verzeichnis.

    Gepatcht wird auf config, nicht auf gold – magda/gold.py liest die Pfade
    zur Laufzeit als config.X, genau wie magda/api.py.
    """
    words_dir = tmp_path / "words"
    gold_dir = tmp_path / "gold"
    words_dir.mkdir()
    gold_dir.mkdir()
    monkeypatch.setattr(config, "WORDS_DIR", words_dir)
    monkeypatch.setattr(config, "GOLD_DIR", gold_dir)
    return words_dir, gold_dir


def _write_page(words_dir, gold_dir, page_id, texts, spans, status="done", hash_override=None):
    words = [{"text": t, "bbox": [0, 0, 1, 1]} for t in texts]
    with open(words_dir / f"{page_id}.json", "w") as f:
        json.dump({"page_id": page_id, "width": 100, "height": 200, "words": words}, f)
    with open(gold_dir / f"{page_id}.json", "w") as f:
        json.dump(
            {
                "page_id": page_id,
                "words_hash": hash_override or gold.words_hash(words),
                "status": status,
                "annotator": "",
                "spans": spans,
            },
            f,
        )


def test_laedt_fertige_seite_mit_bio_tags(gold_dirs):
    words_dir, gold_dir = gold_dirs
    _write_page(
        words_dir,
        gold_dir,
        "p1",
        ["Landliebe", "Vollmilch", "1.29"],
        [{"start": 0, "end": 1, "label": "BRAND"}, {"start": 1, "end": 2, "label": "PRODUCT"}],
    )

    result = gold.load_gold_pages()

    assert [p["page_id"] for p in result.pages] == ["p1"]
    assert result.pages[0]["tags"] == ["B-BRAND", "B-PRODUCT", "O"]
    assert result.pages[0]["width"] == 100
    assert len(result.pages[0]["words"]) == 3


def test_ueberspringt_unfertige_seiten(gold_dirs):
    words_dir, gold_dir = gold_dirs
    _write_page(
        words_dir, gold_dir, "p1", ["Landliebe"],
        [{"start": 0, "end": 1, "label": "BRAND"}], status="in_progress",
    )

    result = gold.load_gold_pages()

    assert result.pages == []
    assert result.in_progress == ["p1"]


def test_ueberspringt_stale_seiten(gold_dirs):
    words_dir, gold_dir = gold_dirs
    _write_page(
        words_dir, gold_dir, "p1", ["Landliebe"],
        [{"start": 0, "end": 1, "label": "BRAND"}], hash_override="veraltet",
    )

    result = gold.load_gold_pages()

    assert result.pages == []
    assert result.stale == ["p1"]


def test_ueberspringt_gold_ohne_wortdatei(gold_dirs):
    words_dir, gold_dir = gold_dirs
    _write_page(words_dir, gold_dir, "p1", ["Landliebe"], [{"start": 0, "end": 1, "label": "BRAND"}])
    (words_dir / "p1.json").unlink()

    result = gold.load_gold_pages()

    assert result.pages == []


def test_words_hash_ignoriert_koordinaten():
    """Eine verschobene Box darf die Annotation nicht entwerten."""
    a = [{"text": "Milch", "bbox": [0, 0, 1, 1]}]
    b = [{"text": "Milch", "bbox": [5, 5, 6, 6]}]

    assert gold.words_hash(a) == gold.words_hash(b)


def test_words_hash_reagiert_auf_reihenfolge():
    a = [{"text": "Milch"}, {"text": "1.29"}]
    b = [{"text": "1.29"}, {"text": "Milch"}]

    assert gold.words_hash(a) != gold.words_hash(b)
