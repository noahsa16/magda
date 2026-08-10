"""Auswerten auf einer freien Seitenmenge statt auf einem Split.

Woche 4 steht bewusst in keinem Split - sie ist die unberuehrte
Frischwoche. Fuer die Drift-Messung muss `magda eval` sie trotzdem
auswerten koennen, ohne dass jemand den eingefrorenen Split anfasst.
"""

import pytest

from magda.cli import evaluate


def test_eine_seitenliste_schlaegt_den_split(tmp_path):
    listing = tmp_path / "pages.txt"
    listing.write_text("1355990_p1\n1355990_p2\n")

    assert evaluate.read_page_ids(listing) == ["1355990_p1", "1355990_p2"]


def test_leerzeilen_und_kommentare_werden_uebergangen(tmp_path):
    listing = tmp_path / "pages.txt"
    listing.write_text("# Woche 4\n1355990_p1\n\n  1355990_p2  \n")

    assert evaluate.read_page_ids(listing) == ["1355990_p1", "1355990_p2"]


def test_eine_leere_liste_bricht_ab(tmp_path):
    listing = tmp_path / "pages.txt"
    listing.write_text("# nur ein Kommentar\n")

    with pytest.raises(ValueError, match="keine Seiten"):
        evaluate.read_page_ids(listing)


def test_die_reihenfolge_der_datei_bleibt_erhalten(tmp_path):
    """Der Blackbox-Lauf nummeriert den Fortschritt mit. Waere die Reihenfolge
    unbestimmt, liesse sich ein Abbruch nicht an der Stelle fortsetzen."""
    listing = tmp_path / "pages.txt"
    listing.write_text("b_p2\na_p1\nc_p3\n")

    assert evaluate.read_page_ids(listing) == ["b_p2", "a_p1", "c_p3"]


def test_eine_doppelt_genannte_seite_zaehlt_einmal(tmp_path):
    """Sonst geht dieselbe Seite doppelt in den Nenner ein - und beim
    Blackbox-Lauf auch doppelt aufs Kontingent."""
    listing = tmp_path / "pages.txt"
    listing.write_text("a_p1\nb_p2\na_p1\n")

    assert evaluate.read_page_ids(listing) == ["a_p1", "b_p2"]
