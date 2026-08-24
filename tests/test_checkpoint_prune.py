"""Checkpoint-Ordner aufraeumen, ohne den Trainingsverlauf zu verlieren.

`trainer.save_model()` schreibt in `best/` kein `trainer_state.json`. Wer die
checkpoint-N-Ordner loescht, um die 1,2 GB Optimizer-State je Ordner
freizugeben, macht damit `magda curve` und `/api/model` blind - beide lesen
den Verlauf heute ausschliesslich aus `checkpoint-*/trainer_state.json`.

Der naheliegende Ausweg "Datei nach `best/` kopieren" traegt nicht: `best/`
matcht das Glob `checkpoint-*` nicht, die Kopie waere fuer beide Leser
unsichtbar. Gesichert wird deshalb nach `<lauf>/trainer_state.json` - genau
dort, wo das RunPod-Bundle den Verlauf fuer `gbert` und `layoutxlm` ohnehin
schon ablegt.
"""

import json

import pytest

from magda import checkpoints


def _write_state(directory, step, f1_values):
    directory.mkdir(parents=True, exist_ok=True)
    state = {
        "epoch": float(len(f1_values)),
        "global_step": step,
        "max_steps": step,
        "best_metric": max(f1_values),
        "log_history": [{"epoch": float(i + 1), "eval_f1": f1}
                        for i, f1 in enumerate(f1_values)],
    }
    with open(directory / "trainer_state.json", "w") as f:
        json.dump(state, f)


def _run(root, name, *, checkpoints_at=(), root_state=None, best=True):
    """Einen Lauf-Ordner bauen, wie ihn der Trainer hinterlaesst."""
    run = root / name
    run.mkdir(parents=True)
    if best:
        (run / "best").mkdir()
        (run / "best" / "model.safetensors").write_bytes(b"x" * 64)
    (run / "runs").mkdir()
    for step, f1_values in checkpoints_at:
        directory = run / f"checkpoint-{step}"
        _write_state(directory, step, f1_values)
        (directory / "optimizer.pt").write_bytes(b"y" * 512)
    if root_state is not None:
        step, f1_values = root_state
        _write_state(run, step, f1_values)
    return run


# --- Wo der Verlauf gefunden wird ------------------------------------------


def test_der_verlauf_wird_im_lauf_ordner_gefunden_wenn_kein_checkpoint_mehr_liegt(tmp_path):
    run = _run(tmp_path, "gbert-p25", root_state=(40, [0.7, 0.83]))

    assert checkpoints.training_state_path(run) == run / "trainer_state.json"


def test_der_hoechste_checkpoint_schlaegt_den_gesicherten_verlauf(tmp_path):
    # Solange checkpoint-N liegen, aendert das Sichern die Anzeige nicht -
    # sonst wuerde ein laufendes Training den veralteten Stand zeigen.
    run = _run(tmp_path, "gbert",
               checkpoints_at=[(60, [0.9]), (75, [0.9, 0.94])],
               root_state=(220, [0.5]))

    assert checkpoints.training_state_path(run) == run / "checkpoint-75" / "trainer_state.json"


def test_ohne_jeden_verlauf_kommt_nichts_zurueck(tmp_path):
    run = _run(tmp_path, "gbert-p50")

    assert checkpoints.training_state_path(run) is None


# --- Der Plan: was wuerde geloescht ----------------------------------------


def test_der_plan_nennt_die_checkpoint_ordner_und_ihre_groesse(tmp_path):
    _run(tmp_path, "gbert-p25", checkpoints_at=[(36, [0.7]), (40, [0.7, 0.83])])

    plan = checkpoints.plan_prune(tmp_path)

    assert [e["run"] for e in plan] == ["gbert-p25"]
    assert plan[0]["checkpoints"] == ["checkpoint-36", "checkpoint-40"]
    assert plan[0]["bytes"] > 1000
    # Gesichert wird aus dem hoechsten Checkpoint - nur der hat alle Epochen.
    assert plan[0]["state_source"] == "checkpoint-40"


def test_ein_lauf_ohne_checkpoints_taucht_im_plan_nicht_auf(tmp_path):
    _run(tmp_path, "layoutxlm", root_state=(220, [0.87]))

    assert checkpoints.plan_prune(tmp_path) == []


