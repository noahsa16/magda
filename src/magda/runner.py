"""Pipeline-Schritte aus dem Frontend starten.

Dieses Modul kümmert sich um den Prozess-Lebenszyklus. *Was* startbar ist und
mit welchen Parametern, steht in jobs.py – und nur dort wird aus einer
Nutzereingabe ein Kommando. Es gibt keinen Weg, hier etwas Beliebiges
durchzureichen: die API ist ein Komfort-Knopf für das lokale Forschungssetup,
kein Remote-Shell-Ersatz.

Es läuft höchstens ein Job gleichzeitig. Die Skripte sind idempotent, ein
Abbruch ist also folgenlos: der nächste Lauf macht dort weiter, wo der
abgebrochene aufgehört hat.

Der Ringpuffer hält die letzten Zeilen für die Live-Ansicht; vollständig steht
jeder Lauf über runs.py auf der Platte.
"""

import subprocess
import threading
import time
from collections import deque
from datetime import datetime

from magda import config, jobs, runs

# Ringpuffer: bei mehreren tausend Seiten läuft die Live-Ansicht sonst voll.
_MAX_LINES = 400


class _State:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.job: str | None = None
        self.args: dict = {}
        self.run_id: str | None = None
        self.lines: deque[str] = deque(maxlen=_MAX_LINES)
        self.exit_code: int | None = None
        self.started_at: float | None = None


_state = _State()
_lock = threading.Lock()


def _pump(process: subprocess.Popen, lines: deque[str], run_id: str, meta: dict) -> None:
    """Liest stdout zeilenweise in Ringpuffer und Logdatei, bis der Prozess endet."""
    assert process.stdout is not None
    started_monotonic = meta.pop("_started_monotonic")
    with open(runs.log_path(run_id), "w") as log:
        for raw in process.stdout:
            lines.append(raw.rstrip("\n"))
            log.write(raw)
            log.flush()
    process.wait()
    with _lock:
        _state.exit_code = process.returncode
    meta["exit_code"] = process.returncode
    meta["finished"] = datetime.now().isoformat(timespec="seconds")
    meta["duration"] = round(time.time() - started_monotonic, 1)
    runs.write_meta(run_id, meta)
    runs.prune()


def start(job: str, args: dict | None = None) -> None:
    """Startet einen Pipeline-Schritt.

    ValueError bei ungültiger Eingabe, RuntimeError wenn schon etwas läuft.
    """
    values = dict(args or {})
    # Erst validieren, dann sperren: eine abgelehnte Eingabe soll den laufenden
    # Job nicht einmal berühren.
    command = jobs.build_command(job, values)

    with _lock:
        if _state.process is not None and _state.process.poll() is None:
            raise RuntimeError(f"Es läuft bereits ein Schritt: {_state.job}")

        started = datetime.now()
        run_id = runs.new_run_id(job, started)
        process = subprocess.Popen(
            command,
            cwd=config.PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _state.process = process
        _state.job = job
        _state.args = values
        _state.run_id = run_id
        _state.lines = deque(maxlen=_MAX_LINES)
        _state.exit_code = None
        _state.started_at = time.time()

    meta = {
        "run_id": run_id,
        "job": job,
        "title": jobs.JOBS[job].title,
        "args": values,
        "command": command,
        "started": started.isoformat(timespec="seconds"),
        "finished": None,
        "exit_code": None,
        "duration": None,
    }
    # Schon vor dem ersten Ausgabezeichen schreiben: ein Lauf, der das Backend
    # mit sich reißt, taucht sonst nirgends auf.
    runs.write_meta(run_id, meta)

    threading.Thread(
        target=_pump,
        args=(process, _state.lines, run_id, {**meta, "_started_monotonic": time.time()}),
        daemon=True,
    ).start()


def stop() -> None:
    with _lock:
        if _state.process is not None and _state.process.poll() is None:
            _state.process.terminate()


def status() -> dict:
    with _lock:
        # Nicht poll(), sondern der eingetragene Exit-Code: der Prozess ist
        # eher fertig als _pump, das den letzten Ausgabeblock noch schreibt.
        # Über poll() meldete der Lauf für einen Moment "beendet, Code unbekannt"
        # – das Frontend zeigte dann kurz einen Abbruch, den es nie gab.
        running = _state.process is not None and _state.exit_code is None
        return {
            "running": running,
            "job": _state.job,
            "args": dict(_state.args),
            "run_id": _state.run_id,
            "lines": list(_state.lines),
            "exit_code": None if running else _state.exit_code,
            "elapsed": round(time.time() - _state.started_at, 1) if _state.started_at else None,
        }


def reset() -> None:
    """Verwirft den Zustand. Nur für Tests – Produktivpfade brauchen das nicht."""
    global _state
    _state = _State()
