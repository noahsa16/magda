"""Die Historie ist der einzige Ort, an dem ein Lauf nach dem Backend-Neustart
noch nachvollziehbar ist."""

import json
from datetime import datetime

import pytest

from magda import config, runs


@pytest.fixture(autouse=True)
def runs_dir(tmp_path, monkeypatch):
    d = tmp_path / "runs"
    monkeypatch.setattr(config, "RUNS_DIR", d)
    return d


def _record(job: str, when: datetime, exit_code: int = 0, log: str = "") -> str:
    run_id = runs.new_run_id(job, when)
    runs.write_meta(run_id, {
        "run_id": run_id, "job": job, "args": {}, "command": ["python", f"{job}.py"],
        "started": when.isoformat(timespec="seconds"), "finished": None,
        "exit_code": exit_code, "duration": 1.0,
    })
    runs.log_path(run_id).write_text(log)
    return run_id


def test_run_id_enthaelt_zeit_und_job():
    run_id = runs.new_run_id("train", datetime(2026, 7, 29, 14, 22, 1))

    assert run_id == "20260729-142201_train"


def test_run_id_weicht_bei_kollision_aus():
    when = datetime(2026, 7, 29, 14, 22, 1)
    first = _record("train", when)
    second = runs.new_run_id("train", when)

    assert second != first


def test_write_meta_legt_verzeichnis_an():
    run_id = _record("extract", datetime(2026, 7, 29, 10, 0, 0))

    with open(config.RUNS_DIR / f"{run_id}.json") as f:
        assert json.load(f)["job"] == "extract"


def test_list_runs_sortiert_neueste_zuerst():
    _record("extract", datetime(2026, 7, 29, 10, 0, 0))
    _record("train", datetime(2026, 7, 29, 12, 0, 0))

    assert [r["job"] for r in runs.list_runs()] == ["train", "extract"]


def test_list_runs_ohne_verzeichnis_ist_leer():
    assert runs.list_runs() == []


def test_list_runs_ueberspringt_kaputte_datei():
    _record("train", datetime(2026, 7, 29, 12, 0, 0))
    (config.RUNS_DIR / "20260729-090000_kaputt.json").write_text("{nicht json")

    assert [r["job"] for r in runs.list_runs()] == ["train"]


def test_read_run_liefert_log_dazu():
    run_id = _record("download", datetime(2026, 7, 29, 9, 0, 0), 2, "error: url fehlt")

    entry = runs.read_run(run_id)

    assert entry["exit_code"] == 2
    assert entry["log"] == "error: url fehlt"


def test_read_run_lehnt_pfadangaben_ab():
    """run_id ist ein opaker Schlüssel, kein Pfad."""
    assert runs.read_run("../../etc/passwd") is None
    assert runs.read_run("unbekannt") is None


def test_prune_behaelt_die_juengsten():
    for minute in range(5):
        _record("extract", datetime(2026, 7, 29, 10, minute, 0))

    runs.prune(keep=2)

    remaining = [r["run_id"] for r in runs.list_runs()]
    assert len(remaining) == 2
    assert remaining[0].startswith("20260729-1004")
    # Der Log verschwindet mit den Metadaten, sonst wächst das Verzeichnis weiter.
    assert len(list(config.RUNS_DIR.glob("*.log"))) == 2
