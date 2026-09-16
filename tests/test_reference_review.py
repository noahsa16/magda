"""Referenzhinweise bleiben Vorschläge; menschliche Urteile werden nie erfunden."""

import json

import pytest

from magda import annotation_review, config, gold, reference_audit


def test_p3_preis_ohne_app_wird_zur_pruefung_vorgelegt(tmp_path, monkeypatch):
    original = config.GOLD_DIR
    target = tmp_path / "gold"
    (target / "offers").mkdir(parents=True)
    record = json.loads((original / "1364390_p3.json").read_text())
    price = next(s for s in record["spans"] if s["start"] == 229)
    price["label"] = "OLD_PRICE"
    path = target / "1364390_p3.json"
    path.write_text(json.dumps(record))
    (target / "offers/1364390_p3.json").write_bytes((original / "offers/1364390_p3.json").read_bytes())
    monkeypatch.setattr(config, "GOLD_DIR", target)
    previous = path.read_bytes()
    result = reference_audit.audit_reference(["1364390_p3"])
    assert any(i["code"] == "regular_price_marked_old" and i["start"] == 229 for i in result["issues"])
    assert path.read_bytes() == previous
    price["label"] = "PRICE"
    path.write_text(json.dumps(record))
    assert not any(i["code"] == "regular_price_marked_old" and i["start"] == 229
                   for i in reference_audit.audit_reference(["1364390_p3"])["issues"])


def test_stichprobe_zieht_vorlagen_ohne_modellergebnisse():
    pages = ["p1", "p2", "p3", "p4"]
    selected = annotation_review.select_pages(pages, [[0, 1], [2], [3]], count=10)
    assert selected == ["p1", "p3", "p4"]


def test_fehlende_menschen_liefern_keine_agreement_zahl():
    result = annotation_review.score_reviews({"selected_pages": ["p1"]})
    assert result["scores"] is None
    assert result["status"] == "awaiting_two_human_submissions"


@pytest.fixture
def submissions(tmp_path):
    words = [{"text": "Butter"}, {"text": "1.29"}]
    manifest = {"packet_id": "packet", "pages": [{"page_id": "p1", "words": words,
                                                "words_hash": gold.words_hash(words)}]}
    record = {"packet_id": "packet", "page_id": "p1", "words_hash": gold.words_hash(words),
              "status": "done", "independent_annotation": True,
              "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}], "groups": [[0]]}
    paths = [tmp_path / "a.json", tmp_path / "b.json"]
    for path, name in zip(paths, ["Person A", "Person B"], strict=True):
        path.write_text(json.dumps({"pages": [{**record, "annotator": name}]}))
    return manifest, paths


def test_zwei_echte_abgaben_werden_ohne_aenderung_verglichen(submissions):
    manifest, paths = submissions
    previous = [p.read_bytes() for p in paths]
    result = annotation_review.score_reviews(manifest, *paths)
    assert result["scores"]["matching_schemes"]["strict"]["f1"] == 1
    assert [p.read_bytes() for p in paths] == previous


def test_dieselbe_person_ist_keine_doppelannotation(submissions):
    manifest, paths = submissions
    payload = json.loads(paths[1].read_text())
    payload["pages"][0]["annotator"] = "Person A"
    paths[1].write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="verschiedene Personen"):
        annotation_review.score_reviews(manifest, *paths)


def test_zweifelsfall_bleibt_zur_gemeinsamen_klaerung_offen(submissions):
    manifest, paths = submissions
    payload = json.loads(paths[1].read_text())
    payload["pages"][0]["spans"][0]["label"] = "BRAND"
    paths[1].write_text(json.dumps(payload))
    result = annotation_review.score_reviews(manifest, *paths)
    assert result["status"] == "awaiting_adjudication"
    assert result["differences"][0]["decision"] is None
