"""Read-only-API für das Frontend.

Liest data/ direkt von der Platte – die Pipeline-Skripte bleiben die einzige
Schreibquelle. Start: uvicorn magda.api:app --reload (Port 8000, das
Frontend-Dev-Setup proxied /api hierhin).

Pfade werden bewusst als config.X-Attribute zur Laufzeit gelesen (nicht
importiert), damit die Tests sie auf ein Temp-Verzeichnis umbiegen können.
"""

import base64
import json

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse

from magda import config
from magda.labels import ENTITY_TYPES, id2label
from magda.ocr import extract_words, normalize_bbox, render_png

app = FastAPI(title="Magda API")


def _catalog_of(page_id: str) -> str:
    return page_id.rsplit("_p", 1)[0]


def _page_num(page_id: str) -> int:
    """Für die numerische Sortierung ("p10" nach "p2", nicht davor)."""
    try:
        return int(page_id.rsplit("_p", 1)[1])
    except (IndexError, ValueError):
        return 0


@app.get("/api/schema")
def get_schema():
    return {"entity_types": ENTITY_TYPES}


@app.get("/api/status")
def get_status():
    catalogs: dict[str, dict] = {}

    def bump(catalog: str, key: str):
        entry = catalogs.setdefault(
            catalog, {"id": catalog, "raw": 0, "words": 0, "images": 0, "labeled": 0}
        )
        entry[key] += 1

    for pdf in config.RAW_DIR.glob("*/bk_*.pdf"):
        bump(pdf.parent.name, "raw")
    for f in config.WORDS_DIR.glob("*.json"):
        bump(_catalog_of(f.stem), "words")
    for f in config.IMAGES_DIR.glob("*.png"):
        bump(_catalog_of(f.stem), "images")
    for f in config.LABELED_DIR.glob("*.json"):
        bump(_catalog_of(f.stem), "labeled")

    rows = sorted(catalogs.values(), key=lambda c: c["id"])
    totals = {k: sum(c[k] for c in rows) for k in ("raw", "words", "images", "labeled")}
    return {"catalogs": rows, "totals": totals}


@app.get("/api/pages")
def list_pages():
    labeled_ids = {f.stem for f in config.LABELED_DIR.glob("*.json")}
    pages = [
        {"page_id": f.stem, "catalog": _catalog_of(f.stem), "labeled": f.stem in labeled_ids}
        for f in config.WORDS_DIR.glob("*.json")
    ]
    pages.sort(key=lambda p: (p["catalog"], _page_num(p["page_id"])))
    return pages


@app.get("/api/pages/{page_id}")
def get_page(page_id: str):
    words_file = config.WORDS_DIR / f"{page_id}.json"
    if not words_file.exists():
        raise HTTPException(404, f"Unbekannte Seite: {page_id}")
    with open(words_file) as f:
        page = json.load(f)

    labeled_file = config.LABELED_DIR / f"{page_id}.json"
    if labeled_file.exists():
        with open(labeled_file) as f:
            tags = json.load(f).get("tags")
        if tags is not None:
            page["tags"] = tags
    return page


@app.get("/api/pages/{page_id}/image")
def get_page_image(page_id: str):
    image_file = config.IMAGES_DIR / f"{page_id}.png"
    if not image_file.exists():
        raise HTTPException(404, f"Kein Bild für Seite: {page_id}")
    return FileResponse(image_file, media_type="image/png")


@app.get("/api/evaluation")
def get_evaluation():
    reports = []
    for f in sorted(config.EVAL_DIR.glob("*.json")):
        with open(f) as fh:
            reports.append(json.load(fh))
    return reports


# Modell + Tokenizer sind teuer zu laden – einmal laden, dann wiederverwenden.
# Tests leeren den Cache über monkeypatch.
_MODEL_CACHE: dict = {}


def _load_model():
    if "model" not in _MODEL_CACHE:
        model_dir = config.CHECKPOINTS_DIR / "layoutxlm" / "best"
        if not model_dir.exists():
            raise HTTPException(
                503,
                "Kein trainiertes Modell unter checkpoints/layoutxlm/best. "
                "Erst python scripts/04_train.py layoutxlm laufen lassen.",
            )
        # Import erst hier: torch/transformers sind schwer und für die
        # reinen Daten-Endpoints unnötig.
        from transformers import AutoModelForTokenClassification, AutoTokenizer

        _MODEL_CACHE["tokenizer"] = AutoTokenizer.from_pretrained(config.LAYOUT_MODEL)
        _MODEL_CACHE["model"] = AutoModelForTokenClassification.from_pretrained(model_dir).eval()
    return _MODEL_CACHE["tokenizer"], _MODEL_CACHE["model"]


@app.post("/api/inference")
def run_inference(file: UploadFile):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Nur einseitige PDF-Dateien werden unterstützt.")

    tokenizer, model = _load_model()

    pdf_bytes = file.file.read()
    try:
        page = extract_words(pdf_bytes)
    except Exception:
        raise HTTPException(400, "PDF konnte nicht gelesen werden.")
    if not page["words"]:
        raise HTTPException(
            422, "Kein Textlayer gefunden – reine Bild-PDFs werden nicht unterstützt (kein OCR)."
        )

    import torch

    # Encoding exakt wie in dataset.LayoutDataset, nur ohne Labels/Padding.
    words = [w["text"] for w in page["words"]]
    boxes = [normalize_bbox(w["bbox"], page["width"], page["height"]) for w in page["words"]]
    enc = tokenizer(
        words, boxes=boxes, truncation=True,
        max_length=config.MAX_SEQ_LENGTH, return_tensors="pt",
    )
    with torch.no_grad():
        logits = model(**enc).logits[0]
    pred_ids = logits.argmax(-1).tolist()

    # Erstes Subword trägt die Prediction (Konvention aus alignment.py);
    # abgeschnittene Wörter (>512 Subwords) bleiben "O".
    tags = ["O"] * len(words)
    seen: set[int] = set()
    for token_idx, word_id in enumerate(enc.word_ids()):
        if word_id is not None and word_id not in seen:
            seen.add(word_id)
            tags[word_id] = id2label[pred_ids[token_idx]]

    page["tags"] = tags
    page["image_b64"] = base64.b64encode(render_png(pdf_bytes)).decode("ascii")
    return page
