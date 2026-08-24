"""Das 2x2-Gitter - Merkmalsbloecke einzeln messen.

Die Aufschluesselung nach blindem Fleck ist die eigentliche Kennzahl des
Vorhabens: Farbmerkmale sind fuer den Bereich gebaut, in dem die Arithmetik
schweigt. Eine Gesamtzahl kann steigen, weil das Modell in der ohnehin
prueffbaren Haelfte besser wird - deshalb wird getrennt ausgewiesen.
"""

import pytest

from magda import offer_grid


def _page(tags, texts=None):
    """Vier Entities untereinander, je ein Wort."""
    texts = texts or ["Butter", "1.29", "Milch", "0.99"]
    boxes = [[10, 10 + 30 * i, 60, 20 + 30 * i] for i in range(len(tags))]
    return {
        "page_id": "p1",
        "width": 100,
        "height": 200,
        "words": [{"text": t, "bbox": b} for t, b in zip(texts, boxes)],
        "tags": tags,
    }


MIT_GRUNDPREIS = ["B-PRODUCT", "B-PRICE", "B-UNIT_PRICE", "B-PRODUCT"]
OHNE_GRUNDPREIS = ["B-PRODUCT", "B-PRICE", "B-PRODUCT", "B-PRICE"]


# ------------------------------------------------------------- Bewertung


def test_eine_perfekte_gruppierung_trifft_alles():
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 1, 3: 1}

    counts = offer_grid.judge_page(page, assignment, [[0, 1], [2, 3]])

    assert counts.total.pair_f1 == pytest.approx(1.0)
    assert counts.total.group_f1 == pytest.approx(1.0)
    assert counts.total.exact_groups == 2


def test_alles_in_eine_gruppe_zu_werfen_trifft_keine_gruppe_genau():
    """Gruppen-F1 zaehlt nur exakte Treffer - "die Zeile stimmt"."""
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 1, 3: 1}

    counts = offer_grid.judge_page(page, assignment, [[0, 1, 2, 3]])

    assert counts.total.exact_groups == 0
    assert counts.total.group_f1 == pytest.approx(0.0)
    # Paarweise bleibt trotzdem etwas uebrig: die beiden echten Paare
    # stecken in der grossen Gruppe mit drin.
    assert counts.total.shared_pairs == 2


def test_entities_ausserhalb_der_referenz_bewegen_keine_zahl():
    """Wo der Mensch geschwiegen hat, ist kein Negativbeleg."""
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0}          # die zweite Haelfte fehlt

    counts = offer_grid.judge_page(page, assignment, [[0, 1], [2, 3]])

    assert counts.total.ref_groups == 1
    assert counts.total.ref_pairs == 1


# --------------------------------------------------------- Blinder Fleck


def test_ohne_grundpreis_gilt_das_paar_als_blind():
    """Ohne UNIT_PRICE in der Gruppe kann die Rechnung nicht urteilen."""
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 1, 3: 1}

    counts = offer_grid.judge_page(page, assignment, [[0, 1], [2, 3]])

    assert counts.blind.ref_pairs == 2
    assert counts.checkable.ref_pairs == 0


def test_mit_grundpreis_gilt_das_paar_als_pruefbar():
    page = _page(MIT_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 0, 3: 1}   # Grundpreis in Gruppe 0

    counts = offer_grid.judge_page(page, assignment, [[0, 1, 2], [3]])

    assert counts.checkable.ref_pairs == 3   # drei Paare in Gruppe 0
    assert counts.blind.ref_pairs == 0


def test_blind_und_pruefbar_ergeben_zusammen_das_ganze():
    """Sonst verschwaende eine Teilmenge unbemerkt aus der Auswertung."""
    page = _page(MIT_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 0, 3: 1}

    counts = offer_grid.judge_page(page, assignment, [[0, 1], [2], [3]])

    assert counts.blind.ref_pairs + counts.checkable.ref_pairs == counts.total.ref_pairs
    assert counts.blind.ref_groups + counts.checkable.ref_groups == counts.total.ref_groups


