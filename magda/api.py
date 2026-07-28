"""API für das Frontend.

Liest data/ direkt von der Platte. Schreiben darf sie ausschließlich nach
gold/ (handannotierte Referenz) - alles andere unter data/ erzeugen die
Pipeline-Skripte. Dieselbe Beschränkung wie beim Runner: eng umrissen statt
allgemein. Start: uvicorn magda.api:app --reload (Port 8000, das
Frontend-Dev-Setup proxied /api hierhin).

Pfade werden bewusst als config.X-Attribute zur Laufzeit gelesen (nicht
importiert), damit die Tests sie auf ein Temp-Verzeichnis umbiegen können.
"""

import base64
import hashlib
import json
import os
import tempfile
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from magda import config, runner
from magda.labels import ENTITY_TYPES, id2label, validate_spans
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


def _downloaded_at(catalog: str) -> str | None:
    """Ladedatum aus der Änderungszeit des Katalogverzeichnisses.

    Katalog-IDs sind nichtssagende Blätterkatalog-Nummern. Das Datum macht sie
    in der Übersicht unterscheidbar - anders als der Gültigkeitszeitraum, der
    nur dort existiert, wo das LLM ihn als VALID erkannt hat.
    """
    directory = config.RAW_DIR / catalog
    if not directory.exists():
        return None
    try:
        return datetime.fromtimestamp(directory.stat().st_mtime).date().isoformat()
    except OSError:
        # Ein unlesbarer Katalog (z.B. fehlende Berechtigung) darf nicht die
        # komplette Statusübersicht zerstören. Stattdessen wird das Datum als
        # nicht verfügbar gekennzeichnet.
        return None


@app.get("/api/schema")
def get_schema():
    return {"entity_types": ENTITY_TYPES}


