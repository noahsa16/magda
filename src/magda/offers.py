"""Angebotscluster aus gelabelten Wortspans bauen.

Token-Labels sagen nur: dieses Wort ist PRICE, jenes PRODUCT. Fuer die
eigentliche Information Extraction fehlt der zweite Schritt: Welche dieser
Entities gehoeren auf der Seite zusammen? Dieses Modul gruppiert die gelabelten
Spans heuristisch zu Angebotsbloecken und persistiert sie als relationale Daten.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from magda.labels import ENTITY_TYPES, bio_to_spans

VALUE_TYPES = {
    "PRODUCT",
    "BRAND",
    "PRICE",
    "OLD_PRICE",
    "QUANTITY",
    "DISCOUNT",
    "VALID",
    "UNIT_PRICE",
    "APP_PRICE",
}

PRICE_TYPES = {"PRICE", "APP_PRICE"}
PRICE_NEIGHBORS = {"OLD_PRICE", "DISCOUNT", "UNIT_PRICE"}


@dataclass(frozen=True)
class Entity:
    id: int
    type: str
    text: str
    bbox: tuple[float, float, float, float]
    start: int
    end: int
    context_before: str
    context_after: str


@dataclass
class Offer:
    id: int
    page_id: str
    bbox: tuple[float, float, float, float]
    entities: list[Entity]

    def values(self) -> dict[str, str | None]:
        result: dict[str, str | None] = {entity_type.lower(): None for entity_type in ENTITY_TYPES}
        for entity_type in VALUE_TYPES:
            parts = [entity.text for entity in self.entities if entity.type == entity_type]
            result[entity_type.lower()] = " | ".join(parts) if parts else None
        return result


def _union_bbox(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _span_text(words: list[dict], start: int, end: int) -> str:
    return " ".join(w["text"] for w in words[start:end])


def _context(words: list[dict], start: int, end: int, window: int) -> tuple[str, str]:
    before_start = max(0, start - window)
    after_end = min(len(words), end + window)
    return _span_text(words, before_start, start), _span_text(words, end, after_end)


def entities_from_page(page: dict, context_window: int = 5) -> list[Entity]:
    """BIO-Tags einer Seite in Entities mit Text, Box und Kontext umwandeln."""
    words = page.get("words") or []
    tags = page.get("tags") or []
    entities: list[Entity] = []
    for idx, span in enumerate(bio_to_spans(tags)):
        start, end, entity_type = span["start"], span["end"], span["label"]
        if entity_type not in ENTITY_TYPES or end > len(words):
            continue
        before, after = _context(words, start, end, context_window)
        entities.append(
            Entity(
                id=idx,
                type=entity_type,
                text=_span_text(words, start, end),
                bbox=_union_bbox([tuple(w["bbox"]) for w in words[start:end]]),
                start=start,
                end=end,
                context_before=before,
                context_after=after,
            )
        )
    return entities


def _center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2


def _vertical_distance(a: Entity, b: Entity, page_height: float) -> float:
    _, ay = _center(a.bbox)
    _, by = _center(b.bbox)
    return abs(ay - by) / max(1.0, page_height)


def _distance_to_anchor(entity: Entity, anchor: Entity, page: dict) -> float:
    width = max(1.0, float(page.get("width") or 1.0))
    height = max(1.0, float(page.get("height") or 1.0))
    ex, ey = _center(entity.bbox)
    ax, ay = _center(anchor.bbox)

    dy = abs(ey - ay) / height
    dx = abs(ex - ax) / width
    same_band_bonus = 0.0 if dy <= 0.13 else 0.35
    left_of_price_bonus = -0.08 if ex <= ax and dy <= 0.18 else 0.0
    return dy * 2.8 + dx * 0.55 + same_band_bonus + left_of_price_bonus


def _nearest_anchor(entity: Entity, anchors: list[Entity], page: dict) -> Entity:
    return min(anchors, key=lambda anchor: (_distance_to_anchor(entity, anchor, page), anchor.id))


def _close_to_offer(entity: Entity, offer_entities: list[Entity], page: dict) -> bool:
    height = max(1.0, float(page.get("height") or 1.0))
    nearest = min(_vertical_distance(entity, other, height) for other in offer_entities)
    return nearest <= 0.09


def cluster_page(page: dict) -> list[Offer]:
    """Gruppiert die gelabelten Entities einer Seite zu Angebotsdatensaetzen.

    Preise sind die staerksten Anker, weil fast jedes Angebot einen sichtbaren
    Preisblock hat. Produkt, Marke, Menge und Grundpreis werden dem vertikal
    naechsten Preisanker zugeordnet; weit entfernte Rest-Entities bilden eigene
    Cluster. VALID bleibt meist ein Seitenfeld und wird nur aufgenommen, wenn es
    nah an einem Angebot steht.
    """
    page_id = page.get("page_id") or "unknown"
    entities = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]
    if not entities:
        return []

    price_anchors = [e for e in entities if e.type in PRICE_TYPES]
    if not price_anchors:
        return _fallback_clusters(page_id, entities)

    by_anchor: dict[int, list[Entity]] = {anchor.id: [anchor] for anchor in price_anchors}
    leftovers: list[Entity] = []
    for entity in entities:
        if entity.type in PRICE_TYPES:
            continue
        anchor = _nearest_anchor(entity, price_anchors, page)
        distance = _distance_to_anchor(entity, anchor, page)
        limit = 0.74
        if entity.type in PRICE_NEIGHBORS:
            limit = 0.55
        elif entity.type == "VALID":
            limit = 0.35
        if distance <= limit:
            by_anchor[anchor.id].append(entity)
        else:
            leftovers.append(entity)

    offers = [
        _make_offer(page_id, offer_id, members)
        for offer_id, members in enumerate(by_anchor.values())
    ]

    # Preislose Entities, die sehr nah an einem Angebot liegen, werden dort
    # nachtraeglich angehaengt. Der Rest bleibt als unvollstaendiges Angebot
    # sichtbar, statt beim Export verloren zu gehen.
    for entity in leftovers:
        candidate = min(offers, key=lambda offer: _distance_to_offer(entity, offer, page))
        if _close_to_offer(entity, candidate.entities, page):
            candidate.entities.append(entity)
            candidate.bbox = _union_bbox([e.bbox for e in candidate.entities])
        else:
            offers.append(_make_offer(page_id, len(offers), [entity]))

    for offer in offers:
        offer.entities.sort(key=lambda e: (e.bbox[1], e.bbox[0], e.start))
        offer.bbox = _union_bbox([e.bbox for e in offer.entities])
    offers.sort(key=lambda offer: (offer.bbox[1], offer.bbox[0]))
    for idx, offer in enumerate(offers):
        offer.id = idx
    return offers


def _distance_to_offer(entity: Entity, offer: Offer, page: dict) -> float:
    return min(_distance_to_anchor(entity, other, page) for other in offer.entities)


def _make_offer(page_id: str, offer_id: int, members: list[Entity]) -> Offer:
    return Offer(
        id=offer_id,
        page_id=page_id,
        bbox=_union_bbox([entity.bbox for entity in members]),
        entities=sorted(members, key=lambda e: (e.bbox[1], e.bbox[0], e.start)),
    )


def _fallback_clusters(page_id: str, entities: list[Entity]) -> list[Offer]:
    """Preislose Seiten in einfache vertikale Gruppen teilen."""
    if not entities:
        return []
    entities = sorted(entities, key=lambda e: (e.bbox[1], e.bbox[0], e.start))
    heights = [max(1.0, e.bbox[3] - e.bbox[1]) for e in entities]
    threshold = max(18.0, sorted(heights)[len(heights) // 2] * 3.0)
    groups: list[list[Entity]] = [[entities[0]]]
    for entity in entities[1:]:
        previous = groups[-1][-1]
        if entity.bbox[1] - previous.bbox[3] <= threshold:
            groups[-1].append(entity)
        else:
            groups.append([entity])
    return [_make_offer(page_id, idx, group) for idx, group in enumerate(groups)]


def write_sqlite(pages: list[dict], db_path: Path, source: str) -> dict:
    """Schreibt Angebotscluster in eine SQLite-Datenbank."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _create_schema(conn)
        conn.execute("delete from offer_entities where source = ?", (source,))
        conn.execute("delete from offers where source = ?", (source,))

        offer_count = 0
        entity_count = 0
        for page in pages:
            for offer in cluster_page(page):
                values = offer.values()
                bbox_json = json.dumps(list(offer.bbox))
                cursor = conn.execute(
                    """
                    insert into offers (
                        source, page_id, offer_index, bbox,
                        product, brand, price, old_price, quantity,
                        discount, valid, unit_price, app_price
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source,
                        offer.page_id,
                        offer.id,
                        bbox_json,
                        values["product"],
                        values["brand"],
                        values["price"],
                        values["old_price"],
                        values["quantity"],
                        values["discount"],
                        values["valid"],
                        values["unit_price"],
                        values["app_price"],
                    ),
                )
                db_offer_id = int(cursor.lastrowid)
                offer_count += 1
                for entity in offer.entities:
                    conn.execute(
                        """
                        insert into offer_entities (
                            source, offer_id, page_id, entity_type, text, bbox,
                            word_start, word_end, context_before, context_after
                        )
                        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            source,
                            db_offer_id,
                            offer.page_id,
                            entity.type,
                            entity.text,
                            json.dumps(list(entity.bbox)),
                            entity.start,
                            entity.end,
                            entity.context_before,
                            entity.context_after,
                        ),
                    )
                    entity_count += 1
        conn.commit()
    return {"pages": len(pages), "offers": offer_count, "entities": entity_count}


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists offers (
            id integer primary key autoincrement,
            source text not null,
            page_id text not null,
            offer_index integer not null,
            bbox text not null,
            product text,
            brand text,
            price text,
            old_price text,
            quantity text,
            discount text,
            valid text,
            unit_price text,
            app_price text,
            unique(source, page_id, offer_index)
        );

        create table if not exists offer_entities (
            id integer primary key autoincrement,
            source text not null,
            offer_id integer not null references offers(id) on delete cascade,
            page_id text not null,
            entity_type text not null,
            text text not null,
            bbox text not null,
            word_start integer not null,
            word_end integer not null,
            context_before text not null,
            context_after text not null
        );

        create index if not exists idx_offers_source_page
            on offers(source, page_id);
        create index if not exists idx_offer_entities_offer
            on offer_entities(offer_id);
        create index if not exists idx_offer_entities_type
            on offer_entities(source, entity_type);
        """
    )
