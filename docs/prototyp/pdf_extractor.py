import logging
import re
import json
import time
import threading
import requests
import fitz  # pymupdf
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any, Callable
from google import genai
from google.genai import types

PDF_BASE = "https://penny-publish.blaetterkatalog.de/frontend/catalogs"
CATALOG_BASE = "https://penny-publish.blaetterkatalog.de/frontend/getcatalog.do"

log = logging.getLogger(__name__)

MAX_WORKERS = 15
_semaphore = threading.Semaphore(15)  # max. gleichzeitige Gemini-API-Calls

# ---------------------------------------------------------------------------
# Response schema – Structured Output (kein JSON-Parsing-Overhead)
# ---------------------------------------------------------------------------
CATEGORY_ENUM = [
    "produce", "dairy", "cheese", "meat", "poultry", "fish",
    "bakery_savory", "bakery_sweet",
    "pantry_oils_sauces", "pasta_rice_cereals", "canned_jarred",
    "spices_baking", "frozen", "ready_meals",
    "snacks", "sweets", "beverages",
]

FOOD_ROLE_ENUM = [
    "ingredient_core_candidate",  # main cookable ingredient
    "pantry_staple",              # oil, vinegar, flour, spices, stock
    "ready_component",            # burger buns, pizza dough, pre-made sauce as component
    "ready_meal",                 # complete ready-to-eat meal
    "snack",
    "sweet",
    "beverage",
]

NET_QUANTITY_UNIT_ENUM = ["g", "kg", "ml", "l", "stk"]

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "deals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "product_name":            {"type": "string"},
                    "brand":                   {"type": "string",  "nullable": True},
                    # Canonical identity — 3 levels
                    "canonical_name_raw":      {"type": "string",  "nullable": True},
                    "base_ingredient":         {"type": "string",  "nullable": True},
                    "processing_form":         {"type": "string",  "nullable": True},
                    # Classification
                    "category_enum":           {"type": "string",  "enum": CATEGORY_ENUM},
                    "sub_category_enum":       {"type": "string",  "nullable": True},
                    "food_role":               {"type": "string",  "enum": FOOD_ROLE_ENUM},
                    # Pricing
                    "offer_price":             {"type": "number"},
                    "original_price":          {"type": "number",  "nullable": True},
                    "discount_pct":            {"type": "integer", "nullable": True},
                    # Quantity
                    "amount_text":             {"type": "string",  "nullable": True},
                    "net_quantity_value":      {"type": "number",  "nullable": True},
                    "net_quantity_unit":       {"type": "string",
                                               "enum": NET_QUANTITY_UNIT_ENUM, "nullable": True},
                    "pack_count":              {"type": "integer", "nullable": True},
                    "packaging_type":          {"type": "string",  "nullable": True},
                    "total_net_quantity_value":{"type": "number",  "nullable": True},
                    "total_net_quantity_unit": {"type": "string",  "nullable": True},
                    "price_per_unit_value":    {"type": "number",  "nullable": True},
                    "price_per_unit_unit":     {"type": "string",  "nullable": True},
                    # Validity
                    "period":                  {"type": "string"},
                    "valid_from":              {"type": "string",  "nullable": True},
                    "valid_to":                {"type": "string",  "nullable": True},
                    "is_permanent_low_price":  {"type": "boolean"},
                    "is_seasonal":             {"type": "boolean"},
                },
                "required": ["product_name", "offer_price", "category_enum",
                             "food_role", "is_permanent_low_price", "is_seasonal"],
            },
        },
        "ignored_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name":          {"type": "string"},
                    "reason_type":   {"type": "string",
                                      "enum": ["PRICE_MISSING", "NON_FOOD", "BAD_LAYOUT",
                                               "SEASONAL_DECO", "OTHER"]},
                    "reason_detail": {"type": "string"},
                },
                "required": ["name", "reason_type", "reason_detail"],
            },
        },
    },
    "required": ["deals", "ignored_items"],
}