@app.get("/api/status")
def get_status():
    catalogs: dict[str, dict] = {}

    def bump(catalog: str, key: str):
        entry = catalogs.setdefault(
            catalog, {"id": catalog, "raw": 0, "words": 0, "images": 0, "labeled": 0,
             "downloaded": None}
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

    for catalog, entry in catalogs.items():
        entry["downloaded"] = _downloaded_at(catalog)

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


def _training_state(variant: str) -> dict:
    """Trainingsstand aus dem jüngsten Checkpoint.

    `trainer.save_model()` schreibt kein trainer_state.json nach best/, der
    Verlauf steht nur in den checkpoint-N-Ordnern. Der mit der höchsten
    Schrittzahl ist der aktuellste.
    """
    variant_dir = config.CHECKPOINTS_DIR / variant
    checkpoints = sorted(
        variant_dir.glob("checkpoint-*"),
        key=lambda p: int(p.name.split("-")[1]) if p.name.split("-")[1].isdigit() else 0,
    )
    entry: dict = {
        "variant": variant,
        "trained": (variant_dir / "best").exists(),
        "epoch": None,
        "steps": None,
        "max_steps": None,
        "best_f1": None,
        "history": [],
    }
    if not checkpoints:
        return entry

    state_file = checkpoints[-1] / "trainer_state.json"
    if not state_file.exists():
        return entry
    with open(state_file) as f:
        state = json.load(f)

    entry["epoch"] = state.get("epoch")
    entry["steps"] = state.get("global_step")
    entry["max_steps"] = state.get("max_steps")
    entry["best_f1"] = state.get("best_metric")
    entry["history"] = [
        {"epoch": row.get("epoch"), "f1": row["eval_f1"]}
        for row in state.get("log_history", [])
        if "eval_f1" in row
    ]
    return entry


@app.get("/api/model")
def get_model_status():
    """Trainingsstand beider Varianten – die Demo zeigt daran, wie weit das
    Modell ist, das dort gerade rechnet."""
    return [_training_state(v) for v in ("layoutxlm", "gbert")]


class RunRequest(BaseModel):
    job: str
    variant: str | None = None


@app.post("/api/run")
def start_run(req: RunRequest):
    try:
        runner.start(req.job, req.variant)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return runner.status()


@app.get("/api/run")
def get_run():
    return runner.status()


@app.post("/api/run/stop")
def stop_run():
    runner.stop()
    return runner.status()


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


# ---------------------------------------------------------------------------
# Gold-Annotationen (handgelabelt, versioniert unter gold/)
# ---------------------------------------------------------------------------


class GoldSpan(BaseModel):
    start: int
    end: int
    label: str


class GoldPayload(BaseModel):
    words_hash: str
    status: Literal["in_progress", "done"]
    annotator: str = ""
    spans: list[GoldSpan]


def _words_hash(words: list[dict]) -> str:
    """Fingerabdruck der Wortliste, gegen stille Index-Verschiebung.

    Nur die Texte in ihrer Reihenfolge - Koordinaten bleiben außen vor, damit
    eine um einen Punkt verschobene Box die Annotation nicht entwertet.
    """
    payload = json.dumps([w["text"] for w in words], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_words(page_id: str) -> dict:
    words_file = config.WORDS_DIR / f"{page_id}.json"
    if not words_file.exists():
        raise HTTPException(404, f"Unbekannte Seite: {page_id}")
    with open(words_file) as f:
        return json.load(f)


@app.get("/api/gold")
def list_gold():
    rows = []
    for words_file in config.WORDS_DIR.glob("*.json"):
        page_id = words_file.stem
        gold_file = config.GOLD_DIR / f"{page_id}.json"
        entry = {
            "page_id": page_id,
            "catalog": _catalog_of(page_id),
            "status": "untouched",
            "annotator": "",
            "num_spans": 0,
            "stale": False,
        }
        if gold_file.exists():
            try:
                with open(gold_file) as f:
                    gold = json.load(f)
                with open(words_file) as f:
                    current_hash = _words_hash(json.load(f)["words"])
            except (json.JSONDecodeError, KeyError, TypeError):
                # gold/ ist versioniert und wird gemergt - ein Konfliktmarker in
                # einer Datei ist der wahrscheinlichste Fehlerfall überhaupt.
                # Der darf nicht die ganze Übersicht mitreißen, sonst fällt das
                # Werkzeug für alle 40 Seiten aus.
                entry["status"] = "broken"
            else:
                entry["status"] = gold.get("status", "in_progress")
                entry["annotator"] = gold.get("annotator", "")
                entry["num_spans"] = len(gold.get("spans", []))
                # Derselbe Vergleich wie in get_gold: Ohne ihn meldet die
                # Übersicht nach einem erneuten Schritt 02 weiter "fertig",
                # obwohl jede Seite auf die falschen Wörter zeigt.
                entry["stale"] = gold.get("words_hash") != current_hash
        rows.append(entry)

    rows.sort(key=lambda r: (r["catalog"], _page_num(r["page_id"])))
    return rows


@app.get("/api/gold/{page_id}")
def get_gold(page_id: str):
    page = _load_words(page_id)
    current_hash = _words_hash(page["words"])

    gold_file = config.GOLD_DIR / f"{page_id}.json"
    if not gold_file.exists():
        return {
            "page_id": page_id,
            "words_hash": current_hash,
            "status": "untouched",
            "annotator": "",
            "updated": None,
            "spans": [],
            "stale": False,
        }

    with open(gold_file) as f:
        gold = json.load(f)
    # Der gespeicherte Hash wird mitgeliefert, nicht der aktuelle - nur so kann
    # das Frontend beim Speichern denselben Wert zurückschicken. stale sagt
    # ihm vorab, dass die Wortliste sich seither geändert hat.
    # page_id steht bewusst hinter dem Splat: Eine kopierte Gold-Datei trägt die
    # page_id ihrer Herkunft, maßgeblich ist die angefragte. "updated" dagegen
    # davor - dort ist der Dateiinhalt maßgeblich und None nur der Default für
    # eine von Hand angelegte Datei ohne Zeitstempel.
    return {
        "updated": None,
        **gold,
        "page_id": page_id,
        "stale": gold.get("words_hash") != current_hash,
    }


@app.put("/api/gold/{page_id}")
def put_gold(page_id: str, payload: GoldPayload):
    page = _load_words(page_id)

    if payload.words_hash != _words_hash(page["words"]):
        raise HTTPException(
            409,
            "Die Wortliste dieser Seite hat sich geändert. Die Annotation passt "
            "nicht mehr zu den Wortindizes und wurde nicht gespeichert.",
        )

    spans = [s.model_dump() for s in payload.spans]
    errors = validate_spans(spans, len(page["words"]))
    if errors:
        raise HTTPException(422, " ".join(errors))

    config.GOLD_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "page_id": page_id,
        "words_hash": payload.words_hash,
        "status": payload.status,
        "annotator": payload.annotator,
        "updated": datetime.now().isoformat(timespec="seconds"),
        "spans": spans,
    }
    # Erst in eine Nachbardatei schreiben, dann per os.replace umhängen: Die
    # Gold-Datei ist das einzige Artefakt, das sich nicht neu erzeugen lässt,
    # und sie wird während einer Sitzung im Sekundentakt überschrieben. Ein
    # Abbruch mitten im Schreiben hinterlässt sonst einen Torso statt der
    # vorherigen Fassung. mkstemp statt festem Namen, damit zwei gleichzeitige
    # Anfragen für dieselbe Seite sich nicht gegenseitig ins Temp schreiben.
    fd, tmp_path = tempfile.mkstemp(dir=config.GOLD_DIR, prefix=f".{page_id}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(record, f, ensure_ascii=False, indent=1)
        # mkstemp legt 0600 an, und os.replace nimmt den Modus mit. Die Dateien
        # in gold/ werden aber geteilt und versioniert, also der übliche Modus.
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, config.GOLD_DIR / f"{page_id}.json")
    except Exception:
        os.unlink(tmp_path)
        raise

    # stale gehört nicht in die Datei (abgeleiteter Zustand), aber in die
    # Antwort: Erst damit ist sie formgleich mit der von GET und das Frontend
    # kann sie ohne Nacharbeit in seinen Cache legen.
    return {**record, "stale": False}
