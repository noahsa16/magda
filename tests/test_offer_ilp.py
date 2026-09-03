"""Der ILP-Dekoder gegen den Transitivitaetsfehler der Zusammenhangskomponenten.

`groups_from_edges` benennt sein Problem im eigenen Docstring: A-B und B-C
verschmelzen, auch wenn A-C weit unter der Schwelle liegt. Genau dieser Fall
steht hier als erster Test - alles andere sichert ab, dass der neue Dekoder
sonst nichts veraendert.
"""

import math

import pytest

from magda import offer_ilp, offer_pairs

# Wer nur `requirements.txt` installiert hat, soll hier nicht auf elf
# roten Tests sitzen - `pulp` ist optional wie `flair`. In CI steht es
# in den dev-Extras, dort laufen sie also wirklich.
pytest.importorskip("pulp")


def _probability(weight: float, threshold: float) -> float:
    """Wahrscheinlichkeit, deren Gewicht `weight` betraegt - die Umkehrung des Offsets."""
    logit = math.log(threshold / (1 - threshold)) + weight
    return 1 / (1 + math.exp(-logit))


def test_das_dreieck_wird_nicht_verschmolzen():
    """Der Fall, um den es geht: zwei starke Kanten, eine klar dagegen.

    Union-Find macht daraus eine Gruppe aus drei Entities, weil es A-C nie
    ansieht. Das ILP muss die schwaechste der drei Kanten kappen.
    """
    threshold = 0.9
    edges = {
        (0, 1): _probability(+4.0, threshold),
        (1, 2): _probability(+4.0, threshold),
        (0, 2): _probability(-9.0, threshold),
    }

    union = offer_pairs.groups_from_edges(3, edges, threshold)
    ilp = offer_ilp.groups_from_edges_ilp(3, edges, threshold)

    assert sorted(len(g) for g in union) == [3], "Vorbedingung: Union-Find verschmilzt"
    assert sorted(len(g) for g in ilp) == [1, 2], "das ILP muss aufspalten"


def test_ohne_widerspruch_dasselbe_ergebnis_wie_union_find():
    """Wo kein Dreieck verletzt ist, darf sich nichts aendern.

    Sonst waere der Vergleich beider Dekoder kein Vergleich zweier
    Dekodierregeln, sondern zweier verschiedener Systeme.
    """
    threshold = 0.9
    edges = {
        (0, 1): _probability(+5.0, threshold),
        (0, 2): _probability(+5.0, threshold),
        (1, 2): _probability(+5.0, threshold),
        (0, 3): _probability(-5.0, threshold),
        (1, 3): _probability(-5.0, threshold),
        (2, 3): _probability(-5.0, threshold),
    }

    union = {frozenset(g) for g in offer_pairs.groups_from_edges(4, edges, threshold)}
    ilp = {frozenset(g) for g in offer_ilp.groups_from_edges_ilp(4, edges, threshold)}

    assert ilp == union == {frozenset({0, 1, 2}), frozenset({3})}


@pytest.mark.parametrize("probability,zusammen", [(0.95, True), (0.85, False)])
def test_die_schwelle_ist_der_nullpunkt(probability, zusammen):
    """Der Offset im Gewicht, nicht das rohe log-odds.

    Ohne `- logit(threshold)` laege der Nullpunkt bei 0.5. Die Schwelle wird
    aber out-of-fold bei 0.94 gewaehlt - das ILP arbeitete dann an einer
    ganz anderen Stelle als die Kalibrierung annimmt.
    """
    threshold = 0.9
    groups = offer_ilp.groups_from_edges_ilp(2, {(0, 1): probability}, threshold)

    assert (sorted(len(g) for g in groups) == [2]) is zusammen


def test_das_ilp_verfeinert_die_komponenten_nur():
    """Die Invariante, auf der die Zerlegung nach Komponenten beruht.

    Eine ILP-Gruppe liegt immer *innerhalb* einer Union-Find-Gruppe: Ueber
    die Komponentengrenze hinweg gibt es nur negative Kanten, und sie dort
    zu teilen ist strikt besser. Faellt dieser Test, ist die Zerlegung in
    `_components` keine Optimierung mehr, sondern eine stille Naeherung.
    """
    threshold = 0.9
    edges = {
        (0, 1): _probability(+3.0, threshold),
        (1, 2): _probability(+3.0, threshold),
        (0, 2): _probability(-8.0, threshold),
        (2, 3): _probability(+3.0, threshold),
        (0, 3): _probability(-8.0, threshold),
        (1, 3): _probability(-8.0, threshold),
        (0, 4): _probability(-8.0, threshold),
        (1, 4): _probability(-8.0, threshold),
        (2, 4): _probability(-8.0, threshold),
        (3, 4): _probability(-8.0, threshold),
    }

    union = [set(g) for g in offer_pairs.groups_from_edges(5, edges, threshold)]
    ilp = [set(g) for g in offer_ilp.groups_from_edges_ilp(5, edges, threshold)]

    for group in ilp:
        assert any(group <= component for component in union), \
            f"{group} liegt in keiner Union-Find-Komponente"


