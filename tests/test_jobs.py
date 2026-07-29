"""Der Job-Katalog ist die Sicherheitsgrenze zwischen Frontend und Subprozess."""


import pytest

from magda import jobs


def test_build_command_setzt_positional_und_option():
    cmd = jobs.build_command("01_download_flyers", {"url": "https://x/?catalogId=1", "max_pages": 5})

    assert cmd[0].endswith("python")
    assert cmd[1] == "-u"
    assert cmd[2].endswith("scripts/01_download_flyers.py")
    assert cmd[3:] == ["https://x/?catalogId=1", "--max-pages", "5"]


def test_build_command_laesst_optionale_parameter_weg():
    cmd = jobs.build_command("01_download_flyers", {"url": "https://x/?catalogId=1"})

    assert "--max-pages" not in cmd


def test_build_command_kennt_alle_pipeline_schritte():
    assert set(jobs.JOBS) == {
        "01_download_flyers", "02_extract_words", "03_label_words",
        "04_train", "05_evaluate", "06_check_duplicates", "07_flair_baseline",
    }


def test_build_command_lehnt_unbekannten_job_ab():
    with pytest.raises(ValueError, match="Unbekannter Schritt"):
        jobs.build_command("rm -rf /", {})


def test_build_command_lehnt_unbekannten_parameter_ab():
    with pytest.raises(ValueError, match="Unbekannter Parameter"):
        jobs.build_command("02_extract_words", {"outfile": "/etc/passwd"})


def test_build_command_lehnt_wert_ausserhalb_choices_ab():
    with pytest.raises(ValueError, match="bash"):
        jobs.build_command("04_train", {"variant": "bash"})


def test_build_command_lehnt_falschen_typ_ab():
    with pytest.raises(ValueError, match="Zahl"):
        jobs.build_command("01_download_flyers", {"url": "https://x", "max_pages": "viele"})


def test_build_command_verlangt_pflichtparameter():
    with pytest.raises(ValueError, match="URL"):
        jobs.build_command("01_download_flyers", {})


def test_build_command_lehnt_positional_mit_bindestrich_ab():
    """argparse liest "--help" als Option, nicht als URL – der Lauf täte etwas
    anderes als der Nutzer meint."""
    with pytest.raises(ValueError, match="Bindestrich"):
        jobs.build_command("01_download_flyers", {"url": "--help"})


def test_leerer_wert_zaehlt_wie_nicht_gesetzt():
    """Ein leeres Formularfeld ist keine Eingabe – sonst landet "" im argv."""
    cmd = jobs.build_command("01_download_flyers", {"url": "https://x", "max_pages": ""})

    assert "--max-pages" not in cmd


def test_describe_liefert_json_faehigen_katalog():
    entry = next(j for j in jobs.describe() if j["job"] == "04_train")

    assert entry["title"]
    variant = next(p for p in entry["params"] if p["key"] == "variant")
    assert variant["choices"] == ["gbert", "layoutxlm"]
    assert variant["required"] is True
    epochs = next(p for p in entry["params"] if p["key"] == "epochs")
    assert epochs["default"] == 10
    assert epochs["kind"] == "int"


def test_flag_wird_ohne_wert_gesetzt():
    cmd = jobs.build_command("06_check_duplicates", {"apply": True})

    assert cmd[-1] == "--apply"


def test_flag_bleibt_ohne_zustimmung_weg():
    """Ein nicht gesetzter Schalter darf nichts loeschen."""
    cmd = jobs.build_command("06_check_duplicates", {"apply": False, "threshold": 0.9})

    assert "--apply" not in cmd
    assert cmd[-2:] == ["--threshold", "0.9"]
