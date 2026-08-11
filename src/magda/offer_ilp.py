"""Correlation Clustering als Dekoder - gegen den Transitivitaetsfehler.

`offer_pairs.groups_from_edges` benennt sein Problem selbst: A-B und B-C
verschmelzen zu einer Gruppe, auch wenn A-C weit unter der Schwelle liegt.
Bei einer Legendenspalte kann das eine ganze Seite zu einem Angebot machen.

Das ist nicht nur ein Randfall, sondern erklaert die Kalibrierungszahlen.
Die Schwelle landet out-of-fold bei 0.94 bis 0.96, weit ueber dem
natuerlichen Schnitt; bei 0.5 entstanden 83 Gruppen statt 268. Union-Find
hat gegen eine einzige durchgerutschte Kante nur einen Hebel - *alle*
Kanten pessimistischer machen. Deshalb muss die Kalibrierung so weit nach
oben drehen, und deshalb zerfallen danach Angebote, deren Kanten legitim
mittelstark sind.

Correlation Clustering hat einen zweiten Hebel: Es entscheidet ueber alle
Kanten gemeinsam unter der Nebenbedingung, dass das Ergebnis eine gueltige
Partition ist, und darf die schwaechste Kante eines widerspruechlichen
Dreiecks kappen statt alle zu bestrafen.

**Der Nullpunkt ist die Schwelle, nicht 0.5.** Das Gewicht ist
`logit(p) - logit(threshold)`, nicht das rohe log-odds. Ohne den Offset
arbeitete das ILP bei 0.5, waehrend die Kalibrierung 0.94 gewaehlt hat -
und der Vergleich beider Dekoder waere keiner.

**Was hier bewusst *nicht* als Nebenbedingung steht:**

*Die Rechnung Menge x Grundpreis.* Sie ist das einzige Signal, das sich
selbst beweist, und damit der einzige unbeteiligte Richter in `magda
offers-verify`. Als Constraint erzwungen bewertete sie sich hinterher
selbst - derselbe Zirkelschluss, gegen den `offers_report` die Ablation
braucht. Dasselbe Muster wie beim Merkmalsausschluss in `offer_pairs`.

*Kardinalitaet ("hoechstens ein PRICE je Angebot").* Bei Penny schlicht
falsch: Variantenbloecke tragen legitim mehrere Preise (`Pfanne: 20 cm
9.99 / 24 cm 14.99 / 28 cm 17.99`). Ein harter Constraint zementierte den
Plaettungsfehler, statt ihn zu beheben.
"""

from __future__ import annotations

import math

# Damit `p = 1.0` kein unendliches Gewicht ergibt. Die Wahrscheinlichkeiten
# kommen aus einem float32-Sigmoid und erreichen die Raender wirklich.
EPSILON = 1e-6

# Ab hier wird die Transitivitaet nachgereicht statt vorab aufgezaehlt.
# Vollstaendig sind es n(n-1)(n-2)/2 Ungleichungen: bei 30 Knoten 12180 und
# gemessen 40 s, bei 48 Knoten 51888. Nachgereicht waren es auf denselben
# Instanzen 398 und 4 s bei identischem Zielwert.
#
# Kein Test kann diesen Wert schuetzen, und das ist kein Versehen: Beide
# Wege sind korrekt, die Konstante waehlt nur den schnelleren. Was ein Test
# leisten kann, ist beide Pfade zu pruefen - dafuer gibt es
# `test_schnittebenen_liefern_dasselbe_wie_die_volle_formulierung`. Ohne ihn
# lief der Schnittebenen-Pfad in keinem Test, obwohl er auf echten Seiten
# der uebliche ist.
LAZY_ABOVE = 8

# Schutz gegen eine nicht konvergierende Schnittebenen-Schleife. Gemessen
# reichten fuenf Runden; wer hier anschlaegt, hat einen Fehler, keinen
# schweren Fall.
MAX_ROUNDS = 40


def _require_pulp():
    """PuLP holen - oder abbrechen, statt still auf Union-Find zurueckzufallen.

    Ein Rueckfall waere die Sorte Fehler, die man spaeter an einer Zahl nicht
    mehr sieht: Der Report saehe aus wie ein ILP-Lauf und waere keiner.
    `pulp` steht bewusst nicht in `requirements.txt` - wer nur trainiert,
    soll es nicht installieren muessen, gleiche Begruendung wie bei `flair`.
    """
    try:
        import pulp
    except ImportError as error:
        raise RuntimeError(
            "Der ILP-Dekoder braucht pulp. `.venv/bin/pip install pulp` - "
            "es steht absichtlich nicht in requirements.txt, weil Training "
            "und Pipeline ohne es auskommen."
        ) from error
    return pulp


def _weight(probability: float, threshold: float) -> float:
    """log-odds gegen die Schwelle. Positiv genau dann, wenn p ueber ihr liegt."""
    p = min(max(float(probability), EPSILON), 1 - EPSILON)
    t = min(max(float(threshold), EPSILON), 1 - EPSILON)
    return math.log(p / (1 - p)) - math.log(t / (1 - t))


