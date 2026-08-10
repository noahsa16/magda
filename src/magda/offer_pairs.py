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
from dataclasses import dataclass, field
from functools import lru_cache

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

CONTEXT_NAMES = [
    "products_between",  # ein zweiter Produktanker dazwischen trennt
    "closer_rivals_i",   # wie viele des eigenen Typs naeher am Partner liegen
    "closer_rivals_j",
    "distance_ratio",    # Abstand im Verhaeltnis zur naechsten Alternative
    "words_between",     # ungelabelte Woerter - Kleingedrucktes trennt
]

COLOR_NAMES = [
    "bg_distance",       # RGB-Abstand der Hintergruende: gleiche Kachel?
    "path_same_bg",      # Anteil der Verbindungslinie in einem der Hintergruende
    "bg_offpage_i",      # steht die Entity auf einer Kachel oder auf Grund?
    "bg_offpage_j",
]

# Anker eines Angebots. Ein Angebot ist ein Stern um genau einen Produktnamen;
# Preis-Badges schweben dagegen frei, ein fremder PRICE dazwischen trennt
# deshalb *nicht* zuverlaessig (deshalb kein `prices_between`).
ANCHOR_TYPES = frozenset({"PRODUCT", "BRAND"})

# Kappung des Abstandsverhaeltnisses. Ungekappt fittet das MLP Ausreisser
# am Seitenrand, wo die naechste Alternative sehr weit weg liegt.
RATIO_CAP = 5.0

# Wie viele Punkte auf der Verbindungslinie hoechstens abgetastet werden.
# Mehr kostet nur Zeit: die Linie ist selten laenger als eine halbe Seite.
PATH_SAMPLES = 200

# Blockgroesse der Glaettung. Sie ersetzt den frueheren 3x3-Median je
# Abtastpunkt und wird einmal je Seite gerechnet.
SMOOTH_FACTOR = 3

# Groesster moeglicher RGB-Abstand, damit `bg_distance` in [0, 1] liegt.
COLOR_MAX = math.sqrt(3 * 255 ** 2)

# Bloecke, weil die Messung sie einzeln an- und abschalten muss (2x2-Gitter:
# Basis, +Geometrie, +Farbe, +beide). Die Reihenfolge ist fest und neue
# Bloecke haengen hinten an - sonst zeigt jedes gelernte Gewicht auf eine
# andere Spalte, und das faellt durch keine Pruefung auf.
FEATURE_BLOCKS: dict[str, list[str]] = {
    "types": [f"type_i_{t}" for t in TYPES] + [f"type_j_{t}" for t in TYPES],
    "geometry_base": GEOMETRY_NAMES,
    "geometry_plus": CONTEXT_NAMES,
    "color": COLOR_NAMES,
}
BLOCK_ORDER = ("types", "geometry_base", "geometry_plus", "color")

DEFAULT_BLOCKS = ("types", "geometry_base")
GEOMETRY_BLOCKS = ("types", "geometry_base", "geometry_plus")
ALL_BLOCKS = BLOCK_ORDER


def feature_names(blocks=DEFAULT_BLOCKS) -> list[str]:
    """Die Merkmalsnamen der gewaehlten Bloecke, in fester Reihenfolge."""
    unknown = [b for b in blocks if b not in FEATURE_BLOCKS]
    if unknown:
        raise ValueError(
            f"Merkmalsblock unbekannt: {', '.join(unknown)}. "
            f"Bekannt sind: {', '.join(BLOCK_ORDER)}."
        )
    return [name for block in BLOCK_ORDER if block in blocks
            for name in FEATURE_BLOCKS[block]]


# Die heutigen 30 - bleibt als Name bestehen, weil Checkpoints und der
# Verboten-Test darauf zeigen.
FEATURE_NAMES = feature_names(DEFAULT_BLOCKS)


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
    feature_names: list[str] = field(default_factory=lambda: list(FEATURE_NAMES))


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


