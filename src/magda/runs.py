"""Lauf-Historie auf Platte.

Je Lauf zwei Dateien: ein kleines Metadaten-JSON und der vollständige Log.
Getrennt, weil ein Trainingslauf zehntausende Zeilen schreibt – die Liste in
der Steuerzentrale liest nur die JSON-Dateien und bleibt schnell. Der
Ringpuffer in runner.py bleibt für die Live-Ansicht; hier steht alles.

Pfade als config.X zur Laufzeit, damit Tests sie umbiegen können.
"""

import json
from datetime import datetime
from pathlib import Path

from magda import config


def new_run_id(job: str, when: datetime | None = None) -> str:
    """Sortierbarer Schlüssel aus Zeit und Job. Weicht aus, wenn er schon existiert."""
    stamp = (when or datetime.now()).strftime("%Y%m%d-%H%M%S")
    base = f"{stamp}_{job}"
    run_id, suffix = base, 2
    while (config.RUNS_DIR / f"{run_id}.json").exists():
        run_id = f"{base}-{suffix}"
        suffix += 1
    return run_id


def log_path(run_id: str) -> Path:
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return config.RUNS_DIR / f"{run_id}.log"


def write_meta(run_id: str, meta: dict) -> None:
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.RUNS_DIR / f"{run_id}.json", "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


def list_runs(limit: int = 100) -> list[dict]:
    """Metadaten aller Läufe, neueste zuerst.

    Der run_id sortiert lexikografisch richtig, weil er mit dem Zeitstempel
    beginnt – kein Öffnen nötig, um die Reihenfolge zu bestimmen.
    """
    entries: list[dict] = []
    if not config.RUNS_DIR.exists():
        return entries
    for meta_file in sorted(config.RUNS_DIR.glob("*.json"), reverse=True):
        try:
            with open(meta_file) as f:
                entries.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            # Ein abgebrochener Schreibvorgang darf nicht die ganze Liste kosten.
            continue
        if len(entries) >= limit:
            break
    return entries


def read_run(run_id: str) -> dict | None:
    """Metadaten samt vollständigem Log. None, wenn es den Lauf nicht gibt.

    run_id wird gegen die vorhandenen Dateien abgeglichen statt an Path
    übergeben – sonst wäre "../../etc/passwd" ein gültiger Schlüssel.
    """
    if not config.RUNS_DIR.exists():
        return None
    known = {p.stem for p in config.RUNS_DIR.glob("*.json")}
    if run_id not in known:
        return None
    with open(config.RUNS_DIR / f"{run_id}.json") as f:
        meta = json.load(f)
    log_file = config.RUNS_DIR / f"{run_id}.log"
    meta["log"] = log_file.read_text() if log_file.exists() else ""
    return meta


def prune(keep: int = 100) -> None:
    """Wirft die ältesten Läufe weg. data/ ist gitignored, aber nicht unbegrenzt."""
    if not config.RUNS_DIR.exists():
        return
    meta_files = sorted(config.RUNS_DIR.glob("*.json"), reverse=True)
    for meta_file in meta_files[keep:]:
        meta_file.unlink(missing_ok=True)
        meta_file.with_suffix(".log").unlink(missing_ok=True)
