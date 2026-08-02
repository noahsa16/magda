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
