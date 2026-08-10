"""Der Paar-Klassifikator: lernt aus einer Gruppierung, statt sie zu erraten.

`offers.py` ordnet Preise ueber Nachbarschaft und Arithmetik zu - beides von
Hand geschrieben, und die Geometrie allein trifft nur 0.463 bis 0.620. Hier
lernt ein kleines MLP dieselbe Entscheidung aus einer vorhandenen
Gruppierung.

Der Vertrag, der leicht still bricht: Die Merkmalsreihenfolge steckt im
Checkpoint. Ein Modell, das auf einer anderen Reihenfolge trainiert wurde,
rechnet mit vertauschten Spalten weiter und faellt durch keine Pruefung auf -
die Vorhersagen sind dann Unsinn, aber wohlgeformter Unsinn.
"""

import pytest

torch = pytest.importorskip("torch")

from magda import offer_model, offer_pairs  # noqa: E402


def _page(page_id="p1", offset=0.0):
    """Zwei Angebote untereinander: Marke, Produkt, Preis rechts daneben."""
    texts = ["Landliebe", "Butter", "1.29", "Ja!", "Milch", "0.99"]
    boxes = [
        [10, 10 + offset, 60, 20 + offset],
        [10, 22 + offset, 60, 32 + offset],
        [70, 10 + offset, 95, 40 + offset],
        [10, 110 + offset, 60, 120 + offset],
        [10, 122 + offset, 60, 132 + offset],
        [70, 110 + offset, 95, 140 + offset],
    ]
    return {
        "page_id": page_id,
        "width": 100,
        "height": 200,
        "words": [{"text": t, "bbox": b} for t, b in zip(texts, boxes)],
        "tags": ["B-BRAND", "B-PRODUCT", "B-PRICE", "B-BRAND", "B-PRODUCT", "B-PRICE"],
    }


def _assignment():
    return {0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1}


def _training_set(count=8):
    """Seiten mit gleicher Struktur, aber verschiedenem Text.

    Verschieden muss der Text sein, weil `page_folds` Duplikate ueber die
    Wortmenge erkennt - identische Seiten landen zu Recht alle im selben
    Fold, und die Kalibrierung haette dann nichts zum Zurueckhalten.
    """
    pages = []
    for i in range(count):
        page = _page(f"p{i}", offset=i * 2.0)
        for position, word in enumerate(page["words"]):
            word["text"] = f"{word['text']}{i}" if position % 2 == 0 else word["text"]
        pages.append(page)
    reference = {page["page_id"]: _assignment() for page in pages}
    return pages, reference


# ------------------------------------------------------------------ Training


def test_das_modell_lernt_die_gruppierung_der_referenz():
    """Der Ende-zu-Ende-Nachweis: ohne ihn ist alles andere Buchhaltung."""
    pages, reference = _training_set()

    model = offer_model.train(pages, reference, epochs=200, seed=0)
    groups = model.group_page(_page("neu"), threshold=0.5)

    assert sorted(map(sorted, groups)) == [[0, 1, 2], [3, 4, 5]]


def test_nicht_trainierbare_paare_kommen_nicht_ins_training():
    """Wo die Referenz schweigt, gibt es kein Beispiel - kein negatives."""
    pages, reference = _training_set(count=2)
    reference["p0"] = {0: 0, 1: 0, 2: 0}   # Angebot 2 fehlt in der Referenz

    stats = offer_model.training_stats(pages, reference)

    assert stats["pairs"] == 15 + 3   # p1 vollstaendig, von p0 nur die drei
    assert stats["skipped"] == 12


def test_ohne_ein_einziges_beispiel_bricht_das_training_ab():
    """Sonst entstuende ein Modell, das nie etwas gesehen hat, und sagt trotzdem etwas."""
    with pytest.raises(ValueError, match="[Kk]ein"):
        offer_model.train([_page()], {}, epochs=1, seed=0)


def test_zwei_laeufe_mit_demselben_seed_sind_gleich():
    """Ohne das ist jede Differenz zweier Messungen nicht zuzuordnen."""
    pages, reference = _training_set(count=4)

    first = offer_model.train(pages, reference, epochs=20, seed=7)
    second = offer_model.train(pages, reference, epochs=20, seed=7)

    assert first.score_page(_page("x")) == second.score_page(_page("x"))


