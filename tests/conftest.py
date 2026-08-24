"""Gemeinsame Absicherung fuer alle Tests.

Angelegt, weil eine Wurzel dazugekommen ist: Tests, die `LABELED_DIR` auf
ein tmp-Verzeichnis umbiegen, lasen `data/labeled_archive/` weiterhin echt
mit. Aufgefallen ist es an `test_default_pair_meidet_denselben_arm`, das
nach dem Archivieren der Vergleichsarme `mistral-medium-3.5-128b` aus dem
Projekt statt `qwen` aus seiner eigenen Fixture bekam.

Der Einzelfix waere gewesen, in drei Testdateien eine Zeile nachzutragen -
und die vierte, die jemand naechste Woche schreibt, haette denselben Fehler
wieder. Ein Test, der stillschweigend echte Projektdaten liest, ist nicht
bloss unsauber: er wird gruen oder rot, je nachdem, was gerade auf der
Platte liegt.
"""

import pytest

from magda import config


@pytest.fixture(autouse=True)
def _archiv_isolieren(monkeypatch, tmp_path_factory):
    """Kein Test sieht das echte `data/labeled_archive/`, sofern er es nicht
    selbst setzt - `monkeypatch.setattr` in einem Test gewinnt weiterhin."""
    monkeypatch.setattr(
        config, "LABELED_ARCHIVE_DIR", tmp_path_factory.mktemp("kein_archiv")
    )