def test_verbotene_paare_bleiben_getrennt():
    """`cannot_link` ist die harte Null - vorbereitet fuer Regeln, die
    ausschliessen koennen, was das Modell nur unwahrscheinlich findet."""
    threshold = 0.9
    edges = {(0, 1): _probability(+6.0, threshold)}

    ohne = offer_ilp.groups_from_edges_ilp(2, edges, threshold)
    mit = offer_ilp.groups_from_edges_ilp(2, edges, threshold, cannot_link={(0, 1)})

    assert sorted(len(g) for g in ohne) == [2]
    assert sorted(len(g) for g in mit) == [1, 1]


def test_gleiche_eingabe_gleiche_gruppen():
    """Zwei Laeufe, dasselbe Ergebnis - sonst schwankt jede Messung mit."""
    threshold = 0.9
    edges = {
        (0, 1): _probability(+4.0, threshold),
        (1, 2): _probability(+2.0, threshold),
        (0, 2): _probability(-3.0, threshold),
        (2, 3): _probability(+1.0, threshold),
        (0, 3): _probability(-2.0, threshold),
        (1, 3): _probability(-6.0, threshold),
    }

    first = offer_ilp.groups_from_edges_ilp(4, edges, threshold)
    second = offer_ilp.groups_from_edges_ilp(4, edges, threshold)

    assert [sorted(g) for g in first] == [sorted(g) for g in second]


def test_jede_entity_kommt_in_genau_einer_gruppe_vor():
    """Auch die, zu der gar keine Kante vorliegt - sie ist ein Angebot fuer sich."""
    groups = offer_ilp.groups_from_edges_ilp(4, {(0, 1): 0.99}, 0.9)

    members = sorted(index for group in groups for index in group)
    assert members == [0, 1, 2, 3]


def test_sichere_wahrscheinlichkeiten_erzeugen_keine_unendlichen_gewichte():
    """p = 1.0 und p = 0.0 kommen aus einem Sigmoid mit float32-Rundung.

    Ungeklippt waere das Gewicht +-inf, und CBC bekaeme eine Zielfunktion
    mit `inf` - das schlaegt nicht sauber fehl, sondern liefert Unsinn.
    """
    groups = offer_ilp.groups_from_edges_ilp(
        3, {(0, 1): 1.0, (1, 2): 0.0, (0, 2): 0.0}, 0.9)

    assert sorted(sorted(g) for g in groups) == [[0, 1], [2]]


def _chain(length: int, threshold: float) -> dict[tuple[int, int], float]:
    """Perlenkette: Nachbarn ziehen sich an, alles andere stoesst sich ab.

    Ein Fall, den Union-Find zu einer einzigen Gruppe macht und der viele
    Dreiecke verletzt - also genau die Sorte Instanz, fuer die es die
    Schnittebenen gibt.
    """
    edges = {}
    for i in range(length):
        for j in range(i + 1, length):
            edges[(i, j)] = _probability(+3.0 if j == i + 1 else -7.0, threshold)
    return edges


def test_schnittebenen_liefern_dasselbe_wie_die_volle_formulierung(monkeypatch):
    """Beide Loesungswege, dieselbe Instanz, dasselbe Ergebnis.

    `LAZY_ABOVE` ist eine reine Laufzeitkonstante: Sie zu verstellen darf
    an keinem Ergebnis etwas aendern. Genau deshalb kann kein Test sie
    "schuetzen" - was ein Test leisten kann, ist beide Pfade zu pruefen.
    Ohne diesen hier lief der Schnittebenen-Pfad in keinem einzigen Test,
    obwohl er auf echten Seiten der uebliche ist.
    """
    threshold = 0.9
    edges = _chain(10, threshold)

    monkeypatch.setattr(offer_ilp, "LAZY_ABOVE", 1000)      # volle Formulierung
    exact = [sorted(g) for g in offer_ilp.groups_from_edges_ilp(10, edges, threshold)]

    monkeypatch.setattr(offer_ilp, "LAZY_ABOVE", 0)         # nur Schnittebenen
    lazy = [sorted(g) for g in offer_ilp.groups_from_edges_ilp(10, edges, threshold)]

    assert lazy == exact
    assert len(exact) > 1, "Vorbedingung: die Kette muss aufgespalten werden"


def test_nicht_konvergierende_schnittebenen_brechen_ab(monkeypatch):
    """Lieber ein Abbruch als eine Partition, die keine ist.

    Wird die Schleife vorzeitig verlassen, kann die Loesung noch verletzte
    Dreiecke enthalten - `_partition` macht daraus trotzdem Gruppen, und die
    Zahl saehe aus wie ein ILP-Ergebnis.
    """
    threshold = 0.9
    monkeypatch.setattr(offer_ilp, "LAZY_ABOVE", 0)
    monkeypatch.setattr(offer_ilp, "MAX_ROUNDS", 1)

    with pytest.raises(RuntimeError, match="konvergieren"):
        offer_ilp.groups_from_edges_ilp(10, _chain(10, threshold), threshold)


