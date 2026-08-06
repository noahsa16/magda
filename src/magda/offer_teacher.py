"""Eine Angebots-Gruppierung, die ein Vision-Modell erzeugt hat.

`gold/offers/` sollte von Hand entstehen. Das Team hat am 06.08.2026
entschieden, dass 30 bis 50 Seiten Handarbeit den Projektrahmen sprengen -
also gruppiert ein Modell, das das Seitenbild sieht. Der Unterschied darf
dabei nicht verschwinden, und deshalb liegt das Ergebnis in einem eigenen
Ordner mit `provenance` in jeder Datei:

    gold/offers/                    Mensch. Misst, ohne selbst gemessen zu werden.
    data/offer_groups/<quelle>/     Modell. Misst Uebereinstimmung, nicht Richtigkeit.

Der Sinn bleibt trotzdem erhalten, weil die Informationsquellen verschieden
sind: Die Heuristik in `offers.py` kennt nur Wortkoordinaten, das Modell sieht
den gelben Preiskasten und den tuerkisen App-Sticker. Wo beide sich einig
sind, ist das ein Argument; wo nicht, zeigt es auf eine Seite zum Nachsehen.
Was die Zahl *nicht* darf, ist als Gold auftreten - dafuer gibt es
`offers_verify`, das die Gruppierung arithmetisch gegenprueft.

**Der Teacher antwortet in Entity-Nummern, gespeichert werden Wortindizes.**
Entities sind die Einheit, in der auch der Annotator klickt - ein Angebot hat
schnell zwoelf Woerter, und wortweise zu antworten vervielfacht die Ausgabe
ohne Gewinn an Ausdruckskraft. Wortindizes sind die Einheit, die den naechsten
Labeling-Lauf ueberlebt: Spans gehoeren einem Labelordner, Woerter der Seite.
"""

from __future__ import annotations

import json
import os
import tempfile

from magda import config
from magda.gold import words_hash
from magda.offers import VALUE_TYPES, entities_from_page
from magda.offers_gold import validate_groups

# Aendert sich der Wortlaut der Aufgabe, aendert sich die Gruppierung. Ohne
# die Nummer in der Datei laesst sich hinterher nicht mehr sagen, welche
# Seiten unter welcher Anweisung entstanden sind.
PROMPT_VERSION = 1


def teacher_dir(source: str):
    """Laufzeit statt Import, damit Tests config umbiegen koennen."""
    return config.OFFER_GROUPS_DIR / config.model_slug(source)


def build_task(page: dict) -> dict:
    """Die Aufgabe fuer eine Seite: nummerierte Entities plus Seitenbild.

    Nur `VALUE_TYPES` - dieselbe Grundmenge, ueber die `offers_gold.judge_page`
    hinterher urteilt. Waere sie hier weiter, gruppierte der Teacher Entities,
    die in keiner Zahl vorkommen.
    """
    page_id = page.get("page_id") or "unknown"
    entities = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]
    return {
        "page_id": page_id,
        "image": str(config.IMAGES_DIR / f"{page_id}.png"),
        "width": page.get("width"),
        "height": page.get("height"),
        "entities": [
            {
                "index": index,
                "type": entity.type,
                "text": entity.text,
                "bbox": [round(v, 1) for v in entity.bbox],
            }
            for index, entity in enumerate(entities)
        ],
    }


def expand_entity_groups(page: dict, entity_groups: list[list[int]]) -> list[list[int]]:
    """Entity-Nummern der Aufgabe in Wortindizes der Seite uebersetzen.

    Zwei Fehler werden abgelehnt statt repariert: eine Nummer, die es nicht
    gibt (Modelle verzaehlen sich), und dieselbe Entity in zwei Angeboten.
    Still zu ignorieren hiesse, eine halbe Antwort als ganze zu speichern -
    und die Referenz waere um genau den Betrag falsch, den niemand sieht.
    """
    entities = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]
    groups: list[list[int]] = []
    seen: dict[int, int] = {}
    for group_id, group in enumerate(entity_groups):
        words: list[int] = []
        for entity_index in group:
            if not isinstance(entity_index, int) or not 0 <= entity_index < len(entities):
                raise ValueError(
                    f"Entity {entity_index} gibt es auf {page.get('page_id')} nicht "
                    f"(0..{len(entities) - 1})."
                )
            if entity_index in seen:
                raise ValueError(
                    f"Entity {entity_index} steht in zwei Angeboten "
                    f"({seen[entity_index]} und {group_id})."
                )
            seen[entity_index] = group_id
            words.extend(range(entities[entity_index].start, entities[entity_index].end))
        groups.append(sorted(words))
    return groups


def save_grouping(page: dict, groups: list[list[int]], source: str,
                  model: str | None = None, notes: str = ""):
    """Schreibt eine Gruppierung nach data/offer_groups/<quelle>/<seite>.json.

    Validiert vorher mit derselben Funktion, die auch die API benutzt: eine
    kaputte Gruppierung darf gar nicht erst auf der Platte landen, sonst
    faellt sie erst beim Messen auf und die Seite gilt als erledigt.
    """
    page_id = page.get("page_id") or "unknown"
    errors = validate_groups(groups, len(page.get("words") or []))
    if errors:
        raise ValueError(f"{page_id}: " + " ".join(errors))

    target = teacher_dir(source)
    target.mkdir(parents=True, exist_ok=True)
    payload = {
        "page_id": page_id,
        "words_hash": words_hash(page["words"]),
        "status": "done",
        "annotator": source,
        "provenance": {
            "kind": "llm",
            "source": source,
            "model": model or source,
            "prompt_version": PROMPT_VERSION,
        },
        "notes": notes,
        "groups": groups,
    }

    # Atomar wie in api.put_gold: ein abgebrochener Lauf darf keine halbe
    # Datei hinterlassen, die beim Laden als gueltige Referenz durchgeht.
    path = target / f"{page_id}.json"
    handle, temporary = tempfile.mkstemp(dir=target, suffix=".tmp")
    with os.fdopen(handle, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)
    return path
