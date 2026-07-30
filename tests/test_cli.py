"""Die CLI ist der einzige Einstieg in die Pipeline – sie muss vollständig
und aufrufbar sein. Fehlt ein Modul, fällt das sonst erst beim Ausführen auf.
"""

import importlib

import pytest

from magda import cli, jobs


def test_jeder_befehl_hat_ein_modul_mit_main():
    for name, befehl in cli.BEFEHLE.items():
        modul = importlib.import_module(f"magda.cli.{befehl.modul}")
        assert callable(modul.main), f"{name}: kein main()"


def test_jeder_startbare_job_ist_ein_cli_befehl():
    """jobs.py baut `python -m magda <job>` – ein Job ohne Befehl liefe ins Leere."""
    assert set(jobs.JOBS) <= set(cli.BEFEHLE)


def test_hilfe_nennt_jeden_befehl():
    text = cli._hilfe()

    for name in cli.BEFEHLE:
        assert name in text


def test_unbekannter_befehl_endet_mit_fehlercode(capsys):
    assert cli.main(["rm-rf"]) == 2
    assert "Unbekannter Befehl" in capsys.readouterr().err


def test_ohne_argumente_kommt_die_uebersicht(capsys):
    assert cli.main([]) == 0
    assert "Pipeline" in capsys.readouterr().out


def test_hilfe_laedt_keine_schweren_module():
    """`magda --help` darf torch nicht importieren – sonst dauert eine Liste
    zehn Sekunden. Der Dispatcher importiert erst beim konkreten Aufruf."""
    import sys

    for modul in ("torch", "transformers"):
        sys.modules.pop(modul, None)
    cli.main(["--help"])

    assert "torch" not in sys.modules


@pytest.mark.parametrize("befehl", sorted(cli.BEFEHLE))
def test_jeder_befehl_beantwortet_help(befehl, capsys):
    """--help darf nichts ausführen. `extract` hat das früher getan: ohne
    eigenen Parser lief die Extraktion los, statt die Optionen zu zeigen."""
    with pytest.raises(SystemExit) as beendet:
        cli.main([befehl, "--help"])

    assert beendet.value.code == 0
    assert capsys.readouterr().out.startswith(f"usage: magda {befehl}")
