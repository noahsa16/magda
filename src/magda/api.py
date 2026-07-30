"""API für das Frontend.

Liest data/ direkt von der Platte. Geschrieben wird nur an drei aufgezählten
Stellen: gold/ (handannotierte Referenz), catalogs.json (Katalog-Verzeichnis)
und data/runs/ (Lauf-Historie). Alles andere unter data/ erzeugen die
Pipeline-Skripte. Dieselbe Beschränkung wie beim Runner: eine Erlaubnisliste
statt eines allgemeinen Schreibzugriffs. Start: uvicorn magda.api:app --reload
(Port 8000, das Frontend-Dev-Setup proxied /api hierhin).

Pfade werden bewusst als config.X-Attribute zur Laufzeit gelesen (nicht
importiert), damit die Tests sie auf ein Temp-Verzeichnis umbiegen können.
"""

import json
import os
import tempfile
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from magda import (
    agreement, catalog_meta, catalogs, config, dedupe, jobs, runner, runs, scraping,
)
from magda.gold import count_by_status, words_hash
from magda.labels import ENTITY_TYPES, validate_spans

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
    try:
        # stat() wirft FileNotFoundError bei fehlendem Verzeichnis und PermissionError
        # bei Zugriffsproblemen auf Elternverzeichnissen. Beides ist OSError und wird
        # als „Datum nicht verfügbar" behandelt — ein einzelner unlesbarer Katalog
        # darf nicht die komplette Statusübersicht zerstören.
        return datetime.fromtimestamp(directory.stat().st_mtime).date().isoformat()
    except OSError:
        return None


@app.get("/api/schema")
def get_schema():
    return {"entity_types": ENTITY_TYPES}


@app.get("/api/status")
def get_status():
    # Nicht "catalogs": das verdeckte hier das gleichnamige Modul.
    by_catalog: dict[str, dict] = {}

    def bump(catalog: str, key: str):
        entry = by_catalog.setdefault(
            catalog, {"id": catalog, "raw": 0, "words": 0, "images": 0, "labeled": 0,
             "excluded": 0, "pending": 0, "downloaded": None}
        )
        entry[key] += 1

    for pdf in config.RAW_DIR.glob("*/bk_*.pdf"):
        bump(pdf.parent.name, "raw")
    for f in config.WORDS_DIR.glob("*.json"):
        bump(_catalog_of(f.stem), "words")
    for f in config.IMAGES_DIR.glob("*.png"):
        bump(_catalog_of(f.stem), "images")
    # Eine Seite gilt als gelabelt, sobald *ein* Modell sie gelabelt hat. Für
    # den Pipeline-Fortschritt zählt, ob die Arbeit getan ist – nicht von wem.
    # Die Aufschlüsselung je Modell steht darunter in labeled_by_model.
    for page_id in config.labeled_page_ids():
        bump(_catalog_of(page_id), "labeled")
    # Ohne diese Zeile klafft in der Übersicht eine Lücke: 327 geladen, 196
    # extrahiert – als hätte die Pipeline ein Drittel liegen lassen. Die
    # Differenz sind Duplikate, und wer das nicht sieht, sucht einen Fehler,
    # den es nicht gibt.
    for page_id in dedupe.load_excluded():
        bump(_catalog_of(page_id), "excluded")

    for catalog, entry in by_catalog.items():
        entry["downloaded"] = _downloaded_at(catalog)

    meta = catalog_meta.load()
    for entry in by_catalog.values():
        # Ohne die Region ist ein Katalog nur eine sechsstellige Nummer - und
        # eine Kachel mit "1 Seite" wirkt wie ein Fehler statt wie das, was sie
        # ist: eine Region, die sich an genau einer Seite unterscheidet.
        info = meta.get(entry["id"], {})
        entry["region"] = catalog_meta.label(entry["id"], meta)
        entry["region_confirmed"] = bool(info.get("confirmed", False)) if info else None

    for entry in by_catalog.values():
        # Was übrig bleibt, wenn man Verarbeitetes und Aussortiertes abzieht.
        # Im Normalfall 0. Bleibt hier etwas stehen, ist es echte Arbeit:
        # Schritt 02 lief nicht durch, oder die Seite hat keinen Textlayer.
        entry["pending"] = max(0, entry["raw"] - entry["words"] - entry["excluded"])

    rows = sorted(by_catalog.values(), key=lambda c: c["id"])
    totals = {
        k: sum(c[k] for c in rows)
        for k in ("raw", "words", "images", "labeled", "excluded", "pending")
    }
    # Gold zählt nicht je Katalog: die Handannotation läuft quer über Kataloge,
    # und die Übersicht braucht davon nur die Gesamtzahl.
    gold_counts = count_by_status()
    totals["gold_done"] = gold_counts["done"]
    totals["gold_in_progress"] = gold_counts["in_progress"]
    # Wer hat wie viel gelabelt? Ohne diese Aufschlüsselung sieht ein Lauf mit
    # drei Modellen genauso aus wie einer mit einem, und ein abgebrochener
    # Vergleichslauf fällt niemandem auf.
    totals["labeled_by_model"] = {
        model: len(list(config.labeled_dir(model).glob("*.json")))
        for model in config.labeled_models()
    }
    return {"catalogs": rows, "totals": totals}