def test_blind_haengt_an_der_referenz_nicht_an_der_vorhersage():
    """Sonst haenge die Einteilung an dem System, das beurteilt werden soll.

    Dieselbe Referenz, zwei verschiedene Systemausgaben - die Zahl der
    blinden Referenzpaare darf sich nicht bewegen.
    """
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 1, 3: 1}

    gut = offer_grid.judge_page(page, assignment, [[0, 1], [2, 3]])
    schlecht = offer_grid.judge_page(page, assignment, [[0, 2], [1, 3]])

    assert gut.blind.ref_pairs == schlecht.blind.ref_pairs


# ------------------------------------------------------------- Bootstrap


def _counts(page_id, ref, sys, shared):
    page = offer_grid.PageCounts(page_id=page_id)
    for scope in (page.total, page.blind):
        scope.ref_pairs, scope.sys_pairs, scope.shared_pairs = ref, sys, shared
    return page


def test_bootstrap_resampelt_cluster_nicht_seiten():
    """Elf Regionalfassungen einer Vorlage sind eine Beobachtung, nicht elf.

    Ueber Seiten resampelt waere das Intervall zu eng - genau der Fehler,
    den `magda significance` fuer die Labelmetriken vermeidet.
    """
    per_page = [_counts("a", 10, 10, 10), _counts("b", 10, 10, 10),
                _counts("c", 10, 10, 0)]

    eng = offer_grid.bootstrap(per_page, [["a"], ["b"], ["c"]], rounds=200)
    weit = offer_grid.bootstrap(per_page, [["a", "b"], ["c"]], rounds=200)

    assert eng["clusters"] == 3
    assert weit["clusters"] == 2
    # Weniger unabhaengige Einheiten -> breiteres Intervall.
    assert (weit["high"] - weit["low"]) > (eng["high"] - eng["low"])


def test_bootstrap_braucht_mindestens_zwei_cluster():
    """Ein einziger Cluster ergibt ein Intervall der Breite null - also keines."""
    result = offer_grid.bootstrap([_counts("a", 10, 10, 10)], [["a"]], rounds=50)

    assert result["low"] is None


def test_bootstrap_ist_bei_gleichem_seed_reproduzierbar():
    per_page = [_counts("a", 10, 10, 9), _counts("b", 10, 10, 4)]
    clusters = [["a"], ["b"]]

    first = offer_grid.bootstrap(per_page, clusters, rounds=100, seed=7)
    second = offer_grid.bootstrap(per_page, clusters, rounds=100, seed=7)

    assert first == second


def test_alle_varianten_bauen_auf_denselben_grundmerkmalen_auf():
    """Ein Gitter vergleicht Zusaetze, keine verschiedenen Systeme."""
    from magda import offer_pairs

    basis = offer_pairs.feature_names(offer_grid.VARIANTS["basis"])
    for name, blocks in offer_grid.VARIANTS.items():
        assert offer_pairs.feature_names(blocks)[:len(basis)] == basis, name


def test_vorhersagen_und_gruppierung_treffen_sich_auf_dev():
    """Ohne Schnittmenge ist keine Ende-zu-Ende-Messung moeglich.

    Belegter Ausgangszustand (10.08.2026): 101 Vorhersagen, alle im
    Testsplit; 51 Gruppierungen, alle in Train/Dev; Schnittmenge null.
    Die Kette war gebaut, aber nie zusammengeschaltet.
    """
    import json
    from pathlib import Path

    from magda.cli.offers_model import SPLIT_FILE

    prediction_dir = Path("data/predictions/gbert")
    grouping_dir = Path("data/offer_groups/claude-sonnet-5")
    if not prediction_dir.is_dir() or not grouping_dir.is_dir():
        pytest.skip("Vorhersagen oder Gruppierung fehlen")

    split = json.loads(SPLIT_FILE.read_text())
    dev = set(split["dev"])
    predicted = {p.stem for p in prediction_dir.glob("*.json")} & dev
    grouped = {p.stem for p in grouping_dir.glob("*.json")} & dev

    assert predicted & grouped, (
        "Keine Dev-Seite hat Vorhersage und Gruppierung. "
        "`magda predict gbert --split dev --labels-from sonnet-5` laufen lassen."
    )


# ------------------------------------------------- Ende-zu-Ende-Verdrahtung


