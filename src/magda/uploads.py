"""Uploads für die Demo: ein fremdes PDF, ohne Umweg über data/raw oder Kataloge.

Die Demo verarbeitet ein einzelnes PDF über `magda.pipeline.extract_offers`,
gestartet vom Runner (`magda extract-pdf` als Job, siehe `jobs.py`). Dieses
Modul kümmert sich um das, was davor und danach an der Platte passiert:
Ablage unter einer vom Server vergebenen ID, nie unter dem Dateinamen des
Nutzers - sonst wäre ein hochgeladener Dateiname ein potenzieller Pfad
("../../etc/passwd.pdf"). `jobs.build_command` löst die ID für den Runner in
einen Pfad unter UPLOADS_DIR auf; hier steht die Gegenseite, die diesen Pfad
tatsächlich anlegt und wieder aufräumt.

Pfade als config.X zur Laufzeit, damit Tests sie umbiegen können.
"""

import secrets
import time
from pathlib import Path

import fitz

from magda import config

# secrets.token_hex(16) -> 32 Hex-Zeichen. Dieselbe Länge steht als Muster in
# jobs.py und in der API - eine Konstante statt einer Zahl an drei Stellen.
UPLOAD_ID_LENGTH = 32
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB - grosszügig für einen einzelnen Prospekt


class InvalidUpload(ValueError):
    """Eingabe abgelehnt - kein PDF, zu groß, unerreichbar oder eine unbekannte ID."""


def new_id() -> str:
    return secrets.token_hex(UPLOAD_ID_LENGTH // 2)


def is_valid_id(upload_id: str) -> bool:
    """Alles, was nicht exakt 32 Hex-Zeichen ist, ist keine ID - auch nicht
    mittelbar ein Pfad. `../../etc` besteht diese Prüfung nicht."""
    return (
        len(upload_id) == UPLOAD_ID_LENGTH
        and all(c in "0123456789abcdef" for c in upload_id)
    )


def _checked(upload_id: str) -> str:
    if not is_valid_id(upload_id):
        raise InvalidUpload(f"Unbekannte Upload-ID: {upload_id!r}")
    return upload_id


def pdf_path(upload_id: str) -> Path:
    return config.UPLOADS_DIR / f"{_checked(upload_id)}.pdf"


def result_path(upload_id: str) -> Path:
    return config.UPLOADS_DIR / f"{_checked(upload_id)}.json"


def images_dir(upload_id: str) -> Path:
    return config.UPLOADS_DIR / _checked(upload_id)


def save_pdf(data: bytes) -> dict:
    """Speichert ein PDF unter einer neuen, zufälligen ID.

    `secrets.token_hex` statt einer fortlaufenden Nummer: eine erratene ID
    darf nicht den Upload einer anderen Person treffen. Geprüft wird die
    Größe vor dem Schreiben und der Inhalt (Magic Bytes, dann ein echter
    Öffnungsversuch) danach - ein Name, der zufällig auf ".pdf" endet, ist
    noch kein PDF.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise InvalidUpload(
            f"PDF ist zu groß ({len(data) / 1_000_000:.1f} MB, erlaubt sind "
            f"{MAX_UPLOAD_BYTES / 1_000_000:.0f} MB)."
        )
    if not data.startswith(b"%PDF"):
        raise InvalidUpload("Das ist kein PDF (Magic Bytes fehlen).")

    upload_id = new_id()
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.UPLOADS_DIR / f"{upload_id}.pdf"
    path.write_bytes(data)

    try:
        with fitz.open(path) as doc:
            pages = doc.page_count
    except Exception as error:
        path.unlink(missing_ok=True)
        raise InvalidUpload(f"PDF lässt sich nicht lesen: {error}") from None

    return {"upload_id": upload_id, "pages": pages, "bytes": len(data)}


def prune(max_age_days: int = 7) -> int:
    """Löscht Uploads, die älter sind als max_age_days. Gibt die Zahl zurück.

    Anders als `data/runs/` (Zahllimit, siehe `runs.prune`) gibt es hier kein
    natürliches Limit für die Anzahl - ein Demo-Versuch pro Tag füllt den
    Ordner sonst unbegrenzt. Alter statt Anzahl, weil ein Ergebnis nach einer
    Woche niemanden mehr interessiert, unabhängig davon, wie viele dazukamen.
    """
    if not config.UPLOADS_DIR.is_dir():
        return 0
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    seen: set[str] = set()
    for path in config.UPLOADS_DIR.iterdir():
        stem = path.name.split(".")[0]
        if not is_valid_id(stem) or stem in seen:
            continue
        pdf = config.UPLOADS_DIR / f"{stem}.pdf"
        if not pdf.exists() or pdf.stat().st_mtime >= cutoff:
            continue
        seen.add(stem)
        for candidate in (pdf, config.UPLOADS_DIR / f"{stem}.json"):
            candidate.unlink(missing_ok=True)
        directory = config.UPLOADS_DIR / stem
        if directory.is_dir():
            for f in directory.iterdir():
                f.unlink(missing_ok=True)
            directory.rmdir()
        removed += 1
    return removed
