"""Merkmalsbloecke einzeln messen - das 2x2-Gitter des Paarmodells.

Eine Leiter (erst Geometrie, dann Farbe obendrauf) schriebe der Farbe nur
den *Rest*-Beitrag zu. Raeumen die Kontextmerkmale die Legendenfaelle schon
ab, saehe Farbe insgesamt nutzlos aus - waehrend sie in Non-Food womoeglich
allein traegt. Bei 16,8 s Training je Variante kostet das Gitter nichts.

**Die Aufschlaesselung nach blindem Fleck ist die eigentliche Kennzahl.**
Farbmerkmale sind fuer den Bereich gebaut, in dem die Arithmetik schweigt;
eine Gesamtzahl kann steigen, weil das Modell in der ohnehin prueffbaren
Haelfte besser wird. Ein Paar zaehlt hier als **blind**, wenn keine der
beiden Referenzgruppen einen UNIT_PRICE enthaelt - ohne Grundpreis in der
Gruppe ist keine Rechnung moeglich.
"""

from __future__ import annotations

# Warum es die Kreuzvalidierung gibt (11.08.2026):
#
# Die Konfidenzintervalle der Gruppen-F1 waren so breit, dass keine Variante
# von einer anderen zu unterscheiden war. Der naheliegende Schluss war "mehr
# Referenz" - und er war halb falsch. Gemessen wird auf **Dev**, und Dev hat
# 21 Seiten in 14 Duplikat-Clustern, *alle* davon bereits gruppiert. Die
# Breite des Intervalls haengt an der Zahl der Auswertungs-Cluster, also an
# 14, und keine weitere Trainingsseite aendert daran etwas. Das Planziel
# "Dev auf 25-30 Seiten ausbauen" war nicht schwer, sondern unmoeglich.
#
# Der Ausweg ist keine Datenfrage, sondern eine Frage des Messaufbaus: jede
# Referenzseite einmal auswerten, mit einem Modell, das sie nicht gesehen
# hat. Aus 14 Clustern werden so alle Cluster der Referenz.

import math
import random
from dataclasses import dataclass, field

from magda import offer_pairs
from magda.offers import VALUE_TYPES, entities_from_page

VARIANTS: dict[str, tuple[str, ...]] = {
    "basis": offer_pairs.DEFAULT_BLOCKS,
    "geometrie": offer_pairs.GEOMETRY_BLOCKS,
    "farbe": ("types", "geometry_base", "color"),
    "beide": offer_pairs.ALL_BLOCKS,
}

# Duplikat-Cluster, ueber die das Bootstrap resampelt - dieselbe Schwelle,
# mit der Dev gezogen wurde. Elf Regionalfassungen einer Vorlage sind eine
# Beobachtung, nicht elf.
CLUSTER_THRESHOLD = 0.7
BOOTSTRAP_ROUNDS = 1000


@dataclass
class Counts:
    """Paar- und Gruppenzahlen, getrennt nach blindem Fleck."""

    ref_pairs: int = 0
    sys_pairs: int = 0
    shared_pairs: int = 0
    ref_groups: int = 0
    sys_groups: int = 0
    exact_groups: int = 0

    def add(self, other: "Counts") -> "Counts":
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(self, name) + getattr(other, name))
        return self

    @property
    def pair_f1(self) -> float | None:
        return _f1(self.shared_pairs, self.sys_pairs, self.ref_pairs)

    @property
    def group_f1(self) -> float | None:
        return _f1(self.exact_groups, self.sys_groups, self.ref_groups)

    def to_dict(self) -> dict:
        out = {name: getattr(self, name) for name in self.__dataclass_fields__}
        out["pair_f1"] = self.pair_f1
        out["group_f1"] = self.group_f1
        return out


@dataclass
class PageCounts:
    page_id: str
    total: Counts = field(default_factory=Counts)
    blind: Counts = field(default_factory=Counts)
    checkable: Counts = field(default_factory=Counts)


def _f1(shared: int, system: int, reference: int) -> float | None:
    if system == 0 and reference == 0:
        return None
    precision = shared / system if system else 0.0
    recall = shared / reference if reference else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _pairs_of(members) -> set[frozenset]:
    ordered = sorted(members)
    return {frozenset((a, b))
            for i, a in enumerate(ordered) for b in ordered[i + 1:]}


