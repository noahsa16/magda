"""Eine Seite von einem Agenten mit Bildzugriff labeln lassen.

Das Gegenstueck zu `offer_teacher`, eine Stufe frueher: dort werden fertige
Entities gruppiert, hier entstehen sie ueberhaupt erst. Beide Wege gibt es
aus demselben Grund - `sonnet-5` ist kein Modell der GWDG-API, sondern ein
Agent, der das Seitenbild selbst liest. `magda label` erreicht ihn nicht.

**Der Guard-Pfad ist der eigentliche Inhalt dieses Moduls.** Die Labels aus
KW30-32 sind durch `trim_spans` und danach durch `apply_app_price_rule`
gelaufen (`magda label --repair`, 03.08.2026). Eine neue Woche, die das
nicht taete, waere kein zusaetzlicher Datensatz, sondern ein zweiter mit
anderen Konventionen - und der Vergleich ueber die Wochen, der den ganzen
Wochen-Split traegt, waere dahin. `finish_spans` haelt die Reihenfolge fest.
"""

from magda import config
from magda.labeling import _PROMPT, apply_app_price_rule, trim_spans
from magda.labels import ENTITY_TYPES, spans_to_bio

# Ein Span ohne diese drei Felder ist keine halbe Antwort, sondern gar keine.
SPAN_KEYS = ("start", "end", "label")


def build_task(page: dict) -> dict:
    """Die Aufgabe fuer eine Seite: derselbe Prompt wie fuer die API, plus Bild.

    Bewusst `_PROMPT` und nicht eine eigene Fassung: zwei Prompts fuer
    dieselbe Aufgabe driften auseinander, und die Labels aus beiden Quellen
    lassen sich hinterher nicht mehr in einen Topf werfen.
    """
    words = page.get("words") or []
    page_id = page.get("page_id") or "unknown"
    word_list = "\n".join(f"{i}: {w['text']}" for i, w in enumerate(words))
    return {
        "page_id": page_id,
        "image": str(config.IMAGES_DIR / f"{page_id}.png"),
        "words": len(words),
        "prompt": _PROMPT.format(word_list=word_list),
    }


def valid_spans(spans: list, words: list[dict]) -> tuple[list[dict], list[str]]:
    """Trennt brauchbare Spans von kaputten und benennt jeden Verwurf.

    Anders als `offer_teacher.expand_entity_groups` wird hier *nicht* die
    ganze Seite abgelehnt. Der Grund ist die Bauart der beiden Referenzen:
    Eine vergessene Entity macht eine Gruppierung still falsch, ein
    verworfener Span dagegen macht ein Wort zu `O` - sichtbar in jeder
    Auszaehlung und ohnehin die Politik von `spans_to_bio`. Die Verwuerfe
    kommen aber zurueck, statt zu verschwinden: eine Antwort, die zur
    Haelfte durchfaellt, ist ein Fehlschlag und kein Ergebnis.
    """
    kept: list[dict] = []
    rejected: list[str] = []
    for position, span in enumerate(spans):
        if not isinstance(span, dict):
            rejected.append(f"#{position}: kein Objekt ({span!r})")
            continue
        missing = [key for key in SPAN_KEYS if key not in span]
        if missing:
            rejected.append(f"#{position}: fehlt {', '.join(missing)}")
            continue
        start, end, label = span["start"], span["end"], span["label"]
        if not isinstance(start, int) or not isinstance(end, int):
            rejected.append(f"#{position}: start/end nicht ganzzahlig ({start!r}, {end!r})")
            continue
        if label not in ENTITY_TYPES:
            rejected.append(f"#{position}: Label unbekannt ({label!r})")
            continue
        # `end` ist exklusiv - ein Span ueber das letzte Wort hat end == len(words).
        # Die Grenze als `end < len(words)` zu schreiben verwirft still jeden
        # Span am Seitenende, und das faellt an keiner Zahl auf.
        if not 0 <= start < end <= len(words):
            rejected.append(f"#{position}: {start}..{end} liegt nicht in 0..{len(words)}")
            continue
        kept.append({"start": start, "end": end, "label": label})
    return kept, rejected


def finish_spans(spans: list[dict], words: list[dict]) -> list[str]:
    """Spans zu BIO-Tags - ueber genau die Kette aus `magda label --repair`.

    `apply_app_price_rule` *nach* `trim_spans`, nicht davor: die Regel sieht
    das Wort hinter dem Span nach der Fussnote an, und `trim_spans`
    verschiebt genau dieses Ende.
    """
    cleaned = trim_spans(spans, words)
    return spans_to_bio(len(words), apply_app_price_rule(cleaned, words))


def boundary_words(model: str, label: str) -> dict[str, tuple[int, int]]:
    """Welche Woerter zieht der Bestand in `label` hinein, welche nicht?

    Gezaehlt wird das Wort *hinter* einem Span dieses Labels: einmal, wenn
    es noch dazugehoert, einmal, wenn nicht. Reine Zahlen bleiben draussen,
    sie sind nie strittig.

    Der Zweck ist die Konventionsfrage, und die stellt sich staendig neu.
    Bei `QUANTITY` sagt der Prompt "Stueck gehoert NICHT dazu", der Korpus
    aber 33:3 dafuer - wer das nicht auszaehlt, labelt eine neue Woche
    buchstabengetreu gegen die eigene Referenz. Seitenweise sieht man
    Einzelfaelle, ueber den Korpus den Widerspruch; dasselbe Argument wie
    bei den Gebinde-Komposita in CLAUDE.md.
    """
    import json
    import re

    inside: dict[str, int] = {}
    outside: dict[str, int] = {}
    directory = config.labeled_dir(model)
    for path in sorted(directory.glob("*.json")):
        with open(path) as f:
            page = json.load(f)
        tags = page.get("tags") or []
        words = [w["text"] for w in (page.get("words") or [])]
        for index in range(1, min(len(tags), len(words))):
            if not tags[index - 1].endswith(label):
                continue
            word = words[index]
            if re.match(r"^[\d,.]+$", word):
                continue
            key = word.rstrip(",.").lower()
            target = inside if tags[index].endswith(label) else outside
            target[key] = target.get(key, 0) + 1
    return {word: (inside.get(word, 0), outside.get(word, 0))
            for word in set(inside) | set(outside)}


def pending(model: str) -> list[str]:
    """Seiten aus `data/words`, fuer die dieser Labelordner nichts hat."""
    extracted = {path.stem for path in config.WORDS_DIR.glob("*.json")}
    directory = config.labeled_dir(model)
    done = {path.stem for path in directory.glob("*.json")} if directory.is_dir() else set()
    return sorted(extracted - done)
