"""Verzeichnis gefundener Blätterkatalog-IDs.

Liegt als catalogs.json im Projektwurzelverzeichnis und ist versioniert –
dieselbe Begründung wie bei gold/: eine Katalog-ID lässt sich nicht erzeugen,
nur wiederfinden, und die Suche danach kostet Zeit. Erraten geht nicht: 14
Proben rund um eine gültige ID ergaben 0 Treffer, der ID-Raum ist dünn besetzt.
Geteilt wird deshalb das Ergebnis, nicht der Weg dorthin.

Geschrieben wird atomar, gelesen fehlertolerant: Die Datei wird gemergt, ein
Konfliktmarker darin ist der wahrscheinlichste Fehlerfall überhaupt und darf
nicht die Steuerzentrale lahmlegen.

Pfade als config.X zur Laufzeit, damit Tests sie umbiegen können.
"""

import json
import os
import tempfile
from datetime import datetime
from typing import NamedTuple

from magda import config


class Registry(NamedTuple):
    entries: list[dict]
    error: str | None


def load() -> Registry:
    if not config.CATALOGS_FILE.exists():
        return Registry(entries=[], error=None)
    try:
        with open(config.CATALOGS_FILE) as f:
            entries = json.load(f)
        if not isinstance(entries, list):
            raise ValueError("kein JSON-Array")
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        return Registry(
            entries=[],
            error=f"catalogs.json ist nicht lesbar ({exc}). Merge-Konflikt?",
        )
    return Registry(entries=entries, error=None)


def _save(entries: list[dict]) -> None:
    """Erst in eine Nachbardatei, dann per os.replace umhängen – ein Abbruch
    mitten im Schreiben hinterlässt sonst einen Torso statt der Vorfassung."""
    directory = config.CATALOGS_FILE.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".catalogs.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
        # mkstemp legt 0600 an und os.replace nimmt den Modus mit; die Datei
        # wird aber geteilt und versioniert.
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, config.CATALOGS_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise


def add(entry: dict) -> dict:
    """Legt einen Eintrag an. KeyError, wenn die ID schon im Verzeichnis steht."""
    registry = load()
    if registry.error:
        raise ValueError(registry.error)
    if any(e.get("id") == entry["id"] for e in registry.entries):
        raise KeyError(f"Katalog {entry['id']} steht schon im Verzeichnis.")

    record = {
        "id": entry["id"],
        "url": entry.get("url", ""),
        "title": entry.get("title") or "",
        "version": entry.get("version") or "1",
        "pages": entry.get("pages"),
        "added": datetime.now().isoformat(timespec="seconds"),
        "added_by": entry.get("added_by", ""),
        "note": entry.get("note", ""),
    }
    _save([*registry.entries, record])
    return record


def remove(catalog_id: str) -> bool:
    """True, wenn etwas entfernt wurde."""
    registry = load()
    if registry.error:
        raise ValueError(registry.error)
    remaining = [e for e in registry.entries if e.get("id") != catalog_id]
    if len(remaining) == len(registry.entries):
        return False
    _save(remaining)
    return True
