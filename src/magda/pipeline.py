"""Ein fremdes PDF direkt zu Angeboten, ohne Umweg über `data/`.

Die Pipeline besteht bisher aus einzelnen Schritten, die je über die Platte
kommunizieren: `magda extract` liest `data/raw` und schreibt `data/words` +
`data/images`, `magda predict` liest `data/words` und schreibt
`data/predictions`, `magda offers` liest `data/predictions` und schreibt
SQLite. Für ein einzelnes, fremdes PDF (kein Katalog, keine Regionalausgabe,
keine Woche) ist das der falsche Umweg: Nichts davon muss versioniert oder
später wiedergefunden werden. `extract_offers` fasst dieselben drei Schritte
in einem Funktionsaufruf zusammen, ganz im Speicher.

`load_models` und `extract_offers` sind bewusst getrennt: Modelle einmal
laden (Sekunden bis Minuten, je nach Variante), dann beliebig viele PDFs
durchreichen (Millisekunden bis Sekunden je Seite). Wer `magda predict` und
`magda offers` je PDF neu startet, bezahlt das Laden jedes Mal mit.

NER läuft mit Sliding Window über `magda.predict.predict_pages` - derselben
Funktion, die auch `magda predict` benutzt (siehe `magda.cli.predict`).
Gruppiert wird über `offers.pair_model_grouping` - demselben Aufbau, den
`magda offers --grouper pair-model` verwendet. Beide Wiederverwendungen sind
kein Zufall: eine zweite Implementierung derselben Schritte liefe frueher
oder spaeter auf andere Zahlen als `data/predictions/` und `offers.sqlite`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from magda import offers


@dataclass
class LoadedModels:
    """NER- und Paarmodell, einmal geladen - für `extract_offers` über viele PDFs."""

    variant: str
    checkpoint: Path
    ner_model: object
    tokenizer: object
    spec: object  # magda.config.Variant - hier nicht importiert, um transformers/torch fern zu halten
    pair_model: object  # magda.offer_model.PairClassifier
    pairs_checkpoint: Path


def load_models(
    variant: str = "gbert",
    checkpoint: str | None = None,
    pairs_checkpoint: str | Path | None = None,
) -> LoadedModels:
    """Lädt NER-Modell (checkpoints/<variant>/best) und Paarmodell einmal.

    Bricht mit einer klaren Meldung ab, wenn ein Checkpoint fehlt - dieselbe
    Regel wie in `magda predict` und `magda offers --grouper pair-model`,
    hier zusammengeführt, weil `extract_offers` beide zwingend braucht.
    """
    from magda import config, offer_model
    from magda.predict import load_ner_model

    ner_model, tokenizer, spec = load_ner_model(variant, checkpoint)
    checkpoint_dir = config.CHECKPOINTS_DIR / (checkpoint or variant) / "best"

    pairs_path = Path(pairs_checkpoint) if pairs_checkpoint else (
        config.CHECKPOINTS_DIR / "offer_pairs" / "model.pt"
    )
    if not pairs_path.is_file():
        raise FileNotFoundError(
            f"Paarmodell-Checkpoint fehlt: {pairs_path}. Erst `magda offers-model train` "
            "laufen lassen oder pairs_checkpoint auf einen vorhandenen Pfad zeigen."
        )
    pair_model = offer_model.load(pairs_path)

    return LoadedModels(
        variant=variant,
        checkpoint=checkpoint_dir,
        ner_model=ner_model,
        tokenizer=tokenizer,
        spec=spec,
        pair_model=pair_model,
        pairs_checkpoint=pairs_path,
    )


@dataclass
class PipelineOffer:
    """Ein Angebot, flach - dieselben Felder wie eine Zeile der `offers`-Tabelle
    plus die Wortbereiche seiner Entities, um daraus bei Bedarf (`to_sqlite`)
    wieder vollständige Entities mit Text/Box/Kontext zu rekonstruieren."""

    page_index: int
    bbox: tuple[float, float, float, float]
    product: str | None
    brand: str | None
    price: str | None
    old_price: str | None
    quantity: str | None
    unit_price: str | None
    app_price: str | None
    discount: str | None
    valid: str | None
    variants: list[offers.Variant]
    confidence: float | None
    arithmetic: str
    entity_word_ranges: list[dict]  # [{"type", "start", "end"}, ...]


@dataclass
class PipelinePage:
    page_index: int
    width: float
    height: float
    words: list[dict]
    entities: list[dict]
    offers: list[PipelineOffer]
    png_bytes: bytes | None = None


@dataclass
class ModelInfo:
    variant: str
    checkpoint: str
    pairs_checkpoint: str
    pair_threshold: float


@dataclass
class PipelineResult:
    doc_id: str
    pages: list[PipelinePage]
    offers: list[PipelineOffer]
    timing: dict[str, float]
    models: ModelInfo
    pages_without_text: list[str] = field(default_factory=list)


def _to_pipeline_offer(page_index: int, offer: "offers.Offer", verdict: str) -> PipelineOffer:
    values = offer.values()
    return PipelineOffer(
        page_index=page_index,
        bbox=tuple(offer.bbox),
        product=values["product"],
        brand=values["brand"],
        price=values["price"],
        old_price=values["old_price"],
        quantity=values["quantity"],
        unit_price=values["unit_price"],
        app_price=values["app_price"],
        discount=values["discount"],
        valid=values["valid"],
        variants=offer.variants(),
        confidence=offer.confidence,
        arithmetic=verdict,
        entity_word_ranges=[
            {"type": entity.type, "start": entity.start, "end": entity.end}
            for entity in offer.entities
        ],
    )


def extract_offers(
    pdf_bytes: bytes,
    models: LoadedModels,
    *,
    progress: Callable[[int, int, float], None] | None = None,
    render_images: bool = False,
) -> PipelineResult:
    """Baut aus einem mehrseitigen PDF Wörter, Entities und Angebote je Seite.

    `progress(page_index, page_count, seconds)` wird nach jeder fertig
    verarbeiteten Seite aufgerufen (0-indiziert), `seconds` ist die Zeit für
    genau diese Seite über alle drei Stufen.

    Seiten ohne Textlayer (0 Wörter - ein reines Bild-PDF, ein Deckblatt ohne
    Text) werden nicht übersprungen: Sie landen mit leeren Entities/Angeboten
    im Ergebnis und zusätzlich in `pages_without_text`, damit eine stumm
    ausgefallene Seite nicht wie eine leere Seite aussieht.

    `doc_id` (Grundlage für die Seiten-IDs `<doc_id>_p<n>`) ist der Hash der
    PDF-Bytes, nicht ein Dateiname - ein fremdes PDF hat keine Katalog-ID, und
    zwei Aufrufe mit demselben Inhalt sollen dieselben Seiten-IDs ergeben.

    `render_images=True` erzwingt das Rendern jeder Seite unabhängig davon,
    ob Variante oder Paarmodell ein Bild brauchen - für `gbert` (kein Bild
    nötig) wäre `png_bytes` sonst durchgehend `None`. Die Demo braucht das
    Seitenbild trotzdem, um Angebots-Boxen darauf zu zeichnen, egal welche
    Variante gewählt wurde; ohne den eigenen Bedarf jeder Variante/jedes
    Paarmodells zu kennen, wäre das sonst nur über den Umweg "immer Bild"
    für alle drei magda-Wege (`magda predict`, `magda offers`, hier) lösbar.
    """
    import fitz  # PyMuPDF

    from magda import config, offers_verify
    from magda.labels import spans_to_bio
    from magda.ocr import extract_words_from_page, render_png_page
    from magda.predict import page_output, predict_pages

    doc_id = hashlib.sha1(pdf_bytes).hexdigest()[:12]
    grouping_fn = offers.pair_model_grouping(models.pair_model)
    # Der Farbmerkmalsblock braucht das Seitenbild unabhängig von der
    # NER-Variante (`offer_pairs.load_pixels` liest `config.IMAGES_DIR`) -
    # der Default-Checkpoint nutzt ihn nicht, ein selbst trainierter könnte.
    needs_pixels = "color" in getattr(models.pair_model, "blocks", ())

    pages: list[PipelinePage] = []
    flat_offers: list[PipelineOffer] = []
    pages_without_text: list[str] = []
    timing = {"extract": 0.0, "ner": 0.0, "grouping": 0.0}

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc, \
            tempfile.TemporaryDirectory(prefix="magda-pipeline-") as tmp:
        images_dir = Path(tmp)
        page_count = doc.page_count

        for i in range(page_count):
            page_start = time.perf_counter()
            page_id = f"{doc_id}_p{i + 1}"

            t0 = time.perf_counter()
            words_info = extract_words_from_page(doc[i])
            timing["extract"] += time.perf_counter() - t0

            if not words_info["words"]:
                pages_without_text.append(page_id)
                pages.append(PipelinePage(
                    page_index=i, width=words_info["width"], height=words_info["height"],
                    words=[], entities=[], offers=[], png_bytes=None,
                ))
                if progress is not None:
                    progress(i, page_count, time.perf_counter() - page_start)
                continue

            word_page = {
                "page_id": page_id,
                "width": words_info["width"],
                "height": words_info["height"],
                "words": words_info["words"],
            }

            png_bytes = None
            if models.spec.image or needs_pixels or render_images:
                png_bytes = render_png_page(doc[i])
                (images_dir / f"{page_id}.png").write_bytes(png_bytes)

            t0 = time.perf_counter()
            tags, scores = predict_pages(
                [word_page], models.ner_model, models.tokenizer, models.spec,
                images_dir=images_dir if models.spec.image else None,
            )[0]
            out = page_output(word_page, tags, scores, models.variant, None)
            out["tags"] = spans_to_bio(len(out["words"]), out["entities"])
            timing["ner"] += time.perf_counter() - t0

            t0 = time.perf_counter()
            if needs_pixels:
                # `offer_pairs.load_pixels` liest `config.IMAGES_DIR` direkt -
                # ohne diesen Umweg müsste die Farbmerkmal-Funktion einen
                # Bildpfad als Parameter kennen, den sie heute nicht hat.
                # Nicht nebenläufig sicher; für einen synchronen Lauf über
                # ein PDF ist das hier in Kauf genommen.
                previous_images_dir = config.IMAGES_DIR
                config.IMAGES_DIR = images_dir
                try:
                    page_offers_raw = grouping_fn(out)
                finally:
                    config.IMAGES_DIR = previous_images_dir
            else:
                page_offers_raw = grouping_fn(out)
            verdicts = offers_verify.judge_offers(out, page_offers_raw)
            timing["grouping"] += time.perf_counter() - t0

            page_offers = [
                _to_pipeline_offer(i, offer, verdict)
                for offer, verdict in zip(page_offers_raw, verdicts)
            ]
            flat_offers.extend(page_offers)
            pages.append(PipelinePage(
                page_index=i, width=out["width"], height=out["height"],
                words=out["words"], entities=out["entities"], offers=page_offers,
                png_bytes=png_bytes,
            ))

            if progress is not None:
                progress(i, page_count, time.perf_counter() - page_start)

    return PipelineResult(
        doc_id=doc_id,
        pages=pages,
        offers=flat_offers,
        timing=timing,
        models=ModelInfo(
            variant=models.variant,
            checkpoint=str(models.checkpoint),
            pairs_checkpoint=str(models.pairs_checkpoint),
            pair_threshold=float(models.pair_model.threshold),
        ),
        pages_without_text=pages_without_text,
    )


def _offer_to_json(offer: PipelineOffer) -> dict:
    payload = asdict(offer)
    payload["bbox"] = list(offer.bbox)
    return payload


def to_json(result: PipelineResult, *, embed_images: bool = True) -> str:
    """Das ganze Ergebnis als JSON-String - Seitenbilder base64-kodiert.

    `embed_images=False` lässt `png_base64` durchgehend `None`, auch wenn
    `png_bytes` vorliegt: Wer die Seitenbilder ohnehin separat ablegt (die
    Demo über `--images-dir`, siehe `cli/extract_pdf.py`), soll sie nicht ein
    zweites Mal - base64-aufgebläht - in derselben Datei tragen.
    """
    import base64

    payload = {
        "doc_id": result.doc_id,
        "models": asdict(result.models),
        "timing": result.timing,
        "pages_without_text": result.pages_without_text,
        "pages": [
            {
                "page_index": page.page_index,
                "width": page.width,
                "height": page.height,
                "png_base64": (
                    base64.b64encode(page.png_bytes).decode("ascii")
                    if embed_images and page.png_bytes else None
                ),
                "words": page.words,
                "entities": page.entities,
                "offers": [_offer_to_json(o) for o in page.offers],
            }
            for page in result.pages
        ],
        "offers": [_offer_to_json(o) for o in result.offers],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def from_json(text: str) -> PipelineResult:
    """Baut ein `PipelineResult` aus der Ausgabe von `to_json` zurück.

    Ohne `png_bytes` (die Demo legt Seitenbilder separat unter --images-dir
    ab, siehe `embed_images` oben) - für `to_csv`/`to_sqlite` reicht das,
    beide lesen nur Wörter, Entities und Angebotsfelder. Gebraucht vom
    Export-Endpunkt der Demo, der csv/sqlite aus dem einmal geschriebenen
    JSON erzeugt, statt Modell und Paarmodell ein zweites Mal laufen zu lassen.
    """
    payload = json.loads(text)

    def _offer(raw: dict, page_index: int) -> PipelineOffer:
        return PipelineOffer(
            page_index=page_index,
            bbox=tuple(raw["bbox"]),
            product=raw["product"], brand=raw["brand"], price=raw["price"],
            old_price=raw["old_price"], quantity=raw["quantity"],
            unit_price=raw["unit_price"], app_price=raw["app_price"],
            discount=raw["discount"], valid=raw["valid"],
            variants=[offers.Variant(**v) for v in raw["variants"]],
            confidence=raw["confidence"], arithmetic=raw["arithmetic"],
            entity_word_ranges=raw["entity_word_ranges"],
        )

    pages: list[PipelinePage] = []
    flat_offers: list[PipelineOffer] = []
    for raw_page in payload["pages"]:
        page_offers = [_offer(o, raw_page["page_index"]) for o in raw_page["offers"]]
        flat_offers.extend(page_offers)
        pages.append(PipelinePage(
            page_index=raw_page["page_index"], width=raw_page["width"],
            height=raw_page["height"], words=raw_page["words"],
            entities=raw_page["entities"], offers=page_offers, png_bytes=None,
        ))

    return PipelineResult(
        doc_id=payload["doc_id"],
        pages=pages,
        offers=flat_offers,
        timing=payload["timing"],
        models=ModelInfo(**payload["models"]),
        pages_without_text=payload["pages_without_text"],
    )


_CSV_FIELDS = [
    "page_index", "product", "brand", "position", "quantity", "unit_price",
    "price", "old_price", "app_price", "discount", "valid", "confidence",
    "arithmetic", "bbox",
]


def to_csv(result: PipelineResult) -> str:
    """Eine Zeile je Variante (Größe/Preis-Kombination), Angebotsfelder wiederholt.

    Ein Angebot ohne die fünf variantentragenden Typen (nur BRAND/VALID, z.B.
    ein Legendeneintrag) bekäme sonst gar keine Zeile und würde aus der CSV
    verschwinden - dieselbe Zeile wird deshalb einmal mit leeren
    Variantenfeldern geschrieben.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    empty_variant = offers.Variant(0, None, None, None, None, None)
    for offer in result.offers:
        for variant in offer.variants or [empty_variant]:
            writer.writerow({
                "page_index": offer.page_index,
                "product": offer.product,
                "brand": offer.brand,
                "position": variant.position,
                "quantity": variant.quantity,
                "unit_price": variant.unit_price,
                "price": variant.price,
                "old_price": variant.old_price,
                "app_price": variant.app_price,
                "discount": offer.discount,
                "valid": offer.valid,
                "confidence": offer.confidence,
                "arithmetic": offer.arithmetic,
                "bbox": json.dumps(list(offer.bbox)),
            })
    return buffer.getvalue()


