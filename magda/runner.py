"""Pipeline-Schritte aus dem Frontend starten.

Bewusst eng gehalten: nur die fünf Pipeline-Skripte, nur die Varianten, die
`04_train`/`05_evaluate` ohnehin kennen. Es gibt keinen Weg, hier ein
beliebiges Kommando durchzureichen – die API ist ein Komfort-Knopf für das
lokale Forschungssetup, kein Remote-Shell-Ersatz.

Es läuft höchstens ein Job gleichzeitig. Die Skripte sind idempotent, ein
Abbruch ist also folgenlos: der nächste Lauf macht dort weiter, wo der
abgebrochene aufgehört hat.
"""

import subprocess
import sys
import threading
import time
from collections import deque

from magda import config

# Skript-Name -> erlaubte Varianten (leer = das Skript nimmt keine Argumente).
JOBS: dict[str, tuple[str, ...]] = {
    "01_download_flyers": (),
    "02_extract_words": (),
    "03_label_words": (),
    "04_train": ("layoutxlm", "gbert"),
    "05_evaluate": ("layoutxlm", "gbert"),
}

# Ringpuffer: bei mehreren tausend Seiten läuft das Log sonst voll.
_MAX_LINES = 400


class _State:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.job: str | None = None
        self.lines: deque[str] = deque(maxlen=_MAX_LINES)
        self.exit_code: int | None = None
        self.started_at: float | None = None


_state = _State()
_lock = threading.Lock()


def _pump(process: subprocess.Popen, lines: deque[str]) -> None:
    """Liest stdout zeilenweise in den Ringpuffer, bis der Prozess endet."""
    assert process.stdout is not None
    for raw in process.stdout:
        lines.append(raw.rstrip("\n"))
    process.wait()
    with _lock:
        _state.exit_code = process.returncode


def start(job: str, variant: str | None = None) -> None:
    """Startet einen Pipeline-Schritt. Wirft ValueError bei ungültiger Eingabe."""
    if job not in JOBS:
        raise ValueError(f"Unbekannter Schritt: {job}")
    allowed = JOBS[job]
    if variant is not None and variant not in allowed:
        raise ValueError(f"Ungültige Variante für {job}: {variant}")
    if allowed and variant is None:
        raise ValueError(f"{job} braucht eine Variante: {' oder '.join(allowed)}")

    with _lock:
        if _state.process is not None and _state.process.poll() is None:
            raise RuntimeError(f"Es läuft bereits ein Schritt: {_state.job}")

        script = config.PROJECT_ROOT / "scripts" / f"{job}.py"
        cmd = [sys.executable, "-u", str(script)]
        if variant:
            cmd.append(variant)

        process = subprocess.Popen(
            cmd,
            cwd=config.PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _state.process = process
        _state.job = job if not variant else f"{job} {variant}"
        _state.lines = deque(maxlen=_MAX_LINES)
        _state.exit_code = None
        _state.started_at = time.time()

    threading.Thread(target=_pump, args=(process, _state.lines), daemon=True).start()


def stop() -> None:
    with _lock:
        if _state.process is not None and _state.process.poll() is None:
            _state.process.terminate()


def status() -> dict:
    with _lock:
        running = _state.process is not None and _state.process.poll() is None
        return {
            "running": running,
            "job": _state.job,
            "lines": list(_state.lines),
            "exit_code": None if running else _state.exit_code,
            "elapsed": round(time.time() - _state.started_at, 1) if _state.started_at else None,
        }


def reset() -> None:
    """Verwirft den Zustand. Nur für Tests – Produktivpfade brauchen das nicht."""
    global _state
    _state = _State()
