"""Katalog-Verzeichnis und der reparierte Versions-Fallback.

Kein Netz: die Tests fahren eine gefälschte requests.Session.
"""

import json

import pytest

from magda import catalogs, config, scraping


class _FakeResponse:
    def __init__(self, status_code=200, text="", content=b""):
        self.status_code = status_code
        self.text = text
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSession:
    def __init__(self, routes: dict):
        self.routes = routes
        self.seen: list[str] = []

    def get(self, url, timeout=None):
        self.seen.append(url)
        for fragment, response in self.routes.items():
            if fragment in url:
                return response
        return _FakeResponse(404)


@pytest.fixture(autouse=True)
def registry_file(tmp_path, monkeypatch):
    path = tmp_path / "catalogs.json"
    monkeypatch.setattr(config, "CATALOGS_FILE", path)
    return path


# --- scraping ---------------------------------------------------------------


def test_version_faellt_bei_404_auf_eins_zurueck():
    """Für Katalog 1342881 ist getcatalog.do inzwischen 404, die PDFs liegen aber
    noch da. raise_for_status() hätte den dokumentierten Fallback nie erreicht."""
    session = _FakeSession({})

    assert scraping.get_catalog_version("1342881", session) == "1"


def test_version_wirft_bei_serverfehler():
    session = _FakeSession({"getcatalog": _FakeResponse(500)})

    with pytest.raises(RuntimeError):
        scraping.get_catalog_version("1342881", session)


def test_meta_liest_version_und_titel():
    html = "<html><title>KW32 34835 SUEDBAYERN</title>catalogVersion = '2'</html>"
    session = _FakeSession({"getcatalog": _FakeResponse(200, html)})

    meta = scraping.fetch_catalog_meta("1350000", session)

    assert meta == {"found": True, "version": "2", "title": "KW32 34835 SUEDBAYERN"}


def test_probe_meldet_erreichbare_seite():
    html = "<html><title>KW33 NORD</title>catalogVersion = '1'</html>"
    session = _FakeSession({
        "getcatalog": _FakeResponse(200, html),
        "bk_1.pdf": _FakeResponse(200, content=b"x" * 4096),
    })

    probe = scraping.probe_catalog("https://x/?catalogId=1351234", session)

    assert probe["catalog_id"] == "1351234"
    assert probe["title"] == "KW33 NORD"
    assert probe["page_1_status"] == 200
    assert probe["page_1_bytes"] == 4096


def test_probe_meldet_gesperrte_seite():
    html = "<html><title>KW32</title>catalogVersion = '1'</html>"
    session = _FakeSession({
        "getcatalog": _FakeResponse(200, html),
        "bk_1.pdf": _FakeResponse(403),
    })

    probe = scraping.probe_catalog("https://x/?catalogId=1350000", session)

    assert probe["page_1_status"] == 403
    assert probe["page_1_bytes"] == 0


# --- Verzeichnis ------------------------------------------------------------


def test_load_ohne_datei_ist_leer():
    assert catalogs.load() == catalogs.Registry(entries=[], error=None)


def test_add_und_load():
    catalogs.add({"id": "1342881", "url": "https://x/?catalogId=1342881", "title": "KW30"})

    registry = catalogs.load()

    assert registry.error is None
    assert registry.entries[0]["id"] == "1342881"
    assert registry.entries[0]["added"] is not None


def test_add_lehnt_duplikat_ab():
    catalogs.add({"id": "1342881", "url": "https://x", "title": "KW30"})

    with pytest.raises(KeyError):
        catalogs.add({"id": "1342881", "url": "https://x", "title": "KW30 nochmal"})


def test_remove():
    catalogs.add({"id": "1342881", "url": "https://x", "title": "KW30"})

    assert catalogs.remove("1342881") is True
    assert catalogs.load().entries == []
    assert catalogs.remove("1342881") is False


def test_kaputte_datei_ergibt_leeres_verzeichnis_mit_fehler(registry_file):
    """catalogs.json wird gemergt – ein Konfliktmarker ist der wahrscheinlichste
    Fehlerfall und darf nicht die ganze Seite mitreißen."""
    registry_file.write_text("<<<<<<< HEAD\n[]\n=======")

    registry = catalogs.load()

    assert registry.entries == []
    assert "catalogs.json" in registry.error


def test_schreiben_ist_atomar(registry_file):
    catalogs.add({"id": "1", "url": "https://x", "title": "a"})
    catalogs.add({"id": "2", "url": "https://y", "title": "b"})

    with open(registry_file) as f:
        assert len(json.load(f)) == 2
    # Keine Temp-Reste neben der Datei.
    assert list(registry_file.parent.glob(".catalogs*")) == []


def test_probe_ruft_niemals_die_uebergebene_url_ab():
    """Kein SSRF: Aus der Eingabe wird nur die catalogId gelesen.

    Die Ziffern landen in zwei fest verdrahteten Basis-URLs, der Rest der
    Eingabe wird verworfen. Wer hier künftig direkt `session.get(url)` einbaut,
    macht aus dem Prüf-Knopf einen Proxy in fremde Netze – dieser Test fällt
    dann um.
    """
    for angriff in (
        "http://169.254.169.254/latest/meta-data/?catalogId=1",
        "file:///etc/passwd?catalogId=1",
        "http://localhost:8000/api/run?catalogId=1",
        "https://evil.example/?catalogId=1%2F..%2F..%2Fetc",
    ):
        session = _FakeSession({})
        scraping.probe_catalog(angriff, session)

        assert all(url.startswith(scraping.CATALOG_BASE) or url.startswith(scraping.PDF_BASE)
                   for url in session.seen), session.seen


def test_probe_lehnt_url_ohne_catalog_id_ab():
    with pytest.raises(ValueError, match="Keine catalogId"):
        scraping.probe_catalog("http://169.254.169.254/latest/meta-data/", _FakeSession({}))
