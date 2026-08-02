"""Die vier Schemata müssen sich genau dort unterscheiden, wo die Grenzfrage
sitzt – sonst wäre die zusätzliche Zahl nur Dekoration.

Der Fall, um den es geht: Referenz `"Frische Lammspieße* Mariniert,"`,
Vorhersage `"Frische Lammspieße*"`. Für die Angebots-Rekonstruktion folgenlos,
für `strict` ein doppelter Fehler.
"""

from magda.matching import count_page, evaluate, evaluate_per_label

def span(start, end, label):
    return {"start": start, "end": end, "label": label}


def test_exakter_treffer_zaehlt_in_allen_schemata():
    ergebnis = evaluate([[span(0, 2, "PRODUCT")]], [[span(0, 2, "PRODUCT")]])

    for schema in ("strict", "exact", "partial", "type"):
        assert ergebnis[schema]["f1"] == 1.0, schema


def test_grenzfehler_trifft_strict_aber_nicht_type():
    """Der Sortenzusatz-Fall: richtiger Typ, Grenze verschoben."""
    ergebnis = evaluate([[span(0, 3, "PRODUCT")]], [[span(0, 2, "PRODUCT")]])

    assert ergebnis["strict"]["f1"] == 0.0
    assert ergebnis["exact"]["f1"] == 0.0
    assert ergebnis["type"]["f1"] == 1.0
    assert ergebnis["partial"]["f1"] == 0.5   # MUC: Teiltreffer zählt halb


def test_typverwechslung_trifft_type_aber_nicht_exact():
    """Preis als Streichpreis gelabelt – Grenze stimmt, Bedeutung nicht."""
    ergebnis = evaluate([[span(0, 1, "PRICE")]], [[span(0, 1, "OLD_PRICE")]])

    assert ergebnis["type"]["f1"] == 0.0
    assert ergebnis["strict"]["f1"] == 0.0
    assert ergebnis["exact"]["f1"] == 1.0     # richtige Stelle, falsches Feld


def test_uebersehene_und_erfundene_entity():
    ergebnis = evaluate([[span(0, 1, "PRICE")]], [[span(5, 6, "BRAND")]])

    for schema in ("strict", "exact", "partial", "type"):
        assert ergebnis[schema]["f1"] == 0.0, schema
        assert ergebnis[schema]["missing"] == 1
        assert ergebnis[schema]["spurious"] == 1


def test_exakter_treffer_schlaegt_zufaellige_ueberlappung():
    """Sonst hinge das Ergebnis an der Reihenfolge der Spans."""
    referenz = [span(0, 5, "PRODUCT")]
    # Die zweite Vorhersage ist deckungsgleich, die erste ueberlappt nur.
    vorhersage = [span(4, 8, "PRODUCT"), span(0, 5, "PRODUCT")]

    counts = count_page(referenz, vorhersage)

    assert counts["strict"].correct == 1
    assert counts["strict"].spurious == 1


def test_possible_bleibt_die_zahl_der_referenz_entities():
    referenz = [[span(0, 1, "PRICE"), span(2, 3, "BRAND")], [span(0, 2, "PRODUCT")]]
    vorhersage = [[span(0, 1, "PRICE")], []]

    ergebnis = evaluate(referenz, vorhersage)

    for schema in ("strict", "exact", "partial", "type"):
        assert ergebnis[schema]["possible"] == 3, schema


def test_je_label_summiert_sich_zur_gesamtzahl():
    referenz = [[span(0, 1, "PRICE"), span(2, 4, "PRODUCT")]]
    vorhersage = [[span(0, 1, "PRICE"), span(2, 3, "PRODUCT")]]

    je_label = evaluate_per_label(referenz, vorhersage, scheme="type")

    assert je_label["PRICE"]["f1"] == 1.0
    assert je_label["PRODUCT"]["f1"] == 1.0   # Grenzfehler, aber Typ stimmt
    assert sum(v["possible"] for v in je_label.values()) == 2


def test_type_ist_nie_schlechter_als_strict():
    """Jedes Schema lockert nur – eine Verschärfung wäre ein Fehler im Zählwerk."""
    referenz = [[span(0, 3, "PRODUCT"), span(5, 6, "PRICE"), span(8, 9, "BRAND")]]
    vorhersage = [[span(0, 2, "PRODUCT"), span(5, 6, "OLD_PRICE"), span(8, 9, "BRAND")]]

    ergebnis = evaluate(referenz, vorhersage)

    assert ergebnis["type"]["f1"] >= ergebnis["strict"]["f1"]
    assert ergebnis["partial"]["f1"] >= ergebnis["exact"]["f1"]