# ---------------------------------------------------------------------------
# System instruction – kompakt, ohne Beispiel-JSONs
# ---------------------------------------------------------------------------
def _system_instruction(reference_year: int | None = None) -> str:
    current_year = reference_year or date.today().year
    return f"""\
Du extrahierst Lebensmittel- und Getränkeangebote aus Penny-Prospektseiten (Deutschland).

DATUM ERZWINGUNG:
Scanne die gesamte Seite ZUERST nach einem Gültigkeitszeitraum (Überschrift oder Banner,
z.B. "Mo, 16.3. – Sa, 21.3."). ZWINGEND: Wende das Seiten-Datum auf JEDES Produkt an –
keine Ausnahme. Nur wenn die gesamte Seite kein Datum hat: valid_from/valid_to = null.
valid_from/valid_to immer als YYYY-MM-DD, Jahr ist IMMER {current_year}.

GETEILTER PREIS: Ein Preis unter/zwischen mehreren Produkten gilt für ALLE.
Erkennungsmerkmale: "oder", "versch. Sorten", "je", Preis zentriert unter Gruppe.
→ Eigener Deal-Eintrag pro Produkt mit demselben Preis.

NON-FOOD gehört NIEMALS in deals!
Haushalt, Garten, Drogerie, Elektro, Bekleidung, Tiernahrung, Pflanzen, Reinigungsmittel,
Küchengeräte (Pfannen, Töpfe), Möbel, Werkzeug → ZWINGEND in ignored_items (NON_FOOD).
Konkrete Beispiele die IMMER Non-Food sind — niemals in deals, immer in ignored_items:
  Bekleidung/Textilien: Socken, Unterwäsche, Shorts, Sneaker, Hemd, T-Shirt, BH, Slip, Bademode
  Drogerie/Körperpflege: Shampoo, Spülung, Zahncreme, Zahnpasta, Duschgel, Deo, Conditioner, Pflegespülung
  Tiernahrung: Katzenfutter, Hundefutter, Trockenfutter, Tiernahrung, Katzenstreu, Tierfutter
  Gutscheine/Aktionen: Gutschein, €-Gutschein, Gewinnspiel-Coupon, Rabattcode, Coupon
  Haushalt/Reinigung: Waschmittel, Spülmittel, Putzmittel, Toilettenpapier, Müllbeutel, Schwämme
  Pflanzen/Garten: Blumenzwiebeln, Setzlinge, Pflanzerde, Dünger
Wenn unklar ob Lebensmittel: Zweifel → ignored_items mit reason_type=NON_FOOD. Niemals category=beverages für Non-Food nutzen!

FELDER:

brand: Markenname (z.B. "Milka", "Jacobs"). Bei No-Name/Eigenmarken: Eigenmarkennamen
(NATURGUT, PUDA, BESTE ERNTE). Unbekannt: null.

canonical_name_raw: Sichtbare spezifische Produktidentität — so präzise wie möglich,
darf Form und Verarbeitung des HAUPTPRODUKTS enthalten. Wenn unsicher: lieber null als generisch falsch.
WICHTIG: Hauptprodukt präzise benennen, aber zusammengesetzte Produktidentitäten vollständig erhalten.
Nur additive Zusätze kürzen — nicht blind alles nach "mit" oder "in" abschneiden.
  Richtig: "passierte Tomaten", "Kirschtomaten", "Mozzarella", "Burgerbrötchen",
           "Rinderhackfleisch", "Lachsfilet", "Filterkaffee", "Tafelschokolade",
           "Chili Schoten gehackt", "Bohnen in Tomatensauce", "Matjes in Kräutercreme"
  Falsch:  "Tomaten" statt "Kirschtomaten", "Käse" statt "Mozzarella",
           "Brötchen" statt "Burgerbrötchen", "Kaffee" statt "Filterkaffee",
           "Chili Schoten gehackt mit nativem Olivenöl extra" → nur "Chili Schoten gehackt"
  Regel:
    - "mit ..." nur kürzen, wenn es klar eine Nebenzutat, Füllung, Topping oder Zugabe beschreibt.
    - "in ..." nur kürzen, wenn es reine Marinade/Zubereitungsinfo ist und die Produktidentität ohne den Zusatz eindeutig bleibt.
    - NICHT kürzen, wenn "in ..." oder "mit ..." das etablierte Produkt beschreibt
      (z.B. Bohnen in Tomatensauce, Matjes in Kräutercreme, Thunfisch in eigenem Saft).

base_ingredient: Breitere Zutatenfamilie — optional, null wenn unklar.
  Beispiele: Tomate, Käse, Brot, Lachs, Hähnchen, Öl, Mehl

processing_form: Art der Verarbeitung oder Präsentation — optional, null wenn unklar.
  Beispiele: passiert, gerieben, in Scheiben, TK, mariniert, paniert, geräuchert, frisch

category_enum: Eines der folgenden Werte (kein freier Text):
  produce            → frisches Obst & Gemüse
  dairy              → Milch, Joghurt, Sahne, Butter, Eier
  cheese             → alle Käsesorten
  meat               → Rind, Schwein, Lamm, Wild
  poultry            → Hähnchen, Pute, Ente
  fish               → Fisch und Meeresfrüchte
  bakery_savory      → Brot, Brötchen, Laugenwaren, herzhafte Backwaren
  bakery_sweet       → Kuchen, Süßgebäck, Croissants, Franzbrötchen
  pantry_oils_sauces → Öl, Essig, Ketchup, Senf, Sojasoße, Brühe, Fertigsaucen
  pasta_rice_cereals → Nudeln, Reis, Müsli, Cornflakes, Haferflocken, Grieß
  canned_jarred      → Konserven, Gläser (Hülsenfrüchte, Tomaten, Mais, Fisch)
  spices_baking      → Gewürze, Mehl, Zucker, Backpulver, Hefe, Kakao
  frozen             → alle Tiefkühlprodukte
  ready_meals        → Fertiggerichte, Suppen, Meal Kits
  snacks             → Chips, Nüsse, Cracker, Popcorn, Reiswaffeln
  sweets             → Schokolade, Bonbons, Kekse, Eis, Waffeln
  beverages          → alle Getränke (Wasser, Säfte, Softdrinks, Bier, Wein, Kaffee, Tee)

sub_category_enum: Optionale Feingranularität als Freitext-Schlüssel — null wenn unklar.
  Beispiele: tomato_products, leafy_greens, hard_cheese, fresh_cheese, ground_meat,
             buns, sweet_pastry, soft_drinks, beer, wine, salmon, white_fish

food_role: Eines der folgenden Werte:
  ingredient_core_candidate → Nur direkt verwendbare EINZELZUTATEN: Fleisch, Fisch, Gemüse,
                               Obst, Käse, Eier, Milch, Sahne, Butter, Pasta, Reis, Hülsenfrüchte.
                               NICHT: Backmischungen, Dekorationsartikel, komplette Brotlaibe,
                               Desserts, Kuchen, Waffelröllchen → diese sind ready_component oder sweet.
  pantry_staple             → Grundvorrat: Öl, Essig, Mehl, Zucker, Gewürze, Brühe
  ready_component           → Fertige Komponente: Burgerbrötchen, Pizzateig, Fertigsauce,
                               Backmischungen, Paniermehl — verwendbar in einem Rezept als Komponente
  ready_meal                → Komplettes Fertiggericht, keine Kochzutat
  snack                     → Chips, Nüsse, Cracker, Reiswaffeln
  sweet                     → Schokolade, Bonbons, Kekse, Eis, Kuchen, Waffeln, Streusel,
                               Dekorartikel für Backwaren, Marshmallows
  beverage                  → alle Getränke

MENGENFELDER:
amount_text:             Roher Mengentext wie auf dem Prospekt, z.B. "2 x 125 g", "1 l"
net_quantity_value/unit: Nettogewicht/-volumen einer Einheit. unit: g | kg | ml | l | stk
pack_count:              Anzahl Einheiten im Gebinde (z.B. 2 bei "2 x 125 g")
total_net_quantity_*:    Gesamtmenge = net_quantity_value × pack_count
packaging_type:          Beutel | Flasche | Dose | Glas | Packung | Becher | Schachtel
price_per_unit_value/unit: Preis pro Einheit wie abgedruckt, z.B. 2.13 / "kg"

PREISARTEN:
Wochenangebot: Badge -XX%, Streichpreis → is_permanent_low_price: false
Dauerhaft günstig: kein Badge, kein Streichpreis → is_permanent_low_price: true,
  original_price: null, discount_pct: null. offer_price trotzdem extrahieren!

is_seasonal:
true  → Saisonales Spezialangebot ohne Jahresrund-Relevanz:
        Oster-/Weihnachts-/Karnevals-Artikel (Ostereier-Kit, Nikolaus-Schokolade,
        Adventskalender, Weihnachtsstollen, Karnevals-Backset).
false → Normales ganzjähriges Angebot (auch saisonales Naturprodukt wie Erdbeeren im
        Sommer zählt als false — nur thematische Saisonartikel sind true).

Bei räumlich getrenntem Preis: Verbinde Produktname mit nächstliegendem Preis.
Bei zwei Preisen: Badge-Preis = Angebotspreis; kein Badge = niedrigerer Preis.
"""

