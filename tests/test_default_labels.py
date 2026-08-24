"""Welche Labels nimmt ein Schritt ohne `--labels-from`?

Die Antwort war `CHAT_AI_VISION_MODEL`, also `mistral-medium-3.5-128b` -
und damit ein Modell, mit dem im Projekt gar nicht gelabelt wird. Gemessen,
was das kostet: `magda offers-verify` fand mit Mistral-Labels 399 Preise und
kam auf Genauigkeit 0.927 bei Abdeckung 0.446; mit sonnet-5 sind es 494
Preise, 0.936 und 0.478. Dieselbe Gruppierung, dieselbe Rechnung, ein
Viertel mehr Preise - die Zahl beantwortete leise eine andere Frage.
"""

from magda import config


def test_die_kanonische_quelle_gewinnt_vor_dem_env_modell(monkeypatch):
    """Sonst entscheidet der Inhalt einer .env, woran gemessen wird."""
    monkeypatch.setattr(config, "labeled_models",
                        lambda: {"sonnet-5", "mistral-medium-3.5-128b"})
    monkeypatch.setattr(config, "CHAT_AI_VISION_MODEL", "mistral-medium-3.5-128b")

    assert config.default_labeled_model() == "sonnet-5"


def test_ohne_die_kanonische_quelle_gilt_weiter_das_env_modell(monkeypatch):
    """Wer bewusst mit einem anderen Modell labelt, soll dessen Labels
    bekommen - der Vorrang gilt nur, wenn sonnet-5 tatsaechlich vorliegt."""
    monkeypatch.setattr(config, "labeled_models",
                        lambda: {"mistral-medium-3.5-128b", "qwen3.5-397b-a17b"})
    monkeypatch.setattr(config, "CHAT_AI_VISION_MODEL", "mistral-medium-3.5-128b")

    assert config.default_labeled_model() == "mistral-medium-3.5-128b"


def test_ohne_jede_labelquelle_kommt_nichts(monkeypatch):
    monkeypatch.setattr(config, "labeled_models", lambda: set())

    assert config.default_labeled_model() is None


def test_der_korrigierte_ordner_verdraengt_die_referenz_nicht(monkeypatch):
    """`sonnet-5-app` ist gleich gross wie `sonnet-5` und darf trotzdem nicht
    gewinnen: gegen `sonnet-5` wurden alle bisherigen Zahlen gemessen. Ueber
    die Groesse allein entschiede hier die Sortierreihenfolge."""
    monkeypatch.setattr(config, "labeled_models",
                        lambda: {"sonnet-5", "sonnet-5-app"})
    monkeypatch.setattr(config, "CHAT_AI_VISION_MODEL", "gibtsnicht")

    assert config.default_labeled_model() == "sonnet-5"


def test_im_echten_repo_ist_die_voreinstellung_sonnet():
    """Der Fall, der die Messungen verschoben hat - ohne Monkeypatch."""
    if "sonnet-5" not in config.labeled_models():
        return
    assert config.default_labeled_model() == "sonnet-5"
