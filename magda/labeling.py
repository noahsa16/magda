"""Schritt 2 der Pipeline: automatisches Labeln der Wörter per LLM.

Das LLM bekommt das Seitenbild plus die nummerierte Wortliste und soll
Spans über Wortindizes zurückgeben (start/end/label). Spans statt
Wort-für-Wort-Labels, weil LLMs bei "gib mir exakt N Labels" gern die
Länge verfehlen – Spans lassen sich dagegen sauber validieren und
notfalls einzeln verwerfen (passiert in labels.spans_to_bio).
"""

import base64
import json
import re

from openai import OpenAI

from magda.labels import ENTITY_TYPES, spans_to_bio

_PROMPT = """\
Du siehst eine Seite aus einem deutschen Supermarkt-Prospekt sowie die Liste
aller Wörter auf der Seite, jeweils mit Index.

Markiere alle Entitäten als Spans über die Wortindizes. Erlaubte Labels:
{entity_types}

PRODUCT = Produktbezeichnung, BRAND = Marke, PRICE = Aktionspreis,
OLD_PRICE = durchgestrichener Originalpreis, QUANTITY = Menge/Gewicht/Inhalt,
DISCOUNT = Rabattangabe, VALID = Gültigkeitszeitraum.

Antworte ausschließlich mit einem JSON-Array dieser Form:
[{{"start": 12, "end": 14, "label": "PRODUCT"}}, ...]
"end" ist exklusiv. Wörter, die zu keiner Entität gehören, lässt du weg.
Kein Markdown, keine Erklärungen.

Wortliste:
{word_list}
"""


def _strip_code_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()


def _extract_json_array(text: str) -> str:
    """Schneidet das JSON-Array aus einer Antwort mit Beiwerk heraus.

    Trotz "kein Markdown, keine Erklärungen" im Prompt liefert das Modell
    regelmäßig Prosa drumherum – beobachtet wurden Einleitungssätze, eine
    angehängte Zusammenfassung und (einmal) beides auf Koreanisch. Statt
    daran zu scheitern, nehmen wir schlicht alles zwischen der ersten '['
    und der dazu passenden schließenden ']'.
    """
    text = _strip_code_fences(text)
    start = text.find("[")
    if start == -1:
        raise ValueError(f"Kein JSON-Array in der Antwort: {text[:150]}")

    # Klammern zählen, statt rfind(']') zu nehmen: hinter dem Array kann noch
    # Fließtext mit weiteren Klammern stehen.
    depth = 0
    for i, char in enumerate(text[start:], start=start):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise ValueError(f"JSON-Array nicht geschlossen (abgeschnitten?): {text[:150]}")


def label_page(
    words: list[dict],
    page_png: bytes,
    client: OpenAI,
    model: str,
) -> list[str]:
    """Labelt eine Seite und gibt die BIO-Tagfolge zurück (ein Tag pro Wort)."""
    word_list = "\n".join(f"{i}: {w['text']}" for i, w in enumerate(words))
    prompt = _PROMPT.format(
        entity_types=", ".join(ENTITY_TYPES),
        word_list=word_list,
    )
    b64 = base64.b64encode(page_png).decode("ascii")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
        # Nicht 0: bei greedy decoding ist das Modell auf einer Seite in eine
        # Endlosschleife gelaufen (hunderte Wiederholungen von '" a "'), bis
        # das Token-Limit griff. Ein bisschen Temperatur bricht solche Loops.
        # Die Labels werden dadurch nicht mehr exakt reproduzierbar – für
        # einmalig erzeugte Trainingsdaten ist Robustheit hier wichtiger.
        temperature=0.2,
        # Ohne Limit greift das Server-Default und schneidet die Antwort mitten
        # im JSON ab. Gemessen an echten Seiten braucht Mistral rund 25 Zeichen
        # JSON pro Wort, und JSON ist tokendicht (~2 Zeichen pro Token) – also
        # etwa 13 Token pro Wort. Mit Faktor 30 liegt genug Puffer drauf, falls
        # ein Modell geschwätziger antwortet.
        max_tokens=max(2048, len(words) * 30),
    )

    choice = response.choices[0]
    text = choice.message.content or ""

    # Abgeschnittene Antworten früh und mit klarer Meldung abfangen – sonst
    # kommt nur ein kryptisches "Expecting ',' delimiter" aus json.loads.
    if choice.finish_reason == "length":
        raise ValueError(
            f"Antwort wurde bei {len(text)} Zeichen abgeschnitten "
            f"(max_tokens zu klein für {len(words)} Wörter)"
        )
    if not text.strip():
        raise ValueError("LLM hat eine leere Antwort geliefert")

    spans = json.loads(_extract_json_array(text))
    if not isinstance(spans, list):
        raise ValueError(f"LLM hat kein JSON-Array geliefert: {text[:200]}")

    return spans_to_bio(len(words), spans)
