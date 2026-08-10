"""Die LLM-Blackbox gegen die eigene Pipeline messen.

Der Vergleich laeuft ueber die *gemeinsame* Feldmenge (name, price,
original_price). Das Blackbox-Schema kennt weder App-Preise noch
Menge/Grundpreis - ihr das anzulasten hiesse, sie an einer Aufgabe zu
messen, die sie nie hatte. Umgekehrt gilt dasselbe: unsere Zusatzfelder
zaehlen hier nicht als Vorsprung.

Gepaart wird ueber den Preis (exakt) und den Namen (unscharf): Preise sind
in einem Prospekt eindeutig, Namen variieren in Sortenzusaetzen - genau die
Grenzfrage, die im Projekt ohnehin offen ist. Jedes Angebot wird hoechstens
einmal gepaart, sonst treibt ein System seinen Recall mit Duplikaten hoch.

Beide Seiten laufen durch **dieselbe** Funktion. Wer die Blackbox unscharf
und die eigene Ausgabe exakt matcht, verzerrt in unbekannte Richtung - und
zwar in die eigene.
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
COMMON_FIELDS = ("name", "price", "original_price")

_PRICE = re.compile(r"\d+(?:[.,]\d+)?")


def parse_price(text) -> float | None:
    """Erste Zahl aus einem Wertfeld, deutsche und englische Schreibweise.

    `Offer.values()` joint mehrere Angaben mit " | ". Genommen wird die
    erste - bei Groessenvarianten ist das die in Lesereihenfolge erste, und
    die Blackbox nennt in aller Regel ebenfalls nur eine.
    """
    if text is None:
        return None
    match = _PRICE.search(str(text))
    if match is None:
        return None
    return float(match.group().replace(",", "."))


def deal_from_offer(offer) -> dict | None:
    """Projiziert ein Angebot der eigenen Pipeline auf die gemeinsame Feldmenge.

    Ohne Name *und* Preis ist es kein Angebot, sondern ein Fragment. Solche
    Bruchstuecke gelten nicht als Ausgabe: sie als Falsch-Positive zu zaehlen
    haette kein Gegenstueck auf der Blackbox-Seite, die gar keine Fragmente
    ausgibt. Gezaehlt werden sie trotzdem - `compare_pages` weist sie aus.
    """
    values = offer.values()
    name = " ".join(part for part in (values.get("brand"), values.get("product"))
                    if part).strip()
    price = parse_price(values.get("price"))
    if not name or price is None:
        return None
    return {"name": name, "price": price,
            "original_price": parse_price(values.get("old_price"))}


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def match_deals(system: list[dict], reference: list[dict],
                price_tolerance: float = 0.0) -> dict:
    """Paart zwei Angebotslisten einer Seite ueber Preis und Name."""
    unused = list(range(len(reference)))
    matched = 0
    for deal in system:
        price = deal.get("price")
        best, best_score = None, 0.0
        for index in unused:
            other = reference[index]
            if price is None or other.get("price") is None:
                continue
            if abs(float(price) - float(other["price"])) > price_tolerance:
                continue
            score = _similar(deal.get("name", ""), other.get("name", ""))
            if score >= NAME_SIMILARITY and score > best_score:
                best, best_score = index, score
        if best is not None:
            unused.remove(best)
            matched += 1

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
