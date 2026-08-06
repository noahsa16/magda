"""Handannotierte Gruppierungsreferenz und die Metriken darauf.

`magda offers-report` misst das Clustering per Ablation gegen die Rechnung
Menge x Grundpreis. Das ist unbestechlich, aber nur dort anwendbar, wo ein
Grundpreis steht: ueber die Haelfte der Urteile lautet "nicht beurteilbar",
und das deckt sich fast mit Non-Food. Dort ist die Geometrie alleinige
Instanz *und* ohne Kontrolle. Diese Luecke schliesst kein Schwellwert,
sondern nur eine Referenz von Hand.

**Gruppiert werden Wortindizes, nicht Entity-Spans.** Ein Span gehoert immer
einem Labelordner; eine Referenz darueber waere nach dem naechsten
Labeling-Lauf wertlos und koennte die gbert-Vorhersagen gar nicht beurteilen,
weil deren Spans anders liegen. Ueber Wortindizes beurteilt dieselbe
Annotation die Heuristik, ein LLM als Gruppierungs-Teacher und spaeter einen
OFFER-Kopf. Abgesichert wie `gold/`: mit `words_hash`.

Zwei Zahlen, weil sie verschiedene Fragen beantworten:

    pair_f1    Ueber Entity-Paare: "gehoeren diese beiden zusammen?" Teilweise
               richtige Gruppen zaehlen anteilig. Die uebliche Primaerzahl der
               Line-Item-Literatur (DocILE, arXiv:2302.05658).
    group_f1   Nur exakt getroffene Angebote zaehlen. Das ist die Zahl, die
               "die Zeile in der Datenbank stimmt" entspricht - und die
               deutlich niedrigere.

Was der Mensch keinem Angebot zugeordnet hat (Kleingedrucktes, Seitenkopf),
bewegt keine Zahl, sondern wird als `unassignable` ausgewiesen.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field, fields

from magda import config
from magda.gold import words_hash
from magda.offers import VALUE_TYPES, Offer, cluster_page, entities_from_page


@dataclass
class Reference:
    """Zuordnung Wortindex -> Angebotsnummer je Seite, plus die Ausschluesse.

    Die Ausschlussgruende gehoeren ins Ergebnis, nicht nur auf stderr: Wer
    eine Zahl ueber 12 statt 40 Seiten berichtet, muss das im Report sehen.
    """

    assignments: dict[str, dict[int, int]] = field(default_factory=dict)
    stale: list[str] = field(default_factory=list)
    in_progress: list[str] = field(default_factory=list)
    broken: list[str] = field(default_factory=list)


def reference_dir():
    """Laufzeit statt Import, damit Tests config.GOLD_DIR umbiegen koennen."""
    return config.GOLD_DIR / "offers"


def validate_groups(groups: list[list[int]], num_words: int) -> list[str]:
    """Prueft eine Gruppierung, bevor sie gespeichert wird. Leer heisst in Ordnung.

    Ein Wort in zwei Angeboten ist kein Grenzfall, sondern eine kaputte
    Annotation - stillschweigend die letzte Gruppe gewinnen zu lassen, waere
    genau die Art Fehler, die niemand an der Zahl bemerkt. Deshalb wird hier
    abgelehnt statt beim Laden repariert.
    """
    errors, seen = [], {}
    for group_id, group in enumerate(groups):
        if not group:
            errors.append(f"Angebot {group_id} ist leer.")
        for word_index in group:
            if not 0 <= word_index < num_words:
                errors.append(
                    f"Wortindex {word_index} liegt ausserhalb der Seite (0..{num_words - 1})."
                )
            elif word_index in seen:
                errors.append(
                    f"Wort {word_index} steht in zwei Angeboten ({seen[word_index]} und {group_id})."
                )
            else:
                seen[word_index] = group_id
    return errors


def _assignment(groups: list[list[int]], num_words: int) -> dict[int, int] | None:
    """Gruppenliste in Wort -> Gruppe. None, wenn die Gruppierung ungueltig ist."""
    if validate_groups(groups, num_words):
        return None
    return {i: group_id for group_id, group in enumerate(groups) for i in group}


def load_reference() -> Reference:
    """Laedt die fertigen Gruppierungsseiten unter gold/offers/.

    Dieselben drei Ausschluesse wie in `gold.load_gold_pages`, aus denselben
    Gruenden - dazu die doppelt vergebenen Woerter.
    """
    reference = Reference()
    directory = reference_dir()
    if not directory.is_dir():
        return reference

    for annotation_file in sorted(directory.glob("*.json")):
        page_id = annotation_file.stem
        with open(annotation_file) as f:
            annotation = json.load(f)

        words_file = config.WORDS_DIR / f"{page_id}.json"
        if not words_file.exists():
            continue
        with open(words_file) as f:
            page = json.load(f)

        if annotation.get("status") != "done":
            reference.in_progress.append(page_id)
            continue
        if annotation.get("words_hash") != words_hash(page["words"]):
            reference.stale.append(page_id)
            continue

        assignment = _assignment(annotation.get("groups", []), len(page["words"]))
        if assignment is None:
            reference.broken.append(page_id)
            continue
        reference.assignments[page_id] = assignment

    return reference


@dataclass
class PageScore:
    """Zaehler einer Seite. Alles ganzzahlig, damit summierbar."""

    page_id: str = ""
    pages: int = 1
    entities: int = 0
    unassignable: int = 0
    ref_pairs: int = 0
    sys_pairs: int = 0
    shared_pairs: int = 0
    ref_groups: int = 0
    sys_groups: int = 0
    exact_groups: int = 0
    ref_groups_without_entities: int = 0


def _pairs(count: int) -> int:
    return count * (count - 1) // 2


def _reference_group(entity, assignment: dict[int, int]) -> int | None:
    """Die Angebotsnummer, der die Mehrheit der Woerter dieser Entity gehoert.

    Mehrheit statt Alles-oder-nichts, weil eine Entity ueber eine
    Angebotsgrenze reichen kann - `"Löslicher Kaffee Classic,"` mit einem
    angehaengten Wort des Nachbarn. Bei Gleichstand die kleinere Nummer,
    damit das Ergebnis nicht von der Reihenfolge abhaengt.
    """
    votes = Counter(
        assignment[i] for i in range(entity.start, entity.end) if i in assignment
    )
    if not votes:
        return None
    best = max(votes.values())
    return min(group for group, count in votes.items() if count == best)


def judge_page(page: dict, assignment: dict[int, int], offers: list[Offer]) -> PageScore:
    """Vergleicht eine Systemgruppierung mit der Referenz einer Seite.

    Die Entity-Grundmenge kommt aus der Seite, nicht aus `offers`. Sonst
    verbesserte ein System seinen Recall, indem es Entities einfach weglaesst:
    was in keinem Angebot steht, bildet hier eine eigene Einermenge und traegt
    zu keinem Paar bei.
    """
    score = PageScore(page_id=page.get("page_id") or "unknown")
    universe = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]

    system_group: dict[tuple[int, int], int] = {}
    for offer_index, offer in enumerate(offers):
        for entity in offer.entities:
            system_group[(entity.start, entity.end)] = offer_index

    reference_members: dict[int, set] = {}
    system_members: dict[int, set] = {}
    loose = len(offers)

    for entity in universe:
        score.entities += 1
        key = (entity.start, entity.end)
        group = _reference_group(entity, assignment)
        if group is None:
            score.unassignable += 1
            continue
        reference_members.setdefault(group, set()).add(key)
        if key in system_group:
            system_members.setdefault(system_group[key], set()).add(key)
        else:
            system_members[loose] = {key}
            loose += 1

    score.ref_groups = len(reference_members)
    score.sys_groups = len(system_members)
    score.ref_groups_without_entities = len(set(assignment.values())) - score.ref_groups
    score.ref_pairs = sum(_pairs(len(m)) for m in reference_members.values())
    score.sys_pairs = sum(_pairs(len(m)) for m in system_members.values())

    reference_of = {key: group for group, m in reference_members.items() for key in m}
    for members in system_members.values():
        by_reference = Counter(reference_of[key] for key in members)
        score.shared_pairs += sum(_pairs(count) for count in by_reference.values())

    exact = {frozenset(m) for m in reference_members.values()}
    score.exact_groups = sum(1 for m in system_members.values() if frozenset(m) in exact)
    return score


@dataclass
class Report:
    """Summe ueber Seiten. Alle Quoten sind None, wenn nichts zu messen war."""

    pages: int = 0
    entities: int = 0
    unassignable: int = 0
    ref_pairs: int = 0
    sys_pairs: int = 0
    shared_pairs: int = 0
    ref_groups: int = 0
    sys_groups: int = 0
    exact_groups: int = 0
    ref_groups_without_entities: int = 0

    @staticmethod
    def _f1(shared: int, system: int, reference: int) -> float | None:
        if system == 0 and reference == 0:
            return None
        precision = shared / system if system else 0.0
        recall = shared / reference if reference else 0.0
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    @property
    def pair_f1(self) -> float | None:
        return self._f1(self.shared_pairs, self.sys_pairs, self.ref_pairs)

    @property
    def group_f1(self) -> float | None:
        return self._f1(self.exact_groups, self.sys_groups, self.ref_groups)

    def to_dict(self) -> dict:
        result = {f.name: getattr(self, f.name) for f in fields(self)}
        result["pair_f1"] = self.pair_f1
        result["group_f1"] = self.group_f1
        return result


def collect(pages: list[dict], reference: Reference, grouping=cluster_page) -> Report:
    """Misst eine Gruppierung ueber alle Seiten, fuer die eine Referenz vorliegt.

    `grouping` ist austauschbar: heute die Heuristik, spaeter ein LLM-Teacher
    oder ein OFFER-Kopf. Alle drei werden gegen dieselbe Annotation gemessen -
    das ist der Zweck, Wortindizes statt Spans zu gruppieren.
    """
    report = Report()
    for page in pages:
        assignment = reference.assignments.get(page.get("page_id"))
        if assignment is None:
            continue
        score = judge_page(page, assignment, grouping(page))
        for f in fields(report):
            setattr(report, f.name, getattr(report, f.name) + getattr(score, f.name))
    return report