def _components(count: int, positive: list[tuple[int, int]]) -> list[list[int]]:
    """Zusammenhangskomponenten der Kanten ueber der Schwelle.

    Sie duerfen einzeln geloest werden, und das ist keine Naeherung: Eine
    Gruppe ueber eine Komponentengrenze hinweg enthaelt dort ausschliesslich
    negative Kanten; sie entlang der Grenze zu teilen entfernt genau diese
    und laesst alles andere unberuehrt, ist also strikt besser. Das Optimum
    liegt damit immer *innerhalb* der Komponenten.

    Inhaltlich ist das die Semantik des Dekoders: Das ILP spaltet
    Union-Find-Gruppen auf, es fuehrt nie zwei zusammen. Genau der eine
    Fehlermodus, gegen den es gebaut ist.

    Die Bedingung `weight > 0` ist nur in *einer* Richtung durch Tests
    gedeckt: Zu streng gefasst uebersieht sie Kanten und liefert falsche
    Gruppen (geprueft). Zu grosszuegig gefasst entstehen groessere
    Komponenten, die das ILP trotzdem optimal loest - nur langsamer. Wer
    hier etwas aendert, misst die Laufzeit mit.
    """
    parent = list(range(count))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j in positive:
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    members: dict[int, list[int]] = {}
    for index in range(count):
        members.setdefault(find(index), []).append(index)
    return list(members.values())


def _violations(nodes: list[int], value) -> list[tuple[tuple, tuple, tuple]]:
    """Verletzte Dreiecke der aktuellen Loesung, als (a, b, gegen)-Tripel."""
    found = []
    for a, i in enumerate(nodes):
        for b, j in enumerate(nodes[a + 1:], a + 1):
            for k in nodes[b + 1:]:
                ij, jk, ik = value(i, j), value(j, k), value(i, k)
                if ij + jk - ik > 1:
                    found.append(((i, j), (j, k), (i, k)))
                if ij + ik - jk > 1:
                    found.append(((i, j), (i, k), (j, k)))
                if jk + ik - ij > 1:
                    found.append(((j, k), (i, k), (i, j)))
    return found


def _solve_component(nodes: list[int], weights: dict[tuple[int, int], float],
                     cannot_link: set[tuple[int, int]]) -> list[list[int]]:
    """Eine Komponente optimal partitionieren."""
    pulp = _require_pulp()

    problem = pulp.LpProblem("correlation_clustering", pulp.LpMaximize)
    variables = {}
    for a, i in enumerate(nodes):
        for j in nodes[a + 1:]:
            variable = pulp.LpVariable(f"z_{i}_{j}", cat="Binary")
            if (i, j) in cannot_link:
                variable.setInitialValue(0)
                variable.fixValue()
            variables[(i, j)] = variable

    problem += pulp.lpSum(weights.get(key, 0.0) * variable
                          for key, variable in variables.items())

    def value(i: int, j: int) -> int:
        return round(variables[(i, j) if i < j else (j, i)].value() or 0)

    if len(nodes) <= LAZY_ABOVE:
        for a, i in enumerate(nodes):
            for b, j in enumerate(nodes[a + 1:], a + 1):
                for k in nodes[b + 1:]:
                    x, y, z = variables[(i, j)], variables[(j, k)], variables[(i, k)]
                    problem += x + y - z <= 1
                    problem += x + z - y <= 1
                    problem += y + z - x <= 1
        problem.solve(pulp.PULP_CBC_CMD(msg=0))
    else:
        # Schnittebenen: loesen, verletzte Dreiecke nachreichen, wiederholen.
        # Die Loesung ist am Ende exakt - abgebrochen wird erst, wenn keine
        # Verletzung mehr auftritt.
        for _ in range(MAX_ROUNDS):
            problem.solve(pulp.PULP_CBC_CMD(msg=0))
            violated = _violations(nodes, value)
            if not violated:
                break
            for first, second, against in violated:
                problem += (variables[first] + variables[second]
                            - variables[against] <= 1)
        else:
            raise RuntimeError(
                f"Die Schnittebenen konvergieren nach {MAX_ROUNDS} Runden nicht "
                f"({len(nodes)} Entities). Das ist ein Fehler, kein schwerer Fall."
            )

    return _partition(nodes, value)


def _partition(nodes: list[int], value) -> list[list[int]]:
    """Aus den z-Werten Gruppen bilden.

    Ueber Zusammenhang statt ueber Cliquen: Nach der Transitivitaet ist
    beides dasselbe, und Zusammenhang kommt ohne eine zweite Schleife aus.
    """
    parent = {index: index for index in nodes}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, i in enumerate(nodes):
        for j in nodes[a + 1:]:
            if value(i, j) == 1:
                root_i, root_j = find(i), find(j)
                if root_i != root_j:
                    parent[root_i] = root_j

    members: dict[int, list[int]] = {}
    for index in nodes:
        members.setdefault(find(index), []).append(index)
    return [sorted(group) for group in members.values()]


def groups_from_edges_ilp(count: int, edges: dict[tuple[int, int], float],
                          threshold: float,
                          cannot_link: set[tuple[int, int]] | None = None
                          ) -> list[list[int]]:
    """Kantenwahrscheinlichkeiten zu Gruppen - global statt kantenweise.

    Signaturgleich zu `offer_pairs.groups_from_edges`, damit beide Dekoder
    an denselben Stellen einsetzbar sind und der Vergleich wirklich nur die
    Dekodierregel betrifft.

    `cannot_link` verbietet einzelne Paare hart. Vorbereitet, aber im
    Projekt bisher unbenutzt: Gedacht ist es fuer Regeln, die *ausschliessen*
    koennen, was das Modell nur unwahrscheinlich findet.
    """
    cannot_link = {tuple(sorted(pair)) for pair in (cannot_link or ())}
    weights = {tuple(sorted(key)): _weight(value, threshold)
               for key, value in edges.items()}
    positive = [key for key, weight in weights.items()
                if weight > 0 and key not in cannot_link]

    groups: list[list[int]] = []
    for component in _components(count, positive):
        if len(component) == 1:
            groups.append(component)
        else:
            groups.extend(_solve_component(sorted(component), weights, cannot_link))
    return sorted(groups, key=lambda group: group[0])