def _args(**overrides):
    import argparse

    base = {"labels_from": "sonnet-5", "predictions": None,
            "splits": "dev", "train_splits": "train", "train_labels_from": None}
    return argparse.Namespace(**{**base, **overrides})


def test_der_report_traegt_die_entity_quelle_im_namen():
    """Sonst ueberschreibt der Vorhersagelauf den Lehrerlauf still.

    Beide messen `dev`, beantworten aber verschiedene Fragen: der eine, wie
    gut gruppiert wird, wenn die Entities stimmen; der andere, was die ganze
    Kette leistet. Ein gemeinsamer Dateiname macht aus zwei Zahlen eine.
    """
    from magda.cli import offers_grid

    auf_labels = offers_grid.report_name(_args())
    auf_vorhersagen = offers_grid.report_name(_args(predictions="gbert"))

    assert auf_labels != auf_vorhersagen
    assert "dev" in auf_labels and "dev" in auf_vorhersagen


def test_ohne_eigene_trainingsquelle_erbt_das_training_die_messquelle():
    from magda.cli import offers_grid

    train = offers_grid.train_namespace(_args(predictions="gbert"))

    assert train.predictions == "gbert"
    assert train.splits == "train"


def test_eine_eigene_trainingsquelle_trennt_lehrer_von_schueler():
    """Der Einsatzfall: das Paarmodell lernt an Lehrer-Entities, weil nur die
    annotiert sind, und arbeitet zur Laufzeit auf denen des Schuelers.

    Ohne die Trennung traineirte das Gitter auf null Seiten - fuer den
    Trainingssplit existieren keine Vorhersagen.
    """
    from magda.cli import offers_grid

    train = offers_grid.train_namespace(
        _args(predictions="gbert", train_labels_from="sonnet-5"))

    assert train.predictions is None
    assert train.labels_from == "sonnet-5"
    assert train.splits == "train"


# ------------------------------------------------------- Kreuzvalidierung


def test_kreuzvalidierung_bewertet_jede_seite_genau_einmal():
    """Sonst zaehlte eine Seite mehrfach in Zaehler und Nenner.

    Der Zweck der Kreuzvalidierung ist, die Zahl der unabhaengigen
    Auswertungseinheiten zu erhoehen - eine doppelt gezaehlte Seite
    verengte das Intervall genau um den Betrag, den sie vortaeuscht.
    """
    from magda import offer_grid, offer_model

    pages = [_page(OHNE_GRUNDPREIS) for _ in range(6)]
    for index, page in enumerate(pages):
        page["page_id"] = f"p{index}"
        for word_index, word in enumerate(page["words"]):
            word["text"] = f"{word['text']}{index}"

    folds = offer_model.page_folds(pages, 3)
    verteilt = [page_id for fold in folds for page_id in fold]

    assert sorted(verteilt) == sorted(p["page_id"] for p in pages)
    assert len(verteilt) == len(set(verteilt))


def test_die_auswertungseinheiten_wachsen_ueber_dev_hinaus():
    """Der Grund fuer die Kreuzvalidierung, als Zahl.

    Dev hat 21 Seiten in 14 Duplikat-Clustern und ist vollstaendig
    gruppiert - mehr Trainingsreferenz macht das Intervall dort nicht
    schmaler. Ueber die ganze Referenz sind es deutlich mehr Cluster.
    """
    import json
    from pathlib import Path

    from magda import offer_grid
    from magda.cli.offers import _load_labeled_pages
    from magda.cli.offers_model import SPLIT_FILE

    grouping = Path("data/offer_groups/claude-sonnet-5")
    if not grouping.is_dir() or not SPLIT_FILE.is_file():
        pytest.skip("Gruppierungsreferenz oder Split fehlen")

    split = json.loads(SPLIT_FILE.read_text())
    grouped = {p.stem for p in grouping.glob("*.json")}
    pages = {p["page_id"]: p for p in _load_labeled_pages("sonnet-5")}

    dev = [pages[i] for i in grouped & set(split["dev"]) if i in pages]
    alle = [pages[i] for i in grouped if i in pages]

    assert len(offer_grid.clusters_of(alle)) > len(offer_grid.clusters_of(dev))


