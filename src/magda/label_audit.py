"""Kandidaten für die Handprüfung eines einzelnen Labels sammeln.

Anlass ist APP_PRICE. Penny zeichnet den App-Preis auf zwei Arten aus: mit dem
Text "mit PENNY App" daneben – der steht im Textlayer – oder mit einem blauen
Kasten samt Logo, und *der* ist Grafik. PyMuPDF liefert davon nur die Zahl und
eine hochgestellte Fußnotenziffer. Gemessen über alle Seiten steht das Wort
"App" bei einem Drittel der APP_PRICE-Spans nirgends in der Nähe; auf acht
Seiten kommt es im ganzen Textlayer nicht vor, obwohl App-Preise gelabelt sind.

Das Labeling-Modell sieht das Seitenbild und erkennt den Kasten. Ein reines
Textmodell kann das nicht – und eine Textregel auch nicht. Deshalb wird hier
die Hintergrundfarbe an der Wortposition aus dem Originalbild gelesen, in
voller Auflösung. Gemessen über 296 Seiten liegen PRICE und OLD_PRICE im
Penny-Preisgelb (243, 207, 34), während 42.7 % der APP_PRICE auf blauem Grund
stehen gegen 3.7 % der PRICE.

**Die Farbe entscheidet hier nichts.** Sie sortiert vor, ein Mensch urteilt.
Ein automatisch umgeschriebenes Label sähe in der Metrik aus wie eine
Verbesserung, wäre aber nur eine andere Heuristik – und die Referenz ist genau
das, was hier belastbar werden soll. Deshalb liefert dieses Modul Kandidaten
und Urteile, aber schreibt niemals in `data/labeled/`.

Gesammelt wird in beide Richtungen, denn beide Fehler kommen vor:

    labeled     trägt das Label bereits – stimmt es?
    candidate   trägt es nicht, sitzt aber auf passendem Grund – fehlt es?
"""

import json
from pathlib import Path

from magda import config
from magda.labels import bio_to_spans

# Der Farbton des App-Kastens, abgelesen an einer von Hand verifizierten Stelle
# (`1347375_p5`, Wort 97: der Preis 1.69 im blauen Kasten mit dem App-Logo).
# Daneben liegt derselbe Preistyp im Preisgelb (255, 212, 0) – die beiden Töne
# sind weit auseinander, deshalb genügt der euklidische Abstand im RGB-Raum.
#
# Ein grober Test "Blaukanal über Rotkanal" reicht *nicht*: er fängt auch die
# hellblauen Kacheln (196, 227, 248), und die stehen ausgerechnet neben dem
# Text "ohne PENNY App".
APP_BACKGROUND = (0, 124, 132)
COLOR_TOLERANCE = 60

# Wie weit über die Wortbox hinaus gemessen wird. Innerhalb der Box ist Schrift,
# der Hintergrund liegt daneben.
BORDER_PAD = 4

CONTEXT_WORDS = 8


def background_color(bbox, pixels, page_width: float, page_height: float):
    """Median der Randpixel um die Wortbox, als (r, g, b).

    Der Median statt des Mittelwerts, weil der Rand fast immer ein paar
    Schriftpixel mitnimmt; ein Mittelwert zöge die Farbe zur Schrift hin.
    """
    height, width = pixels.shape[0], pixels.shape[1]
    scale_x = width / page_width
    scale_y = height / page_height

    x0, y0, x1, y1 = bbox
    left = max(0, int(x0 * scale_x) - BORDER_PAD)
    right = min(width, int(x1 * scale_x) + BORDER_PAD)
    top = max(0, int(y0 * scale_y) - BORDER_PAD)
    bottom = min(height, int(y1 * scale_y) + BORDER_PAD)
    if right - left < 3 or bottom - top < 3:
        return None

    import numpy as np

    patch = pixels[top:bottom, left:right]
    border = np.concatenate([
        patch[0].reshape(-1, 3), patch[-1].reshape(-1, 3),
        patch[:, 0].reshape(-1, 3), patch[:, -1].reshape(-1, 3),
    ])
    return [int(v) for v in np.median(border, axis=0)]


def color_distance(color, reference=APP_BACKGROUND) -> float | None:
    """Euklidischer Abstand im RGB-Raum, oder None wenn nicht messbar."""
    if not color:
        return None
    return sum((a - b) ** 2 for a, b in zip(color, reference)) ** 0.5


def on_app_background(color) -> bool:
    distance = color_distance(color)
    return distance is not None and distance < COLOR_TOLERANCE


def _context(words: list[str], start: int, end: int) -> str:
    before = " ".join(words[max(0, start - CONTEXT_WORDS):start])
    span = " ".join(words[start:end])
    after = " ".join(words[end:end + CONTEXT_WORDS])
    return f"{before}  «{span}»  {after}".strip()


def _split_roles() -> dict[str, str]:
    split_file = config.SPLITS_DIR / "split.json"
    if not split_file.exists():
        return {}
    splits = json.loads(split_file.read_text())
    return {
        page_id: name
        for name, page_ids in splits.items()
        if isinstance(page_ids, list)
        for page_id in page_ids
    }