def test_ohne_pulp_bricht_der_aufruf_ab(monkeypatch):
    """Kein stiller Rueckfall auf Union-Find.

    Ein Rueckfall waere die Sorte Fehler, die man spaeter an einer Zahl
    nicht mehr sieht: Der Report saehe aus wie ein ILP-Lauf und waere
    keiner. `pulp` steht bewusst nicht in `requirements.txt`.
    """
    import builtins

    original = builtins.__import__

    def ohne_pulp(name, *args, **kwargs):
        if name == "pulp":
            raise ImportError("kein pulp")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", ohne_pulp)

    with pytest.raises(RuntimeError, match="pulp"):
        offer_ilp.groups_from_edges_ilp(2, {(0, 1): 0.99}, 0.9)


def test_grosse_komponenten_werden_durchgereicht_und_gezaehlt(monkeypatch):
    """Die Kappung darf nicht still sein.

    Wo sie greift, *ist* das ILP Union-Find - und zwar an genau der Stelle,
    an der es seinen Vorteil ausspielen sollte. Eine Kurve, die das nicht
    ausweist, sieht aus wie ein ILP-Ergebnis und ist teilweise keines.
    """
    threshold = 0.9
    monkeypatch.setattr(offer_ilp, "MAX_COMPONENT", 4)
    offer_ilp.reset_counters()

    edges = _chain(8, threshold)
    groups = offer_ilp.groups_from_edges_ilp(8, edges, threshold)

    assert offer_ilp.LAST_RUN["capped"] == 1
    assert offer_ilp.LAST_RUN["largest_capped"] == 8
    assert offer_ilp.LAST_RUN["optimised"] == 0
    # Durchgereicht heisst: dasselbe wie Union-Find, nicht irgendetwas.
    assert [sorted(g) for g in groups] == \
        [sorted(g) for g in offer_pairs.groups_from_edges(8, edges, threshold)]


def test_unterhalb_der_kappung_wird_optimiert(monkeypatch):
    """Die Gegenprobe - sonst koennte die Kappung immer greifen."""
    threshold = 0.9
    monkeypatch.setattr(offer_ilp, "MAX_COMPONENT", 40)
    offer_ilp.reset_counters()

    offer_ilp.groups_from_edges_ilp(8, _chain(8, threshold), threshold)

    assert offer_ilp.LAST_RUN["capped"] == 0
    assert offer_ilp.LAST_RUN["optimised"] == 1


def test_beide_solver_finden_dasselbe_optimum(monkeypatch):
    """Der Solverwechsel ist eine Laufzeitfrage, keine methodische.

    Gemessen an einer echten Instanz aus dem Gitterlauf (93 Entities, 4278
    Variablen): HiGHS 96 s, CBC nach 900 s noch nicht fertig, Zielwert
    beide Male 990.238714. Der Wechsel darf am Ergebnis nichts aendern -
    genau wie `LAZY_ABOVE` ist der Solver eine reine Laufzeitkonstante,
    und wie dort kann ein Test ihn nicht "schuetzen", nur beide Wege
    pruefen.

    Uebersprungen, wenn highspy fehlt: dann laeuft ohnehin nur CBC, und
    ein Vergleich mit sich selbst sichert nichts zu.
    """
    import pulp

    try:
        highs = pulp.HiGHS(msg=False)
    except (AttributeError, pulp.PulpError):
        pytest.skip("HiGHS nicht verfuegbar")
    if not highs.available():
        pytest.skip("HiGHS nicht verfuegbar")

    threshold = 0.9
    edges = _chain(10, threshold)

    monkeypatch.setattr(offer_ilp, "_SOLVER", pulp.PULP_CBC_CMD(msg=0))
    mit_cbc = [sorted(g) for g in offer_ilp.groups_from_edges_ilp(10, edges, threshold)]

    monkeypatch.setattr(offer_ilp, "_SOLVER", highs)
    mit_highs = [sorted(g) for g in offer_ilp.groups_from_edges_ilp(10, edges, threshold)]

    assert mit_highs == mit_cbc
    assert len(mit_cbc) > 1, "Vorbedingung: die Kette muss aufgespalten werden"


def test_ohne_highspy_faellt_der_solver_auf_cbc_zurueck(monkeypatch):
    """Ein fehlendes highspy macht den Lauf langsamer, nicht falsch."""
    import pulp

    monkeypatch.setattr(offer_ilp, "_SOLVER", None)
    monkeypatch.delattr(pulp, "HiGHS", raising=False)

    assert isinstance(offer_ilp._solver(), pulp.PULP_CBC_CMD)