def test_gepaart_ist_das_intervall_der_differenz_enger_als_zwei_einzelne():
    """Der Grund, warum ueberlappende Einzelintervalle nichts beweisen.

    Beide Varianten sehen dieselben Seiten. Ist eine Seite schwer, ist sie
    es fuer beide - diese gemeinsame Streuung faellt beim gepaarten
    Resampling heraus. Hier gebaut: zwei Varianten, die sich auf jeder
    Seite um genau denselben Betrag unterscheiden, bei stark
    schwankendem Niveau. Die Differenz ist konstant, also muss ihr
    Intervall praktisch die Breite null haben - waehrend die Einzelwerte
    ueber den ganzen Bereich streuen.
    """
    from magda import offer_grid

    left, right = [], []
    for index, ref in enumerate([10, 10, 10, 10, 10, 10]):
        shared_left = 10 if index % 2 else 2      # mal leicht, mal schwer
        page_left = _counts(f"p{index}", ref, 10, shared_left)
        page_right = _counts(f"p{index}", ref, 10, shared_left - 1)
        left.append(page_left)
        right.append(page_right)
    clusters = [[f"p{i}"] for i in range(6)]

    einzeln = offer_grid.bootstrap(left, clusters, "total", "pair_f1", rounds=300)
    gepaart = offer_grid.paired_bootstrap(left, right, clusters, "total",
                                          "pair_f1", rounds=300)

    assert (gepaart["high"] - gepaart["low"]) < (einzeln["high"] - einzeln["low"])
    assert gepaart["difference"] > 0


def test_zwei_gleiche_varianten_ergeben_eine_differenz_um_null():
    from magda import offer_grid

    pages = [_counts(f"p{i}", 10, 10, 7) for i in range(5)]
    clusters = [[f"p{i}"] for i in range(5)]

    result = offer_grid.paired_bootstrap(pages, list(pages), clusters,
                                         "total", "pair_f1", rounds=200)

    assert result["difference"] == pytest.approx(0.0)
    assert result["p_two_sided"] == pytest.approx(1.0)


def test_der_report_traegt_auch_den_dekoder_im_namen():
    """Derselbe Grund wie bei der Entity-Quelle, nur eine Ebene tiefer.

    Ein ILP-Lauf und ein Union-Find-Lauf ueber dieselben Seiten sind zwei
    Messungen. Unter einem Dateinamen ueberschriebe der zweite den ersten -
    und genau die beiden nebeneinander sind der Vergleich.
    """
    from magda.cli import offers_grid

    union = offers_grid.report_name(_args(decoder="union"))
    ilp = offers_grid.report_name(_args(decoder="ilp"))

    assert union != ilp
    assert "ilp" in ilp


def test_ohne_dekoder_bleibt_der_alte_dateiname():
    """Sonst zeigen die Reports aus frueheren Laeufen ins Leere."""
    from magda.cli import offers_grid

    assert offers_grid.report_name(_args()) == "offers_grid_dev.json"
    assert offers_grid.report_name(_args(decoder="union")) == "offers_grid_dev.json"


def test_die_lernkurve_ueberschreibt_den_variantenvergleich_nicht():
    """Ein Kurvenlauf hat dieselben Splits, denselben Dekoder, andere Zahlen.

    Beim Bauen genau einmal passiert: der Probelauf mit `--curve` legte sich
    auf `offers_grid_dev_cv_ilp.json` und war damit der Variantenvergleich,
    aus dem der Dekoder-Befund stammt.
    """
    from magda.cli import offers_grid

    ohne = offers_grid.report_name(_args(decoder="ilp"))
    mit = offers_grid.report_name(_args(decoder="ilp", curve="10,0"))

    assert ohne != mit
    assert "curve" in mit


def test_mehrere_dekoder_ergeben_einen_dateinamen():
    """Der Vergleichslauf darf keinen der Einzellaeufe ueberschreiben."""
    from magda.cli import offers_grid

    beide = offers_grid.report_name(_args(decoder="union,ilp"))

    assert beide == "offers_grid_dev_union-ilp.json"
    assert beide != offers_grid.report_name(_args(decoder="ilp"))
    assert beide != offers_grid.report_name(_args())


# --------------------------------------------------------- Variantenbloecke


