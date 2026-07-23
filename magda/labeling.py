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
        temperature=0,  # Labeling soll deterministisch sein, nicht kreativ
    )

    text = _strip_code_fences(response.choices[0].message.content or "")
    spans = json.loads(text)
    if not isinstance(spans, list):
        raise ValueError(f"LLM hat kein JSON-Array geliefert: {text[:200]}")

    return spans_to_bio(len(words), spans)
