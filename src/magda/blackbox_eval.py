"""Angebotsvergleich v2: Name und Aktionspreis je Preisvariante.

Altpreis und Zusatzfelder sind nicht Teil des Haupt-F1. Beide Systeme und
Referenzen werden auf dieselbe Einheit projiziert; ein maximales bipartites
Matching verhindert einen Einfluss der Ausgabereihenfolge auf die Trefferzahl.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Unter diesem Wert gilt ein Name als anderes Produkt. 0.6 laesst
# Sortenzusaetze durch ("Butter" ~ "Butter 250 g") und trennt verschiedene
# Artikel zum selben Preis - der Fall, den eine reine Preisgleichheit auf
# einer Seite voller 0.99-Angebote nicht auseinanderhaelt.
NAME_SIMILARITY = 0.6

# Was beide Systeme ausdruecken koennen. Alles andere bleibt draussen.
COMMON_FIELDS = ("name", "price")
EVALUATION_VERSION = "offer-price-v2"

_PRICE = re.compile(r"\d+(?:[.,]\d+)?")


def parse_price(text) -> float | None:
    """Eine einzelne Preisangabe; Varianten werden vor dem Parsen getrennt."""
    if text is None:
        return None
    match = _PRICE.search(str(text))
    if match is None:
        return None
    return float(match.group().replace(",", "."))


def deals_from_offer(offer) -> list[dict]:
    """Eine Zeile je unterschiedlichem Aktionspreis derselben Angebotsgruppe.

    Gleiche Preise innerhalb einer Gruppe entsprechen dem Promptfall
    „Varianten mit gemeinsamem Preis“. Altpreise bleiben Zusatzinformationen.
    """
    values = offer.values()
    name = " ".join(part for part in (values.get("brand"), values.get("product")) if part).strip()
    if not name:
        return []
    prices = (values.get("price") or "").split(" | ")
    old_prices = (values.get("old_price") or "").split(" | ")
    result = {}
    for index, value in enumerate(prices):
        price = parse_price(value)
        if price is not None:
            result.setdefault(price, {
                "name": name, "price": price,
                "original_price": parse_price(old_prices[index]) if index < len(old_prices) else None,
            })
    return list(result.values())


def _similar(a: str, b: str) -> float:
    # SequenceMatcher kann bei gleicher Eingabe in umgekehrter Richtung
    # unterschiedlich werten. Der Mittelwert macht die Kanten symmetrisch.
    a, b = (a or "").lower(), (b or "").lower()
    return (SequenceMatcher(None, a, b).ratio() + SequenceMatcher(None, b, a).ratio()) / 2


def match_deals(system: list[dict], reference: list[dict],
                price_tolerance: float = 0.0) -> dict:
    """Maximale Trefferzahl; Preise exakt, Namensähnlichkeit als feste Schwelle."""
    edges = []
    for deal in system:
        price = deal.get("price")
        edges.append([
            index for index, other in enumerate(reference)
            if price is not None and other.get("price") is not None
            and abs(float(price) - float(other["price"])) <= price_tolerance
            and _similar(deal.get("name", ""), other.get("name", "")) >= NAME_SIMILARITY
        ])
    assigned: dict[int, int] = {}

    def augment(index: int, seen: set[int]) -> bool:
        for target in edges[index]:
            if target in seen:
                continue
            seen.add(target)
            if target not in assigned or augment(assigned[target], seen):
                assigned[target] = index
                return True
        return False

    matched = sum(augment(index, set()) for index in range(len(system)))
    return _rates(matched, len(system), len(reference))


def _rates(matched: int, system: int, reference: int) -> dict:
    if not system and not reference:
        precision = recall = f1 = None
    else:
        precision = matched / system if system else 0.0
        recall = matched / reference if reference else 0.0
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"matched": matched, "only_system": system - matched,
            "only_reference": reference - matched,
            "system": system, "reference": reference,
            "precision": precision, "recall": recall, "f1": f1}


def compare_pages(pages: dict[str, tuple[list[dict], list[dict]]]) -> dict:
    """Summiert die seitenweisen Treffer, statt die Quoten zu mitteln.

    Ein Mittel ueber Seiten gewichtet eine Seite mit zwei Angeboten so stark
    wie eine mit dreissig. Der Prospekt hat beides.
    """
    matched = system = reference = 0
    for own, other in pages.values():
        counts = match_deals(own, other)
        matched += counts["matched"]
        system += len(own)
        reference += len(other)
    result = _rates(matched, system, reference)
    result["pages"] = len(pages)
    return result
