"""`magda extract --render-missing` fuer den frischen Klon.

`data/words/` ist versioniert, `data/images/` nicht. Der normale Lauf
ueberspringt eine Seite schon an der vorhandenen Wortdatei und rendert
deshalb kein einziges Bild - gemessen am 2026-09-03: "0 Seiten verarbeitet,
666 schon vorhanden". Der Annotator zeigt danach leere Seiten.
"""

import json

import fitz
import pytest

from magda.cli import extract


def _pdf_bytes(text: str) -> bytes:
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), text)
        return doc.tobytes()


@pytest.fixture
def projekt(tmp_path, monkeypatch):
    """Ein Katalog mit zwei Seiten, davon eine mit Wortdatei."""
    raw = tmp_path / "raw" / "1364390"
    raw.mkdir(parents=True)
    (raw / "bk_1.pdf").write_bytes(_pdf_bytes("Butter 1.99"))
    (raw / "bk_2.pdf").write_bytes(_pdf_bytes("Milch 0.99"))

    words = tmp_path / "words"
    words.mkdir()
    payload = {"page_id": "1364390_p1", "words": [{"text": "Butter"}], "width": 1, "height": 1}
    (words / "1364390_p1.json").write_text(json.dumps(payload))

    images = tmp_path / "images"
    images.mkdir()

    monkeypatch.setattr(extract, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(extract, "WORDS_DIR", words)
    monkeypatch.setattr(extract, "IMAGES_DIR", images)
    return tmp_path


def test_fehlendes_bild_wird_nachgerendert(projekt):
    extract.main(["--render-missing"])

    image = projekt / "images" / "1364390_p1.png"
    assert image.exists()
    assert image.read_bytes().startswith(b"\x89PNG")


def test_die_wortdatei_bleibt_unveraendert(projekt):
    words_file = projekt / "words" / "1364390_p1.json"
    before = words_file.read_bytes()

    extract.main(["--render-missing"])

    # Die Wortreihenfolge ist der Vertrag, an dem alle Label-Indizes haengen.
    # Ein Nachrendern, das sie neu schreibt, entwertet data/labeled/ still.
    assert words_file.read_bytes() == before


def test_seiten_ohne_wortdatei_bekommen_kein_bild(projekt):
    extract.main(["--render-missing"])

    # Seite 2 ist entweder Duplikat oder nie extrahiert - ein Bild dafuer
    # waere Masse ohne Leser.
    assert not (projekt / "images" / "1364390_p2.png").exists()


def test_vorhandenes_bild_wird_nicht_neu_geschrieben(projekt):
    image = projekt / "images" / "1364390_p1.png"
    image.write_bytes(b"\x89PNG platzhalter")

    extract.main(["--render-missing"])

    assert image.read_bytes() == b"\x89PNG platzhalter"


def test_ohne_die_option_entsteht_kein_bild(projekt):
    # Das ist der gemessene Fehlerfall: der normale Lauf ueberspringt an der
    # Wortdatei und rendert nichts.
    extract.main([])

    assert not (projekt / "images" / "1364390_p1.png").exists()