@app.get("/api/pages")
def list_pages(model: str | None = None):
    """Seitenliste für den Inspektor.

    Ohne ?model zeigt "labeled" an, ob irgendein Modell die Seite gelabelt hat;
    mit ?model, ob genau dieses es getan hat. Der Inspektor braucht beides: die
    Übersicht will den Fortschritt, der Vergleich einen bestimmten Lauf.
    """
    labeled_ids = (
        {f.stem for f in config.labeled_dir(model).glob("*.json")}
        if model
        else config.labeled_page_ids()
    )
    pages = [
        {"page_id": f.stem, "catalog": _catalog_of(f.stem), "labeled": f.stem in labeled_ids}
        for f in config.WORDS_DIR.glob("*.json")
    ]
    pages.sort(key=lambda p: (p["catalog"], _page_num(p["page_id"])))
    return pages


@app.get("/api/sources")
def list_label_sources():
    """Die Label-Quellen als Ordner-Ebene für Inspektor und Annotator.

    Zwei Sorten, die sich grundsätzlich unterscheiden und deshalb getrennt
    gehören: was ein LLM erzeugt hat (reproduzierbar, liegt unter
    data/labeled/<modell>/) und was ein Mensch oder eine Vorannotation in
    gold/ hinterlassen hat.

    Gold wird nach `annotator` gruppiert, nicht als ein Topf ausgeliefert.
    Seit Seiten vorannotiert werden, stehen dort zwei verschiedene Dinge
    nebeneinander: geprüfte Handarbeit und ungeprüfte Vorschläge. Wer die
    zusammenwirft, weiß hinterher nicht mehr, worauf er sich verlassen kann.
    """
    sources = [
        {
            "kind": "model",
            "id": model,
            "name": model,
            "pages": len(list(config.labeled_dir(model).glob("*.json"))),
            "done": len(list(config.labeled_dir(model).glob("*.json"))),
        }
        for model in config.labeled_models()
    ]

    by_annotator: dict[str, dict] = {}
    for gold_file in config.GOLD_DIR.glob("*.json"):
        try:
            with open(gold_file) as f:
                gold = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Eine kaputte Gold-Datei darf die Ordnerliste nicht leeren –
            # gold/ ist versioniert, ein Merge-Konflikt ist der häufigste Fall.
            continue
        name = (gold.get("annotator") or "").strip() or "ohne Namen"
        entry = by_annotator.setdefault(
            name, {"kind": "gold", "id": name, "name": name, "pages": 0, "done": 0}
        )
        entry["pages"] += 1
        if gold.get("status") == "done":
            entry["done"] += 1

    return sources + sorted(by_annotator.values(), key=lambda s: s["name"])


@app.get("/api/labelers")
def list_labelers():
    """Welche Modelle haben gelabelt, und wie viele Seiten? Füttert die Auswahl."""
    return [
        {"model": model, "pages": len(list(config.labeled_dir(model).glob("*.json")))}
        for model in config.labeled_models()
    ]


