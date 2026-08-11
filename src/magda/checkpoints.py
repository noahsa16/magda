"""Checkpoint-Ordner aufräumen, ohne den Trainingsverlauf zu verlieren.

`save_total_limit=2` hinterlässt je Lauf bis zu zwei `checkpoint-N/`-Ordner,
und jeder davon trägt neben dem Modell den Optimizer-State: 1,2 GB gegen
417 MB in `best/`. Über sieben Läufe sind das 14 GB, die niemand mehr braucht,
sobald `best/` steht.

Nur löschen darf man sie trotzdem nicht. `trainer.save_model()` schreibt in
`best/` kein `trainer_state.json`; `magda curve` und `/api/model` lesen den
Verlauf ausschließlich aus `checkpoint-*/trainer_state.json`. Wer die Ordner
entfernt, macht beide blind.

Der naheliegende Ausweg trägt nicht: eine Kopie nach `best/` matcht das Glob
`checkpoint-*` nicht und ist für beide Leser unsichtbar. Gesichert wird
deshalb nach `<lauf>/trainer_state.json` – dort, wo das RunPod-Bundle den
Verlauf für `gbert` und `layoutxlm` ohnehin schon abgelegt hat. Ein bereits
vorhandener Verlauf wird nie überschrieben: In `checkpoints/gbert` stammen
die checkpoint-N vom 30.07. und gehören zu `best.vor-3wochen-split`, während
die Wurzeldatei (02.08.) zum eingefrorenen `best/` gehört. Ein Überschreiben
ersetzte dort den richtigen Verlauf durch einen fremden.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

STATE_FILE = "trainer_state.json"


def _step(directory: Path) -> int:
    tail = directory.name.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _checkpoint_dirs(run_dir: Path) -> list[Path]:
    """Die `checkpoint-N`-Ordner eines Laufs, nach Schrittzahl sortiert."""
    return sorted((d for d in run_dir.glob("checkpoint-*") if d.is_dir()), key=_step)


def training_state_path(run_dir: Path) -> Path | None:
    """Wo der Trainingsverlauf eines Laufs steht – vor und nach dem Aufräumen.

    Der höchste Checkpoint gewinnt, solange es einen gibt: Während ein
    Training läuft, ist er der aktuellere Stand, und die gesicherte Datei darf
    die laufende Anzeige nicht zurückdrehen.
    """
    for directory in reversed(_checkpoint_dirs(run_dir)):
        candidate = directory / STATE_FILE
        if candidate.is_file():
            return candidate
    fallback = run_dir / STATE_FILE
    return fallback if fallback.is_file() else None


def _directory_bytes(directory: Path) -> int:
    return sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())


def plan_prune(checkpoints_dir: Path) -> list[dict]:
    """Was in `checkpoints/` freigeräumt würde – ohne etwas anzufassen.

    `state_source` nennt den Checkpoint, aus dem der Verlauf gesichert wird,
    oder `None`, wenn im Lauf-Ordner schon einer liegt.
    """
    plan = []
    for run_dir in sorted(p for p in checkpoints_dir.iterdir() if p.is_dir()):
        stale = _checkpoint_dirs(run_dir)
        if not stale:
            continue
        keeps_state = (run_dir / STATE_FILE).is_file()
        plan.append({
            "run": run_dir.name,
            "path": run_dir,
            "checkpoints": [d.name for d in stale],
            "bytes": sum(_directory_bytes(d) for d in stale),
            "state_source": None if keeps_state else stale[-1].name,
            "has_best": (run_dir / "best").is_dir(),
        })
    return plan


def _validated_state(path: Path) -> str:
    """Rohtext des Verlaufs, nachdem er sich als lesbar erwiesen hat.

    Geprüft wird vor dem Löschen, nicht danach: eine kaputte Sicherung fällt
    sonst erst auf, wenn die Quelle schon weg ist.
    """
    try:
        state = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path} ist nicht lesbar: {error}") from error
    if not isinstance(state, dict) or "log_history" not in state:
        raise ValueError(f"{path} enthält keinen Trainingsverlauf")
    return json.dumps(state, indent=2, ensure_ascii=False)


def apply_prune(checkpoints_dir: Path) -> list[dict]:
    """Verlauf sichern, dann die `checkpoint-N`-Ordner entfernen.

    Alles oder nichts: Erst werden alle Läufe geprüft, dann wird geschrieben
    und gelöscht. Ein Lauf ohne `best/` bricht ab, statt zu raten – dort steht
    das einzige Modell, das nach dem Aufräumen noch existiert.
    """
    plan = plan_prune(checkpoints_dir)

    without_best = [e["run"] for e in plan if not e["has_best"]]
    if without_best:
        raise ValueError(
            "Kein best/ in: " + ", ".join(without_best)
            + " – ohne das bleibt vom Lauf nichts übrig. Nichts gelöscht.")

    rescued = {}
    for entry in plan:
        if entry["state_source"]:
            source = entry["path"] / entry["state_source"] / STATE_FILE
            rescued[entry["run"]] = _validated_state(source)

    for entry in plan:
        if entry["run"] in rescued:
            target = entry["path"] / STATE_FILE
            temporary = target.with_suffix(".json.tmp")
            temporary.write_text(rescued[entry["run"]])
            os.replace(temporary, target)
        for name in entry["checkpoints"]:
            shutil.rmtree(entry["path"] / name)

    return plan
