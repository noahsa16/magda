"""Schritt 1 der Pipeline: Wörter + Positionen aus den Flyer-PDFs holen.

Im Proposal heißt dieser Schritt "OCR". In der Praxis haben die Penny-PDFs
aber einen eingebetteten Textlayer, d.h. wir bekommen Wörter und Koordinaten
direkt über PyMuPDF – schneller und fehlerfrei im Vergleich zu echter OCR.
Sollten später Händler ohne Textlayer dazukommen (reine Bild-PDFs), braucht
es hier einen Tesseract-Fallback.
"""

import fitz  # PyMuPDF


def _is_artifact(text: str) -> bool:
    """Filtert Steuerdaten des Blätterkatalogs aus dem Textlayer.

    Die Penny-PDFs enthalten unsichtbare Tokens wie
    "json://…_1279x1076.gif;0.000;0.000;112.688;133.926" oder "animation://…",
    mit denen der Web-Viewer seine Animationen platziert. Die sind kein
    Seiteninhalt und hätten im Training nichts verloren.
    """
    return text.startswith(("json://", "animation://", "video://", "link://"))


def extract_words(pdf_bytes: bytes) -> dict:
    """Extrahiert alle Wörter der ersten Seite eines (einseitigen) PDFs.

    Rückgabe: {"width": ..., "height": ..., "words": [{"text", "bbox"}, ...]}
    bbox ist [x0, y0, x1, y1] in PDF-Punkten, Ursprung oben links.
    Die Reihenfolge entspricht der Lesereihenfolge von PyMuPDF
    (Block -> Zeile -> Wort), darauf verlassen sich die Wortindizes im Labeling.
    """
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc[0]
        raw = page.get_text("words")  # (x0, y0, x1, y1, text, block, line, word)
        words = [
            {"text": w[4], "bbox": [round(w[0], 2), round(w[1], 2), round(w[2], 2), round(w[3], 2)]}
            for w in raw
            if w[4].strip() and not _is_artifact(w[4])
        ]
        return {
            "width": round(page.rect.width, 2),
            "height": round(page.rect.height, 2),
            "words": words,
        }


def render_png(pdf_bytes: bytes, dpi: int = 150) -> bytes:
    """Rendert die Seite als PNG. Brauchen wir fürs LLM-Labeling (Vision-Input)
    und später evtl. für den visuellen Backbone von LayoutXLM."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        pix = doc[0].get_pixmap(dpi=dpi)
        return pix.tobytes("png")


def normalize_bbox(bbox: list[float], width: float, height: float) -> list[int]:
    """Skaliert eine Bounding-Box auf das 0-1000-Raster, das LayoutLM erwartet.

    Achtung, klassischer Stolperstein: LayoutXLM will Koordinaten im Bereich
    0-1000 pro Achse, nicht die rohen PDF-Punkte. Werte werden zusätzlich
    geclippt, weil PyMuPDF vereinzelt Boxen minimal außerhalb der Seite liefert.
    """
    x0, y0, x1, y1 = bbox
    return [
        max(0, min(1000, round(x0 / width * 1000))),
        max(0, min(1000, round(y0 / height * 1000))),
        max(0, min(1000, round(x1 / width * 1000))),
        max(0, min(1000, round(y1 / height * 1000))),
    ]
