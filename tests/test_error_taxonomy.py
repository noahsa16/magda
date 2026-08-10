"""Fehlerklassen - und die Frage, was sie je Klasse loesen wuerde.

Gearbeitet wird auf Spans, nicht auf Woertern: ein um ein Wort verschobener
Sortenzusatz ist ein Fehler, nicht zwei.
"""

from magda import error_taxonomy


def _klassen(words, reference, predicted):
    return [e["klasse"] for e in
            error_taxonomy.classify_page(words, reference, predicted)]


# ------------------------------------------------------------ je eine Klasse


def test_ein_exakter_treffer_ist_kein_fehler():
    """Gefragt sind die Fehler; die Trefferquote misst `magda eval`."""
    assert _klassen(["Butter", "1.29"],
                    ["B-PRODUCT", "B-PRICE"],
                    ["B-PRODUCT", "B-PRICE"]) == []


def test_derselbe_span_mit_anderem_typ_ist_eine_typverwechslung():
    assert _klassen(["1.29"], ["B-APP_PRICE"], ["B-PRICE"]) == ["typverwechslung"]


def test_derselbe_typ_mit_anderer_grenze_ist_ein_grenzfehler():
    """Der Sortenzusatz-Fall: 106 von 135 PRODUCT-Fehlern sehen so aus."""
    assert _klassen(["Loeslicher", "Kaffee", "Classic,"],
                    ["B-PRODUCT", "I-PRODUCT", "I-PRODUCT"],
                    ["B-PRODUCT", "I-PRODUCT", "O"]) == ["grenzfehler"]


def test_ein_span_ohne_gegenstueck_ist_ein_falsch_positiv():
    assert _klassen(["Garantie"], ["O"], ["B-PRODUCT"]) == ["echtes_falsch_positiv"]


def test_ein_uebersehener_span_ist_ein_falsch_negativ():
    assert _klassen(["Butter"], ["B-PRODUCT"], ["O"]) == ["echtes_falsch_negativ"]


# ------------------------------------------------------------ Lehrerluecken


def test_ein_preis_neben_einer_fussnotenziffer_ist_eine_lehrerluecke():
    """Belegt: das Muster `<preis> <ziffer>` ist in den sonnet-5-Labels 1x
    als APP_PRICE und 60x als O vergeben. Wo der Schueler dort einen Preis
    sieht, liegt er eher richtig als die Referenz."""
    assert _klassen(["Aktion", "1.99", "2"],
                    ["O", "O", "O"],
                    ["O", "B-PRICE", "O"]) == ["lehrerluecke"]


def test_ein_preis_neben_dem_wort_app_ist_eine_lehrerluecke():
    assert _klassen(["mit", "PENNY", "App", "1.69"],
                    ["O", "O", "O", "O"],
                    ["O", "O", "O", "B-PRICE"]) == ["lehrerluecke"]


def test_ein_produkt_neben_einer_ziffer_ist_keine_lehrerluecke():
    """Sonst wuerde die Klasse zur Ausrede: jede Uebervorhersage neben einer
    Zahl hiesse 'der Lehrer war schuld'. Die Badge-Erklaerung gilt nur fuer
    Preistypen."""
    assert _klassen(["Handtuch", "3"],
                    ["O", "O"],
                    ["B-PRODUCT", "O"]) == ["echtes_falsch_positiv"]


def test_eine_lange_zahl_daneben_ist_keine_fussnote():
    """Fussnoten sind ein- bis zweistellig. Eine Jahreszahl oder eine
    Artikelnummer daneben belegt nichts."""
    assert _klassen(["1.99", "2026"],
                    ["O", "O"],
                    ["B-PRICE", "O"]) == ["echtes_falsch_positiv"]


def test_ein_preis_mit_gegenstueck_wird_nicht_zur_lehrerluecke_erklaert():
    """Wo die Referenz etwas sagt, ist die Abweichung eine Verwechslung -
    auch wenn zufaellig eine Ziffer danebensteht."""
    assert _klassen(["1.99", "2"],
                    ["B-OLD_PRICE", "O"],
                    ["B-PRICE", "O"]) == ["typverwechslung"]


# -------------------------------------------------------------- Buchfuehrung


def test_jede_referenz_entity_wird_hoechstens_einmal_verbraucht():
    """Sonst erklaerte ein einziger Referenz-Span zwei Vorhersagen zu
    Grenzfehlern und die Falsch-Positiven verschwaenden aus der Statistik."""
    klassen = _klassen(["Butter", "Milch"],
                       ["B-PRODUCT", "I-PRODUCT"],
                       ["B-PRODUCT", "B-PRODUCT"])

    assert sorted(klassen) == ["echtes_falsch_positiv", "grenzfehler"]


def test_die_zusammenfassung_nennt_je_klasse_die_loesbarkeit():
    """Die vierte Spalte ist der Gehalt der Taxonomie, nicht die Haeufigkeit."""
    errors = error_taxonomy.classify_page(["1.29"], ["B-APP_PRICE"], ["B-PRICE"])

    summary = error_taxonomy.summarize(errors)

    assert summary["total"] == 1
    assert summary["classes"]["typverwechslung"]["count"] == 1
    assert summary["classes"]["typverwechslung"]["solvability"]
    assert all(name in summary["classes"] for name in error_taxonomy.CLASSES)


def test_die_anteile_summieren_sich_zu_eins():
    errors = error_taxonomy.classify_page(
        ["Butter", "1.29", "Garantie"],
        ["B-PRODUCT", "B-APP_PRICE", "O"],
        ["O", "B-PRICE", "B-PRODUCT"])

    summary = error_taxonomy.summarize(errors)

    # Die Anteile sind auf vier Stellen gerundet, damit im Report keine
    # Scheinpraezision steht - drei Drittel ergeben deshalb 0.9999.
    anteile = sum(c["share"] for c in summary["classes"].values() if c["share"])
    assert abs(anteile - 1.0) < 1e-3
