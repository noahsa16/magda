"""Misst das Angebots-Clustering, ohne sein eigenes Kriterium zu befragen.

`_match_badges` ordnet einen Preis bevorzugt ueber Menge x Grundpreis zu und
faellt nur dann auf geometrische Naehe zurueck, wenn die Rechnung bei keinem
Block aufgeht. Hinterher zu zaehlen, wie oft ein Preis bei einem Produkt
landet, misst deshalb zweierlei nicht: nicht die Korrektheit (ein Preis am
falschen Produkt zaehlt mit) und nicht unabhaengig (fuer die geometrischen
Faelle steht das arithmetische Urteil schon fest - es ist gescheitert).

Deshalb Ablation: `cluster_page(page, arithmetic=False)` laesst die Geometrie
allein zuordnen, und erst danach rechnet dieses Modul nach. Die Arithmetik ist
so ein unbeteiligter Richter ueber jede einzelne Zuordnung:

    confirmed      Geometrie waehlte den Block, den die Rechnung waehlt
    contradicted   Die Rechnung zeigt auf einen anderen Block der Seite
    unjudgeable    Kein Grundpreis vorhanden - kein Urteil moeglich

Gemessen wird damit das schwache Bein des Verfahrens: der geometrische
Rueckfall traegt alles ohne Grundpreis, also praktisch das ganze
Non-Food-Sortiment. Was die Ablation nicht abdeckt, bleibt `unjudgeable` und
wird als solches ausgewiesen - dort hilft nur eine handannotierte
Gruppierungsreferenz.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

# Bewusst die modulinternen Helfer von `offers`: der Report muss mit exakt
# derselben Arithmetik nachrechnen, mit der `_match_badges` zuordnet. Eine
# eigene Kopie wuerde bei der naechsten Toleranzaenderung auseinanderlaufen.
from magda.offers import (
    PRICE_TYPES,
    Offer,
    _expected_prices,
    _price_matches,
    _price_value,
    cluster_page,
)

DESCRIPTION_ANCHORS = ("PRODUCT", "BRAND")


@dataclass
class PageVerdict:
    """Urteile und Zaehler einer Seite. Alles ganzzahlig, damit summierbar."""

    page_id: str = ""
    pages: int = 1
    confirmed: int = 0
    contradicted: int = 0
    unjudgeable: int = 0
    contradicted_strict: int = 0
    unjudgeable_strict: int = 0
    arithmetic_assignments: int = 0
    geometric_assignments: int = 0
    unmatched: int = 0
    offers_total: int = 0
    offers_with_product_and_price: int = 0
    fragments: int = 0
    blocks_without_matching_pairing: int = 0


@dataclass
class Report:
    """Summe ueber Seiten. `geometric_accuracy` ist None, wenn nichts beurteilbar war."""

    pages: int = 0
    confirmed: int = 0
    contradicted: int = 0
    unjudgeable: int = 0
    contradicted_strict: int = 0
    unjudgeable_strict: int = 0
    arithmetic_assignments: int = 0
    geometric_assignments: int = 0
    unmatched: int = 0
    offers_total: int = 0
    offers_with_product_and_price: int = 0
    fragments: int = 0
    blocks_without_matching_pairing: int = 0

    @property
    def judged(self) -> int:
        return self.confirmed + self.contradicted

    @property
    def judged_strict(self) -> int:
        return self.confirmed + self.contradicted_strict

    @property
    def geometric_accuracy(self) -> float | None:
        """Nachsichtige Lesart - None statt 0.0, wenn nichts beurteilbar war.

        Der Unterschied ist keine Kosmetik: 0.0 hiesse "alles falsch", None
        heisst "hier war nichts zu messen".
        """
        if self.judged == 0:
            return None
        return self.confirmed / self.judged

    @property
    def geometric_accuracy_strict(self) -> float | None:
        """Strenge Lesart: auch ein belegter Block zaehlt als Alternative.

        Zusammen mit `geometric_accuracy` die untere und obere Schranke. Eine
        der beiden zur richtigen zu erklaeren, hiesse eine Genauigkeit zu
        behaupten, die die Messung nicht hergibt.
        """
        if self.judged_strict == 0:
            return None
        return self.confirmed / self.judged_strict

    def to_dict(self) -> dict:
        result = {f.name: getattr(self, f.name) for f in fields(self)}
        result["judged"] = self.judged
        result["judged_strict"] = self.judged_strict
        result["geometric_accuracy"] = self.geometric_accuracy
        result["geometric_accuracy_strict"] = self.geometric_accuracy_strict
        return result


def _has(offer: Offer, types) -> bool:
    return any(entity.type in types for entity in offer.entities)


def _pairing_fails(offer: Offer, page: dict) -> bool:
    """Menge x Grundpreis vorhanden, aber kein Preis des Blocks trifft sie.

    Das ist der Fall `1351497_p20` aus CLAUDE.md: `900 g | 750 ml | 313,5 g` bei
    Preis 4.49, und nur eine der drei Rechnungen geht auf - keine Varianten,
    sondern drei zusammengeworfene Nachbarprodukte. Findet Clustering-Fehler
    ohne Handannotation.
    """
    expected = _expected_prices(offer, page)
    if not expected:
        return False
    values = [
        _price_value(entity.text)
        for entity in offer.entities
        if entity.type in PRICE_TYPES
    ]
    values = [v for v in values if v is not None]
    if not values:
        return False
    return not any(_price_matches(value, expected) for value in values)


def judge_page(page: dict) -> PageVerdict:
    """Ablation und Zaehlung fuer eine Seite."""
    verdict = PageVerdict(page_id=page.get("page_id") or "unknown")

    ablated: list = []
    cluster_page(page, arithmetic=False, trace=ablated)
    for match in ablated:
        if match.path != "geometric":
            continue
        if match.target in match.arithmetic_targets:
            verdict.confirmed += 1
        elif not match.arithmetic_targets:
            verdict.unjudgeable += 1
        else:
            verdict.contradicted += 1

        # Zweite Lesart, nur in den beiden Gegenkategorien verschieden:
        # `confirmed` faellt unter beiden gleich aus, weil das gewaehlte Ziel
        # zum Zeitpunkt der Zuordnung immer frei war.
        if match.target not in match.arithmetic_targets_any:
            if match.arithmetic_targets_any:
                verdict.contradicted_strict += 1
            else:
                verdict.unjudgeable_strict += 1

    regular: list = []
    offers = cluster_page(page, trace=regular)
    for match in regular:
        if match.path == "arithmetic":
            verdict.arithmetic_assignments += 1
        elif match.path == "geometric":
            verdict.geometric_assignments += 1
        else:
            verdict.unmatched += 1

    verdict.offers_total = len(offers)
    for offer in offers:
        complete = _has(offer, DESCRIPTION_ANCHORS) and _has(offer, PRICE_TYPES)
        if complete:
            verdict.offers_with_product_and_price += 1
        else:
            verdict.fragments += 1
        if _pairing_fails(offer, page):
            verdict.blocks_without_matching_pairing += 1

    return verdict


def collect(pages: list[dict]) -> Report:
    """Summiert die Seitenurteile."""
    report = Report()
    for page in pages:
        verdict = judge_page(page)
        for f in fields(report):
            setattr(report, f.name, getattr(report, f.name) + getattr(verdict, f.name))
    return report
