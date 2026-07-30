"""Startet die API und auf Wunsch den Frontend-Dev-Server.

Aufruf:
    magda serve                # nur die API auf Port 8000
    magda serve --frontend     # zusaetzlich Vite auf 5173
    magda serve --port 8080

Warum ein eigener Befehl und nicht `uvicorn magda.api:app --reload`: Das
`uvicorn` aus dem PATH gehoert hier zu Anaconda, und dort ist `magda` nicht
installiert. Solange das Paket im Arbeitsverzeichnis lag, hat Python es
trotzdem gefunden – seit es unter src/ liegt, endet derselbe Befehl in
`ModuleNotFoundError: No module named 'magda'`. Als `magda serve` laeuft die
API zwangslaeufig in dem Interpreter, in dem das Paket auch installiert ist.
"""

import argparse
import shutil
import subprocess
import sys

from magda.config import PROJECT_ROOT

FRONTEND_DIR = PROJECT_ROOT / "frontend"


def _starte_frontend() -> subprocess.Popen | None:
    """Vite als Kindprozess. Fehlt etwas, sagt es das und laeuft ohne weiter."""
    if not (FRONTEND_DIR / "package.json").exists():
        print(f"Kein Frontend unter {FRONTEND_DIR} – starte nur die API.")
        return None

    npm = shutil.which("npm")
    if npm is None:
        print("npm nicht gefunden – starte nur die API.")
        return None

    if not (FRONTEND_DIR / "node_modules").is_dir():
        print("Frontend-Abhängigkeiten fehlen, installiere sie einmalig …")
        if subprocess.run([npm, "install"], cwd=FRONTEND_DIR).returncode != 0:
            print("npm install fehlgeschlagen – starte nur die API.")
            return None

    return subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND_DIR)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--frontend", action="store_true",
                        help="zusätzlich den Vite-Dev-Server starten")
    parser.add_argument("--no-reload", action="store_true",
                        help="nicht bei Codeänderungen neu laden")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ModuleNotFoundError:
        sys.exit("uvicorn fehlt. Einmalig: pip install -e '.[dev]'")

    vite = _starte_frontend() if args.frontend else None
    if vite is not None:
        print("Frontend: http://localhost:5173")
    print(f"API:      http://{args.host}:{args.port}")

    try:
        uvicorn.run(
            "magda.api:app",
            host=args.host,
            port=args.port,
            # Der Reloader beobachtet sonst auch data/ und checkpoints/ und
            # startet mitten in einem Pipeline-Lauf neu, sobald dort eine
            # Datei entsteht.
            reload=not args.no_reload,
            reload_dirs=[str(PROJECT_ROOT / "src")],
        )
    finally:
        if vite is not None:
            vite.terminate()
            try:
                vite.wait(timeout=5)
            except subprocess.TimeoutExpired:
                vite.kill()
