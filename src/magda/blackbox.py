"""Die bestehende LLM-Blackbox: Flyerseite rein, fertige Angebote raus.

Das ist der ursprüngliche Prototyp (vorher pdf_extractor.py). Er bleibt im
Projekt, weil wir ihn laut Proposal als Vergleichssystem brauchen: unser
trainiertes Modell tritt am Ende gegen genau diese Blackbox an
(Requirements-Stufe "Excellent").
"""

import base64
import json
import re

import requests
from openai import OpenAI
from tqdm import tqdm

from magda import scraping
from magda.ocr import render_png

_EXTRACT_PROMPT = """\
Extract all product deals from this Penny supermarket catalog page.
Return a JSON array. Each element must have exactly these fields:
  "name": product name (string)
  "price": current sale price (number)
  "original_price": original price before discount, or null
  "discount_pct": discount as negative integer e.g. -33, or null
  "period": validity period string e.g. "Mo, 9.3. bis Sa, 14.3." or ""

Include only actual food/product deals. Skip promotional text, store info, and app labels.
Return only valid JSON — no markdown, no explanation, no other text.\
"""


def extract_deals_from_page(pdf_bytes: bytes, client: OpenAI, model: str) -> list[dict]:
    """Schickt eine gerenderte Seite ans Vision-LLM und parst die Angebotsliste."""
    png_bytes = render_png(pdf_bytes)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _EXTRACT_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    # LLMs packen die Antwort trotz Anweisung gern in ```json-Fences
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def get_deals_from_catalog(
    flipping_book_url: str,
    session: requests.Session,
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
                page_deals = extract_deals_from_page(pdf_bytes, client, model)
                all_deals.extend(page_deals)
                pbar.set_postfix(page=page, deals=len(all_deals))
            except Exception as e:
                pbar.write(f"  [Seite {page}] Parse-Fehler: {e}")
            pbar.update(1)

    return all_deals
