"""Zugriff auf die handannotierte Referenz unter gold/.

Der einzige Gold-Lesepfad lag bisher in api.py, also in der HTTP-Schicht, wo
ihn kein Skript erreicht. Der Vergleich gegen Gold ist aber Kernlogik – er
beantwortet die Frage, wofür das Gold-Set überhaupt existiert.

Pfade werden wie in api.py als config.X-Attribute zur Laufzeit gelesen, nicht
importiert – nur so biegen die Tests sie auf ein Temp-Verzeichnis um.
"""

import hashlib
import json
from typing import NamedTuple

from magda import config
from magda.labels import spans_to_bio


def words_hash(words: list[dict]) -> str:
    """Fingerabdruck der Wortliste, gegen stille Index-Verschiebung.

    Nur die Texte in ihrer Reihenfolge – Koordinaten bleiben außen vor, damit
    eine um einen Punkt verschobene Box die Annotation nicht entwertet.
    """
    payload = json.dumps([w["text"] for w in words], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GoldPages(NamedTuple):
    """Geladene Seiten plus die Gründe, warum andere fehlen.

    Die Ausschlüsse gehören ins Ergebnis, nicht nur auf stderr: Wer eine Zahl
    über 12 statt 40 Seiten berichtet, muss das im Report sehen können.
    """

    pages: list[dict]
    stale: list[str]
    in_progress: list[str]


def load_gold_pages() -> GoldPages:
    """Lädt fertig annotierte Gold-Seiten in der Form von load_labeled_pages().

    Zwei Ausschlüsse, beide notwendig:

    Halb annotierte Seiten (`in_progress`) erzeugen Falsch-Negative und ziehen
    jeden Vergleichsarm gleichmäßig nach unten – ein Messfehler, den niemand
    an der Zahl erkennt.

    Bei abweichendem `words_hash` zeigen die Span-Indizes auf andere Wörter.
    Genau dagegen existiert der Hash; die Seite still mitzunehmen wäre der
    Fehler, den er verhindern soll.
    """
    pages, stale, in_progress = [], [], []

    for gold_file in sorted(config.GOLD_DIR.glob("*.json")):
        page_id = gold_file.stem
        with open(gold_file) as f:
            annotation = json.load(f)

        words_file = config.WORDS_DIR / f"{page_id}.json"
        if not words_file.exists():
            continue
        with open(words_file) as f:
            page = json.load(f)

        if annotation.get("status") != "done":
            in_progress.append(page_id)
            continue
        if annotation.get("words_hash") != words_hash(page["words"]):
            stale.append(page_id)
            continue

        pages.append(
            {
                "page_id": page_id,
                "width": page["width"],
                "height": page["height"],
                "words": page["words"],
                "tags": spans_to_bio(len(page["words"]), annotation.get("spans", [])),
            }
        )

    return GoldPages(pages=pages, stale=stale, in_progress=in_progress)
