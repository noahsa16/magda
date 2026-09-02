"""Speicherung von Demo-Uploads unter einer server-vergebenen ID.

Der Kern der Sicherheitseigenschaft: der Dateiname des Nutzers landet nirgends
im Pfad, nur eine zufaellige ID, die `save_pdf` selbst vergibt.
"""

import time

import fitz
import pytest

from magda import config, uploads


@pytest.fixture
def uploads_dir(tmp_path, monkeypatch):
    d = tmp_path / "uploads"
    monkeypatch.setattr(config, "UPLOADS_DIR", d)
    return d


def _tiny_pdf(pages: int = 2) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=100, height=100)
        page.insert_text((10, 30), f"Seite {i + 1}", fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def test_save_pdf_vergibt_eine_id_ohne_den_dateinamen_des_nutzers(uploads_dir):
    result = uploads.save_pdf(_tiny_pdf(2))

    assert uploads.is_valid_id(result["upload_id"])
    assert result["pages"] == 2
    assert result["bytes"] == len(_tiny_pdf(2))
    # Die Datei liegt unter der ID, nicht unter irgendeinem Nutzernamen.
    assert (uploads_dir / f"{result['upload_id']}.pdf").is_file()


def test_save_pdf_zwei_uploads_bekommen_verschiedene_ids(uploads_dir):
    a = uploads.save_pdf(_tiny_pdf(1))
    b = uploads.save_pdf(_tiny_pdf(1))

    assert a["upload_id"] != b["upload_id"]


def test_save_pdf_lehnt_daten_ohne_pdf_signatur_ab(uploads_dir):
    with pytest.raises(uploads.InvalidUpload, match="kein PDF"):
        uploads.save_pdf(b"Das hier ist gar kein PDF.")
    # Die Pruefung greift vor dem Schreiben - kein Ordner mit Datenmuell.
    assert not uploads_dir.exists()


def test_save_pdf_lehnt_zu_grosse_dateien_ab(uploads_dir, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(uploads.InvalidUpload, match="zu groß"):
        uploads.save_pdf(_tiny_pdf(1))


def test_save_pdf_raeumt_nach_einem_kaputten_pdf_wieder_auf(uploads_dir):
    """Magic Bytes stimmen, der Rest ist Muell - fitz.open() scheitert erst
    beim echten Oeffnen. Die angelegte Datei darf danach nicht liegen bleiben."""
    with pytest.raises(uploads.InvalidUpload, match="lässt sich nicht lesen"):
        uploads.save_pdf(b"%PDF-1.7\n" + b"\x00" * 40)
    assert list(uploads_dir.glob("*.pdf")) == []


@pytest.mark.parametrize("bad_id", [
    "zu-kurz",
    "0123456789abcdef0123456789abcdeff",  # ein Zeichen zu lang
    "../../etc/passwd",
    "0123456789ABCDEF0123456789ABCDEF",  # Grossbuchstaben - token_hex liefert keine
    "0123456789abcdef0123456789abcd/f",  # Pfadtrenner mitten drin
])
def test_ungueltige_ids_werden_ueberall_abgelehnt(uploads_dir, bad_id):
    with pytest.raises(uploads.InvalidUpload):
        uploads.pdf_path(bad_id)
    with pytest.raises(uploads.InvalidUpload):
        uploads.result_path(bad_id)
    with pytest.raises(uploads.InvalidUpload):
        uploads.images_dir(bad_id)


def test_prune_entfernt_nur_alte_uploads(uploads_dir):
    old = uploads.save_pdf(_tiny_pdf(1))
    new = uploads.save_pdf(_tiny_pdf(1))

    old_pdf = uploads.pdf_path(old["upload_id"])
    eight_days_ago = time.time() - 8 * 86400
    import os
    os.utime(old_pdf, (eight_days_ago, eight_days_ago))

    removed = uploads.prune(max_age_days=7)

    assert removed == 1
    assert not uploads.pdf_path(old["upload_id"]).exists()
    assert uploads.pdf_path(new["upload_id"]).exists()


def test_prune_ohne_verzeichnis_ist_folgenlos(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp_path / "nie_angelegt")
    assert uploads.prune() == 0