SPARSE_OFFERS = 12


def _sparse_page(page_id="s1", salt=0):
    """Zwoelf Angebote untereinander: 276 Paare, davon 12 positiv (4,3 %).

    `_page` ist mit 40 % positiven Paaren viel zu ausgeglichen; die echten
    Daten liegen bei 8,9 % und einzelne Seiten deutlich darunter. Gemessen
    mit diesem Aufbau: hoechste Kantenwahrscheinlichkeit 0.981 mit
    Gegengewicht, 0.376 ohne. Bei 9 % lernt das Netz die Kanten auch
    ungewichtet - die Schieflage muss also spuerbar sein, damit der Test
    ueberhaupt etwas zeigt.
    """
    words, tags = [], []
    for index in range(SPARSE_OFFERS):
        top = 10 + index * 14
        words.append({"text": f"Produkt{index}_{salt}", "bbox": [10, top, 60, top + 8]})
        words.append({"text": f"{index}.99", "bbox": [70, top, 95, top + 10]})
        tags += ["B-PRODUCT", "B-PRICE"]
    return {"page_id": page_id, "width": 100, "height": 400, "words": words, "tags": tags}


def _sparse_set(count=6):
    pages = [_sparse_page(f"s{index}", salt=index) for index in range(count)]
    reference = {p["page_id"]: {w: w // 2 for w in range(SPARSE_OFFERS * 2)} for p in pages}
    return pages, reference


def test_die_klassenschieflage_wird_ausgeglichen():
    """Ohne Gegengewicht lernt das Netz "nie zusammen" - und liegt fast immer richtig.

    Bei 4,3 % positiven Paaren ist "alles getrennt" die bequemste Loesung -
    95,7 % richtig und voellig nutzlos. Auf den echten Daten stehen 4553
    positive gegen 46359 negative Paare. Ein Modell, das nie eine Kante
    zieht, macht jede Seite zu lauter Einzelangeboten.
    """
    pages, reference = _sparse_set()

    model = offer_model.train(pages, reference, epochs=150, seed=0)
    scores = model.score_page(_sparse_page("neu", salt=99))

    assert max(scores.values()) > 0.5, "keine einzige Kante ueber der Schwelle"


# ------------------------------------------------------------- Kalibrierung


def test_die_schwelle_wird_out_of_fold_gewaehlt():
    """0.5 ist geraten, nicht gemessen.

    `pos_weight` gleicht die Schieflage aus und schiebt dabei alle
    Wahrscheinlichkeiten nach oben - auf den echten Daten entstanden bei 0.5
    nur 83 Gruppen statt 268. Die Schwelle gehoert also gemessen, und zwar
    auf Seiten, die das jeweilige Modell nicht gesehen hat.
    """
    pages, reference = _training_set(count=10)

    result = offer_model.calibrate(pages, reference, folds=2, epochs=30, seed=0)

    assert 0.0 < result["threshold"] < 1.0
    assert len(result["curve"]) > 1


def test_duplikate_landen_im_selben_fold():
    """Sonst leckt die Kalibrierung.

    Penny gibt je Woche 44 fast gleiche Regionalausgaben heraus. Zufaellig
    auf Folds verteilt bewertet das Modell eine Vorlage, die es in einer
    anderen Fassung im Training hatte - und die Schwelle faellt zu
    nachsichtig aus.
    """
    pages = [_page("zwilling_a"), _page("zwilling_b"), _page("anders", offset=50.0)]
    pages[2]["words"] = [{"text": t, "bbox": w["bbox"]}
                         for t, w in zip("A B C D E F".split(), pages[2]["words"])]

    folds = offer_model.page_folds(pages, folds=2)

    zusammen = [f for f in folds if "zwilling_a" in f]
    assert zusammen and "zwilling_b" in zusammen[0]


def test_jede_seite_liegt_in_genau_einem_fold():
    pages, _ = _training_set(count=6)

    folds = offer_model.page_folds(pages, folds=3)

    alle = [page_id for fold in folds for page_id in fold]
    assert sorted(alle) == sorted(p["page_id"] for p in pages)
    assert len(alle) == len(set(alle))


# --------------------------------------------------------------- Vorhersage


def test_jedes_paar_bekommt_eine_wahrscheinlichkeit():
    pages, reference = _training_set(count=2)
    model = offer_model.train(pages, reference, epochs=10, seed=0)

    scores = model.score_page(_page("x"))

    assert set(scores) == set(offer_pairs.page_pairs(_page("x")).index_pairs)
    assert all(0.0 <= v <= 1.0 for v in scores.values())


def test_die_gruppen_kommen_als_wortindizes_heraus():
    """Wortindizes ueberleben den naechsten Labeling-Lauf, Entity-Nummern nicht."""
    pages, reference = _training_set(count=4)
    model = offer_model.train(pages, reference, epochs=100, seed=0)

    words = model.group_page_words(_page("x"), threshold=0.5)

    assert sorted(map(sorted, words)) == [[0, 1, 2], [3, 4, 5]]


def test_eine_seite_ohne_entities_liefert_keine_gruppe_statt_eines_fehlers():
    pages, reference = _training_set(count=2)
    model = offer_model.train(pages, reference, epochs=5, seed=0)
    leer = {"page_id": "leer", "width": 100, "height": 200, "words": [], "tags": []}

    assert model.group_page(leer, threshold=0.5) == []


# ------------------------------------------------------------ Speichern/Laden


def test_ein_geladenes_modell_sagt_dasselbe_voraus(tmp_path):
    pages, reference = _training_set(count=4)
    model = offer_model.train(pages, reference, epochs=20, seed=0)
    path = tmp_path / "model.pt"
    model.save(path)

    geladen = offer_model.load(path)

    assert geladen.score_page(_page("x")) == model.score_page(_page("x"))


def test_der_checkpoint_haelt_die_merkmalsreihenfolge_fest(tmp_path):
    """Vertauschte Spalten erzeugen wohlgeformten Unsinn - er muss auffallen."""
    pages, reference = _training_set(count=2)
    model = offer_model.train(pages, reference, epochs=5, seed=0)
    path = tmp_path / "model.pt"
    model.save(path)

    payload = torch.load(path, weights_only=True)
    payload["feature_names"] = ["etwas", "anderes"]
    torch.save(payload, path)

    with pytest.raises(ValueError, match="Merkmal"):
        offer_model.load(path)


def test_eine_andere_netzgroesse_ueberlebt_das_speichern(tmp_path):
    """Die Schichtgroessen muessen mit in den Checkpoint.

    Sonst baut `load` das Standardnetz auf und `load_state_dict` scheitert an
    Formen - oder schlimmer, es passt zufaellig und rechnet falsch.
    """
    pages, reference = _training_set(count=2)
    model = offer_model.train(pages, reference, epochs=5, seed=0, hidden=(16, 8))
    path = tmp_path / "model.pt"
    model.save(path)

    assert offer_model.load(path).score_page(_page("x")) == model.score_page(_page("x"))


def test_die_kalibrierte_schwelle_ueberlebt_das_speichern(tmp_path):
    """Sie gehoert zum Modell, nicht zum Aufruf.

    Geht sie beim Speichern verloren, misst der naechste `eval`-Lauf bei 0.5
    - und damit ein anderes System als das kalibrierte. Auf den echten Daten
    ist das der Unterschied zwischen 138 und 55 Angeboten.
    """
    pages, reference = _training_set(count=2)
    model = offer_model.train(pages, reference, epochs=5, seed=0)
    model.threshold = 0.94
    path = tmp_path / "model.pt"
    model.save(path)

    assert offer_model.load(path).threshold == 0.94


def test_der_checkpoint_nennt_seine_herkunft(tmp_path):
    """Ein Modell, das aus einer LLM-Gruppierung gelernt hat, erbt deren Status."""
    pages, reference = _training_set(count=2)
    model = offer_model.train(pages, reference, epochs=5, seed=0,
                              provenance={"reference": "claude-sonnet-5", "kind": "llm"})
    path = tmp_path / "model.pt"
    model.save(path)

    assert offer_model.load(path).provenance["kind"] == "llm"
