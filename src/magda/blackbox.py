"""Die bestehende LLM-Blackbox: Flyerseite rein, fertige Angebote raus.

Das ist der ursprüngliche Prototyp (vorher pdf_extractor.py). Er bleibt im
Projekt, weil wir ihn laut Proposal als Vergleichssystem brauchen: unser
trainiertes Modell tritt am Ende gegen genau diese Blackbox an
(Requirements-Stufe "Excellent").
"""

import base64
import json
import re
import time

from openai import OpenAI
from tqdm import tqdm

from magda import scraping
from magda.labeling import is_retryable
from magda.ocr import render_png

# Wie `offer_teacher.PROMPT_VERSION`: der Prompt lebt sonst nur in der
# Konversation, in der er entstand, und ein zweiter Lauf ist dann nicht
# vergleichbar. Text und Begründung stehen in docs/blackbox-extraction-prompt.md.
PROMPT_VERSION = 1

# Dieselbe Absicherung wie in labeling.py (dort erklärt): Qwen-Modelle
# denken vor der Antwort und verbrauchen dabei max_tokens. Lokal
# dupliziert statt aus labeling importiert - beides sind modulprivate
# Konstanten des jeweiligen Prompts, keine gemeinsame Schnittstelle.
_NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}
_rejects_thinking_flag: set[str] = set()


def _is_unsupported_param(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 400 and "chat_template" in str(exc)


def _extract_json_array(text: str) -> str:
    """Schneidet das JSON-Array aus einer Antwort mit Beiwerk heraus.

    Wie labeling._extract_json_array: LLMs liefern trotz gegenteiliger
    Anweisung gern Prosa oder Markdown-Fences drumherum.
    """
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = text.find("[")
    if start == -1:
        raise ValueError(f"Kein JSON-Array in der Antwort: {text[:150]}")

    depth = 0
    for i, char in enumerate(text[start:], start=start):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise ValueError(f"JSON-Array nicht geschlossen (abgeschnitten?): {text[:150]}")

# Fasst dieselbe Domänenkenntnis wie labeling._PROMPT zusammen, aber auf
# Objekt- statt Wort-Span-Ebene: die Blackbox liefert fertige Angebote, kein
# BIO-Tagging. Die Feldnamen sind bewusst an ENTITY_TYPES angelehnt
# (price/old_price/app_price/quantity/unit_price/discount_pct/valid), damit
# eine spätere arithmetische Gegenprobe (Menge × Grundpreis) ohne
# Feldumbenennung möglich wird - das Vorgänger-Schema kannte weder quantity
# noch unit_price.
_EXTRACT_PROMPT = """\
Du siehst eine Seite aus einem deutschen Supermarkt-Prospekt (Penny).
Extrahiere alle beworbenen Angebote als JSON-Array. Jedes Element hat genau
diese Felder:

  "brand"         Markenname, oder null wenn keine erkennbar ist
  "product"       Produktname inkl. Sortenangabe, ohne Menge und Preis
  "quantity"      Füllmenge als Text, z. B. "500 g", "6 x 1,5 l", oder null
  "price"         Aktionspreis, den man ohne Bedingung zahlt (Zahl)
  "old_price"     durchgestrichener/höherer Vergleichspreis, oder null
  "app_price"     Preis, den nur PENNY-App-Nutzer zahlen, oder null
  "discount_pct"  Rabatt als negative Zahl, z. B. -33, oder null
  "unit_price"    Grundpreis wie gedruckt, z. B. "(1 kg = 11.98)", oder null
  "valid"         Gültigkeitszeitraum der Seite, z. B. "Mo, 9.3. bis Sa, 14.3.", oder ""

Domänenwissen, das beim Zuordnen häufig zu Fehlern führt:

- **price vs. old_price**: die kleinere Zahl ist immer price, die größere
  old_price - unabhängig davon, welche zuerst steht oder größer gedruckt
  ist. Steht nur eine Zahl da, ist sie price.
- **app_price** ist ein dritter, eigener Fall, erkennbar an "mit PENNY App",
  "Nur mit der App" oder einem blauen App-Symbol/-Kasten. Der Preis ohne
  App bleibt price, auch wenn er höher ist als der App-Preis - die
  Ziffernregel oben gilt nur zwischen price und old_price.
- **product** enthält die Sortenangabe ("Löslicher Kaffee Classic"), aber
  NICHT Handelsklasse, Haltungsform oder Herkunftsland ("Kl. I",
  "Haltungsform 2", "Deutschland") und NICHT die Menge oder den Grundpreis.
- **quantity** ist nur Zahl und Einheit. Wörter wie "je", "ca.", "zzgl.",
  "Pfand" gehören nicht hinein.
- **unit_price** steht immer in runden Klammern der Form "(1 kg = 11.98)"
  oder "(1 l = 0.70)" - gib den Text wie gedruckt zurück, keine eigene
  Umrechnung.
- Ignoriere Seitenkopf, Kleingedrucktes ("Abgabe nur in haushaltsüblichen
  Mengen"), Öffnungszeiten und die Druckkennung am rechten Seitenrand
  (Form "25_02-09-10") - das sind keine Angebote.

Was zu EINEM Angebot zusammengehört (maßgeblich ist die Bildkachel, nicht
die Textnähe - Preise stehen bei Penny oft in einem gelben Kasten, der
räumlich näher am Nachbarangebot liegt als am eigenen Produkt):

- **Größen- oder Sortenvarianten mit je eigenem Preis** (z. B. "20 cm 9.99 /
  24 cm 14.99") sind dasselbe Angebot mit demselben Produktnamen - gib pro
  Preis ein eigenes JSON-Objekt aus, jeweils mit identischem "brand" und
  "product".
- **Varianten mit gemeinsamem Preis** ("je 205 g oder 190 g, 0.69") sind ein
  einziges JSON-Objekt; wähle eine der Mengenangaben oder trenne sie mit
  " | ".
- **Legendenlayouts**: nummerierte Produkte ("④ Pflanztopf-Set") mit einer
  Preisliste an anderer Stelle der Seite. Dort entscheidet die Nummer, nicht
  die Nähe im Bild.
- Ein Angebot ohne erkennbaren Produktnamen (nur Foto + Preis) bekommt
  "product": null - erfinde keinen Namen.

Antworte ausschließlich mit dem JSON-Array, keine Markdown-Fences, keine
Erklärung, kein Vorspann.\
"""


def extract_deals_from_page(pdf_bytes: bytes, client: OpenAI, model: str) -> list[dict]:
    """Schickt eine gerenderte Seite ans Vision-LLM und parst die Angebotsliste."""
    png_bytes = render_png(pdf_bytes)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    messages = [
        {
            "role": "user",
            # Bild vor dem Text: gemma-4-31b-it antwortet bei Text-zuerst mit
            # "du hast mir noch kein Bild geschickt" und sieht das Bild
            # schlicht nicht - reproduziert mit und ohne enable_thinking,
            # verschwindet mit dieser Reihenfolge. Mistral und Qwen
            # verarbeiten beide Reihenfolgen gleich, insofern kostenlos.
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": _EXTRACT_PROMPT},
            ],
        }
    ]

    def call(extra_body: dict | None):
        return client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            # Seiten mit vielen kleinen Angeboten (Deko/Non-Food, teils mit
            # langen Feldwerten) haben 4096 gerissen - gemessen an
            # mistral-medium-3.5-128b, 7 von 42 Seiten abgeschnitten trotz
            # nur 8-14 Angeboten. 8192 wie labeling.py: lieber Puffer als
            # eine Seite verlieren.
            max_tokens=8192,
            extra_body=extra_body,
        )

    # Dieselbe Absicherung wie beim Labeling (labeling.label_page): Qwen-
    # Modelle denken vor der Antwort und verbrauchen dabei max_tokens, bevor
    # ein einziges Zeichen JSON steht. Mistral lehnt den Schalter mit HTTP
    # 400 ab, deshalb wird er nur einmal je Modell ausprobiert.
    if model in _rejects_thinking_flag:
        response = call(None)
    else:
        try:
            response = call(_NO_THINKING)
        except Exception as exc:
            if not _is_unsupported_param(exc):
                raise
            _rejects_thinking_flag.add(model)
            response = call(None)

    choice = response.choices[0]
    text = (choice.message.content or "").strip()
    if choice.finish_reason == "length":
        raise ValueError(f"Antwort bei {len(text)} Zeichen abgeschnitten "
                         f"(max_tokens zu klein oder Reasoning-Overhead)")
    if not text:
        raise ValueError("LLM hat eine leere Antwort geliefert")

    deals = json.loads(_extract_json_array(text))
    if not isinstance(deals, list):
        raise ValueError(f"LLM hat kein JSON-Array geliefert: {text[:200]}")
    return deals