_USER_PROMPT = "Extrahiere alle Lebensmittel- und Getränkeangebote aus dieser Seite. Non-Food gehört nur in ignored_items."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_catalog_id(flipping_book_url: str) -> str:
    match = re.search(r"catalogId=(\d+)", flipping_book_url)
    if not match:
        raise ValueError(f"No catalogId found in URL: {flipping_book_url}")
    return match.group(1)


def _get_catalog_version(catalog_id: str, session: requests.Session) -> str:
    url = f"{CATALOG_BASE}?catalogId={catalog_id}"
    resp = session.get(url, timeout=15)
    resp.raise_for_status()

    match = re.search(r"catalogVersion\s*[=:]\s*['\"]?(\d+)['\"]?", resp.text)
    if match:
        return match.group(1)

    match = re.search(rf"/catalogs/{catalog_id}/(\d+)/pdf/", resp.text)
    if match:
        return match.group(1)

    return "1"


def _fetch_page_pdf(
    catalog_id: str, version: str, page: int, session: requests.Session
) -> bytes | None:
    url = f"{PDF_BASE}/{catalog_id}/{version}/pdf/save/bk_{page}.pdf"
    resp = session.get(url, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content


def _pdf_to_jpeg(pdf_bytes: bytes, dpi: int = 150) -> bytes:
    """Convert first page of a single-page PDF to JPEG at given DPI."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes("jpeg")


def _get_total_pages(catalog_id: str, version: str, session: requests.Session) -> int:
    """Binary search to find the total number of pages in the catalog."""
    lo, hi = 1, 200
    while lo < hi:
        mid = (lo + hi + 1) // 2
        for attempt in range(3):
            try:
                if _fetch_page_pdf(catalog_id, version, mid, session) is not None:
                    lo = mid
                else:
                    hi = mid - 1
                break
            except Exception as e:
                if _is_retryable_exception(e) and attempt < 2:
                    time.sleep(_retry_backoff_seconds(attempt))
                    continue
                raise
    return lo


def _parse_response(text: str | None) -> tuple[list[dict], list[dict]]:
    """Returns (deals, ignored_items) or raises on invalid JSON/schema."""
    if not text:
        raise ResponseParseError("empty_model_response")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise ResponseParseError(f"invalid_json:{e}") from e

    if not isinstance(parsed, dict):
        raise ResponseParseError("response_root_not_object")

    deals = parsed.get("deals")
    ignored_items = parsed.get("ignored_items")
    if not isinstance(deals, list) or not isinstance(ignored_items, list):
        raise ResponseParseError("response_schema_missing_lists")

    required_deal_fields = {
        "product_name",
        "offer_price",
        "category_enum",
        "food_role",
        "is_permanent_low_price",
        "is_seasonal",
    }
    for idx, deal in enumerate(deals):
        if not isinstance(deal, dict):
            raise ResponseParseError(f"deal_{idx}_not_object")
        missing = sorted(required_deal_fields - set(deal))
        if missing:
            raise ResponseParseError(f"deal_{idx}_missing_required:{','.join(missing)}")

    for idx, item in enumerate(ignored_items):
        if not isinstance(item, dict):
            raise ResponseParseError(f"ignored_item_{idx}_not_object")

    return deals, ignored_items


@dataclass(slots=True)
class _CallbackPersistSnapshot:
    success: bool
    persisted_count: int = 0
    blocked_count: int = 0
    dropped_count: int = 0
    skipped_existing_better: int = 0
    failure_reason: str | None = None


def _coerce_persist_result(page_num: int, raw_count: int, result: Any) -> _CallbackPersistSnapshot:
    if result is None:
        return _CallbackPersistSnapshot(success=True, persisted_count=raw_count)
    if isinstance(result, bool):
        return _CallbackPersistSnapshot(
            success=result,
            persisted_count=raw_count if result else 0,
            failure_reason=None if result else "callback_returned_false",
        )

    success = bool(getattr(result, "success", None))
    if isinstance(result, dict):
        success = bool(result.get("success", True))
        return _CallbackPersistSnapshot(
            success=success,
            persisted_count=int(result.get("persisted_count", 0) or 0),
            blocked_count=int(result.get("blocked_count", 0) or 0),
            dropped_count=int(result.get("dropped_count", 0) or 0),
            skipped_existing_better=int(result.get("skipped_existing_better", 0) or 0),
            failure_reason=result.get("failure_reason"),
        )

    return _CallbackPersistSnapshot(
        success=bool(getattr(result, "success", True)),
        persisted_count=int(getattr(result, "persisted_count", 0) or 0),
        blocked_count=int(getattr(result, "blocked_count", 0) or 0),
        dropped_count=int(getattr(result, "dropped_count", 0) or 0),
        skipped_existing_better=int(getattr(result, "skipped_existing_better", 0) or 0),
        failure_reason=getattr(result, "failure_reason", None),
    )


_PRICE_INPUT_PER_M   = 0.10   # USD per 1M input tokens  (gemini-2.5-flash-lite)
_PRICE_OUTPUT_PER_M  = 0.40   # USD per 1M output tokens (gemini-2.5-flash-lite)
_PRICE_THINK_PER_M   = 3.50   # USD per 1M thinking tokens (falls aktiviert)
_EUR_RATE            = 0.92   # USD → EUR


@dataclass(slots=True)
class PageExtractionResult:
    page_num: int
    status: str
    deals: list[dict] = field(default_factory=list)
    ignored_items: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    raw_response_json: str | None = None
    error_kind: str | None = None
    error_message: str | None = None


class ResponseParseError(ValueError):
    """Raised when Gemini returns invalid JSON or an unusable response schema."""


def _clone_session(base_session: requests.Session) -> requests.Session:
    worker = requests.Session()
    worker.headers.update(getattr(base_session, "headers", {}))
    worker.cookies.update(getattr(base_session, "cookies", {}))
    return worker


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError):
        status = getattr(exc.response, "status_code", None)
        return status in {408, 409, 425, 429, 500, 502, 503, 504}
    if isinstance(exc, fitz.FileDataError):
        return True

    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "429",
            "500",
            "502",
            "503",
            "504",
            "rate limit",
            "temporarily unavailable",
            "service unavailable",
            "deadline exceeded",
            "timeout",
            "timed out",
            "connection reset",
            "connection aborted",
            "broken document",
        )
    )


def _retry_backoff_seconds(attempt: int) -> float:
    return min(4.0, 0.75 * (2 ** attempt))


def _extract_page_with_retry(
    page: int,
    total_pages: int,
    catalog_id: str,
    version: str,
    session: requests.Session,
    client: genai.Client,
    reference_year: int,
    max_retries: int = 3,
) -> PageExtractionResult:
    """Fetch, render and extract a single page without aborting the overall run."""
    worker_session = _clone_session(session)
    try:
        for attempt in range(max_retries):
            raw_json: str | None = None
            input_tok = 0
            output_tok = 0
            think_tok = 0
            try:
                pdf_bytes = _fetch_page_pdf(catalog_id, version, page, worker_session)
                if pdf_bytes is None:
                    log.info(f"  Seite {page:>2}/{total_pages}: 404 – nicht gefunden")
                    return PageExtractionResult(page_num=page, status="not_found")

                jpeg_bytes = _pdf_to_jpeg(pdf_bytes)

                with _semaphore:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash-lite",
                        contents=[
                            types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                            types.Part.from_text(text=_USER_PROMPT),
                        ],
                        config=types.GenerateContentConfig(
                            system_instruction=_system_instruction(reference_year=reference_year),
                            temperature=0.1,
                            thinking_config=types.ThinkingConfig(thinking_budget=0),
                            response_mime_type="application/json",
                            response_schema=RESPONSE_SCHEMA,
                        ),
                    )

                raw_json = response.text
                deals, ignored = _parse_response(raw_json)
                meta = response.usage_metadata
                input_tok = getattr(meta, "prompt_token_count", 0) or 0
                output_tok = getattr(meta, "candidates_token_count", 0) or 0
                think_tok = getattr(meta, "thoughts_token_count", 0) or 0
                log.info(
                    f"  Seite {page:>2}/{total_pages}: "
                    f"{'✓' if deals else '–'} {len(deals)} Deals extrahiert, "
                    f"{len(ignored)} Produkte ignoriert  "
                    f"[{input_tok} in / {output_tok} out / {think_tok} think]"
                )
                return PageExtractionResult(
                    page_num=page,
                    status="success" if deals else "no_food",
                    deals=deals,
                    ignored_items=ignored,
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    thinking_tokens=think_tok,
                    raw_response_json=raw_json,
                )
            except ResponseParseError as e:
                log.error(f"  Seite {page:>2}/{total_pages}: Parse-/Schema-Fehler – {e}")
                return PageExtractionResult(
                    page_num=page,
                    status="parse_failed",
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    thinking_tokens=think_tok,
                    raw_response_json=raw_json,
                    error_kind="parse_failure",
                    error_message=str(e),
                )
            except Exception as e:
                retryable = _is_retryable_exception(e)
                if retryable and attempt < max_retries - 1:
                    wait = _retry_backoff_seconds(attempt)
                    log.warning(
                        f"  Seite {page:>2}/{total_pages}: retryable Fehler "
                        f"({type(e).__name__}: {e!s:.80}), warte {wait:.1f}s..."
                    )
                    time.sleep(wait)
                    continue
                kind = "retryable_failure" if retryable else "permanent_failure"
                log.error(
                    f"  Seite {page:>2}/{total_pages}: "
                    f"{'retryable' if retryable else 'permanent'} Fehler – {type(e).__name__}: {e}"
                )
                return PageExtractionResult(
                    page_num=page,
                    status="failed",
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    thinking_tokens=think_tok,
                    raw_response_json=raw_json,
                    error_kind=kind,
                    error_message=str(e),
                )
    finally:
        worker_session.close()

    return PageExtractionResult(page_num=page, status="failed", error_kind="unexpected_fallthrough")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_deals_from_catalog(
    flipping_book_url: str,
    session: requests.Session,
    client: genai.Client,
    week_start: str,
    on_page_done: Callable[[int, list[dict]], Any] | None = None,
) -> list[dict]:
    """Extract all deals from a Penny catalog with per-page checkpointing.

    Skips pages already processed this week. Calls on_page_done(page_num, deals)
    immediately after each page so the caller can save incrementally.
    Returns only newly extracted deals (previously saved pages are excluded).
    """
    from database.db import (
        get_processed_pages,
        mark_page_processed,
        save_extraction_logs,
        save_page_extraction,
    )

    catalog_id = _extract_catalog_id(flipping_book_url)
    version = _get_catalog_version(catalog_id, session)

    processed_pages = get_processed_pages(week_start, catalog_id=catalog_id, catalog_version=version)

    total_pages = _get_total_pages(catalog_id, version, session)
    pages_to_process = [p for p in range(1, total_pages + 1) if p not in processed_pages]

    if processed_pages:
        log.info(f"Katalog {catalog_id} v{version}: {total_pages} Seiten, "
                 f"{len(processed_pages)} bereits verarbeitet, {len(pages_to_process)} neu")
    else:
        log.info(f"Katalog {catalog_id} v{version}: {total_pages} Seiten")

    if not pages_to_process:
        log.info("  Alle Seiten bereits verarbeitet – nichts zu tun.")
        return []

    start = time.time()
    all_deals: list[dict] = []
    pages_done = 0
    pages_no_food = 0
    pages_not_found = 0
    pages_error = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_think_tokens = 0
    persisted_deals_total = 0
    dropped_deals_total = 0
    blocked_deals_total = 0

    log.info(f"Starte Extraktion: {len(pages_to_process)} Seiten mit {MAX_WORKERS} Workers")

    args = [
        (page, total_pages, catalog_id, version, session, client, date.fromisoformat(week_start).year)
        for page in pages_to_process
    ]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_extract_page_with_retry, *arg): arg[0]
            for arg in args
        }
        for future in as_completed(futures):
            page_num = futures[future]
            try:
                result = future.result()
            except Exception as e:
                pages_error += 1
                log.error(f"  Seite {page_num:>2}/{total_pages}: Future-Fehler – {type(e).__name__}: {e}")
                continue

            total_input_tokens += result.input_tokens
            total_output_tokens += result.output_tokens
            total_think_tokens += result.thinking_tokens

            raw_json = result.raw_response_json
            if raw_json:
                try:
                    ignored_json = json.dumps(result.ignored_items) if result.ignored_items else None
                    save_page_extraction(
                        catalog_id,
                        version,
                        week_start,
                        result.page_num,
                        raw_json,
                        ignored_json,
                        len(result.deals),
                    )
                except Exception as e:
                    pages_error += 1
                    log.error(
                        f"  Seite {result.page_num:>2}/{total_pages}: "
                        f"save_page_extraction fehlgeschlagen – {type(e).__name__}: {e}"
                    )
                    continue

            if result.ignored_items:
                try:
                    save_extraction_logs(week_start, result.page_num, result.ignored_items)
                except Exception as e:
                    pages_error += 1
                    log.error(
                        f"  Seite {result.page_num:>2}/{total_pages}: "
                        f"save_extraction_logs fehlgeschlagen – {type(e).__name__}: {e}"
                    )
                    continue

            if result.status == "not_found":
                try:
                    mark_page_processed(
                        week_start,
                        result.page_num,
                        catalog_id=catalog_id,
                        catalog_version=version,
                    )
                    pages_not_found += 1
                except Exception as e:
                    pages_error += 1
                    log.error(
                        f"  Seite {result.page_num:>2}/{total_pages}: "
                        f"mark_page_processed fehlgeschlagen – {type(e).__name__}: {e}"
                    )
                continue

            if result.status in {"failed", "parse_failed"}:
                pages_error += 1
                continue

            for deal in result.deals:
                deal["source_page_num"] = result.page_num
                deal["catalog_id"] = catalog_id
                deal["catalog_version"] = version

            try:
                callback_result = on_page_done(result.page_num, result.deals) if on_page_done else None
            except Exception as e:
                pages_error += 1
                log.error(
                    f"  Seite {result.page_num:>2}/{total_pages}: "
                    f"on_page_done fehlgeschlagen – {type(e).__name__}: {e}"
                )
                continue

            persist_snapshot = _coerce_persist_result(result.page_num, len(result.deals), callback_result)
            persisted_deals_total += persist_snapshot.persisted_count
            dropped_deals_total += persist_snapshot.dropped_count
            blocked_deals_total += persist_snapshot.blocked_count

            # Sanity-check: alle Deals aus dem Extractor-Ergebnis müssen im Persist-Ergebnis
            # erfasst sein (persisted + blocked + dropped + skipped).  Fehlende Deals deuten
            # auf partiellen Datenverlust hin — wir loggen eine Warnung, blockieren aber nicht,
            # da die bereits persistierten Deals wertvoll sind.
            accounted = (
                persist_snapshot.persisted_count
                + persist_snapshot.blocked_count
                + persist_snapshot.dropped_count
                + persist_snapshot.skipped_existing_better
            )
            if result.deals and accounted < len(result.deals):
                log.warning(
                    f"  Seite {result.page_num:>2}/{total_pages}: "
                    f"{len(result.deals) - accounted} von {len(result.deals)} Deals "
                    "nicht im Persist-Ergebnis erfasst (möglicher partieller Datenverlust)"
                )

            if not persist_snapshot.success:
                pages_error += 1
                log.error(
                    f"  Seite {result.page_num:>2}/{total_pages}: Persist-Vertrag fehlgeschlagen"
                    + (f" ({persist_snapshot.failure_reason})" if persist_snapshot.failure_reason else "")
                )
                continue

            try:
                mark_page_processed(
                    week_start,
                    result.page_num,
                    catalog_id=catalog_id,
                    catalog_version=version,
                )
            except Exception as e:
                pages_error += 1
                log.error(
                    f"  Seite {result.page_num:>2}/{total_pages}: "
                    f"mark_page_processed fehlgeschlagen – {type(e).__name__}: {e}"
                )
                continue

            if persist_snapshot.persisted_count > 0:
                pages_done += 1
                all_deals.extend(result.deals)
            else:
                pages_no_food += 1

    elapsed = time.time() - start

    total_cost_usd = (
        total_input_tokens  / 1_000_000 * _PRICE_INPUT_PER_M +
        total_output_tokens / 1_000_000 * _PRICE_OUTPUT_PER_M +
        total_think_tokens  / 1_000_000 * _PRICE_THINK_PER_M
    )
    total_deals = len(all_deals)
    cost_per_deal = (total_cost_usd * _EUR_RATE) / total_deals if total_deals else 0

    log.info("")
    log.info("=" * 45)
    log.info("Extraktion abgeschlossen:")
    log.info(f"  Seiten total:              {total_pages}")
    log.info(f"  Seiten neu verarbeitet:    {pages_done + pages_no_food}")
    log.info(f"  Seiten mit Food:           {pages_done}")
    log.info(f"  Seiten kein Food:          {pages_no_food}")
    log.info(f"  Seiten nicht gefunden:     {pages_not_found}")
    log.info(f"  Seiten mit Fehler:         {pages_error}")
    log.info(f"  Deals (neu):               {total_deals}")
    log.info(f"  Deals persistiert:         {persisted_deals_total}")
    log.info(f"  Deals geblockt:            {blocked_deals_total}")
    log.info(f"  Deals gedroppt:            {dropped_deals_total}")
    log.info(f"  Dauer:                     {elapsed:.1f}s")
    log.info(f"  Input Tokens:              {total_input_tokens:,}")
    log.info(f"  Output Tokens:             {total_output_tokens:,}")
    log.info(f"  Thinking Tokens:           {total_think_tokens:,}")
    log.info(f"  Kosten:                    ${total_cost_usd:.4f} / €{total_cost_usd * _EUR_RATE:.4f}")
    log.info(f"  Kosten pro Deal:           €{cost_per_deal:.4f}")
    log.info("=" * 45)

    try:
        from reporting.reporter import save_run_report, save_category_stats, save_price_history
        run_stats = {
            "week_start": week_start,
            "duration_sec": elapsed,
            "pages_total": total_pages,
            "pages_processed": pages_done + pages_no_food,
            "pages_skipped_cache": len(processed_pages),
            "pages_skipped_nonfood": pages_no_food,
            "pages_failed": pages_error,
            "deals_filtered_zero": dropped_deals_total,
            "input_tokens_total": total_input_tokens,
            "output_tokens_total": total_output_tokens,
            "cost_eur": total_cost_usd * _EUR_RATE,
        }
        run_id = save_run_report(run_stats)
        save_category_stats(week_start)
        save_price_history(week_start)
        log.info(f"  Run-Report gespeichert (ID #{run_id})")
    except Exception as e:
        log.warning(f"  Reporting fehlgeschlagen: {e}")

    return all_deals
