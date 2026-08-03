"""Angebotscluster aus gelabelten Wortspans bauen.

Token-Labels sagen nur: dieses Wort ist PRICE, jenes PRODUCT. Fuer die
eigentliche Information Extraction fehlt der zweite Schritt: Welche dieser
Entities gehoeren auf der Seite zusammen? Dieses Modul gruppiert die gelabelten
Spans heuristisch zu Angebotsbloecken und persistiert sie als relationale Daten.
"""

from __future__ import annotations

import json
import re
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


def _column_bands(entities: list[Entity], page_width: float) -> list[tuple[float, float]]:
    """Fasst x-Bereiche zu Spalten zusammen, getrennt durch eine Mindestluecke.

    `_distance_to_anchor` gewichtet die Hoehe so stark (Faktor 2.8 gegen 0.55),
    dass ein Preis der Nachbarspalte naeher wirken kann als der eigene, sobald
    beide etwa auf gleicher Hoehe liegen. Spalten wirken als harte Vorauswahl
    *vor* diesem Distanzvergleich: eine Entity darf nur dann in eine andere
    Spalte greifen, wenn ihre eigene keinen Preis-Anker enthaelt.
    """
    if not entities:
        return []
    gap = max(20.0, 0.05 * page_width)
    spans = sorted((e.bbox[0], e.bbox[2]) for e in entities)
    bands = [list(spans[0])]
    for x0, x1 in spans[1:]:
        if x0 - bands[-1][1] <= gap:
            bands[-1][1] = max(bands[-1][1], x1)
        else:
            bands.append([x0, x1])
    return [tuple(b) for b in bands]


def _band_of(bbox: tuple[float, float, float, float], bands: list[tuple[float, float]]) -> int:
    center = (bbox[0] + bbox[2]) / 2
    for i, (b0, b1) in enumerate(bands):
        if b0 <= center <= b1:
            return i
    return min(range(len(bands)), key=lambda i: min(abs(center - bands[i][0]), abs(center - bands[i][1])))


def _close_to_offer(entity: Entity, offer_entities: list[Entity], page: dict) -> bool:
    height = max(1.0, float(page.get("height") or 1.0))
    nearest = min(_vertical_distance(entity, other, height) for other in offer_entities)
    return nearest <= 0.09


def cluster_page(page: dict) -> list[Offer]:
    """Gruppiert die gelabelten Entities einer Seite zu Angebotsdatensaetzen.

    Preise sind die staerksten Anker, weil fast jedes Angebot einen sichtbaren
    Preisblock hat. Produkt, Marke, Menge und Grundpreis werden dem vertikal
    naechsten Preisanker zugeordnet, aber nur innerhalb der eigenen Spalte
    (siehe `_column_bands`) – erst wenn die eigene Spalte keinen Preis
    enthaelt, darf eine Entity ueber die Spaltengrenze greifen. Weit entfernte
    Rest-Entities bilden eigene Cluster. VALID bleibt meist ein Seitenfeld und
    wird nur aufgenommen, wenn es nah an einem Angebot steht. Ein letzter
    Durchlauf (`_reconcile_prices`) korrigiert Preise, die geometrisch beim
    falschen Angebot gelandet sind, ueber Menge x Grundpreis.
    """
    page_id = page.get("page_id") or "unknown"
    entities = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]
    if not entities:
        return []

    price_anchors = [e for e in entities if e.type in PRICE_TYPES]
    if not price_anchors:
        return _fallback_clusters(page_id, entities)

    width = float(page.get("width") or 1.0)
    bands = _column_bands(entities, width)
    anchor_band = {anchor.id: _band_of(anchor.bbox, bands) for anchor in price_anchors}

    by_anchor: dict[int, list[Entity]] = {anchor.id: [anchor] for anchor in price_anchors}
    leftovers: list[Entity] = []
    for entity in entities:
        if entity.type in PRICE_TYPES:
            continue
        own_band = _band_of(entity.bbox, bands)
        same_column = [a for a in price_anchors if anchor_band[a.id] == own_band]
        candidates = same_column or price_anchors
        anchor = _nearest_anchor(entity, candidates, page)
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

    offers = _reconcile_prices(offers, page)

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


