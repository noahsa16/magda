"""Der Runner startet nur, was jobs.py erlaubt – und schreibt jeden Lauf mit."""

import time

import pytest

from magda import config, runner, runs


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    runner.reset()
    yield
    runner.stop()
    # Erst warten, dann aufräumen: der Pump-Thread schreibt die Metadaten
    # nachträglich und löst config.RUNS_DIR dabei erneut auf. Endet der Test
    # vorher, ist das Monkeypatch schon zurückgenommen und der Lauf landet im
    # echten data/runs/.
    deadline = time.time() + 10
    while runner.status()["running"] and time.time() < deadline:
        time.sleep(0.05)
    runner.reset()


def _wait_until_done(timeout: float = 10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not runner.status()["running"]:
            return runner.status()
        time.sleep(0.05)
    raise AssertionError("Lauf wurde nicht fertig")


def test_start_lehnt_unbekannten_job_ab():
    with pytest.raises(ValueError, match="Unbekannter Schritt"):
        runner.start("rm -rf /")


def test_start_lehnt_unbekannten_parameter_ab():
    with pytest.raises(ValueError, match="Unbekannter Parameter"):
        runner.start("02_extract_words", {"outfile": "/etc/passwd"})


def test_start_verlangt_pflichtparameter():
    with pytest.raises(ValueError, match="URL"):
        runner.start("01_download_flyers", {})


def test_status_ist_leer_ohne_lauf():
    assert runner.status() == {
        "running": False, "job": None, "args": {}, "run_id": None,
        "lines": [], "exit_code": None, "elapsed": None,
    }


def test_lauf_landet_in_der_historie():
    """02_extract_words bricht ohne data/raw sofort ab – genau deshalb taugt es
    als schneller Testlauf: echter Subprozess, echter Exit-Code, kein Netz."""
    runner.start("02_extract_words")
    state = _wait_until_done()

    assert state["exit_code"] is not None
    history = runs.list_runs()
    assert len(history) == 1
    assert history[0]["job"] == "02_extract_words"
    assert history[0]["command"][-1].endswith("02_extract_words.py")
    assert history[0]["exit_code"] == state["exit_code"]
    assert runs.read_run(history[0]["run_id"])["log"] != ""


def test_zweiter_lauf_waehrend_eines_laufs_wird_abgelehnt():
    runner.start("02_extract_words")
    try:
        with pytest.raises(RuntimeError, match="läuft bereits"):
            runner.start("02_extract_words")
    finally:
        _wait_until_done()


def test_args_stehen_im_status_und_in_der_historie():
    runner.start("02_extract_words")
    _wait_until_done()

    assert runs.list_runs()[0]["args"] == {}