class _FixedModel:
    """Ein Modell mit vorgegebener Gruppierung und vorgegebenen Kanten.

    Die Auszaehlung soll geprueft werden, nicht das Paarmodell. Mit einem
    echten Modell haenge der Test an dessen Gewichten und wuerde rot, sobald
    jemand die Epochenzahl aendert - also genau dann, wenn nichts kaputt ist.
    """

    def __init__(self, groups, edges=None, threshold=0.5):
        from magda import offer_pairs

        self.blocks = offer_pairs.DEFAULT_BLOCKS
        self.threshold = threshold
        self._groups = groups
        self._edges = edges or {}

    def group_page_words(self, page, threshold):
        return self._groups

    def score_page(self, page):
        from magda import offer_pairs

        pairs = offer_pairs.page_pairs(page, blocks=self.blocks)
        return {pair: self._edges.get(pair, 0.0) for pair in pairs.index_pairs}


ZWEI_PREISE = ["B-PRODUCT", "B-PRICE", "B-PRICE", "B-PRODUCT"]


def test_zwei_preise_in_einer_gruppe_sind_ein_variantenblock():
    """Die Form aus Issue #6: ein Produktname, mehrere Preise."""
    page = _page(ZWEI_PREISE, texts=["Pfanne", "9.99", "14.99", "Topf"])
    assignment = {0: 0, 1: 0, 2: 0, 3: 1}

    result = offer_grid.variant_blocks(
        [page], {"p1": assignment}, _FixedModel([[0, 1, 2], [3]]))

    assert result["groups"]["variant"]["total"] == 1
    assert result["groups"]["plain"]["total"] == 1
    assert result["groups"]["all"]["total"] == 2


def test_ohne_doppelten_werttyp_ist_es_kein_variantenblock():
    """Die Gegenprobe - sonst zaehlte jede Gruppe als Variantenblock."""
    page = _page(OHNE_GRUNDPREIS)
    assignment = {0: 0, 1: 0, 2: 1, 3: 1}

    result = offer_grid.variant_blocks(
        [page], {"p1": assignment}, _FixedModel([[0, 1], [2, 3]]))

    assert result["groups"]["variant"]["total"] == 0
    assert result["groups"]["plain"]["total"] == 2


def test_ein_zerfallener_variantenblock_zaehlt_nicht_als_treffer():
    """Exakt heisst exakt: ein fehlender Preis macht die Zeile falsch."""
    page = _page(ZWEI_PREISE, texts=["Pfanne", "9.99", "14.99", "Topf"])
    assignment = {0: 0, 1: 0, 2: 0, 3: 1}

    zerfallen = offer_grid.variant_blocks(
        [page], {"p1": assignment}, _FixedModel([[0, 1], [2], [3]]))
    getroffen = offer_grid.variant_blocks(
        [page], {"p1": assignment}, _FixedModel([[0, 1, 2], [3]]))

    assert zerfallen["groups"]["variant"]["hit"] == 0
    assert getroffen["groups"]["variant"]["hit"] == 1


def test_nur_zusammengehoerige_kanten_werden_gezaehlt():
    """Die Frage ist, welche Kante das System *verliert*.

    Negative Paare mitzuzaehlen machte die Zahl zu einer Mischung aus Recall
    und Precision - und damit unbrauchbar fuer die Diagnose, wo genau diese
    beiden getrennt gehoeren.
    """
    page = _page(ZWEI_PREISE, texts=["Pfanne", "9.99", "14.99", "Topf"])
    assignment = {0: 0, 1: 0, 2: 0, 3: 1}

    result = offer_grid.variant_blocks(
        [page], {"p1": assignment}, _FixedModel([[0, 1, 2], [3]]))

    # Gruppe 0 hat drei Entities, also drei Paare. Gruppe 1 hat eine, also
    # keins. Die drei Kanten zur vierten Entity sind negativ und fehlen.
    gezaehlt = sum(e["total"] for e in result["edges"]["variant"].values())
    assert gezaehlt == 3
    assert result["edges"]["plain"] == {}