def judge_page(page: dict, assignment: dict[int, int],
               groups: list[list[int]]) -> PageCounts:
    """Eine Systemgruppierung gegen die Referenz, aufgeschluesselt.

    `groups` sind Wortindex-Gruppen, wie sie `group_page_words` liefert.
    Die Entity-Grundmenge kommt aus der *Seite*, nicht aus `groups` - sonst
    verbesserte ein System seinen Recall, indem es Entities weglaesst.
    """
    from magda.offers_gold import _reference_group

    result = PageCounts(page_id=page.get("page_id") or "unknown")
    universe = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]

    system_of: dict[int, int] = {}
    for index, words in enumerate(groups):
        for word in words:
            system_of[word] = index

    reference_members: dict[int, set] = {}
    system_members: dict[int, set] = {}
    types_of_group: dict[int, set[str]] = {}
    loose = len(groups)

    for entity in universe:
        key = (entity.start, entity.end)
        group = _reference_group(entity, assignment)
        if group is None:
            continue                      # der Mensch hat geschwiegen
        reference_members.setdefault(group, set()).add(key)
        types_of_group.setdefault(group, set()).add(entity.type)
        found = {system_of[w] for w in range(entity.start, entity.end)
                 if w in system_of}
        if len(found) == 1:
            system_members.setdefault(found.pop(), set()).add(key)
        else:
            system_members[loose] = {key}
            loose += 1

    # Blind ist eine Eigenschaft der Referenzgruppe, nicht der Vorhersage -
    # sonst haenge die Einteilung am zu bewertenden System.
    blind_group = {g: "UNIT_PRICE" not in t for g, t in types_of_group.items()}
    group_of = {key: g for g, m in reference_members.items() for key in m}

    def bucket(pair) -> str:
        a, b = tuple(pair)
        return "blind" if blind_group[group_of[a]] and blind_group[group_of[b]] \
            else "checkable"

    reference_pairs = {p for m in reference_members.values() for p in _pairs_of(m)}
    system_pairs = {p for m in system_members.values() for p in _pairs_of(m)
                    if all(k in group_of for k in p)}
    shared = reference_pairs & system_pairs

    exact = {frozenset(m) for m in reference_members.values()}
    for group, members in reference_members.items():
        target = result.blind if blind_group[group] else result.checkable
        for counts in (result.total, target):
            counts.ref_groups += 1
    for members in system_members.values():
        keys = [k for k in members if k in group_of]
        if not keys:
            continue
        is_blind = all(blind_group[group_of[k]] for k in keys)
        target = result.blind if is_blind else result.checkable
        hit = 1 if frozenset(members) in exact else 0
        for counts in (result.total, target):
            counts.sys_groups += 1
            counts.exact_groups += hit

    for pairs, name in ((reference_pairs, "ref_pairs"),
                        (system_pairs, "sys_pairs"),
                        (shared, "shared_pairs")):
        for pair in pairs:
            target = result.blind if bucket(pair) == "blind" else result.checkable
            for counts in (result.total, target):
                setattr(counts, name, getattr(counts, name) + 1)

    return result


def cross_validate(pages: list[dict], assignments: dict, blocks,
                   folds: int = 5, epochs: int = 300, seed: int = 0,
                   objective: str = "group_f1",
                   progress=None) -> tuple[list[PageCounts], list[float]]:
    """Jede Referenzseite einmal auswerten - mit einem Modell ohne sie.

    Die Schwelle wird **geschachtelt** gewaehlt: `calibrate` laeuft auf den
    inneren Folds und macht dort seine eigene Kreuzvalidierung, die
    Auswertung trifft nur den aeusseren Fold. Eine einmal auf allem gewaehlte
    Schwelle waere bequemer und genau der Zirkelschluss, gegen den
    `offers_report` die Ablation braucht - die Schwelle ist ein Freiheitsgrad
    wie jeder andere.

    Der Preis ist Rechenzeit: `folds` mal Kalibrierung plus Training. Der
    Gewinn ist die Zahl der unabhaengigen Auswertungseinheiten, und die
    bestimmt die Breite jedes Intervalls.
    """
    from magda import offer_model, offer_pairs

    per_page: list[PageCounts] = []
    thresholds: list[float] = []
    for number, fold in enumerate(offer_model.page_folds(pages, folds), 1):
        held_out = set(fold)
        inner = [p for p in pages if p["page_id"] not in held_out]
        outer = [p for p in pages if p["page_id"] in held_out]
        if not inner or not outer:
            continue
        calibration = offer_model.calibrate(
            inner, assignments, folds=folds, epochs=epochs, seed=seed,
            objective=objective, blocks=blocks)
        threshold = calibration["threshold"]
        thresholds.append(threshold)
        model = offer_model.train(inner, assignments, epochs=epochs, seed=seed,
                                  blocks=blocks)
        model.threshold = threshold
        for page in outer:
            per_page.append(judge_page(page, assignments[page["page_id"]],
                                       model.group_page_words(page, threshold)))
        if progress:
            progress(number, len(outer), threshold)
    return per_page, thresholds


def clusters_of(pages: list[dict]) -> list[list[str]]:
    """Duplikat-Cluster der Seiten - die Einheit, ueber die resampelt wird."""
    from magda.dedupe import group

    words = {p["page_id"]: [w["text"] for w in (p.get("words") or [])] for p in pages}
    clusters = [sorted(c) for c in group(words, threshold=CLUSTER_THRESHOLD)]
    known = {page_id for cluster in clusters for page_id in cluster}
    clusters += [[p["page_id"]] for p in pages if p["page_id"] not in known]
    return clusters


def bootstrap(per_page: list[PageCounts], clusters: list[list[str]],
              field_name: str = "total", metric: str = "pair_f1",
              rounds: int = BOOTSTRAP_ROUNDS, seed: int = 0) -> dict:
    """Konfidenzintervall ueber Cluster, nicht ueber Seiten.

    Elf Regionalfassungen derselben Vorlage sind eine Beobachtung. Ueber
    Seiten resampelt waere das Intervall zu eng - genau der Fehler, den
    `magda significance` fuer die Labelmetriken vermeidet.
    """
    by_page = {p.page_id: p for p in per_page}
    usable = [[pid for pid in c if pid in by_page] for c in clusters]
    usable = [c for c in usable if c]
    if len(usable) < 2:
        return {"clusters": len(usable), "low": None, "high": None}

    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(rounds):
        total = Counts()
        for _ in range(len(usable)):
            for page_id in rng.choice(usable):
                total.add(getattr(by_page[page_id], field_name))
        value = getattr(total, metric)
        if value is not None:
            values.append(value)
    if not values:
        return {"clusters": len(usable), "low": None, "high": None}
    values.sort()
    return {
        "clusters": len(usable),
        "low": values[int(0.025 * len(values))],
        "high": values[min(int(0.975 * len(values)), len(values) - 1)],
    }


def total_of(per_page: list[PageCounts], field_name: str) -> Counts:
    total = Counts()
    for page in per_page:
        total.add(getattr(page, field_name))
    return total
