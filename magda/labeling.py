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
import time

from openai import OpenAI

from magda.labels import spans_to_bio

# Die Regeln unten sind nicht theoretisch, sondern die Fehler aus dem ersten
# Durchlauf über einen echten Prospekt (siehe reports/woche-01.md):
# Grundpreise landeten in QUANTITY, Angaben wurden in Einzelwörter zerrissen,
# und "mit PENNY App" wurde als Marke gelabelt.
_PROMPT = """\
Du siehst eine Seite aus einem deutschen Supermarkt-Prospekt sowie die Liste
aller Wörter auf der Seite, jeweils mit Index.

Markiere alle Entitäten als Spans über die Wortindizes. Erlaubte Labels:

PRODUCT     Produktbezeichnung inkl. Sortenangabe, z.B. "Löslicher Kaffee Classic"
BRAND       Marke, z.B. "MAGICO", "COCA-COLA", "SAN FABIO"
PRICE       Aktionspreis, z.B. "3.99"
OLD_PRICE   durchgestrichener Originalpreis, z.B. "5.99"
QUANTITY    Füllmenge des Produkts, z.B. "500 g", "je 200 g", "6 x 1,5 l"
UNIT_PRICE  Grundpreis in Klammern, z.B. "(1 kg = 24.95)"
DISCOUNT    Rabattangabe, z.B. "-33%"
VALID       Gültigkeitszeitraum, z.B. "Gültig von Mo, 20.7. bis Sa, 25.7."

Wichtige Regeln:

1. Ein Span pro Angabe, zusammenhängend. "je 200 g" ist EIN QUANTITY-Span über
   alle drei Wörter, nicht drei einzelne. Ebenso ist "Löslicher Kaffee Classic"
   EIN PRODUCT-Span.
2. Grundpreise gehören zu UNIT_PRICE, nicht zu QUANTITY. Der Span umfasst die
   ganze Klammer inklusive "(" und ")".
3. Aktions- und Werbetext ist keine Entität: "mit PENNY App", "ohne PENNY App",
   "Nur mit App", "Aktion", Fußnotenzeichen, Aufzählungspunkte und einzelne
   Buchstaben aus Grafiken bleiben ohne Label.
4. Wörter wie "statt" vor einem Streichpreis gehören NICHT zum OLD_PRICE, der
   Span umfasst nur die Zahl.
5. Nutze das Bild, um zu erkennen, welche Angaben zu welchem Angebot gehören.
   Preis und Produkt stehen räumlich beieinander.

Beispiel für "MAGICO Löslicher Kaffee Classic, je 200 g (1 kg = 24.95) 4.99":
[{{"start": 0, "end": 1, "label": "BRAND"}},
 {{"start": 1, "end": 4, "label": "PRODUCT"}},
 {{"start": 4, "end": 7, "label": "QUANTITY"}},
 {{"start": 7, "end": 12, "label": "UNIT_PRICE"}},
 {{"start": 12, "end": 13, "label": "PRICE"}}]

Antworte ausschließlich mit einem JSON-Array dieser Form. "end" ist exklusiv.
Wörter, die zu keiner Entität gehören, lässt du weg.
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


def is_retryable(exc: Exception) -> bool:
    """Ist der Fehler ein Schluckauf oder ein echtes Problem?

    Die GWDG lädt Modelle bei Bedarf und antwortet währenddessen mit 503 oder
    schlicht gar nicht. Ohne diese Unterscheidung landet ein Lauf über 196
    Seiten mit lauter "fehlgeschlagen" im Protokoll, obwohl nur das Modell
    kalt war – und ein abgeschnittenes JSON (ValueError) würde umgekehrt
    dreimal wiederholt, ohne dass sich etwas ändert.
    """
    from openai import APIConnectionError, APITimeoutError, RateLimitError

    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True
    status = getattr(exc, "status_code", None)
    if status in {408, 409, 425, 429, 500, 502, 503, 504}:
        return True
    return any(
        marker in str(exc).lower()
        for marker in ("rate limit", "timeout", "timed out", "temporarily unavailable",
                       "service unavailable", "connection reset", "overloaded")
    )


def label_page_with_retry(
    words: list[dict],
    page_png: bytes,
    client: OpenAI,
    model: str,
    max_retries: int = 3,
) -> list[str]:
    """label_page mit Backoff für vorübergehende Fehler.

    Ein Format- oder Parse-Fehler wird nicht wiederholt: das Modell hat
    geantwortet, die Antwort war nur unbrauchbar. Ein zweiter Versuch mit
    identischer Eingabe kostet nur Zeit. Die Seite bleibt ungelabelt und
    kommt beim nächsten Lauf erneut dran – die Skripte sind idempotent.
    """
    last: Exception | None = None
    for attempt in range(max_retries):
        try:
            return label_page(words, page_png, client, model)
        except Exception as exc:
            last = exc
            if not is_retryable(exc) or attempt == max_retries - 1:
                raise
            time.sleep(min(30.0, 2.0 * (2**attempt)))
    raise last  # unerreichbar, aber macht den Rückgabetyp eindeutig


def label_page(
    words: list[dict],
    page_png: bytes,
    client: OpenAI,
    model: str,
) -> list[str]:
    """Labelt eine Seite und gibt die BIO-Tagfolge zurück (ein Tag pro Wort)."""
    word_list = "\n".join(f"{i}: {w['text']}" for i, w in enumerate(words))
    prompt = _PROMPT.format(word_list=word_list)
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
        # etwa 13 Token pro Wort.
        #
        # Der Faktor 40 statt 30 ist für die Qwen-Modelle: die denken vor der
        # Antwort, und diese Token zählen mit. Beim Vision-Test brauchte
        # qwen3.5-397b 124 Token für das Wort "Rot" – auf einer Prospektseite
        # ginge ein knappes Budget komplett fürs Nachdenken drauf und die
        # Antwort käme abgeschnitten zurück.
        max_tokens=max(4096, len(words) * 40),
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