@app.get("/api/pages/{page_id}")
def get_page(page_id: str, model: str | None = None):
    words_file = config.WORDS_DIR / f"{page_id}.json"
    if not words_file.exists():
        raise HTTPException(404, f"Unbekannte Seite: {page_id}")
    with open(words_file) as f:
        page = json.load(f)

    labeler = model or config.default_labeled_model()
    if labeler:
        labeled_file = config.labeled_dir(labeler) / f"{page_id}.json"
        if labeled_file.exists():
            with open(labeled_file) as f:
                tags = json.load(f).get("tags")
            if tags is not None:
                page["tags"] = tags
                # Ohne dieses Feld weiß das Frontend nicht, wessen Labels es
                # gerade anzeigt – bei mehreren Modellen ist das der halbe Sinn.
                page["model"] = labeler
    return page


@app.get("/api/pages/{page_id}/image")
def get_page_image(page_id: str):
    image_file = config.IMAGES_DIR / f"{page_id}.png"
    if not image_file.exists():
        raise HTTPException(404, f"Kein Bild für Seite: {page_id}")
    return FileResponse(image_file, media_type="image/png")


@app.get("/api/evaluation")
def get_evaluation():
    """Modell-Evaluationen aus data/eval/.

    Der Ordner enthält nicht nur Evaluationsreports: dort landen auch der
    Gold-Vergleich der Labeling-Modelle und die Agreement-Auswertung. Wer
    hier alles durchreicht, schickt dem Frontend Objekte ohne "report"-Feld,
    und die Evaluationsseite stirbt an Object.entries(undefined). Deshalb
    wird auf die Form geprüft statt auf den Dateinamen – ein neuer Report
    mit anderem Namen soll nicht dasselbe nochmal auslösen.
    """
    reports = []
    for f in sorted(config.EVAL_DIR.glob("*.json")):
        try:
            with open(f) as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and isinstance(data.get("report"), dict) and data.get("variant"):
            reports.append(data)
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
    args: dict = {}


@app.post("/api/run")
def start_run(req: RunRequest):
    try:
        runner.start(req.job, req.args)
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


@app.get("/api/jobs")
def get_jobs():
    """Der Job-Katalog. Das Frontend baut seine Formulare daraus, damit ein
    neuer Parameter nicht an zwei Stellen gepflegt werden muss."""
    return jobs.describe()


@app.get("/api/runs")
def list_runs():
    return runs.list_runs()


@app.get("/api/runs/{run_id}")
def get_run_detail(run_id: str):
    entry = runs.read_run(run_id)
    if entry is None:
        raise HTTPException(404, f"Unbekannter Lauf: {run_id}")
    return entry


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
                    current_hash = words_hash(json.load(f)["words"])
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
    current_hash = words_hash(page["words"])

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

    if payload.words_hash != words_hash(page["words"]):
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


# ---------------------------------------------------------------------------
# Katalog-Verzeichnis (versioniert, catalogs.json)
# ---------------------------------------------------------------------------


class CatalogEntry(BaseModel):
    id: str
    url: str = ""
    title: str = ""
    version: str = "1"
    pages: int | None = None
    added_by: str = ""
    note: str = ""


class ProbeRequest(BaseModel):
    url: str


@app.get("/api/catalogs")
def list_catalogs():
    """Verzeichnis samt lokal vorhandener Seitenzahl - erst damit sieht man,
    welcher eingetragene Katalog auch heruntergeladen ist."""
    registry = catalogs.load()
    entries = [
        {**entry, "local_pages": len(list((config.RAW_DIR / entry["id"]).glob("bk_*.pdf")))}
        for entry in registry.entries
    ]
    return {"entries": entries, "error": registry.error}