def extract_deals_from_page_with_retry(
    pdf_bytes: bytes, client: OpenAI, model: str, max_retries: int = 3,
) -> list[dict]:
    """extract_deals_from_page mit Backoff fuer voruebergehende Fehler.

    Leichter als labeling.label_page_with_retry (kein separater
    Rate-Limit-Fahrplan mit Fuenf-Minuten-Wartezeit): eine einzelne Seite
    kostet hier keinen Batch von hunderten Woertern, ein Fehlschlag ist
    billig genug fuer einen einfachen exponentiellen Backoff.

    Anders als labeling.label_page_with_retry wird auch ein ValueError
    (abgeschnittene Antwort, kaputtes JSON) wiederholt, nicht nur
    is_retryable-Fehler. labeling.py begruendet den Verzicht damit, dass
    das Modell "nur geantwortet, die Antwort war nur unbrauchbar" hat -
    bei temperature=0 waere ein zweiter Versuch also deterministisch
    derselbe Fehler. Hier steht temperature=0.2 (siehe extract_deals_
    from_page): gemessen an mistral-medium-3.5-128b liefert derselbe
    Aufruf beim naechsten Versuch reproduzierbar vollstaendiges JSON -
    das Abschneiden ist eine gelegentliche Wiederholungsschleife, kein
    stabiler Fehler.
    """
    last: Exception | None = None
    for attempt in range(max_retries):
        try:
            return extract_deals_from_page(pdf_bytes, client, model)
        except Exception as exc:
            last = exc
            if attempt == max_retries - 1:
                raise
            if not (is_retryable(exc) or isinstance(exc, ValueError)):
                raise
            time.sleep(min(60.0, 5.0 * (2**attempt)) if is_retryable(exc) else 1.0)
    raise last  # unerreichbar, aber macht den Rueckgabetyp eindeutig


def get_deals_from_catalog(
    flipping_book_url: str,
    session,
    client: OpenAI,
    model: str,
    max_pages: int = 20,
) -> list[dict]:
    """Kompletter Blackbox-Durchlauf über einen Katalog."""
    all_deals: list[dict] = []
    pages = scraping.download_catalog(flipping_book_url, session, max_pages)

    with tqdm(desc="Extrahiere Seiten", unit="Seite") as pbar:
        for page, pdf_bytes in pages:
            try:
                page_deals = extract_deals_from_page_with_retry(pdf_bytes, client, model)
                all_deals.extend(page_deals)
                pbar.set_postfix(page=page, deals=len(all_deals))
            except Exception as e:
                pbar.write(f"  [Seite {page}] Parse-Fehler: {e}")
            pbar.update(1)

    return all_deals
