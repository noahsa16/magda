"""Die Rechnung als unbeteiligter Richter ueber eine fremde Gruppierung.

`0,25 kg x 4,00 EUR/kg = 1,00 EUR` stimmt oder stimmt nicht. Das ist das
einzige Signal im System, das sich selbst beweist - und es ist die Antwort
auf den Einwand gegen eine maschinell erzeugte Referenz: Wenn ein Modell nach
dem Seitenbild gruppiert, kann die Arithmetik hinterher nachrechnen, ohne je
an der Zuordnung beteiligt gewesen zu sein.

**Der Unterschied zu `offers_report` ist der Grund fuer ein eigenes Modul.**
Dort ordnet die Heuristik teilweise selbst arithmetisch zu; das Urteil stuende
fest, bevor es faellt, und deshalb braucht der Report die Ablation
(`cluster_page(page, arithmetic=False)`). Ein Vision-Modell hat nie gerechnet
- hier ist keine Ablation noetig und auch keine moeglich.

Vier Urteile je Preis, nicht drei:

    confirmed     Die Rechnung geht in genau dieser Gruppe auf.
    contradicted  Sie geht in einer *anderen* Gruppe der Seite auf.
    unresolved    Sie geht nirgends auf, obwohl ein Grundpreis da ist.
    unjudgeable   Kein Grundpreis - kein Urteil moeglich (praktisch Non-Food).

`unresolved` getrennt von `contradicted` zu fuehren ist keine Feinheit: Ein
Preis, der zu keiner Gruppe passt, belegt nichts gegen die Zuordnung. Die
Ursache ist meist eine Mehrfachpackung ("2 x 350 g", deren Multiplikator
`_quantity_in_unit` ignoriert) oder ein fehlendes Label. Wer ihn als
widerlegt zaehlte, schriebe Labelfehler dem Gruppieren zu.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

# Dieselben Helfer, mit denen `_match_badges` zuordnet - eine eigene Kopie
# liefe bei der naechsten Toleranzaenderung auseinander.
from magda.offers import (
    PRICE_TYPES,
    _expected_prices,
    _price_matches,
    _price_value,
)
from magda.offers_gold import offers_from_reference


@dataclass
class PageVerdict:
    """Urteile einer Seite. Alles ganzzahlig, damit summierbar."""

    page_id: str = ""
    pages: int = 1
    prices: int = 0
    confirmed: int = 0
    contradicted: int = 0
    unresolved: int = 0
    unjudgeable: int = 0
    offers: int = 0


@dataclass
class Report:
    pages: int = 0
    prices: int = 0
    confirmed: int = 0
    contradicted: int = 0
    unresolved: int = 0
    unjudgeable: int = 0
    offers: int = 0

    @property
    def judged(self) -> int:
        return self.confirmed + self.contradicted

    @property
    def accuracy(self) -> float | None:
        """None statt 0.0, wenn nichts beurteilbar war - "alles falsch" waere etwas anderes."""
        return None if self.judged == 0 else self.confirmed / self.judged

    @property
    def coverage(self) -> float | None:
        """Wie viel der Gruppierung die Rechnung ueberhaupt erreicht.

        Die wichtigere Zahl neben `accuracy`: eine Genauigkeit von 0.9 ueber
        ein Fuenftel der Preise sagt wenig ueber die uebrigen vier Fuenftel.
        """
        return None if self.prices == 0 else self.judged / self.prices

    def to_dict(self) -> dict:
        result = {f.name: getattr(self, f.name) for f in fields(self)}
        result["judged"] = self.judged
        result["accuracy"] = self.accuracy
        result["coverage"] = self.coverage
        return result


def _judge_prices(page: dict, offers: list):
    """Urteil je Preis-Entity - der gemeinsame Kern von `judge_page` (Summe
    ueber die Seite) und `judge_offers` (ein Wort je Angebot).

    Liefert (offer_index, verdict)-Paare, `verdict` eines von confirmed /
    contradicted / unresolved / unjudgeable - dieselben vier Woerter, mit
    denen `PageVerdict` seine Felder benennt.
    """
    expected = {index: _expected_prices(offer, page) for index, offer in enumerate(offers)}
    for index, offer in enumerate(offers):
        for entity in offer.entities:
            if entity.type not in PRICE_TYPES:
                continue
            value = _price_value(entity.text)
            if value is None:
                continue
            if expected[index] and _price_matches(value, expected[index]):
                yield index, "confirmed"
            elif any(_price_matches(value, other)
                     for other_index, other in expected.items()
                     if other_index != index and other):
                yield index, "contradicted"
            elif expected[index]:
                yield index, "unresolved"
            else:
                yield index, "unjudgeable"


def judge_page(page: dict, assignment: dict[int, int]) -> PageVerdict:
    """Rechnet jede Preiszuordnung einer Seite nach."""
    offers = offers_from_reference(page, assignment)
    verdict = PageVerdict(page_id=page.get("page_id") or "unknown", offers=len(offers))
    for _, label in _judge_prices(page, offers):
        verdict.prices += 1
        setattr(verdict, label, getattr(verdict, label) + 1)
    return verdict


def judge_offers(page: dict, offers: list) -> list[str]:
    """Ein verdichtetes Urteil je Angebot statt eines Zaehlers je Seite.

    Ein Angebot kann mehrere Preis-Entities tragen (Varianten, App-Preis
    neben regulaerem Preis); die Prioritaet `contradicted` > `confirmed` >
    `unresolved` > `unverifiable` faellt so aus, dass ein einziger
    widerlegter Preis das ganze Angebot faerbt - ein Angebot mit einem
    falschen und einem richtigen Preis ist kein halb bestaetigtes.
    `unverifiable` fasst zwei Faelle zusammen, die fuer diese Spalte
    gleichbedeutend sind: kein Grundpreis vorhanden (`unjudgeable`) oder gar
    kein Preis im Angebot.
    """
    by_offer: dict[int, set[str]] = {index: set() for index in range(len(offers))}
    for index, label in _judge_prices(page, offers):
        by_offer[index].add(label)

    result = []
    for index in range(len(offers)):
        labels = by_offer[index]
        if "contradicted" in labels:
            result.append("contradicted")
        elif "confirmed" in labels:
            result.append("confirmed")
        elif "unresolved" in labels:
            result.append("unresolved")
        else:
            result.append("unverifiable")
    return result


def collect(pages: list[dict], assignments: dict[str, dict[int, int]]) -> Report:
    """Summiert ueber alle Seiten, fuer die eine Gruppierung vorliegt."""
    report = Report()
    for page in pages:
        assignment = assignments.get(page.get("page_id"))
        if assignment is None:
            continue
        verdict = judge_page(page, assignment)
        for f in fields(Report):
            setattr(report, f.name, getattr(report, f.name) + getattr(verdict, f.name))
    return report