@app.post("/api/catalogs")
def add_catalog(entry: CatalogEntry):
    try:
        return catalogs.add(entry.model_dump())
    except KeyError as e:
        raise HTTPException(409, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.delete("/api/catalogs/{catalog_id}")
def delete_catalog(catalog_id: str):
    try:
        removed = catalogs.remove(catalog_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if not removed:
        raise HTTPException(404, f"Unbekannter Katalog: {catalog_id}")
    return {"removed": catalog_id}


@app.post("/api/catalogs/probe")
def probe_catalog(req: ProbeRequest):
    """Prüft eine Katalog-URL, ohne etwas zu laden.

    Netzfehler werden zu 400: für den Nutzer ist eine unerreichbare URL eine
    fehlerhafte Eingabe, kein Serverfehler.
    """
    import requests

    try:
        return scraping.probe_catalog(req.url, requests.Session())
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Katalog nicht erreichbar: {e}")


@app.get("/api/labels/agreement")
def get_label_agreement(a: str, b: str):
    """Wo widersprechen sich zwei Labeling-Modelle?

    Ergänzt /api/labels/vs-gold um die Sicht auf *alle* Seiten statt nur die
    drei annotierten. Die Rangfolge der uneinigsten Seiten ist dabei der
    praktische Teil: sie sagt, welche Seite als Nächstes von Hand annotiert
    gehört.

    Keine Qualitätsaussage – zwei Modelle können sich einig und gemeinsam
    irren. Übereinstimmung ist eine Obergrenze für Vertrauen, kein Ersatz
    für Gold.
    """
    known = config.labeled_models()
    for model in (a, b):
        if config.model_slug(model) not in known:
            raise HTTPException(404, f"Keine Labels für Modell: {model}")

    result = agreement.compare_models(a, b)
    return {
        **result,
        "per_label": agreement.label_agreement(a, b),
        # Die ganze Seitenliste wäre bei 196 Seiten viel Ballast für eine
        # Übersicht; wer mehr will, ruft das Skript auf.
        "pages": result["pages"][:25],
    }


@app.get("/api/labels/vs-gold")
def get_labels_vs_gold():
    """Rangfolge der Labeling-Modelle gegen die handannotierte Referenz.

    Liest den Report, den magda gold schreibt, statt selbst
    zu rechnen: seqeval über alle Modelle bei jedem Seitenaufruf wäre teuer,
    und die Zahl ändert sich nur, wenn jemand neu labelt oder annotiert.

    Fehlt die Datei, ist das kein Fehler – der Vergleich wurde dann noch nicht
    gefahren, und das Frontend blendet den Abschnitt aus.
    """
    report_file = config.EVAL_DIR / "labels_vs_gold.json"
    if not report_file.exists():
        return {"gold_pages": [], "results": []}
    try:
        with open(report_file) as f:
            report = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"gold_pages": [], "results": []}

    return {
        "gold_pages": report.get("gold_pages", []),
        "results": [
            {
                "model": entry["model"],
                "pages_compared": entry["pages_compared"],
                "f1": entry["report"].get("micro avg", {}).get("f1-score"),
                "precision": entry["report"].get("micro avg", {}).get("precision"),
                "recall": entry["report"].get("micro avg", {}).get("recall"),
                # Je Entity-Typ, damit sichtbar wird *wo* ein Modell verliert –
                # ein micro-F1 allein sagt nicht, ob Marken oder Preise fehlen.
                "per_label": {
                    label: scores.get("f1-score")
                    for label, scores in entry["report"].items()
                    if label in ENTITY_TYPES
                },
            }
            for entry in report.get("results", [])
        ],
    }


@app.get("/api/labels/distribution")
def get_label_distribution(model: str | None = None):
    """Wie oft kommt welcher Entity-Typ in den Labels eines Modells vor?

    Gezählt werden B-Tags, also Entities statt Wörter - ein sechswortiger
    Produktname soll nicht sechsmal zählen.

    Bewusst je Modell und nicht über alle: die Verteilung ist der schnellste
    Blick auf die Labelqualität ("Marken fast nie erkannt"), und summiert über
    mehrere Modelle mittelt sich genau der Unterschied weg, den man sehen will.
    """
    counts = {entity: 0 for entity in ENTITY_TYPES}
    pages = 0
    labeler = model or config.default_labeled_model()
    if labeler is None:
        return {"pages": 0, "counts": counts, "total": 0, "model": None}
    for labeled_file in config.labeled_dir(labeler).glob("*.json"):
        try:
            with open(labeled_file) as f:
                tags = json.load(f).get("tags") or []
        except (json.JSONDecodeError, OSError):
            continue
        pages += 1
        for tag in tags:
            if tag.startswith("B-") and tag[2:] in counts:
                counts[tag[2:]] += 1
    return {
        "pages": pages,
        "counts": counts,
        "total": sum(counts.values()),
        "model": labeler,
    }
