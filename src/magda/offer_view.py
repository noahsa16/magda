"""Eine Gruppierung als Bild ansehen, statt Wortindizes zu lesen.

Eine Gruppe ist eine Liste von Zahlen - `[[5, 6, 8], [12, 13, 15]]` sagt
niemandem, ob sie stimmt. Sichtbar wird das erst auf der Seite, und genau
dort ist auch die Information, aus der die Referenz entstanden ist: der
gelbe Preiskasten, der Kachelrahmen, die Legendenspalte.

Gebaut fuer die Qualitaetskontrolle einer *maschinellen* Referenz. Wer 350
Seiten von einem Modell gruppieren laesst, muss stichprobenhaft nachsehen
koennen, ohne sie einzeln in ein Frontend zu klicken - sonst ist die einzige
Kontrolle die Zahl am Ende, und die sagt nur, dass etwas nicht stimmt, nie wo.
"""

import base64
import html
import io
import json

from magda import config

# Zwoelf Farben mit genug Abstand zueinander; zyklisch vergeben. Mehr als
# zwoelf Angebote je Seite kommen vor, dann wiederholt sich eine Farbe -
# besser als Toene, die sich nur ein Mensch mit Farbkarte auseinanderhaelt.
COLORS = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9a6324",
]
IMAGE_WIDTH = 760


def _image_data_uri(page_id: str, width: int = IMAGE_WIDTH) -> tuple[str, int, int]:
    """Seitenbild verkleinert und als data-URI - die Ansicht bleibt eine Datei."""
    from PIL import Image

    path = config.IMAGES_DIR / f"{page_id}.png"
    if not path.is_file():
        return "", 0, 0
    image = Image.open(path).convert("RGB")
    height = round(image.height * width / image.width)
    image = image.resize((width, height), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=72)
    return ("data:image/jpeg;base64,"
            + base64.b64encode(buffer.getvalue()).decode("ascii"), width, height)


def _boxes(page: dict, groups: list[list[int]], scale: float) -> list[dict]:
    """Je Gruppe die Woerterboxen, skaliert auf die Bildbreite.

    Wortweise und nicht als eine Huellbox je Gruppe: ein Angebot besteht oft
    aus Produktname links und Preiskasten rechts, die Huelle darum deckte die
    halbe Seite und zeigte gerade nicht, was zusammengefasst wurde.
    """
    words = page.get("words") or []
    result = []
    for number, group in enumerate(groups):
        color = COLORS[number % len(COLORS)]
        for index in group:
            if not 0 <= index < len(words):
                continue
            x0, y0, x1, y1 = words[index]["bbox"]
            result.append({
                "group": number, "color": color,
                "left": x0 * scale, "top": y0 * scale,
                "width": max(1.0, (x1 - x0) * scale),
                "height": max(1.0, (y1 - y0) * scale),
                "text": words[index]["text"],
            })
    return result


def render(entries: list[tuple[dict, dict]], source: str) -> str:
    """HTML fuer mehrere Seiten. `entries` ist (Seite, Annotation)."""
    parts = [_STYLE, f"<h1>Angebotsgruppierung <span class=src>{html.escape(source)}</span></h1>"]
    for page, annotation in entries:
        page_id = page.get("page_id", "?")
        groups = annotation.get("groups") or []
        uri, width, height = _image_data_uri(page_id)
        scale = width / page["width"] if page.get("width") else 1.0
        boxes = _boxes(page, groups, scale)

        parts.append(f'<section><h2>{html.escape(page_id)}'
                     f'<span class="count">{len(groups)} Angebote</span></h2>')
        parts.append(f'<div class="sheet" style="width:{width}px;height:{height}px">')
        if uri:
            parts.append(f'<img src="{uri}" width="{width}" height="{height}" alt="">')
        for box in boxes:
            parts.append(
                f'<span class="box" style="left:{box["left"]:.1f}px;'
                f'top:{box["top"]:.1f}px;width:{box["width"]:.1f}px;'
                f'height:{box["height"]:.1f}px;border-color:{box["color"]};'
                f'background:{box["color"]}33" '
                f'title="Angebot {box["group"] + 1}: {html.escape(box["text"])}"></span>')
        parts.append("</div>")

        parts.append('<ol class="legend">')
        words = page.get("words") or []
        for number, group in enumerate(groups):
            texts = " ".join(words[i]["text"] for i in group if 0 <= i < len(words))
            color = COLORS[number % len(COLORS)]
            parts.append(f'<li><span class="dot" style="background:{color}"></span>'
                         f'{html.escape(texts)}</li>')
        parts.append("</ol>")
        if annotation.get("notes"):
            parts.append(f'<p class="notes">{html.escape(annotation["notes"])}</p>')
        parts.append("</section>")
    return "\n".join(parts)


def load(source: str, page_ids: list[str] | None = None,
         limit: int = 0) -> list[tuple[dict, dict]]:
    """Seiten samt Annotation laden - Wortliste aus `data/words`, nicht aus Labels.

    Die Gruppierung zeigt auf Wortindizes, und die gehoeren der Wortliste.
    Ueber einen Labelordner zu gehen hiesse, die Ansicht an eine Labelquelle
    zu binden, die mit der Gruppierung nichts zu tun hat.
    """
    from magda import offer_teacher

    directory = offer_teacher.teacher_dir(source)
    available = sorted(path.stem for path in directory.glob("*.json"))
    wanted = [p for p in (page_ids or available) if p in set(available)]
    if limit:
        wanted = wanted[:limit]

    entries = []
    for page_id in wanted:
        words_path = config.WORDS_DIR / f"{page_id}.json"
        if not words_path.is_file():
            continue
        with open(words_path) as f:
            page = json.load(f)
        with open(directory / f"{page_id}.json") as f:
            entries.append((page, json.load(f)))
    return entries


_STYLE = """<style>
:root { color-scheme: light dark; --fg: #111; --bg: #fff; --muted: #666; --line: #ddd; }
@media (prefers-color-scheme: dark) {
  :root { --fg: #e8e8e8; --bg: #16181c; --muted: #9aa0a6; --line: #333; }
}
:root[data-theme="dark"] { --fg: #e8e8e8; --bg: #16181c; --muted: #9aa0a6; --line: #333; }
:root[data-theme="light"] { --fg: #111; --bg: #fff; --muted: #666; --line: #ddd; }
body { font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       color: var(--fg); background: var(--bg); margin: 0; padding: 2rem 1.5rem; }
h1 { font-size: 1.4rem; margin: 0 0 1.5rem; }
.src { font-weight: 400; color: var(--muted); }
section { margin: 0 0 3rem; padding: 0 0 2rem; border-bottom: 1px solid var(--line); }
h2 { font-size: 1.05rem; margin: 0 0 .75rem; font-family: ui-monospace, monospace; }
.count { font-family: sans-serif; font-weight: 400; color: var(--muted);
         margin-left: .75rem; font-size: .85rem; }
.sheet { position: relative; max-width: 100%; }
.sheet img { display: block; max-width: 100%; height: auto; }
.box { position: absolute; border: 1.5px solid; border-radius: 2px; }
.legend { margin: 1rem 0 0; padding-left: 1.2rem; font-size: .86rem; }
.legend li { margin: .25rem 0; }
.dot { display: inline-block; width: .7rem; height: .7rem; border-radius: 2px;
       margin-right: .5rem; vertical-align: baseline; }
.notes { margin: 1rem 0 0; padding: .75rem 1rem; background: color-mix(in srgb, var(--fg) 6%, transparent);
         border-left: 3px solid var(--muted); font-size: .86rem; color: var(--muted); }
</style>"""
