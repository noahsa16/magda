"""Das Trainingsbündel muss vollständig sein – ein fehlender Split fällt sonst
erst auf der fremden Maschine auf, und dann sind die Zahlen nicht vergleichbar."""

import json
import tarfile

import pytest
from PIL import Image

from magda import bundle, config


@pytest.fixture
def projekt(tmp_path, monkeypatch):
    """Ein Miniaturprojekt: eine gelabelte Seite, ein Bild, ein Split."""
    labels = tmp_path / "labeled" / "testmodell"
    labels.mkdir(parents=True)
    (labels / "1_p1.json").write_text(json.dumps({"page_id": "1_p1", "words": [], "tags": []}))

    images = tmp_path / "images"
    images.mkdir()
    Image.new("RGB", (993, 1754), "white").save(images / "1_p1.png")

    splits = tmp_path / "splits"
    splits.mkdir()
    (splits / "split.json").write_text(json.dumps({"train": ["1_p1"], "dev": [], "test": []}))

    monkeypatch.setattr(config, "LABELED_DIR", tmp_path / "labeled")
    monkeypatch.setattr(bundle, "IMAGES_DIR", images)
    monkeypatch.setattr(bundle, "SPLITS_DIR", splits)
    # Kein echtes git-Archiv im Test: die Codeauswahl ist nicht das Interessante.
    monkeypatch.setattr(bundle, "_tracked_files", lambda: [])
    return tmp_path


def test_buendel_enthaelt_labels_split_und_bootstrap(projekt):
    ziel = projekt / "b.tgz"

    zaehler = bundle.build(ziel, "testmodell")

    with tarfile.open(ziel) as tar:
        namen = set(tar.getnames())
    assert "data/labeled/testmodell/1_p1.json" in namen
    assert "data/splits/split.json" in namen
    assert "data/images/1_p1.png" in namen
    assert "bootstrap.sh" in namen
    assert zaehler["labels"] == 1 and zaehler["bilder"] == 1


def test_bilder_kommen_auf_die_groesse_die_das_modell_erwartet(projekt):
    ziel = projekt / "b.tgz"

    bundle.build(ziel, "testmodell")

    with tarfile.open(ziel) as tar:
        with Image.open(tar.extractfile("data/images/1_p1.png")) as bild:
            assert bild.size == (bundle.IMAGE_SIZE, bundle.IMAGE_SIZE)


def test_bootstrap_traegt_modell_und_epochen(projekt):
    ziel = projekt / "b.tgz"

    bundle.build(ziel, "testmodell", epochs=3)

    with tarfile.open(ziel) as tar:
        skript = tar.extractfile("bootstrap.sh").read().decode()
    assert "--labels-from testmodell" in skript
    assert "--epochs 3" in skript


def test_fehlender_split_bricht_ab_statt_unvollstaendig_zu_packen(projekt):
    (projekt / "splits" / "split.json").unlink()

    with pytest.raises(ValueError, match="split.json"):
        bundle.build(projekt / "b.tgz", "testmodell")


def test_unbekanntes_modell_bricht_ab(projekt):
    with pytest.raises(ValueError, match="Keine Labels"):
        bundle.build(projekt / "b.tgz", "gibtsnicht")


def test_seite_ohne_bild_wird_gemeldet(projekt):
    (projekt / "images" / "1_p1.png").unlink()

    zaehler = bundle.build(projekt / "b.tgz", "testmodell")

    assert zaehler["fehlende_bilder"] == ["1_p1"]