def _center(bbox) -> tuple[float, float]:
    x0, y0, x1, y1 = bbox
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def _enclosing(a, b) -> tuple[float, float, float, float]:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _inside(point, rect) -> bool:
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


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

    geometry = [
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

    parts = {"types": one_hot, "geometry_base": geometry}
    if "geometry_plus" in context["blocks"]:
        parts["geometry_plus"] = _context_features(
            entity_i, entity_j, index_i, index_j, context)
    if "color" in context["blocks"]:
        parts["color"] = _color_features(index_i, index_j, context)

    return [v for block in BLOCK_ORDER if block in parts for v in parts[block]]


def _context_features(entity_i, entity_j, index_i: int, index_j: int,
                      context: dict) -> list[float]:
    """Anker, Konkurrenz und ungelabelte Woerter zwischen dem Paar.

    Alle fuenf beantworten dieselbe Frage von verschiedenen Seiten: Steht
    zwischen diesen beiden etwas, das sie trennt - und gibt es einen
    besseren Kandidaten als den Partner? Der Legendenversatz ist ein
    Margenproblem, kein Abstandsproblem: der falsche Name ist nur *knapp*
    naeher.
    """
    entities = context["entities"]
    rect = _enclosing(entity_i.bbox, entity_j.bbox)
    count = max(context["count"], 1)

    products = sum(
        1 for k, e in enumerate(entities)
        if k not in (index_i, index_j)
        and e.type in ANCHOR_TYPES
        and _inside(_center(e.bbox), rect)
    )

    words = sum(
        1 for w in context["word_boxes"]
        if _inside(_center(w), rect)
    ) - (entity_i.end - entity_i.start) - (entity_j.end - entity_j.start)

    center_i, center_j = _center(entity_i.bbox), _center(entity_j.bbox)
    distance = math.dist(center_i, center_j)

    by_type = context["by_type"]
    rivals_i = sum(
        1 for k in by_type.get(entity_i.type, ())
        if k != index_i and math.dist(_center(entities[k].bbox), center_j) < distance
    )
    rivals_j = sum(
        1 for k in by_type.get(entity_j.type, ())
        if k != index_j and math.dist(_center(entities[k].bbox), center_i) < distance
    )

    # Der Abstand zum naechsten Kandidaten vom Typ j - j selbst zaehlt mit,
    # das Verhaeltnis ist also immer >= 1 und genau dann 1, wenn j der
    # naechste ist.
    nearest = min(
        (math.dist(_center(entities[k].bbox), center_i)
         for k in by_type.get(entity_j.type, ())),
        default=distance,
    )
    ratio = distance / nearest if nearest > 0 else 1.0

    return [
        products / count,
        rivals_i / max(len(by_type.get(entity_i.type, ())), 1),
        rivals_j / max(len(by_type.get(entity_j.type, ())), 1),
        min(ratio, RATIO_CAP) / RATIO_CAP,
        max(words, 0) / max(context["words"], 1),
    ]


@lru_cache(maxsize=32)
def load_pixels(page_id: str):
    """Das gerenderte Seitenbild als RGB-Array, oder None wenn es fehlt.

    Seit der Auslagerung liegt `data/images/` nicht mehr im Repo (siehe
    docs/archive/). Wer hier None bekommt und Farbmerkmale braucht, laesst
    `magda extract` laufen - `page_pairs` sagt das im Abbruch auch so.

    Der Cache ist bewusst klein: Ein Seitenbild belegt entpackt rund 5 MB,
    die Kalibrierung laeuft aber fuenfmal ueber dieselben Trainingsseiten.
    32 Bilder decken einen Fold ab und kosten ~160 MB - alle 51 waeren 266.
    """
    import numpy as np
    from PIL import Image

    from magda import config

    path = config.IMAGES_DIR / f"{page_id}.png"
    if not path.exists():
        return None
    with Image.open(path) as image:
        return np.array(image.convert("RGB"))


def _nearest_points(a, b) -> tuple[tuple[float, float], tuple[float, float]]:
    """Die naechstliegenden Punkte zweier Rechtecke.

    Mittelpunktslinien laufen bei grossen Boxen mitten durch das
    Produktfoto und zaehlen dessen Kanten als Kachelgrenzen. Zwischen den
    Raendern gemessen liegt die Linie im Zwischenraum, wo die Kachelgrenze
    tatsaechlich sitzt.
    """
    def axis(a0, a1, b0, b1):
        if a1 < b0:
            return a1, b0
        if b1 < a0:
            return a0, b1
        middle = (max(a0, b0) + min(a1, b1)) / 2
        return middle, middle

    px, qx = axis(a[0], a[2], b[0], b[2])
    py, qy = axis(a[1], a[3], b[1], b[3])
    return (px, py), (qx, qy)


def _smoothed(pixels, factor: int = SMOOTH_FACTOR):
    """Blockmittel des Seitenbilds - einmal je Seite statt je Abtastpunkt.

    Die Glaettung soll verhindern, dass eine einzelne Schriftglyphe wie ein
    Kachelwechsel aussieht. Als 3x3-Median *je Abtastpunkt* gerechnet kostete
    das 2,7 ms je Paar und damit ueber eine Stunde je Gitterlauf - quadratisch
    in der Entity-Zahl. Einmal je Seite geglaettet ist dieselbe Wirkung fuer
    einen Bruchteil: danach ist jeder Abtastpunkt ein einzelner Zugriff.
    """
    import numpy as np

    height = pixels.shape[0] // factor * factor
    width = pixels.shape[1] // factor * factor
    if height < factor or width < factor:
        return pixels.astype("float32")
    trimmed = pixels[:height, :width].astype("float32")
    return trimmed.reshape(height // factor, factor,
                           width // factor, factor, 3).mean(axis=(1, 3))


def _path_same_bg(pixels, box_i, box_j, color_i,
                  scale_x: float, scale_y: float) -> float:
    """Anteil der Verbindungslinie, der im Hintergrund von *i* bleibt.

    Gemessen wird gegen **einen** Hintergrund, nicht gegen beide: Wer
    Farben akzeptiert, die zu i *oder* j passen, erklaert einen Pfad von
    Weiss in eine gelbe Kachel zum durchgehenden - obwohl er genau die
    Kachelgrenze quert, um die es geht. Die Paare stehen in Lesereihenfolge,
    die Wahl von i ist also deterministisch; dass die beiden Hintergruende
    ueberhaupt verschieden sind, sagt `bg_distance` daneben.

    **Der Vorgaenger zaehlte Farbwechsel und war unbrauchbar:** Auf echten
    Prospektseiten sind 92 % aller Paare am Anschlag von fuenf Wechseln, und
    auch bei vervierfachter Toleranz noch 80 % - eine Prospektseite ist
    visuell dicht, jede Linie kreuzt Fotos, Text und Kacheln. Gemessen an
    gemalten Testkacheln sah das Merkmal gut aus, an echten Seiten war es
    faktisch eine Konstante.

    Ein Anteil saettigt nicht. Liegen beide Entities in derselben Kachel,
    bleibt die Linie ueberwiegend in deren Farbe; fuehrt sie ueber eine
    Kachelgrenze, faellt der Anteil.
    """
    from magda.label_audit import COLOR_TOLERANCE

    start, end = _nearest_points(box_i, box_j)
    length = math.dist(start, end)
    if length <= 0:
        return 1.0                        # die Boxen beruehren sich

    steps = min(int(length * max(scale_x, scale_y)), PATH_SAMPLES)
    if steps < 2:
        return 1.0

    import numpy as np

    # Vektorisiert statt Schleife: alle Abtastpunkte in einem Zugriff.
    t = np.linspace(0.0, 1.0, steps + 1)
    columns = np.clip((start[0] + t * (end[0] - start[0])) * scale_x,
                      0, pixels.shape[1] - 1).astype(int)
    rows = np.clip((start[1] + t * (end[1] - start[1])) * scale_y,
                   0, pixels.shape[0] - 1).astype(int)
    difference = pixels[rows, columns] - np.asarray(color_i, dtype="float32")
    hits = int((np.sqrt((difference ** 2).sum(axis=1)) <= COLOR_TOLERANCE).sum())
    return hits / (steps + 1)


def _page_colors(entities: list, pixels, width: float, height: float) -> dict:
    """Hintergrundfarbe je Entity und der seitenuebliche Grund.

    Der Seitengrund ist der Median ueber die Entity-Hintergruende, nicht
    ueber die ganze Seite: So bleibt auch `bg_offpage` relativ und braucht
    keine Annahme ueber Penny-Weiss.
    """
    import numpy as np

    from magda.label_audit import background_color

    colors = [background_color(e.bbox, pixels, width, height) for e in entities]
    known = [c for c in colors if c]
    typical = np.median(np.array(known), axis=0) if known else None
    return {
        "colors": [c if c else (list(typical) if typical is not None else None)
                   for c in colors],
        "typical": typical,
    }


def _color_features(index_i: int, index_j: int, context: dict) -> list[float]:
    colors = context["colors"]["colors"]
    typical = context["colors"]["typical"]
    color_i, color_j = colors[index_i], colors[index_j]

    if color_i is None or color_j is None:
        # Beide Boxen zu klein zum Messen - neutral, aber paarabhaengig.
        return [0.0, 0.0, 0.0, 0.0]

    entities = context["entities"]
    same_bg = _path_same_bg(
        context["pixels"], entities[index_i].bbox, entities[index_j].bbox,
        color_i, context["scale_x"], context["scale_y"],
    )

    def offpage(color):
        if typical is None:
            return 0.0
        return math.dist(color, typical) / COLOR_MAX

    return [
        math.dist(color_i, color_j) / COLOR_MAX,
        same_bg,
        offpage(color_i),
        offpage(color_j),
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


def page_pairs(page: dict, assignment: dict[int, int] | None = None, *,
               pixels=None, blocks=DEFAULT_BLOCKS) -> PagePairs:
    """Alle ungeordneten Entity-Paare einer Seite als Merkmalsvektoren.

    Die Paare stehen in Lesereihenfolge (i < j). Erst dadurch duerfen die
    Deltas ein Vorzeichen tragen - ungeordnet muesste jedes Merkmal
    symmetrisch sein und "der Preis steht *unter* dem Produkt" liesse sich
    nicht ausdruecken.

    `pixels` ist das Seitenbild als RGB-Array und nur fuer den Farbblock
    noetig. Fehlt es dort, bricht der Aufruf ab statt zu schaetzen: Ein
    Sentinel waere seitenkonstant, und bei ~20 unabhaengigen Vorlagen lernt
    das Modell daraus "Seiten ohne Bild sehen anders aus" statt einer Regel.
    """
    from magda.offers_gold import _reference_group

    names = feature_names(blocks)
    entities = [e for e in entities_from_page(page) if e.type in VALUE_TYPES]
    width = max(float(page.get("width") or 0), 1.0)
    height = max(float(page.get("height") or 0), 1.0)

    if "color" in blocks and pixels is None:
        raise ValueError(
            f"Farbmerkmale brauchen das Seitenbild, es fehlt fuer "
            f"{page.get('page_id') or 'diese Seite'}. "
            f"Mit `magda extract` neu rendern (braucht data/raw/ aus dem "
            f"Drive-Archiv, siehe docs/archive/)."
        )

    context = {
        "width": width,
        "height": height,
        "scale": _median_word_height(page),
        "count": len(entities),
        "words": max(len(page.get("words") or []), 1),
        "between": _entities_between(entities),
        "blocks": tuple(blocks),
        "entities": entities,
    }
    if "geometry_plus" in blocks:
        by_type: dict[str, list[int]] = {}
        for k, e in enumerate(entities):
            by_type.setdefault(e.type, []).append(k)
        context["by_type"] = by_type
        context["word_boxes"] = [
            w["bbox"] for w in (page.get("words") or [])
            if len(w.get("bbox") or []) == 4
        ]
    if "color" in blocks:
        # Die Hintergrundfarbe je Entity kommt aus dem Originalbild (einmal
        # je Entity, billig); der Pfad tastet das geglaettete ab (einmal je
        # Paar, und davon gibt es quadratisch viele).
        smooth = _smoothed(pixels)
        context["pixels"] = smooth
        context["scale_x"] = smooth.shape[1] / width
        context["scale_y"] = smooth.shape[0] / height
        context["colors"] = _page_colors(entities, pixels, width, height)

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
        feature_names=names,
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
