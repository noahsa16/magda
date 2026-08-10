"""Urteile der Handprüfung auf einen Labelordner anwenden.

Geschrieben wird immer in einen *neuen* Ordner. `data/labeled/sonnet-5/` ist
die Referenz, gegen die alle bisherigen Zahlen gemessen wurden; wer sie in
place korrigiert, verschiebt deren Grundlage, ohne dass es jemand sieht.
Zwei Ordner nebeneinander machen den Effekt der Übernahme dagegen messbar –
dieselbe Trennung wie zwischen `gold/offers/` und `data/offer_groups/`.

Ein Urteil, das nicht anwendbar ist, bricht ab statt übersprungen zu werden:
eine halb angewandte Korrektur macht den Ordner um genau den Betrag falsch,
den niemand bemerkt. Genau eine Ausnahme davon ist kein Fehler, sondern eine
offene Frage – siehe `unresolved` unten.

Umgetragen wird der **ganze Span**, nicht das beurteilte Wort. Der Mensch hat
im Annotator eine Entity angeklickt; nur ihr erstes Wort umzuschreiben ergäbe
`B-APP_PRICE I-PRICE`, und `bio_to_spans` machte daraus zwei Entities.
"""

from __future__ import annotations

import json
from pathlib import Path


def _span_bounds(tags: list[str], index: int) -> tuple[int, int]:
    """Grenzen des BIO-Spans, in dem `index` liegt (Ende exklusiv)."""
    if tags[index] == "O":
        return index, index + 1
    start = index
    while start > 0 and tags[start].startswith("I-"):
        start -= 1
    end = index + 1
    while end < len(tags) and tags[end].startswith("I-"):
        end += 1
    return start, end


def apply_verdicts(verdicts: dict, source, target) -> dict:
    """Wendet `{"<page_id>:<index>": {...}}` auf einen Labelordner an.

    Rückgabe: `pages` geschriebene Seiten, `changed` geänderte Spans,
    `confirmed` bestätigte Urteile und `unresolved` die Schlüssel, bei denen
    der Mensch das alte Label verworfen, aber kein neues genannt hat. Die
    bleiben unverändert – ein Ersatzlabel zu raten wäre eine Vermutung im
    Gewand einer Handannotation.
    """
    from magda.labels import ENTITY_TYPES

    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve():
        raise ValueError(
            "Ziel und Quelle sind derselbe Ordner. data/labeled/ ist die "
            "Referenz, gegen die gemessen wird, und wird nicht überschrieben."
        )
    target.mkdir(parents=True, exist_ok=True)

    by_page: dict[str, list[tuple[int, dict]]] = {}
    for key, verdict in verdicts.items():
        page_id, _, index = key.rpartition(":")
        if not page_id or not index.isdigit():
            raise ValueError(f"Unlesbarer Urteilsschlüssel: {key}")
        by_page.setdefault(page_id, []).append((int(index), verdict))

    known = {p.stem for p in source.glob("*.json")}
    unknown = sorted(set(by_page) - known)
    if unknown:
        raise ValueError(
            f"Urteile für unbekannte Seiten: {', '.join(unknown[:5])}. "
            f"Passt die Labelquelle zu `labels_from` in der Auditdatei?"
        )

    changed = confirmed = pages = 0
    unresolved: list[str] = []
    for path in sorted(source.glob("*.json")):
        pages += 1
        payload = json.loads(path.read_text())
        tags = payload.get("tags") or []
        for index, verdict in sorted(by_page.get(path.stem, [])):
            if index >= len(tags):
                raise ValueError(
                    f"Urteil {path.stem}:{index} liegt hinter dem Seitenende "
                    f"({len(tags)} Wörter). Hat sich Schritt 02 geändert?"
                )
            if verdict.get("verdict") != "wrong":
                confirmed += 1
                continue
            wanted = (verdict.get("should_be") or "").strip()
            if not wanted:
                # Das alte Label ist verworfen, ein neues nicht genannt.
                unresolved.append(f"{path.stem}:{index}")
                continue
            if wanted not in ENTITY_TYPES:
                raise ValueError(
                    f"Unbekannter Labeltyp {wanted!r} in Urteil "
                    f"{path.stem}:{index}. Bekannt: {', '.join(ENTITY_TYPES)}"
                )
            start, end = _span_bounds(tags, index)
            neu = [f"B-{wanted}"] + [f"I-{wanted}"] * (end - start - 1)
            if tags[start:end] != neu:
                tags[start:end] = neu
                changed += 1
        payload["tags"] = tags
        (target / path.name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False))

    return {"pages": pages, "changed": changed, "confirmed": confirmed,
            "unresolved": unresolved}
