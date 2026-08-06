"""Kann eine flache BIO-Folge ein Angebot ueberhaupt ausdruecken?

Die OFFER-Entscheidung ruht auf einer Zahl: "92,7 % der visuellen Wortgruppen
sind genau ein zusammenhaengender Lauf in der Wortliste". Ein Span-Label kann
nur zusammenfassen, was benachbart ist - faellt ein Angebot in zwei Laeufe,
braucht es zwei Spans und die Zuordnung geht verloren.

Gemessen wird ueber die *gelabelten* Woerter: Fuellwoerter zwischen zwei
Entities desselben Angebots stoeren einen Span nicht, die Entity eines
fremden Angebots schon. Genau das ist die Grenze eines flachen BIO-Schemas.
"""

from magda import offers_sequence
from magda.offers import cluster_page


def _word(text, x0, y0, x1, y1):
    return {"text": text, "bbox": [x0, y0, x1, y1]}


def _page(page_id, words, tags):
    return {"page_id": page_id, "width": 500, "height": 800, "words": words, "tags": tags}


def _offers_from(page, groups):
    """Baut Angebote direkt aus Entity-Indizes - unabhaengig von der Heuristik."""
    from magda.offers import _make_offer, entities_from_page

    entities = entities_from_page(page)
    return [_make_offer(page["page_id"], i, [entities[j] for j in group])
            for i, group in enumerate(groups)]


SEITE = _page(
    "1_p1",
    [
        _word("Landliebe", 40, 100, 90, 112),   # 0
        _word("zzgl", 40, 116, 70, 128),        # 1 - ungelabelt
        _word("Butter", 40, 132, 90, 144),      # 2
        _word("Ja!", 40, 600, 90, 612),         # 3
        _word("1.29", 200, 100, 250, 140),      # 4
    ],
    ["B-BRAND", "O", "B-PRODUCT", "B-BRAND", "B-PRICE"],
)


def test_ungelabelte_woerter_zerreissen_ein_angebot_nicht():
    """"zzgl" zwischen Marke und Produkt kann ein Span mit ueberdecken."""
    offers = _offers_from(SEITE, [[0, 1], [2]])  # Entities 0,1 = Landliebe+Butter

    counts = offers_sequence.run_counts(SEITE, offers)

    assert counts[0] == 1


def test_fremde_entity_dazwischen_zerreisst_es_sehr_wohl():
    """Genau die Grenze eines flachen BIO-Schemas: Verschachtelung geht nicht."""
    # Entity 0 (Landliebe) und 2 (Ja!) in einem Angebot, Entity 1 (Butter)
    # dazwischen in einem anderen.
    offers = _offers_from(SEITE, [[0, 2], [1]])

    counts = offers_sequence.run_counts(SEITE, offers)

    assert counts[0] == 2
    assert counts[1] == 1


def test_einzelnes_angebot_ist_immer_ein_lauf():
    offers = _offers_from(SEITE, [[0, 1, 2, 3]])

    assert offers_sequence.run_counts(SEITE, offers) == [1]


def test_bericht_zaehlt_den_anteil_zusammenhaengender_angebote():
    report = offers_sequence.collect(
        [SEITE], grouping=lambda page: _offers_from(page, [[0, 2], [1]])
    )

    assert report.offers == 2
    assert report.contiguous == 1
    assert report.share == 0.5
    assert report.by_runs == {1: 1, 2: 1}


def test_der_preis_zerreisst_das_angebot_die_beschreibung_nicht():
    """Pennys gelber Preiskasten steht im Textlayer weit weg vom Produktnamen.

    Das ist der entscheidende Unterschied fuer die OFFER-Frage: Ohne die
    Badges ist ein Angebot fast immer ein Lauf, mit ihnen oft nicht - und
    eine flache Tag-Folge kann den Preis dann nicht mit einschliessen.
    """
    # Angebot A: Landliebe(0) + Butter(2) + Preis(4); Angebot B: Ja!(3) liegt
    # dazwischen. Mit Preis zerfaellt A, ohne Preis nicht.
    offers = _offers_from(SEITE, [[0, 1, 3], [2]])

    assert offers_sequence.run_counts(SEITE, offers)[0] == 2

    report = offers_sequence.collect([SEITE], grouping=lambda p: offers)

    assert report.contiguous == 1
    assert report.contiguous_without_badges == 2
    assert report.share_without_badges == 1.0


def test_leere_messung_ist_keine_null_prozent():
    report = offers_sequence.Report()

    assert report.share is None


def test_die_heuristik_laeuft_ueber_denselben_weg():
    """Vorbedingung: der Bericht misst standardmaessig die echte Gruppierung."""
    report = offers_sequence.collect([SEITE])

    assert report.offers == len(cluster_page(SEITE))
