"""Bei 100 Testseiten in nur 43 Clustern entscheidet die Wahl der
Resampling-Einheit über die Breite des Intervalls – und damit darüber, ob ein
berichteter Unterschied zwischen zwei Modellen trägt."""

from magda.significance import (
    bootstrap_f1,
    counts_per_page,
    f1,
    paired_bootstrap,
)

# Zwei Seiten, je ein Entity.
REF = [["B-PRICE", "O"], ["B-PRODUCT", "I-PRODUCT"]]


def test_zaehlt_entities_nicht_token():
    """seqeval-Logik: Span UND Typ müssen exakt stimmen."""
    perfekt = counts_per_page(REF, REF)
    assert perfekt == [(1, 0, 0), (1, 0, 0)]

    # Richtiger Typ, falscher Span -> kein Treffer, sondern FP und FN.
    zu_kurz = counts_per_page(REF, [["B-PRICE", "O"], ["B-PRODUCT", "O"]])
    assert zu_kurz[1] == (0, 1, 1)


def test_f1_randfaelle():
    assert f1(0, 5, 5) == 0.0
    assert f1(2, 0, 0) == 1.0


def test_intervall_umschliesst_den_punktschaetzer():
    clusters = [[0], [1]]

    ergebnis = bootstrap_f1(REF, REF, clusters, resamples=500)

    assert ergebnis["f1"] == 1.0
    assert ergebnis["ci95"][0] <= 1.0 <= ergebnis["ci95"][1]
    assert ergebnis["clusters"] == 2


def test_cluster_statt_seiten_verbreitert_das_intervall():
    """Der Kern der Sache: 11 Kopien einer Vorlage sind eine Beobachtung, nicht elf.

    Dieselben Daten, einmal als 12 unabhängige Seiten gezählt und einmal als
    2 Cluster. Die Clusterung darf das Intervall nicht enger machen.
    """
    # Elf identische Seiten mit Treffer, eine mit Fehlschlag.
    reference = [["B-PRICE"]] * 11 + [["B-PRODUCT"]]
    predicted = [["B-PRICE"]] * 11 + [["O"]]

    als_seiten = bootstrap_f1(reference, predicted, [[i] for i in range(12)], resamples=2000)
    als_cluster = bootstrap_f1(reference, predicted, [list(range(11)), [11]], resamples=2000)

    breite_seiten = als_seiten["ci95"][1] - als_seiten["ci95"][0]
    breite_cluster = als_cluster["ci95"][1] - als_cluster["ci95"][0]
    assert breite_cluster > breite_seiten


def test_gepaarter_vergleich_erkennt_gleichstand():
    """Zwei identische Modelle: Differenz 0, Intervall über der Null."""
    ergebnis = paired_bootstrap(REF, REF, REF, [[0], [1]], resamples=500)

    assert ergebnis["difference"] == 0.0
    assert ergebnis["significant"] is False


def test_gepaarter_vergleich_erkennt_klaren_unterschied():
    reference = [["B-PRICE"] for _ in range(30)]
    gut = [["B-PRICE"] for _ in range(30)]
    schlecht = [["O"] for _ in range(30)]

    ergebnis = paired_bootstrap(reference, gut, schlecht, [[i] for i in range(30)],
                                resamples=2000)

    assert ergebnis["difference"] == 1.0
    assert ergebnis["significant"] is True


def test_beide_modelle_sehen_dieselben_cluster():
    """Ungepaart verglichen verschwände ein kleiner, aber konsistenter Vorsprung.

    Modell A ist auf jeder Seite genau eine Entity besser. Die Seiten selbst
    streuen stark – ungepaart würde diese Streuung den Unterschied überdecken.
    """
    reference = [["B-PRICE", "B-PRODUCT"] if i % 2 else ["B-PRICE"] for i in range(20)]
    a = [list(tags) for tags in reference]
    b = [["O"] + list(tags[1:]) for tags in reference]

    ergebnis = paired_bootstrap(reference, a, b, [[i] for i in range(20)], resamples=2000)

    assert ergebnis["difference"] > 0
    assert ergebnis["significant"] is True


def test_bricht_ab_wenn_wortlisten_fehlen(tmp_path, monkeypatch):
    """Ohne data/words darf nicht heimlich ein einziger Cluster entstehen.

    Genau das passierte auf dem Trainings-Pod: das Bundle enthält data/words
    nicht, der alte Fallback warf alle 100 Seiten in einen Cluster, und der
    Bericht wies ein Intervall der Breite null mit p = 0.0 aus.
    """
    import pytest
    from magda.cli import significance as cli

    monkeypatch.setattr(cli, "WORDS_DIR", tmp_path)
    with pytest.raises(SystemExit) as abbruch:
        cli.test_clusters(["a_p1", "a_p2"])
    assert "Wortlisten fehlen" in str(abbruch.value)


def test_vergleicht_nur_seiten_aus_dem_testsplit():
    """Zwei Vorhersageordner koennen Seiten aus frueheren Splits enthalten.

    Belegter Fall (25.08.2026): nach dem Wochen-Split auf KW35 lagen in
    `data/predictions/gbert` noch 101 KW32-Seiten des Vorlaufs und in
    `layoutxlm` 100. Die blosse Schnittmenge beider Ordner war damit 216
    statt 116 Seiten - und 100 davon sind seit dem neuen Split
    *Trainingsdaten*. Gemessen worden waere zur Haelfte Auswendiggelerntes,
    ohne dass eine Zeile Ausgabe darauf hingewiesen haette.
    """
    from magda.cli.significance import shared_test_pages

    a = {"kw35_p1": [], "kw35_p2": [], "kw32_alt": []}
    b = {"kw35_p1": [], "kw35_p2": [], "kw32_alt": [], "nur_in_b": []}

    genommen, verworfen = shared_test_pages(a, b, {"kw35_p1", "kw35_p2"})

    assert genommen == ["kw35_p1", "kw35_p2"]
    assert verworfen == 1


def test_meldet_wenn_gar_keine_testseite_uebrig_bleibt():
    """Sonst rechnet der Bootstrap ueber eine leere Liste weiter."""
    from magda.cli.significance import shared_test_pages

    genommen, verworfen = shared_test_pages({"alt": []}, {"alt": []}, {"neu"})

    assert genommen == []
    assert verworfen == 1