def test_ein_vorhandener_verlauf_im_lauf_ordner_wird_nicht_ueberschrieben(tmp_path):
    # Belegter Fall: in checkpoints/gbert sind checkpoint-60/75 vom 30.07. und
    # gehoeren zu best.vor-3wochen-split, waehrend trainer_state.json im
    # Wurzelverzeichnis (02.08.) zum eingefrorenen best/ gehoert. Wer den
    # Checkpoint darueberkopiert, ersetzt den richtigen Verlauf durch einen
    # fremden.
    run = _run(tmp_path, "gbert",
               checkpoints_at=[(60, [0.9]), (75, [0.9, 0.94])],
               root_state=(220, [0.5, 0.92]))

    plan = checkpoints.plan_prune(tmp_path)
    assert plan[0]["state_source"] is None

    checkpoints.apply_prune(tmp_path)

    state = json.loads((run / "trainer_state.json").read_text())
    assert state["global_step"] == 220


# --- Das Aufraeumen selbst -------------------------------------------------


def test_ohne_best_ordner_wird_nichts_geloescht(tmp_path):
    # checkpoints/gbert/best traegt jede berichtete Zahl. Ein Lauf ohne best/
    # ist ein unerwarteter Zustand - dann lieber abbrechen als raten.
    _run(tmp_path, "gbert-p25", checkpoints_at=[(40, [0.83])], best=False)

    with pytest.raises(ValueError, match="best"):
        checkpoints.apply_prune(tmp_path)

    assert (tmp_path / "gbert-p25" / "checkpoint-40").is_dir()


def test_das_aufraeumen_entfernt_nur_die_checkpoint_ordner(tmp_path):
    run = _run(tmp_path, "gbert", checkpoints_at=[(60, [0.9]), (75, [0.9, 0.94])])
    (run / "best.vor-3wochen-split").mkdir()

    checkpoints.apply_prune(tmp_path)

    assert not (run / "checkpoint-60").exists()
    assert not (run / "checkpoint-75").exists()
    assert (run / "best").is_dir()
    assert (run / "best.vor-3wochen-split").is_dir()
    assert (run / "runs").is_dir()


def test_die_lernkurve_liest_nach_dem_aufraeumen_dieselbe_zahl(tmp_path):
    from magda.cli import curve

    run = _run(tmp_path, "gbert-p25",
               checkpoints_at=[(36, [0.70, 0.81]), (40, [0.70, 0.81, 0.8348])])
    before = curve.best_dev_f1(run)

    checkpoints.apply_prune(tmp_path)

    assert before == 0.8348
    assert curve.best_dev_f1(run) == before


def test_der_befehl_berichtet_nur_und_loescht_erst_mit_apply(tmp_path, monkeypatch, capsys):
    # Dasselbe Muster wie `magda dedupe`: berichten ist der Default, das
    # Loeschen kostet ein zweites Wort.
    from magda import config
    from magda.cli import prune_checkpoints

    run = _run(tmp_path, "gbert-p25", checkpoints_at=[(40, [0.83])])
    monkeypatch.setattr(config, "CHECKPOINTS_DIR", tmp_path)

    assert prune_checkpoints.main([]) == 0
    assert (run / "checkpoint-40").is_dir()
    assert "gbert-p25" in capsys.readouterr().out

    assert prune_checkpoints.main(["--apply"]) == 0
    assert not (run / "checkpoint-40").exists()
    assert (run / "trainer_state.json").is_file()


def test_ein_zerschossener_verlauf_verhindert_das_loeschen(tmp_path):
    # Erst pruefen, ob die Sicherung lesbar ist, dann loeschen - nicht umgekehrt.
    run = _run(tmp_path, "gbert-p25", checkpoints_at=[(40, [0.83])])
    (run / "checkpoint-40" / "trainer_state.json").write_text("{kaputt")

    with pytest.raises(ValueError):
        checkpoints.apply_prune(tmp_path)

    assert (run / "checkpoint-40").is_dir()


def test_ein_kaputter_lauf_haelt_auch_die_uebrigen_an(tmp_path):
    # Alles oder nichts: Erst werden alle Laeufe geprueft, dann wird
    # geschrieben und geloescht. Sonst raeumt der Abbruch die Haelfte auf und
    # laesst nicht erkennen, wie weit er kam.
    heil = _run(tmp_path, "gbert-a", checkpoints_at=[(40, [0.83])])
    kaputt = _run(tmp_path, "gbert-z", checkpoints_at=[(40, [0.83])])
    (kaputt / "checkpoint-40" / "trainer_state.json").write_text("{kaputt")

    with pytest.raises(ValueError):
        checkpoints.apply_prune(tmp_path)

    assert (heil / "checkpoint-40").is_dir()
    assert not (heil / "trainer_state.json").exists()