def collect(label: str, model: str, sibling_labels=("PRICE", "OLD_PRICE")) -> list[dict]:
    """Alle Spans mit `label` plus die farblich passenden Spans ohne es.

    `sibling_labels` sind die Labels, mit denen `label` verwechselt werden
    kann – für APP_PRICE die beiden anderen Preisarten. Ohne diese
    Einschränkung käme jedes blau hinterlegte Wort der Seite in die Liste.
    """
    import numpy as np
    from PIL import Image

    label_dir = config.labeled_dir(model)
    roles = _split_roles()
    result = []

    for label_file in sorted(label_dir.glob("*.json")):
        page = json.loads(label_file.read_text())
        page_id = page["page_id"]
        image_file = config.IMAGES_DIR / f"{page_id}.png"
        if not image_file.exists():
            continue

        words = [w["text"] if isinstance(w, dict) else w for w in page["words"]]
        boxes = [w["bbox"] if isinstance(w, dict) else None for w in page["words"]]
        spans = bio_to_spans(page["tags"])
        relevant = [s for s in spans if s["label"] in (label, *sibling_labels)]
        if not relevant:
            continue

        with Image.open(image_file) as image:
            pixels = np.asarray(image.convert("RGB"))

        for span in relevant:
            start, end = span["start"], span["end"]
            if boxes[start] is None:
                continue
            color = background_color(boxes[start], pixels, page["width"], page["height"])
            on_background = on_app_background(color)
            is_labeled = span["label"] == label
            # Was weder das Label trägt noch farblich auffällt, muss niemand
            # ansehen – das ist der Normalfall und wären tausende Zeilen.
            if not is_labeled and not on_background:
                continue

            window = " ".join(words[max(0, start - CONTEXT_WORDS):end + CONTEXT_WORDS])
            result.append({
                "key": f"{page_id}:{start}",
                "page_id": page_id,
                "split": roles.get(page_id, ""),
                "start": start,
                "end": end,
                "text": " ".join(words[start:end]),
                "bbox": boxes[start],
                "page_width": page["width"],
                "page_height": page["height"],
                "current_label": span["label"],
                "source": "labeled" if is_labeled else "candidate",
                "background": color,
                "color_distance": round(color_distance(color), 1) if color else None,
                "on_app_background": on_background,
                "app_in_context": "App" in window,
                "context": _context(words, start, end),
            })

    for candidate in result:
        candidate["priority"] = priority_of(candidate, label)
    return _mark_duplicates(result)


def _mark_duplicates(candidates: list[dict]) -> list[dict]:
    """Gleicher Wortlaut im gleichen Kontext = dieselbe Vorlage.

    Penny gibt je Woche 44 fast identische Regionalausgaben heraus. Ohne diese
    Bündelung beurteilt ein Mensch fünfmal denselben Fall und hält am Ende 430
    Entscheidungen für 430 Beobachtungen – dieselbe Falle, wegen der `magda
    queue` clusterweise auswählt. Der erste Fund vertritt die Gruppe; die
    Oberfläche zeigt die übrigen nur auf Wunsch.
    """
    representative: dict[tuple, str] = {}
    for candidate in candidates:
        signature = (candidate["context"], candidate["current_label"])
        first = representative.setdefault(signature, candidate["key"])
        candidate["duplicate_of"] = None if first == candidate["key"] else first
    for candidate in candidates:
        signature = (candidate["context"], candidate["current_label"])
        candidate["duplicates"] = sum(
            1 for other in candidates
            if (other["context"], other["current_label"]) == signature
        )
    return candidates


def priority_of(candidate: dict, label: str) -> str:
    """Wie dringend gehört dieser Fall angesehen?

    Die Rangfolge folgt dem Erwartungswert, nicht der Häufigkeit: Ein Preis auf
    dem App-Hintergrund, der bloß PRICE heißt, ist wahrscheinlich ein
    übersehener App-Preis. Ein OLD_PRICE auf demselben Grund ist dagegen
    meistens richtig – im Kasten steht neben dem reduzierten Preis auch der
    durchgestrichene, und der bleibt OLD_PRICE.
    """
    if candidate["source"] == "labeled":
        return "check"
    if candidate["current_label"] == "OLD_PRICE":
        return "low"
    return "likely_missing"


def audit_file(label: str) -> Path:
    return config.AUDIT_DIR / f"{config.model_slug(label)}.json"


def load_audit(label: str) -> dict:
    """Kandidaten und bisherige Urteile. Fehlt die Datei, ist nichts gesammelt."""
    path = audit_file(label)
    if not path.exists():
        return {"label": label, "candidates": [], "verdicts": {}}
    data = json.loads(path.read_text())
    data.setdefault("verdicts", {})
    return data


def save_audit(data: dict) -> Path:
    """Atomar schreiben – die Datei wird aus der Oberfläche heraus fortgeschrieben."""
    config.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = audit_file(data["label"])
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temp.replace(path)
    return path


def summarize(data: dict) -> dict:
    """Zählt aus, was die Handprüfung bisher ergeben hat."""
    verdicts = data.get("verdicts", {})
    candidates = data.get("candidates", [])
    counts = {"labeled": 0, "candidate": 0, "correct": 0, "wrong": 0, "unsure": 0}
    for candidate in candidates:
        counts[candidate["source"]] += 1
        verdict = verdicts.get(candidate["key"], {}).get("verdict")
        if verdict in counts:
            counts[verdict] += 1
    counts["total"] = len(candidates)
    counts["judged"] = counts["correct"] + counts["wrong"] + counts["unsure"]
    return counts
