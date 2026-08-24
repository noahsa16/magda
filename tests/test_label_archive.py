"""Aktive Labelordner und Archiv liegen getrennt - was das kosten darf.

Das Archiv ist eine Anzeigefrage: `data/labeled/` soll zeigen, womit gerade
gearbeitet wird, statt acht Ordner nebeneinander, von denen sechs erledigt
sind. Es darf aber nichts *funktional* wegnehmen, und zwei Stellen brechen
dabei leicht und leise:

`labeled_page_ids` ist die Sicherung von `magda dedupe` - eine Seite, in die
Labelarbeit geflossen ist, wird nicht als Duplikat entfernt. Faellt das
Archiv aus dem Scan, loescht Schritt 06 Seiten, die ein Archivmodell gelabelt
hat, und Schritt 02 stellt sie beim naechsten Lauf als `pending` wieder ein.

`review.default_pair` braucht zwei Ordner *verschiedener* Modelle. Nach der
Sortierung stehen aktiv nur noch `sonnet-5` und `sonnet-5-app` - gemeinsamer
Praefix, also faende die Funktion kein Paar mehr und `magda queue` verloere
sein Uneinigkeitsmass. Eine Sortierung, die einen Befehl still abschaltet,
waere keine Aufraeumarbeit.
"""

import pytest

from magda import config, review


@pytest.fixture
def zwei_wurzeln(monkeypatch, tmp_path):
    """Ein aktiver Ordner und ein archivierter, mit je einer eigenen Seite."""
    active = tmp_path / "labeled"
    archive = tmp_path / "labeled_archive"
    for root, model, pages in [
        (active, "sonnet-5", ["a_p1", "a_p2"]),
        (archive, "mistral-alt", ["a_p1", "nur_im_archiv_p1"]),
    ]:
        (root / model).mkdir(parents=True)
        for page_id in pages:
            (root / model / f"{page_id}.json").write_text("{}")
    monkeypatch.setattr(config, "LABELED_DIR", active)
    monkeypatch.setattr(config, "LABELED_ARCHIVE_DIR", archive)
    return active, archive


def test_archivseiten_zaehlen_als_gelabelt(zwei_wurzeln):
    """Sonst entfernt `magda dedupe` eine Seite, in die Arbeit geflossen ist."""
    assert config.labeled_page_ids() == {"a_p1", "a_p2", "nur_im_archiv_p1"}


def test_labeled_dir_findet_archivierte_modelle(zwei_wurzeln):
    """`magda agreement mistral-alt …` soll ohne Pfadangabe weiterlaufen."""
    _, archive = zwei_wurzeln
    assert config.labeled_dir("mistral-alt") == archive / "mistral-alt"


def test_aktiv_hat_vorrang_vor_archiv(monkeypatch, tmp_path):
    """Gibt es den Namen zweimal, gilt der aktive Ordner.

    Der umgekehrte Vorrang waere die gefaehrlichere Variante: ein Lauf
    schriebe nach `data/labeled/`, gelesen wuerde aus dem Archiv, und die
    Differenz faellt an keiner Zahl auf.
    """
    active, archive = tmp_path / "labeled", tmp_path / "labeled_archive"
    (active / "doppelt").mkdir(parents=True)
    (archive / "doppelt").mkdir(parents=True)
    monkeypatch.setattr(config, "LABELED_DIR", active)
    monkeypatch.setattr(config, "LABELED_ARCHIVE_DIR", archive)

    assert config.labeled_dir("doppelt") == active / "doppelt"


def test_unbekanntes_modell_zeigt_auf_den_aktiven_ordner(zwei_wurzeln):
    """Ein neuer Labellauf legt seinen Ordner aktiv an, nicht im Archiv."""
    active, _ = zwei_wurzeln
    assert config.labeled_dir("ganz-neu") == active / "ganz-neu"


def test_labeled_models_zeigt_das_archiv_nicht(zwei_wurzeln):
    """Die Liste speist Frontend und Defaults - dort gehoert Erledigtes weg."""
    assert config.labeled_models() == ["sonnet-5"]
    assert config.archived_models() == ["mistral-alt"]


def test_default_pair_greift_ins_archiv(monkeypatch, tmp_path):
    """Aktiv steht nur noch eine Modellfamilie - das Paar kommt aus dem Archiv."""
    active, archive = tmp_path / "labeled", tmp_path / "labeled_archive"
    for root, name, anzahl in [
        (active, "sonnet-5", 20),
        (active, "sonnet-5-app", 15),
        (archive, "mistral-x", 10),
    ]:
        (root / name).mkdir(parents=True)
        for i in range(anzahl):
            (root / name / f"s{i}.json").write_text("{}")
    monkeypatch.setattr(config, "LABELED_DIR", active)
    monkeypatch.setattr(config, "LABELED_ARCHIVE_DIR", archive)

    a, b = review.default_pair()

    assert a == "sonnet-5"
    assert b == "mistral-x", "sonnet-5-app ist derselbe Arm, taugt nicht als zweite Meinung"