def _entity_from_range(words: list[dict], item: dict, context_window: int = 5) -> "offers.Entity":
    """Rekonstruiert eine Entity aus Wortbereich + Seitenwörtern.

    `PipelineOffer` speichert nur `entity_word_ranges` (Typ, Start, Ende),
    nicht Text/Box/Kontext ein zweites Mal - beides steht schon in
    `PipelinePage.words`, und zwei Kopien derselben Information laufen
    auseinander, sobald jemand nur eine davon anfasst.
    """
    from magda.predict import bounding_box

    start, end = item["start"], item["end"]
    text = " ".join(w["text"] for w in words[start:end])
    bbox = tuple(bounding_box([w["bbox"] for w in words[start:end]]))
    before, after = offers._context(words, start, end, context_window)
    return offers.Entity(
        id=0, type=item["type"], text=text, bbox=bbox, start=start, end=end,
        context_before=before, context_after=after,
    )


def to_sqlite(result: PipelineResult, path: str | Path) -> dict:
    """Schreibt das Ergebnis in dasselbe SQLite-Schema wie `offers.write_sqlite`.

    `source` ist `"pipeline:<variant>"` - fremde PDFs teilen sich damit keine
    Zeilen mit `magda offers` (dessen `source` ein Labelordner-/Vorhersagename
    ist), lassen sich aber mit denselben Abfragen lesen. Die Angebote werden
    nicht neu gruppiert, sondern aus dem bereits berechneten
    `PipelineResult` rekonstruiert - kein zweiter, potenziell abweichender
    Lauf des Paarmodells nur fürs Schreiben.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    source = f"pipeline:{result.models.variant}"

    totals = {"offers": 0, "entities": 0, "variants": 0}
    with sqlite3.connect(path) as conn:
        offers._create_schema(conn)
        offers._migrate_schema(conn)
        conn.execute("delete from offer_entities where source = ?", (source,))
        conn.execute(
            "delete from offer_variants where offer_id in "
            "(select id from offers where source = ?)",
            (source,),
        )
        conn.execute("delete from offers where source = ?", (source,))

        for page in result.pages:
            if not page.offers:
                continue
            page_id = f"{result.doc_id}_p{page.page_index + 1}"
            page_offers_raw = []
            for index, po in enumerate(page.offers):
                entities = [_entity_from_range(page.words, r) for r in po.entity_word_ranges]
                offer = offers._make_offer(page_id, index, entities)
                offer.confidence = po.confidence
                page_offers_raw.append(offer)
            verdicts = [po.arithmetic for po in page.offers]
            oc, ec, vc = offers._insert_offers(conn, source, "pair-model", page_offers_raw, verdicts)
            totals["offers"] += oc
            totals["entities"] += ec
            totals["variants"] += vc
        conn.commit()
    return totals