def test_der_kantenrecall_zaehlt_gegen_die_schwelle():
    """`above` ist die Betriebszahl: was haelt bei der kalibrierten Schwelle."""
    page = _page(ZWEI_PREISE, texts=["Pfanne", "9.99", "14.99", "Topf"])
    assignment = {0: 0, 1: 0, 2: 0, 3: 1}
    # Die beiden Ankerkanten halten, die Preis-zu-Preis-Kante nicht.
    edges = {(0, 1): 0.9, (0, 2): 0.9, (1, 2): 0.1}

    result = offer_grid.variant_blocks(
        [page], {"p1": assignment},
        _FixedModel([[0, 1, 2], [3]], edges=edges, threshold=0.5))

    anker = result["edges"]["variant"]["PRICE|PRODUCT"]
    preise = result["edges"]["variant"]["PRICE|PRICE"]
    assert anker["total"] == 2 and anker["above"] == 2
    assert preise["total"] == 1 and preise["above"] == 0
    assert preise["mean_probability"] == pytest.approx(0.1)


def test_kein_fold_modell_sieht_seine_eigenen_seiten(monkeypatch):
    """Die Zusicherung, an der jede Out-of-fold-Zahl haengt.

    Geprueft wird, was in `train` und `calibrate` *hineingeht* - nicht, dass
    die gehaltenen Seiten untereinander disjunkt sind. Die erste Fassung tat
    genau das und blieb gruen, als der Trainingsaufruf versuchsweise alle
    Seiten bekam: sie behauptete eine Eigenschaft, die sie nicht prueft.
    Derselbe Fall wie `test_blind_haengt_an_der_referenz_nicht_an_der_vorhersage`.
    """
    pytest.importorskip("torch")
    from magda import offer_model
    from test_offer_model import _training_set

    trainiert_mit: list[set] = []
    train, calibrate = offer_model.train, offer_model.calibrate

    def spy_train(pages, *args, **kwargs):
        trainiert_mit.append({p["page_id"] for p in pages})
        return train(pages, *args, **kwargs)

    def spy_calibrate(pages, *args, **kwargs):
        trainiert_mit.append({p["page_id"] for p in pages})
        return calibrate(pages, *args, **kwargs)

    monkeypatch.setattr(offer_model, "train", spy_train)
    monkeypatch.setattr(offer_model, "calibrate", spy_calibrate)

    pages, reference = _training_set()
    beurteilt = []
    for _, outer, _ in offer_grid.fold_models(
            pages, reference, ("types", "geometry_base"), folds=3, epochs=5):
        gehalten = {p["page_id"] for p in outer}
        # Alles, was seit dem letzten Fold trainiert wurde, gehoert diesem.
        for gesehen in trainiert_mit:
            assert not (gesehen & gehalten), "Fold-Modell kennt seine Messseiten"
        trainiert_mit.clear()
        beurteilt += sorted(gehalten)

    assert sorted(beurteilt) == sorted(p["page_id"] for p in pages)


def test_die_lernkurve_beschneidet_nur_das_training(monkeypatch):
    """`limit` verkleinert die innere Menge und laesst die aeussere ganz.

    Beides gehoert geprueft: Beschnitte man auch die Messseiten, waeren die
    Kurvenpunkte auf verschieden grossen Mengen gemessen, und ein Anstieg
    hiesse womoeglich nur "weniger schwere Seiten im Nenner".
    """
    pytest.importorskip("torch")
    from magda import offer_model
    from test_offer_model import _training_set

    trainiert_mit: list[int] = []
    train = offer_model.train

    def spy_train(pages, *args, **kwargs):
        trainiert_mit.append(len(pages))
        return train(pages, *args, **kwargs)

    monkeypatch.setattr(offer_model, "train", spy_train)
    pages, reference = _training_set()

    def lauf(limit):
        trainiert_mit.clear()
        gemessen = []
        for _, outer, inner in offer_grid.fold_models(
                pages, reference, ("types", "geometry_base"), folds=3,
                epochs=5, limit=limit):
            gemessen += [p["page_id"] for p in outer]
            assert len(inner) <= limit or not limit
        return sorted(gemessen), list(trainiert_mit)

    ganz_gemessen, ganz_trainiert = lauf(0)
    eng_gemessen, eng_trainiert = lauf(2)

    assert eng_gemessen == ganz_gemessen, "die Messmenge darf sich nicht aendern"
    assert max(eng_trainiert) < max(ganz_trainiert), "limit hat nichts beschnitten"
    assert max(eng_trainiert) <= 2