_QUANTITY_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*-?\s*(kg|g|ml|l)\b", re.IGNORECASE)
_UNIT_PRICE_RE = re.compile(r"1\s*(kg|l)\s*=\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
_NUMBER_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


def _to_float(text: str) -> float:
    return float(text.replace(",", "."))


def _price_value(text: str) -> float | None:
    match = _NUMBER_RE.search(text)
    return _to_float(match.group(1)) if match else None


def _quantity_in_unit(text: str, unit: str) -> float | None:
    """Menge in derselben Einheit wie ein Grundpreis, z.B. "800-g-Packung" -> 0.8 fuer unit="kg".

    Mehrfachpackungen ("6 x 1,5 l") werden nicht erkannt - das Regex liest nur
    das erste Zahl-Einheit-Paar, ohne den Multiplikator. Bewusst kein Fehler:
    ein falscher Erwartungswert findet dann einfach keinen passenden Preis und
    aendert nichts, statt eine falsche Zuordnung zu erzwingen.
    """
    match = _QUANTITY_RE.search(text)
    if not match:
        return None
    value, found_unit = _to_float(match.group(1)), match.group(2).lower()
    if unit == "kg" and found_unit == "g":
        return value / 1000
    if unit == "l" and found_unit == "ml":
        return value / 1000
    return value if found_unit == unit else None


def _expected_prices(offer: Offer, page: dict) -> list[float]:
    """Menge x Grundpreis je QUANTITY, nur fuer UNIT_PRICE-Entities in der Naehe.

    Kein Kreuzprodukt aus allen QUANTITY- und UNIT_PRICE-Entities: landen durch
    einen Clustering-Fehler in Pass 1 mehrere Produkte im selben Angebot (siehe
    1351497_p13, wo Grundpreise eines dritten Produkts ohne eigene Menge
    mithineinrutschen), erzeugt das Kreuzprodukt Zufallstreffer aus Menge und
    fremdem Grundpreis. Die Naehe-Schwelle nimmt trotzdem ALLE nahen Treffer,
    nicht nur den naechsten: ein Produkt mit regulaerem und App-Preis zeigt
    oft zwei Grundpreise auf gleicher Hoehe nebeneinander (belegter Fall:
    1351497_p10, Burger Patties), und beide gehoeren zur selben Menge.
    """
    width = max(1.0, float(page.get("width") or 1.0))
    height = max(1.0, float(page.get("height") or 1.0))

    unit_prices = []
    for entity in offer.entities:
        if entity.type != "UNIT_PRICE":
            continue
        match = _UNIT_PRICE_RE.search(entity.text)
        if match:
            unit_prices.append((entity, match.group(1).lower(), _to_float(match.group(2))))
    if not unit_prices:
        return []

    expected = []
    for entity in offer.entities:
        if entity.type != "QUANTITY":
            continue
        qx, qy = _center(entity.bbox)
        for up_entity, unit, per_unit in unit_prices:
            qty = _quantity_in_unit(entity.text, unit)
            if qty is None:
                continue
            ux, uy = _center(up_entity.bbox)
            if abs(qy - uy) / height <= 0.05 and abs(qx - ux) / width <= 0.18:
                expected.append(round(qty * per_unit, 2))
    return expected


def _price_matches(value: float, expected: list[float]) -> bool:
    return any(abs(value - exp) <= max(0.02, 0.015 * exp) for exp in expected)


def _is_orphan_badge(offer: Offer) -> bool:
    """Ein Angebot ohne PRODUCT/BRAND ist nur ein losgeloester Preis-Sticker."""
    return not any(e.type in ("PRODUCT", "BRAND") for e in offer.entities)


def _is_trustworthy_target(offer: Offer, page: dict) -> bool:
    """Nur ein geometrisch zusammenhaengendes Angebot darf einen Preis dazugewinnen.

    Reines Zaehlen (genau ein PRODUCT) haette Angebote ausgeschlossen, deren
    Produkttext nur durch einen Zeilenumbruch in zwei PRODUCT-Spans zerfaellt
    (z.B. "getraenk," + "versch. Sorten," auf zwei Zeilen desselben Angebots).
    Entscheidend ist stattdessen, ob PRODUCT/BRAND eng beieinander liegen: bei
    einem echten Clustering-Fehler aus Pass 1, der mehrere Produkte vermischt
    (siehe 1351497_p13), liegen sie ueber mehrere Zeilenabstaende auseinander.
    Ein Ziel ganz ohne PRODUCT/BRAND haette ohnehin keinen erkennbaren Bezug.
    """
    height = max(1.0, float(page.get("height") or 1.0))
    markers = [e for e in offer.entities if e.type in ("PRODUCT", "BRAND")]
    if not markers:
        return False
    y0 = min(e.bbox[1] for e in markers)
    y1 = max(e.bbox[3] for e in markers)
    return (y1 - y0) / height <= 0.1


def _reconcile_prices(offers: list[Offer], page: dict) -> list[Offer]:
    """Verschiebt Preise zu dem Angebot, zu dem sie laut Grundpreis gehoeren.

    Preisbadges sitzen auf manchen Seiten weiter von ihrem eigenen Produkt
    entfernt als vom Preisbadge des Nachbarprodukts (belegter Fall:
    1351497_p10, Grundpreis widerlegt die geometrisch naheliegende
    Zuordnung). Geometrie kann das nicht sicher trennen, Arithmetik schon:
    Menge x Grundpreis ergibt fast immer wieder den Verkaufspreis, und dieses
    Signal ist unabhaengig von der Position auf der Seite.

    Ein Angebot ohne eigene Menge/Grundpreis-Angabe (expected == []) hat keinen
    pruefbaren Erwartungswert - das heisst nicht "falsch", sondern "unbekannt".
    Ein echtes Angebot mit PRODUCT oder BRAND bleibt in diesem Fall unangetastet,
    sonst wuerde ein zufaellig gleicher Preis anderswo (z.B. zwei Artikel bei
    5.99) es leerraeumen. Nur reine Preis-Sticker ohne Produkt duerfen umziehen,
    wenn irgendwo ein Angebot ihren Wert rechnerisch erwartet.

    Erst einsammeln, dann verteilen, statt live waehrend der Iteration zu
    verschieben: sonst haengt das Ergebnis von der zufaelligen Reihenfolge der
    Angebote ab, in der ein bereits leergeraeumtes Angebot als Ziel erscheint
    oder nicht. Passen mehrere Angebote rechnerisch zum selben Preis (zwei
    Artikel erwarten beide 1.29), entscheidet die geometrische Naehe zur
    urspruenglichen Position - der Grundpreis sagt nur, wer in Frage kommt,
    nicht wer es tatsaechlich ist.
    """
    expected = {id(offer): _expected_prices(offer, page) for offer in offers}

    pool: list[tuple[Entity, list[Entity], Offer]] = []
    for offer in offers:
        own_expected = expected[id(offer)]
        price_entities = [e for e in offer.entities if e.type in PRICE_TYPES]
        for entity in price_entities:
            value = _price_value(entity.text)
            if value is None:
                continue
            if own_expected:
                if _price_matches(value, own_expected):
                    continue
            elif not _is_orphan_badge(offer):
                continue
            offer.entities.remove(entity)
            # OLD_PRICE/DISCOUNT gehoeren zu genau diesem Preis-Sticker, nicht
            # zum Zielangebot - sie muessen mitziehen, sonst bleiben sie als
            # Rumpf ohne Preis zurueck. Nur eindeutig, wenn das Angebot ohnehin
            # bloss einen Preis hatte; bei mehreren (PRICE + APP_PRICE) bleiben
            # sie beim verbleibenden Preis, statt geraten zu werden.
            companions = []
            if len(price_entities) == 1:
                for companion in list(offer.entities):
                    if companion.type in ("OLD_PRICE", "DISCOUNT"):
                        offer.entities.remove(companion)
                        companions.append(companion)
            pool.append((entity, companions, offer))

    for entity, companions, source in pool:
        value = _price_value(entity.text)
        candidates = [
            o for o in offers
            if _is_trustworthy_target(o, page)
            and not any(e.type == entity.type for e in o.entities)
            and _price_matches(value, expected[id(o)])
        ]
        if candidates:
            target = min(candidates, key=lambda o: _distance_to_offer(entity, o, page))
        elif not any(e.type == entity.type for e in source.entities):
            # kein besseres Ziel gefunden - zurueck ins Ursprungsangebot,
            # aber nur wenn das nicht inzwischen (durch einen anderen Preis
            # aus dem Pool) selbst schon einen Preis desselben Typs bekommen
            # hat. Sonst entstuende genau das Duplikat, das die Pruefung oben
            # verhindern soll.
            target = source
        else:
            target = None
        if target is not None:
            target.entities.append(entity)
            target.entities.extend(companions)

    remaining = [offer for offer in offers if offer.entities]
    for offer in remaining:
        offer.bbox = _union_bbox([e.bbox for e in offer.entities])
    return remaining


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
