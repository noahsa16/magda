"""Angebotscluster aus gelabelten Wortspans bauen.

Token-Labels sagen nur: dieses Wort ist PRICE, jenes PRODUCT. Fuer die
eigentliche Information Extraction fehlt der zweite Schritt: Welche dieser
Entities gehoeren auf der Seite zusammen? Dieses Modul gruppiert die gelabelten
Spans heuristisch zu Angebotsbloecken und persistiert sie als relationale Daten.

Zweistufig statt Anker-Abstimmung: Zuerst werden Beschreibungs-Entities
(PRODUCT, BRAND, QUANTITY, UNIT_PRICE, VALID) rein nach visueller Naehe zu
Bloecken zusammengefasst - unabhaengig davon, wo der Preis am Ende landet.
Preis-Badges (PRICE, APP_PRICE, OLD_PRICE, DISCOUNT) werden separat und
ebenso eng geclustert. Erst danach werden Badges den Bloecken zugeordnet,
bevorzugt ueber Menge x Grundpreis. Der fruehere Ansatz liess jede Entity
unabhaengig fuer den naechsten Preis-Anker abstimmen - dabei konnte die Marke
an einen anderen Preis andocken als das Produkt direkt daneben, sobald ein
Nachbarprodukt zufaellig naeher am selben Anker lag (belegter Fall:
FREIXENET/HARIBO auf 1351497_p1).
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
# OLD_PRICE/DISCOUNT haengen visuell am Preis-Sticker, nicht am Produkttext -
# sie bilden mit PRICE/APP_PRICE eine eigene Gruppe (Badges). UNIT_PRICE
# dagegen steht im Layout fast immer direkt unter QUANTITY, beim Produkt, und
# gehoert deshalb zu den Beschreibungs-Entities.
BADGE_TYPES = {"PRICE", "APP_PRICE", "OLD_PRICE", "DISCOUNT"}
DESCRIPTION_TYPES = VALUE_TYPES - BADGE_TYPES


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


def _distance_to_anchor(entity: Entity, anchor: Entity, page: dict) -> float:
    """Gewichtete Distanz, hoehenlastig: zwei Entities auf gleicher Zeile
    gehoeren eher zusammen als zwei mit gleichem x aber verschiedener Zeile."""
    width = max(1.0, float(page.get("width") or 1.0))
    height = max(1.0, float(page.get("height") or 1.0))
    ex, ey = _center(entity.bbox)
    ax, ay = _center(anchor.bbox)

    dy = abs(ey - ay) / height
    dx = abs(ex - ax) / width
    same_band_bonus = 0.0 if dy <= 0.13 else 0.35
    left_of_price_bonus = -0.08 if ex <= ax and dy <= 0.18 else 0.0
    return dy * 2.8 + dx * 0.55 + same_band_bonus + left_of_price_bonus


def _distance_between_offers(a: Offer, b: Offer, page: dict) -> float:
    return min(_distance_to_anchor(ea, eb, page) for ea in a.entities for eb in b.entities)


def _gap(a: Entity, b: Entity) -> tuple[float, float]:
    """Pixelluecke zwischen zwei Bounding-Boxen in x und y; 0 bei Ueberlappung."""
    dx = max(0.0, b.bbox[0] - a.bbox[2], a.bbox[0] - b.bbox[2])
    dy = max(0.0, b.bbox[1] - a.bbox[3], a.bbox[1] - b.bbox[3])
    return dx, dy


def _same_block(a: Entity, b: Entity, page: dict) -> bool:
    """Zwei Entities gehoeren zum selben Textblock, wenn ihre Boxen in beiden
    Achsen eng beieinander liegen. Anders als bei der Anker-Suche zaehlt hier
    keine Gewichtung zwischen Achsen: ein grosser x-Abstand trennt genauso
    zuverlaessig wie ein grosser y-Abstand (belegter Fall: SCHWARTAU/NUTELLA,
    y-Luecke klein, x-Luecke gross - zwei verschiedene Produkte)."""
    width = max(1.0, float(page.get("width") or 1.0))
    height = max(1.0, float(page.get("height") or 1.0))
    dx, dy = _gap(a, b)
    return dx / width <= 0.10 and dy / height <= 0.02


class _UnionFind:
    def __init__(self, ids: list[int]) -> None:
        self._parent = {i: i for i in ids}

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self._parent[rx] = ry


def _cluster_tight(entities: list[Entity], page: dict) -> list[list[Entity]]:
    """Fasst Entities zu Bloecken zusammen, deren Boxen eng beieinander liegen.

    O(n^2) Paarvergleiche - auf einer Prospektseite mit einigen hundert
    Entities unproblematisch, eine Rasterung nach Position lohnt sich hier
    nicht.
    """
    if not entities:
        return []
    uf = _UnionFind([e.id for e in entities])
    for i, a in enumerate(entities):
        for b in entities[i + 1:]:
            if _same_block(a, b, page):
                uf.union(a.id, b.id)
    groups: dict[int, list[Entity]] = {}
    for e in entities:
        groups.setdefault(uf.find(e.id), []).append(e)
    return list(groups.values())


def _split_multi_product(component: list[Entity], page: dict) -> list[list[Entity]]:
    """Trennt einen Block mit mehreren Produkten in einzelne Angebote auf.

    Zwei Ebenen, in dieser Reihenfolge: zuerst ueber mehrere Marken, sonst
    ueber mehrere PRODUCT-Entities. Beide nur, wenn jeder Anker seine EIGENE
    Menge in der Naehe hat: SOLVEL x3 sind drei echte Produkte, jedes mit
    eigener Menge und eigenem Grundpreis (1351497_p13). Fanta/Coca-Cola
    dagegen ist EIN Angebot mit zwei Markennamen und einer gemeinsamen Menge
    ("2 l") - das bleibt ein Block, sonst reisst der Split ein echtes
    Mehrmarken-Angebot auseinander.

    Die zweite Ebene (PRODUCT statt BRAND) deckt Faelle ab, in denen zwei
    Produkte ein Foto teilen, aber nur eines eine eigene Marke hat - Hähnchen
    und Trauben unter einem Foto, nur das Hähnchen mit MÜHLENHOF (1351497_p1):
    zwei BRAND-Entities gibt es dort nicht, aber zwei PRODUCT-Entities mit je
    eigener Menge und eigenem Grundpreis.

    Rekursiv, weil der Marken-Split allein hier nicht reicht: die MÜHLENHOF-
    Gruppe hat nach der Trennung von HARIBO immer noch Hähnchen *und* Trauben
    zusammen (Trauben hat keine eigene Marke), und "hat eine Menge" ist als
    Abbruchkriterium erfuellt, obwohl innerhalb der Gruppe noch zwei Produkte
    stecken. Jede entstehende Untergruppe wird deshalb erneut versucht zu
    splitten, bis keine Ebene mehr greift.

    Eigene Menge reicht als Kriterium allein nicht: HARIBO Goldbären und
    Pico-Balla haben je ihre eigene Menge (205 g / 190 g), teilen sich aber
    einen Preis ("je 205 g oder 190 g, 0.69"). Getrennt bekaeme nur eine
    Variante den Preis. Erst wenn die erwarteten Preise (Menge x Grundpreis)
    zwischen den Gruppen wirklich verschieden sind, ist der Split gerechtfertigt.
    """
    for anchor_type in ("BRAND", "PRODUCT"):
        anchors = [e for e in component if e.type == anchor_type]
        if len(anchors) < 2:
            continue

        def nearest(entity: Entity, anchors: list[Entity] = anchors) -> Entity:
            return min(anchors, key=lambda a: _distance_to_anchor(entity, a, page))

        by_anchor: dict[int, list[Entity]] = {a.id: [a] for a in anchors}
        for entity in component:
            if entity.type == anchor_type:
                continue
            by_anchor[nearest(entity).id].append(entity)

        groups = list(by_anchor.values())
        if not all(any(e.type == "QUANTITY" for e in members) for members in groups):
            continue

        price_sets = [set(_expected_prices(_make_offer("_tmp", 0, m), page)) for m in groups]
        shares_price = any(
            a & b for i, a in enumerate(price_sets) for b in price_sets[i + 1:]
        )
        if shares_price:
            continue

        result: list[list[Entity]] = []
        for members in groups:
            result.extend(_split_multi_product(members, page))
        return result

    return [component]


def _attach_orphan_descriptions(blocks: list[list[Entity]], page: dict) -> list[list[Entity]]:
    """Haengt Mengen-/Grundpreiszeilen an den Produktblock darueber an.

    Das Naehe-Clustering trennt bei jeder Luecke ueber 2 % der Seitenhoehe,
    und zwischen Produkttext und Mengenzeile steht oft unbeschrifteter Text
    ("je", Fussnoten) - der Block reisst dann mitten im Angebot. Uebrig bleibt
    eine Mengenzeile ohne Produkt, die anschliessend den Preis abfaengt, der
    eigentlich zum Produkt darueber gehoert (belegter Fall: FANTA/COCA-COLA
    auf 1351497_p1, "2 l" und "(1 l = 0.65)" getrennt vom Markennamen).

    Gemessen ueber den Korpus ist die Fortsetzung derselben Kachel an zwei
    Merkmalen erkennbar: die linke Textkante fluchtet exakt (Median 0.0 px),
    und die Luecke betraegt rund eine Zeilenhoehe. Gueltigkeitsbanner, die
    ebenfalls ohne Produkt dastehen, liegen dagegen 240 bis 739 px entfernt
    und werden von der Abstandsgrenze zuverlaessig ausgeschlossen. VALID-only
    Rumpfbloecke bleiben ohnehin aussen vor - ein Banner gehoert der Seite,
    nicht einem Angebot.
    """
    width = max(1.0, float(page.get("width") or 1.0))
    height = max(1.0, float(page.get("height") or 1.0))

    with_product = [b for b in blocks if any(e.type in ("PRODUCT", "BRAND") for e in b)]
    if not with_product:
        return blocks

    result: list[list[Entity]] = []
    for block in blocks:
        if any(e.type in ("PRODUCT", "BRAND") for e in block):
            result.append(block)
            continue
        if not any(e.type in ("QUANTITY", "UNIT_PRICE") for e in block):
            result.append(block)
            continue

        bbox = _union_bbox([e.bbox for e in block])
        candidates = []
        for target in with_product:
            tbox = _union_bbox([e.bbox for e in target])
            if abs(bbox[0] - tbox[0]) / width > 0.012:
                continue
            gap = bbox[1] - tbox[3]  # nur nach unten: die Menge steht unter dem Produkt
            if 0 <= gap / height <= 0.05:
                candidates.append((gap, target))
        if candidates:
            candidates.sort(key=lambda c: c[0])
            candidates[0][1].extend(block)
        else:
            result.append(block)
    return result


def _split_multi_price(component: list[Entity], page: dict) -> list[list[Entity]]:
    """Trennt einen Preis-Block mit mehreren PRICE- oder APP_PRICE-Entities.

    Anders als bei Produkten (`_split_multi_product`) braucht es keine
    Zusatzpruefung: ein einzelnes Angebot hat nie zwei verschiedene reguläre
    Preise gleichzeitig, waehrend Preis-Sticker benachbarter Produkte auf
    dichten Seiten durchaus nah genug beieinander liegen koennen, um von der
    Naehe-Schwelle faelschlich zusammengefasst zu werden.
    """
    prices = [e for e in component if e.type == "PRICE"]
    app_prices = [e for e in component if e.type == "APP_PRICE"]
    if len(prices) <= 1 and len(app_prices) <= 1:
        return [component]

    anchors = prices + app_prices

    def nearest_anchor(entity: Entity) -> Entity:
        return min(anchors, key=lambda a: _distance_to_anchor(entity, a, page))

    by_anchor: dict[int, list[Entity]] = {a.id: [a] for a in anchors}
    for entity in component:
        if entity.type in PRICE_TYPES:
            continue
        by_anchor[nearest_anchor(entity).id].append(entity)
    return list(by_anchor.values())


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

    Kein Kreuzprodukt aus allen QUANTITY- und UNIT_PRICE-Entities: landen
    mehrere Produkte im selben Block (Grenzfall des Naehe-Clusterings),
    erzeugt das Kreuzprodukt Zufallstreffer aus Menge und fremdem Grundpreis.
    Die Naehe-Schwelle nimmt trotzdem ALLE nahen Treffer, nicht nur den
    naechsten: ein Produkt mit regulaerem und App-Preis zeigt oft zwei
    Grundpreise auf gleicher Hoehe nebeneinander (Burger Patties,
    1351497_p10), und beide gehoeren zur selben Menge.
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


# Fallback-Grenze fuer Preis-Badges ohne Grundpreis-Beleg (kein UNIT_PRICE
# gelabelt): geometrische Naehe allein, dieselbe Groessenordnung wie die
# frueheren Akzeptanzschwellen der Anker-Suche.
_NEARBY_LIMIT = 0.6


def _match_badges(blocks: list[Offer], badges: list[Offer], page: dict) -> list[Offer]:
    """Ordnet Preis-Badges den Beschreibungsbloecken zu, denen sie gehoeren.

    Zuerst ueber Menge x Grundpreis: das Signal ist unabhaengig von der
    Position auf der Seite und loest Faelle, in denen ein Preis geometrisch
    naeher am Nachbarprodukt sitzt als am eigenen (belegter Fall:
    1351497_p10, Burger Patties/Lammspiesse). Fehlt eine pruefbare Menge,
    zaehlt die geometrische Naehe als Rueckfall, mit einer Mindestnaehe -
    sonst wuerde jedes uebrig gebliebene Badge irgendeinem Block angehaengt.

    Ein Block bekommt hoechstens ein PRICE und hoechstens ein APP_PRICE -
    ein zweiter Preis desselben Typs bedeutet, dieser Block ist nicht das
    richtige Ziel, auch wenn der Wert rechnerisch passen wuerde.
    """
    expected = {id(block): _expected_prices(block, page) for block in blocks}
    unmatched: list[Offer] = []

    for badge in badges:
        price_entities = [e for e in badge.entities if e.type in PRICE_TYPES]
        if not price_entities:
            unmatched.append(badge)
            continue
        price_type = price_entities[0].type
        value = _price_value(price_entities[0].text)

        def free_of_type(block: Offer, price_type: str = price_type) -> bool:
            return not any(e.type == price_type for e in block.entities)

        grundpreis_candidates = [
            block for block in blocks
            if value is not None and free_of_type(block) and _price_matches(value, expected[id(block)])
        ]
        if grundpreis_candidates:
            target = min(grundpreis_candidates, key=lambda b: _distance_between_offers(badge, b, page))
            target.entities.extend(badge.entities)
            continue

        nearby = [block for block in blocks if free_of_type(block)]
        if nearby:
            target = min(nearby, key=lambda b: _distance_between_offers(badge, b, page))
            if _distance_between_offers(badge, target, page) <= _NEARBY_LIMIT:
                target.entities.extend(badge.entities)
                continue
        unmatched.append(badge)

    return blocks + unmatched


def cluster_page(page: dict) -> list[Offer]:
    """Gruppiert die gelabelten Entities einer Seite zu Angebotsdatensaetzen.

    Zwei getrennte Clustering-Durchlaeufe: Beschreibungs-Entities (PRODUCT,
    BRAND, QUANTITY, UNIT_PRICE, VALID) werden rein nach visueller Naehe zu
    Bloecken zusammengefasst (`_cluster_tight`, anschliessend
    `_split_multi_product` fuer Bloecke mit mehreren Marken/Produkten), Preis-Badges
    (PRICE, APP_PRICE, OLD_PRICE, DISCOUNT) ebenso, aber separat. Erst danach
    ordnet `_match_badges` jedes Badge dem passenden Block zu, bevorzugt ueber
    Menge x Grundpreis. Preis-Entities beeinflussen so nie, welcher
    Beschreibungsblock zu welchem gehoert - andernfalls kann ein Preis, der
    zufaellig naeher an der Marke des Nachbarprodukts liegt als am eigenen,
    diese Marke buchstaeblich abwerben.
    """
    page_id = page.get("page_id") or "unknown"
    entities = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]
    if not entities:
        return []

    description = [e for e in entities if e.type in DESCRIPTION_TYPES]
    badge_entities = [e for e in entities if e.type in BADGE_TYPES]

    groups: list[list[Entity]] = []
    for component in _cluster_tight(description, page):
        groups.extend(_split_multi_product(component, page))
    blocks = [
        _make_offer(page_id, i, group)
        for i, group in enumerate(_attach_orphan_descriptions(groups, page))
    ]

    badges: list[Offer] = []
    for component in _cluster_tight(badge_entities, page):
        for sub in _split_multi_price(component, page):
            badges.append(_make_offer(page_id, len(badges), sub))

    offers = _match_badges(blocks, badges, page)
    if not offers:
        return []

    for offer in offers:
        offer.entities.sort(key=lambda e: (e.bbox[1], e.bbox[0], e.start))
        offer.bbox = _union_bbox([e.bbox for e in offer.entities])
    offers.sort(key=lambda offer: (offer.bbox[1], offer.bbox[0]))
    for idx, offer in enumerate(offers):
        offer.id = idx
    return offers


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
