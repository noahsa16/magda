"""Fingerabdrücke verbinden Messwerte mit unveränderlichen Eingaben."""

import hashlib
import json
import subprocess
from pathlib import Path

from magda import config


def digest(value) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checkpoint_digest(path: Path) -> str:
    """Gewichte und Konfiguration gemeinsam, unabhängig vom Ordnernamen."""
    if path.is_file():
        return file_digest(path)
    files = sorted(p for p in path.rglob("*") if p.is_file())
    if not files:
        raise FileNotFoundError(f"Checkpoint fehlt: {path}")
    return digest({str(p.relative_to(path)): file_digest(p) for p in files})


def code_version() -> dict:
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=config.PROJECT_ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    # Der Commit allein genügt bei noch nicht committeten Korrekturen nicht.
    sources = config.PROJECT_ROOT / "src" / "magda"
    return {"git_revision": revision, "source_sha256": digest({
        str(p.relative_to(sources)): file_digest(p) for p in sorted(sources.rglob("*.py"))
    })}


def reference_identity(pages: list[dict]) -> dict:
    ordered = sorted(pages, key=lambda p: p["page_id"])
    return {
        "page_ids": [p["page_id"] for p in ordered],
        "reference_sha256": digest([
            {key: p.get(key) for key in ("page_id", "words", "tags", "width", "height")}
            for p in ordered
        ]),
    }


def prediction_identity(directory: Path, page_ids: list[str]) -> str:
    return digest({pid: file_digest(directory / f"{pid}.json") for pid in sorted(page_ids)})
