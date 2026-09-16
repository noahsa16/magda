"""Die Fallstudie darf fehlende Eingaben und Trainingsseiten nicht kaschieren."""

import json

import pytest

from magda import config, evaluation_study, study_report
from magda.cli import study_eval


def test_trainingsseite_wird_als_test_abgelehnt():
    with pytest.raises(ValueError, match="außerhalb"):
        evaluation_study.evaluation_clusters(["train1"], {"train": ["train1"], "dev": [], "test": ["test1"]})


def test_gemeinsame_ids_zwischen_splits_werden_abgelehnt():
    with pytest.raises(ValueError, match="gemeinsame"):
        evaluation_study.evaluation_clusters(["p1"], {"train": ["p1"], "dev": [], "test": ["p1"]})


def test_fehlende_brueckenseite_verhindert_scheinpraezises_clustering(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORDS_DIR", tmp_path)
    (tmp_path / "p1.json").write_text(json.dumps({"words": [{"text": "Butter"}]}))
    with pytest.raises(FileNotFoundError):
        evaluation_study.evaluation_clusters(["p1"], {"train": [], "dev": [], "test": ["p1", "bridge"]})


def test_wortlabels_und_entity_export_muessen_dieselbe_ausgabe_beschreiben(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    directory = tmp_path / "predictions/model"
    directory.mkdir(parents=True)
    (directory / "p1.json").write_text(json.dumps({
        "page_id": "p1", "words": [{"text": "Butter", "label": "B-PRODUCT"}],
        "entities": [{"start": 0, "end": 1, "label": "BRAND"}],
    }))
    with pytest.raises(ValueError, match="widersprechen"):
        evaluation_study._prediction_pages("model", ["p1"])


def test_studienabschluss_erzeugt_keine_neue_annotationsaufgabe(tmp_path, monkeypatch):
    monkeypatch.setattr(study_eval, "read_page_ids", lambda path: ["p1"])
    monkeypatch.setattr(evaluation_study, "run_study", lambda *args, **kwargs: {
        "status": "completed_exploratory", "pages": ["p1"], "clusters": [[0]], "reference_audit": {},
    })

    def reject_annotation(*args, **kwargs):
        pytest.fail("Der Standardabschluss darf keine Kontrollannotation starten oder unterstellen.")

    for name in ("create_packet", "score_reviews"):
        monkeypatch.setattr(study_eval.annotation_review, name, reject_annotation)
    monkeypatch.setattr(study_eval.review_packet, "write_editors", reject_annotation)
    monkeypatch.setattr(study_report, "render", lambda study, status, command: command)
    monkeypatch.setattr(study_report, "render_audit", lambda audit: "Diagnostischer Anhang")

    study_eval.main(["--output", str(tmp_path)])
    saved = json.loads((tmp_path / "study.json").read_text())
    review = json.loads((tmp_path / "review-status.json").read_text())
    assert saved["control_annotation"] == review
    assert review["status"] == "not_performed"
    assert review["scores"] is None
    assert "--review-packet" not in (tmp_path / "report.md").read_text()
    assert (tmp_path / "reference-diagnostics.md").is_file()


def test_originalabgaben_ohne_ihr_pruefpaket_werden_vor_der_messung_abgelehnt(tmp_path, monkeypatch):
    def reject_run(*args, **kwargs):
        pytest.fail("Ungültige Abgabeargumente müssen vor dem Studienlauf scheitern.")

    monkeypatch.setattr(evaluation_study, "run_study", reject_run)
    with pytest.raises(SystemExit) as error:
        study_eval.main(["--output", str(tmp_path), "--review-a", "a.json", "--review-b", "b.json"])
    assert error.value.code == 2


@pytest.mark.parametrize("bounds,expected", [
    ([-0.1, 0.1], "kein belastbarer Sieger"),
    ([0.01, 0.1], "schließen die korrigierten Differenzintervalle null aus: A − B"),
    ([-0.1, -0.01], "schließen die korrigierten Differenzintervalle null aus: A − B"),
    (None, "Nicht alle korrigierten Differenzintervalle sind bestimmbar"),
])
def test_statistisches_fazit_folgt_den_berechneten_intervallen(bounds, expected):
    study = {
        "ner_uncertainty": {"comparisons": [{"a": "A", "b": "B", "ci_familywise": bounds}]},
        "offer_uncertainty": {"comparisons": []},
    }
    assert expected in study_report._comparison_conclusion(study)


def test_report_pruefung_erlaubt_neuen_commit_aber_keine_neuen_quellen(tmp_path, monkeypatch):
    from magda import provenance

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CHECKPOINTS_DIR", tmp_path)
    split = tmp_path / "splits/split.json"
    split.parent.mkdir()
    split.write_text("{}")
    checkpoint = tmp_path / "offer_pairs/model.pt"
    checkpoint.parent.mkdir()
    checkpoint.write_bytes(b"unchanged")
    study = {
        "split_sha256": provenance.file_digest(split), "cluster_word_hashes": {},
        "pair_checkpoint_sha256": provenance.file_digest(checkpoint),
        "reference_audit": {"pages": []}, "ner": {}, "replays": {},
        "code": {"git_revision": "before", "source_sha256": "same"},
    }
    monkeypatch.setattr(provenance, "code_version", lambda: {"git_revision": "after", "source_sha256": "same"})
    with pytest.raises(ValueError, match="Quellcode"):
        evaluation_study.verify_snapshot(study)
    evaluation_study.verify_snapshot(study, require_same_revision=False)
    monkeypatch.setattr(provenance, "code_version", lambda: {"git_revision": "after", "source_sha256": "changed"})
    with pytest.raises(ValueError, match="Quellcode"):
        evaluation_study.verify_snapshot(study, require_same_revision=False)
