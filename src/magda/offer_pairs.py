"""Entity-Paare als Merkmalsvektoren - die Eingabe der Relationsklassifikation.

`ENTITY_TYPES` zu erweitern bringt der Gruppierungsfrage nichts: BIO-Tags
koennen ausdruecken "dieses Wort ist ein Preis", aber nicht "dieser Preis
gehoert zu jenem Produkt". Und eine flache OFFER-Folge fasst die
Beschreibung (0.959), den Preis aber nicht mit (0.678) - auf `1342815_p21`
liegt der Preis bei Wort 6, sein Produkt bei Wort 166.

Paarweise gestellt verschwindet die Entfernung: Das Paar (Wort 6, Wort 166)
ist genau eine Kante, und was dazwischen steht, spielt keine Rolle. Das ist
der Standardweg der Line-Item-Literatur (DocILE arXiv:2302.05658, LiLT
arXiv:2202.13669, SPADE arXiv:2005.00642).

**Die Rechnung Menge x Grundpreis ist hier kein Merkmal, und das ist keine
Nachlaessigkeit.** Sie ist das einzige Signal im System, das sich selbst
beweist, und damit der einzige unbestechliche Richter ueber eine
Gruppierung. Gibt man sie dem Modell als Eingabe, misst `magda
offers-verify` hinterher die Rechnung gegen sich selbst - derselbe
Zirkelschluss, gegen den `offers_report` die Ablation braucht. Das
allgemeine Muster: halte das Merkmal zurueck, mit dem du hinterher richten
willst.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from magda.offers import VALUE_TYPES, entities_from_page

# Feste Reihenfolge, weil sie im Checkpoint steckt: ein Modell, das auf einer
# anderen Reihenfolge trainiert wurde, rechnet mit vertauschten Spalten
# weiter und faellt durch keine Pruefung auf.
TYPES = sorted(VALUE_TYPES)

GEOMETRY_NAMES = [
    "dx",                # Mittelpunktsdifferenz x, mit Vorzeichen
    "dy",                # dito y - "der Preis steht unter dem Produkt"
    "gap_x",             # Luecke zwischen den Boxen, 0 bei Ueberlappung
    "gap_y",
    "overlap_x",         # Anteil gemeinsamer Breite
    "overlap_y",
    "distance",          # Mittelpunktsabstand in Medianworthoehen
    "height_i",          # Boxhoehe in Medianworthoehen - der Preis-Sticker
    "height_j",          # ist groesser gesetzt als der Fliesstext
    "reading_gap",       # Abstand in der Entity-Reihenfolge
    "word_gap",          # Abstand in der Wortliste
    "entities_between",  # was dazwischen liegt, trennt
]

FEATURE_NAMES = (
    [f"type_i_{t}" for t in TYPES]
    + [f"type_j_{t}" for t in TYPES]
    + GEOMETRY_NAMES
)


@dataclass
class PagePairs:
    """Alle Entity-Paare einer Seite, samt Merkmalen und - beim Training - Labels.

    `labels` ist `None`, wenn keine Referenz vorliegt (Vorhersage), und sonst
    eine Liste aus 0, 1 und `None`. `None` heisst "nicht trainierbar", nicht
    "negativ": Wo die Referenz eine Entity gar nicht erwaehnt, hat sie
    geschwiegen, nicht "gehoert nirgends hin" gesagt.
    """

    page_id: str
    entities: list
    index_pairs: list[tuple[int, int]]
    features: list[list[float]]
    labels: list[int | None] | None = None


def _median_word_height(page: dict) -> float:
    """Der Massstab der Seite. Absolute Pixel waeren an die DPI gebunden."""
    heights = sorted(
        w["bbox"][3] - w["bbox"][1]
        for w in (page.get("words") or [])
        if len(w.get("bbox") or []) == 4
    )
    if not heights:
        return 1.0
    middle = heights[len(heights) // 2]
    return middle if middle > 0 else 1.0


def _overlap(a0: float, a1: float, b0: float, b1: float) -> tuple[float, float]:
    """(Ueberlappung, Luecke) zweier Intervalle. Eines von beiden ist immer 0."""
    shared = min(a1, b1) - max(a0, b0)
    if shared >= 0:
        return shared, 0.0
    return 0.0, -shared


def _pair_features(entity_i, entity_j, index_i: int, index_j: int,
                   context: dict) -> list[float]:
    ix0, iy0, ix1, iy1 = entity_i.bbox
    jx0, jy0, jx1, jy1 = entity_j.bbox
    width, height, scale = context["width"], context["height"], context["scale"]

    overlap_x, gap_x = _overlap(ix0, ix1, jx0, jx1)
    overlap_y, gap_y = _overlap(iy0, iy1, jy0, jy1)
    center_i = ((ix0 + ix1) / 2, (iy0 + iy1) / 2)
    center_j = ((jx0 + jx1) / 2, (jy0 + jy1) / 2)

    span_x = max(ix1 - ix0, jx1 - jx0, 1.0)
    span_y = max(iy1 - iy0, jy1 - jy0, 1.0)

    one_hot = [0.0] * (2 * len(TYPES))
    one_hot[TYPES.index(entity_i.type)] = 1.0
    one_hot[len(TYPES) + TYPES.index(entity_j.type)] = 1.0

    return one_hot + [
        (center_j[0] - center_i[0]) / width,
        (center_j[1] - center_i[1]) / height,
        gap_x / width,
        gap_y / height,
        overlap_x / span_x,
        overlap_y / span_y,
        math.dist(center_i, center_j) / scale,
        (iy1 - iy0) / scale,
        (jy1 - jy0) / scale,
        (index_j - index_i) / max(context["count"], 1),
        (entity_j.start - entity_i.end) / max(context["words"], 1),
        context["between"][(index_i, index_j)] / max(context["count"], 1),
    ]


def _entities_between(entities: list) -> dict[tuple[int, int], int]:
    """Wie viele andere Entities im umschliessenden Rechteck eines Paares liegen.

    Das ist das Merkmal, das die Legenden-Fehler ansprechbar macht: Auf
    `1347387_p31` greift jeder Preis zum naechstgelegenen Namen, und wenn der
    Abstand einmal kippt, kippt die ganze Spalte mit. Nur der Abstand kann
    das nicht unterscheiden - was dazwischen steht, schon.
    """
    centers = [((e.bbox[0] + e.bbox[2]) / 2, (e.bbox[1] + e.bbox[3]) / 2) for e in entities]
    result: dict[tuple[int, int], int] = {}
    for i in range(len(entities)):
        for j in range(i + 1, len(entities)):
            x0 = min(entities[i].bbox[0], entities[j].bbox[0])
            y0 = min(entities[i].bbox[1], entities[j].bbox[1])
            x1 = max(entities[i].bbox[2], entities[j].bbox[2])
            y1 = max(entities[i].bbox[3], entities[j].bbox[3])
            result[(i, j)] = sum(
                1 for k, (cx, cy) in enumerate(centers)
                if k not in (i, j) and x0 <= cx <= x1 and y0 <= cy <= y1
            )
    return result


def page_pairs(page: dict, assignment: dict[int, int] | None = None) -> PagePairs:
    """Alle ungeordneten Entity-Paare einer Seite als Merkmalsvektoren.

    Die Paare stehen in Lesereihenfolge (i < j). Erst dadurch duerfen die
    Deltas ein Vorzeichen tragen - ungeordnet muesste jedes Merkmal
    symmetrisch sein und "der Preis steht *unter* dem Produkt" liesse sich
    nicht ausdruecken.
    """
    from magda.offers_gold import _reference_group

    entities = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]
    context = {
        "width": max(float(page.get("width") or 0), 1.0),
        "height": max(float(page.get("height") or 0), 1.0),
        "scale": _median_word_height(page),
        "count": len(entities),
        "words": max(len(page.get("words") or []), 1),
        "between": _entities_between(entities),
    }

    groups = None
    if assignment is not None:
        groups = [_reference_group(e, assignment) for e in entities]

    index_pairs: list[tuple[int, int]] = []
    features: list[list[float]] = []
    labels: list[int | None] = []
    for i in range(len(entities)):
        for j in range(i + 1, len(entities)):
            index_pairs.append((i, j))
            features.append(_pair_features(entities[i], entities[j], i, j, context))
            if groups is not None:
                if groups[i] is None or groups[j] is None:
                    labels.append(None)
                else:
                    labels.append(1 if groups[i] == groups[j] else 0)

    return PagePairs(
        page_id=page.get("page_id") or "unknown",
        entities=entities,
        index_pairs=index_pairs,
        features=features,
        labels=labels if assignment is not None else None,
    )


def groups_from_edges(count: int, edges: dict[tuple[int, int], float],
                      threshold: float) -> list[list[int]]:
    """Kanten oberhalb der Schwelle zu Zusammenhangskomponenten verschmelzen.

    Der bekannte Preis dieses Verfahrens ist die Transitivitaet: A-B und B-C
    verschmelzen zu einer Gruppe, auch wenn A-C weit unter der Schwelle
    liegt. Bei einer Legendenspalte kann das eine ganze Seite zu einem
    Angebot machen. Wer den Effekt vermutet, sieht ihn an der
    Gruppenzahl - deshalb berichtet `magda offers-model` sie mit.
    """
    parent = list(range(count))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (i, j), score in edges.items():
        if score >= threshold:
            root_i, root_j = find(i), find(j)
            if root_i != root_j:
                parent[root_i] = root_j

    members: dict[int, list[int]] = {}
    for index in range(count):
        members.setdefault(find(index), []).append(index)
    return list(members.values())


def entity_groups_to_words(page: dict, entity_groups: list[list[int]]) -> list[list[int]]:
    """Entity-Gruppen in Wortindizes - die Einheit, die den Labellauf ueberlebt."""
    from magda.offer_teacher import expand_entity_groups

    return expand_entity_groups(page, entity_groups)
