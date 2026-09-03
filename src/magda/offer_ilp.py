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

# Ab dieser Komponentengroesse wird nicht mehr optimiert, sondern
# durchgereicht - die Komponente *ist* dann die Gruppe, also genau das, was
# Union-Find liefert.
#
# Gemessen ueber 12 echte Seiten, Dekodierzeit je Schwelle:
#
#     Schwelle   groesste Komponente   Union-Find   ILP
#       0.50            83               0.001 s    5.27 s
#       0.70             6               0.001 s    0.51 s
#       0.90+            1               0.001 s    0.02 s
#
# Die Kosten haengen allein an der groessten Komponente.
#
# **Die Kappung ist keine Kleinigkeit fuer die Auslegung der Kurve:** Wo sie
# greift, *ist* das ILP Union-Find - und zwar an genau der Stelle, an der es
# seinen Vorteil ausspielen sollte. Die Schwellenkurve ist deshalb nur
# oberhalb der Kappung aussagekraeftig. Wie oft sie greift, zaehlt
# `LAST_RUN` mit und gehoert in jeden Report.
#
# **Von 40 auf 120 angehoben am 29.08.2026, und der Grund ist gemessen.**
# Mit 40 kappte der Dev-Lauf des auf 494 Seiten neu trainierten Paarmodells
# 5 von 297 Komponenten, die groesste mit 111 Entities. Diese 5 Blobs
# erzeugten 20903 der 26279 vorhergesagten Paare - 80 % - und drueckten
# Paar-F1 auf 0.398, waehrend Gruppen-F1 bei 0.659 stand. Die Kappung war
# also nicht ein bisschen ungenau, sie entschied die Metrik.
#
# Ohne Kappung loest dieselbe 111er-Komponente in 6 bis 28 s und zerfaellt
# in 15 Gruppen mit hoechstens 11 Entities - das ILP kann den Fall, es
# durfte ihn nur nicht anfassen. Ueber eine Stichprobe von 12 Train-Seiten
# und das ganze Kalibrierungsraster (0.50 bis 0.90) kostet 120 gegenueber
# 40 den Faktor 2.7 und kappt dabei kein einziges Mal; die groesste
# gebildete Gruppe faellt von 64 auf 17. Teurer wird dabei das *obere*
# Ende, nicht das untere - unten spart die Kappung ja gerade die Arbeit,
# die sie kaputtmacht.
#
# Der Wert deckt die groesste beobachtete Komponente mit Reserve, er ist
# keine Garantie. Ob er reicht, sagt `LAST_RUN["capped"]` in jedem Report -
# steht dort etwas anderes als 0, ist die Kurve wieder nur teilweise ein
# ILP-Ergebnis.
MAX_COMPONENT = 120

# Zaehlwerk des letzten Laufs. Ein Modul-Zustand ist unschoen, aber die
# Alternative waere ein Rueckgabewert an jedem Aufrufer entlang bis in den
# Report - fuer eine Zahl, die niemand zum Rechnen braucht und die trotzdem
# niemals fehlen darf.
LAST_RUN = {"components": 0, "optimised": 0, "capped": 0, "largest_capped": 0}

# Einmal ermittelt, dann wiederverwendet - `available()` von HiGHS
# kostet sonst je Komponente einen Anlauf.
_SOLVER = None


def reset_counters() -> None:
    """Vor einem Messlauf zuruecksetzen, damit die Zahlen zu ihm gehoeren."""
    LAST_RUN.update({"components": 0, "optimised": 0, "capped": 0,
                     "largest_capped": 0})


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


def _solver():
    """Der schnellste verfuegbare exakte Solver - HiGHS, sonst CBC.

    Gemessen am 30.08.2026 an einer echten Instanz aus dem Gitterlauf (eine
    Komponente mit 93 Entities, 4278 binaere Variablen, 6772 nachgereichte
    Dreiecke): **HiGHS 96 s, CBC nach 900 s noch nicht fertig**, bei
    identischem Zielwert 990.238714. Der Faktor ist also mindestens 9,4 und
    in Wahrheit groesser.

    Zwei Gruende, beide unabhaengig von der Qualitaet der Solver: Das von
    PuLP mitgelieferte CBC ist ein x86_64-Binary und laeuft auf Apple
    Silicon unter Rosetta. Und `PULP_CBC_CMD` startet **je
    Schnittebenen-Runde einen neuen Prozess**, schreibt das Modell als MPS
    und liest es wieder ein - bei dieser Instanz 1,9 MB pro Runde. `HiGHS`
    spricht ueber highspy direkt in den Prozess.

    **Der Wechsel ist methodisch folgenlos.** Gesucht ist das Optimum, und
    beide Solver finden dasselbe; verschieden waere hoechstens die Wahl
    unter gleichwertigen Optima. `test_beide_solver_finden_dasselbe_optimum`
    haelt das fest. Fehlt highspy, faellt der Aufruf auf CBC zurueck - dann
    ist das Ergebnis dasselbe und der Lauf dauert laenger.
    """
    pulp = _require_pulp()

    global _SOLVER
    if _SOLVER is None:
        try:
            candidate = pulp.HiGHS(msg=False)
            _SOLVER = candidate if candidate.available() else pulp.PULP_CBC_CMD(msg=0)
        except (AttributeError, pulp.PulpError):
            _SOLVER = pulp.PULP_CBC_CMD(msg=0)
    return _SOLVER


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
        problem.solve(_solver())
    else:
        # Schnittebenen: loesen, verletzte Dreiecke nachreichen, wiederholen.
        # Die Loesung ist am Ende exakt - abgebrochen wird erst, wenn keine
        # Verletzung mehr auftritt.
        for _ in range(MAX_ROUNDS):
            problem.solve(_solver())
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
        LAST_RUN["components"] += 1
        if len(component) == 1:
            groups.append(component)
        elif len(component) > MAX_COMPONENT:
            # Durchgereicht statt optimiert - das Ergebnis ist hier exakt
            # das von Union-Find. Wird gezaehlt, nicht verschwiegen.
            LAST_RUN["capped"] += 1
            LAST_RUN["largest_capped"] = max(LAST_RUN["largest_capped"], len(component))
            groups.append(sorted(component))
        else:
            LAST_RUN["optimised"] += 1
            groups.extend(_solve_component(sorted(component), weights, cannot_link))
    return sorted(groups, key=lambda group: group[0])
