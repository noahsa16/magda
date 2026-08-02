"""Der Wochen-Split ist die Antwort auf ein gemessenes Datenleck – er muss
Wochen wirklich trennen, sonst ist er nur eine andere Art zu würfeln."""

import pytest

from magda.dataset import group_by_week, split_by_week

# Zwei Erscheinungswochen: innerhalb dicht beieinander, dazwischen eine Lücke
# von mehreren tausend – so sehen Pennys Katalog-IDs tatsächlich aus.
ALT = [f"13428{n:02d}_p{s}" for n in (12, 15, 21) for s in (1, 2)]
NEU = [f"13473{n:02d}_p{s}" for n in (75, 78, 87) for s in (1, 2, 3)]


def test_erkennt_zwei_wochen():
    wochen = group_by_week(ALT + NEU)

    assert len(wochen) == 2
    assert set(wochen[0]) == set(ALT)
    assert set(wochen[1]) == set(NEU)


def test_dichte_ids_bleiben_eine_woche():
    assert len(group_by_week(ALT)) == 1


def test_juengste_woche_wird_test():
    splits = split_by_week(ALT + NEU)

    assert set(splits["test"]) == set(NEU)
    assert set(splits["train"]) | set(splits["dev"]) == set(ALT)


def test_dev_kommt_nicht_aus_der_testwoche():
    """Sonst wählt die Modellauswahl auf den Daten aus, auf denen gemessen wird."""
    splits = split_by_week(ALT + NEU)

    assert not set(splits["dev"]) & set(splits["test"])


def test_keine_seite_geht_verloren_oder_doppelt():
    alle = ALT + NEU
    splits = split_by_week(alle)

    vergeben = splits["train"] + splits["dev"] + splits["test"]
    assert sorted(vergeben) == sorted(alle)


def test_eine_einzige_woche_ist_kein_split():
    with pytest.raises(ValueError, match="zwei Erscheinungswochen"):
        split_by_week(ALT)


def test_ist_deterministisch():
    assert split_by_week(ALT + NEU) == split_by_week(ALT + NEU)


def _jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b)


def test_dev_reisst_keine_zwillinge_aus_dem_training():
    """Zwei Regionalfassungen derselben Seite gehören auf dieselbe Seite des Splits.

    Zufällig je Seite gezogen lag Dev über echten Daten bei Median-Ähnlichkeit
    0.721 zum Training – die Modellauswahl bewertete damit teils Auswendiggelerntes.
    """
    alt = [f"1342812_p{i}" for i in range(1, 21)]
    neu = [f"1347375_p{i}" for i in range(1, 6)]
    # Je zwei aufeinanderfolgende Altseiten teilen 20 von 22 Wörtern (0.909).
    worte = {pid: [f"w{i // 2}_{k}" for k in range(20)] + [f"einzel{i}"]
             for i, pid in enumerate(alt)}
    worte.update({pid: [f"{pid}_{k}" for k in range(20)] for pid in neu})

    splits = split_by_week(alt + neu, dev_share=0.2, pages=worte)

    assert splits["dev"], "Dev darf nicht leer sein"
    for d in splits["dev"]:
        for t in splits["train"]:
            assert _jaccard(worte[d], worte[t]) < 0.7, f"{d} hat Zwilling {t} im Training"


def test_seiten_ohne_wortliste_brechen_den_split_nicht():
    """data/words kann fehlen – dann ist eben jede Seite ihr eigener Cluster."""
    splits = split_by_week(ALT + NEU, pages={})

    assert sorted(splits["train"] + splits["dev"] + splits["test"]) == sorted(ALT + NEU)
    assert splits["dev"]


def test_fehlender_split_wird_nicht_mehr_gewuerfelt(tmp_path, monkeypatch):
    """Der Zufallssplit war der leckende – er darf nicht durch eine fehlende Datei entstehen.

    Auf einer frischen GPU-Instanz oder bei einem Teammitglied ohne die Datei
    entstand er kommentarlos, und seine Zahlen sehen besser aus als die des
    korrekten Wochen-Splits. Ein Fehlschlag ist die einzige sichere Antwort.
    """
    from magda import dataset

    monkeypatch.setattr(dataset, "SPLITS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError, match="magda split"):
        dataset.get_or_create_splits([{"page_id": "1_p1"}])
