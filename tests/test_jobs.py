"""Der Job-Katalog ist die Sicherheitsgrenze zwischen Frontend und Subprozess."""


import pytest

from magda import config, jobs


def test_build_command_setzt_positional_und_option():
    cmd = jobs.build_command("download", {"url": "https://x/?catalogId=1", "max_pages": 5})

    assert cmd[0].endswith("python")
    assert cmd[1:5] == ["-u", "-m", "magda", "download"]
    assert cmd[5:] == ["https://x/?catalogId=1", "--max-pages", "5"]


def test_build_command_laesst_optionale_parameter_weg():
    cmd = jobs.build_command("download", {"url": "https://x/?catalogId=1"})

    assert "--max-pages" not in cmd


def test_build_command_kennt_alle_pipeline_schritte():
    assert set(jobs.JOBS) == {
        "harvest", "download", "extract", "label",
        "train", "eval", "dedupe", "flair",
        "gold", "agreement", "extract-pdf",
    }


def test_freie_modellnamen_duerfen_keine_optionen_sein():
    """09_agreement nimmt Modellnamen als Freitext, weil die Ordner zur
    Laufzeit entstehen. Dann muss der Bindestrich-Schutz greifen – sonst
    liest argparse "--help" als Option und der Lauf tut etwas anderes."""
    with pytest.raises(ValueError, match="Bindestrich"):
        jobs.build_command("agreement", {"model_a": "--help", "model_b": "x"})


def test_build_command_lehnt_unbekannten_job_ab():
    with pytest.raises(ValueError, match="Unbekannter Schritt"):
        jobs.build_command("rm -rf /", {})


def test_build_command_lehnt_unbekannten_parameter_ab():
    with pytest.raises(ValueError, match="Unbekannter Parameter"):
        jobs.build_command("extract", {"outfile": "/etc/passwd"})


def test_build_command_lehnt_wert_ausserhalb_choices_ab():
    with pytest.raises(ValueError, match="bash"):
        jobs.build_command("train", {"variant": "bash"})


def test_build_command_lehnt_falschen_typ_ab():
    with pytest.raises(ValueError, match="Zahl"):
        jobs.build_command("download", {"url": "https://x", "max_pages": "viele"})


def test_build_command_verlangt_pflichtparameter():
    with pytest.raises(ValueError, match="URL"):
        jobs.build_command("download", {})


def test_build_command_lehnt_positional_mit_bindestrich_ab():
    """argparse liest "--help" als Option, nicht als URL – der Lauf täte etwas
    anderes als der Nutzer meint."""
    with pytest.raises(ValueError, match="Bindestrich"):
        jobs.build_command("download", {"url": "--help"})


def test_leerer_wert_zaehlt_wie_nicht_gesetzt():
    """Ein leeres Formularfeld ist keine Eingabe – sonst landet "" im argv."""
    cmd = jobs.build_command("download", {"url": "https://x", "max_pages": ""})

    assert "--max-pages" not in cmd


def test_describe_liefert_json_faehigen_katalog():
    entry = next(j for j in jobs.describe() if j["job"] == "train")

    assert entry["title"]
    variant = next(p for p in entry["params"] if p["key"] == "variant")
    # Gegen die Registry, nicht gegen ein Literal: sonst muss dieser Test bei
    # jedem neuen Arm nachgezogen werden und schuetzt dabei nichts - er wuerde
    # nur festhalten, wie viele Arme es zufaellig gab, als er geschrieben wurde.
    assert variant["choices"] == list(config.VARIANTS)
    assert variant["required"] is True
    epochs = next(p for p in entry["params"] if p["key"] == "epochs")
    assert epochs["default"] == 10
    assert epochs["kind"] == "int"


def test_flag_wird_ohne_wert_gesetzt():
    cmd = jobs.build_command("dedupe", {"apply": True})

    assert cmd[-1] == "--apply"


def test_flag_bleibt_ohne_zustimmung_weg():
    """Ein nicht gesetzter Schalter darf nichts loeschen."""
    cmd = jobs.build_command("dedupe", {"apply": False, "threshold": 0.9})

    assert "--apply" not in cmd
    assert cmd[-2:] == ["--threshold", "0.9"]


# ---------------------------------------------------------------------------
# extract-pdf: upload_id wird nie zu einem freien Pfad
# ---------------------------------------------------------------------------

_UPLOAD_ID = "0123456789abcdef0123456789abcdef"[:32]


def test_extract_pdf_loest_upload_id_zu_einem_pfad_unter_uploads_dir_auf():
    cmd = jobs.build_command("extract-pdf", {"upload_id": _UPLOAD_ID})

    pdf_arg = cmd[cmd.index("extract-pdf") + 1]
    assert pdf_arg == str(config.UPLOADS_DIR / f"{_UPLOAD_ID}.pdf")
    assert "--out" in cmd
    assert cmd[cmd.index("--out") + 1] == str(config.UPLOADS_DIR / f"{_UPLOAD_ID}.json")
    assert "--images-dir" in cmd
    assert cmd[cmd.index("--images-dir") + 1] == str(config.UPLOADS_DIR / _UPLOAD_ID)
    assert "--render-images" in cmd
    assert "--no-embed-images" in cmd


def test_extract_pdf_lehnt_pfadtrenner_in_der_upload_id_ab():
    with pytest.raises(ValueError, match="Format"):
        jobs.build_command("extract-pdf", {"upload_id": "abc/def"})


def test_extract_pdf_lehnt_doppelpunkt_hoch_in_der_upload_id_ab():
    with pytest.raises(ValueError, match="Format"):
        jobs.build_command("extract-pdf", {"upload_id": "../../etc/passwd"})


def test_extract_pdf_lehnt_zu_kurze_oder_zu_lange_id_ab():
    with pytest.raises(ValueError, match="Format"):
        jobs.build_command("extract-pdf", {"upload_id": "abc"})
    with pytest.raises(ValueError, match="Format"):
        jobs.build_command("extract-pdf", {"upload_id": _UPLOAD_ID + "ff"})


def test_extract_pdf_lehnt_grossbuchstaben_ab():
    """secrets.token_hex liefert immer Kleinbuchstaben - eine Grossschreibung
    ist keine gueltige eigene Ausgabe und deshalb ebenso verdaechtig."""
    with pytest.raises(ValueError, match="Format"):
        jobs.build_command("extract-pdf", {"upload_id": _UPLOAD_ID.upper()})


def test_extract_pdf_uebernimmt_die_variante():
    cmd = jobs.build_command("extract-pdf", {"upload_id": _UPLOAD_ID, "variant": "layoutxlm"})

    assert "--variant" in cmd
    assert cmd[cmd.index("--variant") + 1] == "layoutxlm"
