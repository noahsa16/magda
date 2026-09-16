"""Unsicherheit darf sich nicht durch Duplikate oder fehlende Seiten verengen."""

import pytest

from magda.resampling import compare_counts


def test_micro_f1_wird_aus_zaehlern_statt_seitenmittel_berechnet():
    result = compare_counts({"a": [(10, 10, 10), (0, 1, 1)]}, [[0], [1]])
    assert result["systems"]["a"]["f1"] == pytest.approx(10 / 11)
    assert result["systems"]["a"]["ci95"] == [0, 1]


def test_gepaarte_identische_systeme_haben_exakt_nulldifferenz():
    counts = [(5, 8, 10), (2, 3, 4), (9, 10, 10)]
    result = compare_counts({"a": counts, "b": counts}, [[0, 1], [2]], [("a", "b")])
    assert result["comparisons"][0]["ci95"] == [0, 0]
    assert result["comparisons"][0]["ci_familywise"] == [0, 0]


def test_ein_cluster_liefert_kein_scheinpraezises_intervall():
    result = compare_counts({"a": [(1, 2, 2), (1, 2, 2)]}, [[0, 1]])
    assert result["systems"]["a"]["ci95"] is None


@pytest.mark.parametrize("clusters", [[[0]], [[0], [0, 1]], [[0], []], [[0], [2]]])
def test_unvollstaendige_oder_doppelte_cluster_werden_abgelehnt(clusters):
    with pytest.raises(ValueError, match="Cluster"):
        compare_counts({"a": [(1, 1, 1), (1, 1, 1)]}, clusters)


def test_leere_gesamtreferenz_ist_undefiniert():
    result = compare_counts({"a": [(0, 0, 0), (0, 0, 0)]}, [[0], [1]], resamples=100)
    assert result["systems"]["a"]["f1"] is None
    assert result["systems"]["a"]["undefined_resamples"] == 100


def test_bonferroni_intervall_ist_mindestens_so_breit():
    result = compare_counts({"a": [(1, 2, 3), (3, 4, 4), (1, 4, 8)],
                             "b": [(1, 3, 3), (2, 4, 4), (2, 4, 8)],
                             "c": [(0, 3, 3), (1, 4, 4), (1, 4, 8)]},
                            [[0], [1], [2]], [("a", "b"), ("a", "c")])
    for comparison in result["comparisons"]:
        assert comparison["ci_familywise"][0] <= comparison["ci95"][0]
        assert comparison["ci_familywise"][1] >= comparison["ci95"][1]
