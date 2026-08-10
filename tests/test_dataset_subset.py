"""Trainingsteilmengen fuer die Lernkurve - ganze Duplikat-Cluster.

Seitenweise gezogen zaehlen elf Regionalfassungen derselben Vorlage als elf
Datenpunkte. Die Kurve saehe dann steiler aus, als sie ist - derselbe
Fehler, der schon den Seiten-Split lecken liess.
"""

from magda import dataset
from magda.cli import train


def _page(page_id, texts):
    return {"page_id": page_id,
            "words": [{"text": t, "bbox": [0, 0, 1, 1]} for t in texts]}


# ------------------------------------------------------ clusterweise ziehen


def test_es_werden_ganze_cluster_gezogen():
    zwillinge = ["Butter", "Milch", "Kaese", "Brot"]
    pages = [_page("a", zwillinge), _page("b", zwillinge),
             _page("c", ["Wein", "Bier", "Saft", "Wasser"])]

    chosen = dataset.subset_by_clusters(pages, limit=2)

    # a und b sind ein Cluster - entweder beide oder keiner.
    assert set(chosen) in ({"a", "b"}, {"c"})


def test_die_grenze_wird_nicht_ueberschritten():
    pages = [_page(str(i), [f"w{i}", "x", "y", "z"]) for i in range(5)]

    assert len(dataset.subset_by_clusters(pages, limit=3)) <= 3


def test_dieselbe_grenze_ergibt_dieselbe_teilmenge():
    """Sonst ist die Lernkurve zwischen zwei Laeufen nicht vergleichbar."""
    pages = [_page(str(i), [f"w{i}", "x", "y", "z"]) for i in range(8)]

    assert dataset.subset_by_clusters(pages, 4) == dataset.subset_by_clusters(pages, 4)


def test_eine_groessere_grenze_nimmt_nichts_weg():
    """Die Kurvenpunkte muessen ineinanderliegen, sonst misst jeder Punkt
    eine andere Stichprobe statt mehr von derselben.

    Bewusst mit *ungleich grossen* Clustern (3/2/1): bei lauter Einzelseiten
    waere die Eigenschaft geschenkt. Gieriges Auffuellen naehme zu 4 die
    Cluster 3+1 und zu 5 die Cluster 3+2 - und liesse die Einzelseite wieder
    fallen.
    """
    drei = ["Butter", "Milch", "Kaese", "Brot"]
    zwei = ["Wein", "Bier", "Saft", "Wasser"]
    pages = ([_page(f"a{i}", drei) for i in range(3)]
             + [_page(f"b{i}", zwei) for i in range(2)]
             + [_page("c0", ["Seife", "Buerste", "Lappen", "Eimer"])])

    stufen = [set(dataset.subset_by_clusters(pages, n)) for n in (3, 4, 5, 6)]

    for kleiner, groesser in zip(stufen, stufen[1:]):
        assert kleiner <= groesser


def test_eine_grenze_unter_dem_groessten_cluster_bricht_ab():
    """Sonst traineirte der Kurvenpunkt ueber null Seiten und lieferte
    trotzdem eine Zahl."""
    import pytest

    zwillinge = ["Butter", "Milch", "Kaese", "Brot"]
    pages = [_page(f"a{i}", zwillinge) for i in range(4)]

    with pytest.raises(ValueError, match="Duplikat-Cluster"):
        dataset.subset_by_clusters(pages, limit=3)


def test_eine_grenze_ueber_dem_bestand_liefert_alles():
    pages = [_page(str(i), [f"w{i}", "x", "y", "z"]) for i in range(4)]

    assert len(dataset.subset_by_clusters(pages, 99)) == 4


# ------------------------------------------ Checkpoints kollidieren nicht


def test_der_normale_lauf_schreibt_weiter_nach_checkpoints_variant():
    """Der eingefrorene KW30/31-Checkpoint liegt dort. Wer den Pfad aendert,
    macht alle bisherigen Zahlen unreproduzierbar."""
    assert train.checkpoint_name("gbert", labels_from=None, train_pages=None) == "gbert"


def test_eine_andere_labelquelle_bekommt_einen_eigenen_ordner():
    """Sonst ueberschreibt der APP_PRICE-Lauf das Modell, gegen das er
    verglichen werden soll - und der Vergleich misst sich selbst."""
    name = train.checkpoint_name("gbert", labels_from="sonnet-5-app", train_pages=None)

    assert name != "gbert"
    assert "sonnet-5-app" in name


def test_die_labelquelle_des_defaults_bekommt_keinen_eigenen_ordner():
    """`--labels-from sonnet-5` ist genau der bestehende Lauf."""
    assert train.checkpoint_name("gbert", labels_from="sonnet-5",
                                 train_pages=None) == "gbert"


def test_jeder_kurvenpunkt_bekommt_einen_eigenen_ordner():
    """Vier Laeufe nebeneinander - sonst ueberschreibt der naechste den
    vorigen und die Kurve hat einen Punkt."""
    namen = {train.checkpoint_name("gbert", None, n) for n in (25, 50, 100, 175)}

    assert len(namen) == 4
    assert "gbert" not in namen


def test_ein_boesartiger_labelordner_bleibt_ein_pfadbestandteil():
    """Der Name kommt aus einer Nutzereingabe - derselbe Grund wie bei
    `config.model_slug` fuer data/labeled/. Gefordert ist nicht ein huebscher
    Name, sondern dass `CHECKPOINTS_DIR / name` unter CHECKPOINTS_DIR bleibt.
    """
    from pathlib import Path

    from magda.config import CHECKPOINTS_DIR

    name = train.checkpoint_name("gbert", labels_from="../../gold", train_pages=None)
    ziel = (CHECKPOINTS_DIR / name).resolve()

    assert len(Path(name).parts) == 1
    assert ziel.parent == CHECKPOINTS_DIR.resolve()


def test_der_kanonische_anker_ist_sonnet_nicht_das_env_modell():
    """`default_labeled_model()` folgt CHAT_AI_VISION_MODEL und zeigt auf
    mistral - mit dem hier gar nicht gelabelt wird. Waere er der Anker,
    bekaeme der Inhalt einer .env Namensgewalt ueber Checkpoints, an denen
    berichtete Zahlen haengen."""
    from magda import config

    assert config.CANONICAL_LABELS == "sonnet-5"
    assert train.checkpoint_name("gbert", config.CANONICAL_LABELS, None) == "gbert"
