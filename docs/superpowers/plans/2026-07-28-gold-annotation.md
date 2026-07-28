# Gold-Annotation im Dashboard — Umsetzungsplan

> **Für agentische Bearbeiter:** ERFORDERLICHE SUB-SKILL: `superpowers:subagent-driven-development` (empfohlen) oder `superpowers:executing-plans`, um diesen Plan Aufgabe für Aufgabe umzusetzen. Die Schritte nutzen Checkbox-Syntax (`- [ ]`) zur Fortschrittsverfolgung.

**Ziel:** Ein Werkzeug im Dashboard, mit dem sich Prospektseiten von Hand annotieren lassen, damit Katalog 1342881 ein handgelabeltes Gold-Set wird.

**Architektur:** Neue Route `/annotate` im bestehenden React-Frontend, die `PageOverlay` wiederverwendet und Spans als Zustand hält. Drei neue FastAPI-Endpunkte schreiben nach `gold/` — der einzige Schreibpfad der bisher lesenden API. Die Span-Validierung liegt als reine Funktion in `magda/labels.py`, die Auswahl-Logik als reine Funktionen in `span-editor.ts`; beide sind ohne Server bzw. ohne Rendering testbar.

**Tech-Stack:** Python 3.12, FastAPI, pydantic, pytest · React 19, TypeScript, TanStack Query, Vite, Vitest, Tailwind

Zugrundeliegende Spec: `docs/superpowers/specs/2026-07-28-gold-annotation-design.md`

## Globale Randbedingungen

- Kommentare und Docstrings auf **Deutsch**, Code-Identifier auf **Englisch**.
- Docstrings erklären *warum*, nicht *was*. Keine Kommentare, die die Zeile darunter wiederholen.
- `ENTITY_TYPES` in `magda/labels.py` wird **nicht** verändert — weder Reihenfolge noch Inhalt.
- `gold/` liegt auf Repo-Ebene und wird **versioniert**. Nicht zu `.gitignore` hinzufügen.
- Gold-Dateien speichern **Spans**, niemals BIO-Tag-Listen.
- Pfade in `magda/api.py` immer als `config.X` zur Laufzeit lesen, nie importieren — sonst können die Tests sie nicht umbiegen.
- Die API darf ausschließlich nach `gold/` schreiben. Kein weiterer Schreibpfad.
- Bestehende Tests müssen grün bleiben: `pytest` (aktuell 37 Tests) und `cd frontend && npm test`.
- Alle Python-Kommandos aus dem Projektroot mit `.venv/bin/python -m pytest`.

## Dateistruktur

| Datei | Verantwortung |
|---|---|
| `magda/config.py` | ergänzt `GOLD_DIR` |
| `magda/labels.py` | ergänzt `validate_spans()` — Span-Domänenlogik |
| `magda/api.py` | ergänzt drei Gold-Endpunkte + `_words_hash()` |
| `tests/test_labels.py` | Tests für `validate_spans` |
| `tests/test_api.py` | Tests für die Gold-Endpunkte |
| `frontend/src/lib/types.ts` | ergänzt `Span`, `GoldAnnotation`, `GoldSummary` |
| `frontend/src/lib/api.ts` | ergänzt `gold`, `goldPage`, `saveGold` |
| `frontend/src/lib/bio.ts` | ergänzt `spansToTags()` |
| `frontend/src/features/annotate/span-editor.ts` | reine Auswahl- und Überlappungslogik |
| `frontend/src/features/annotate/use-annotation.ts` | Laden, Auto-Speichern, Speicherstatus |
| `frontend/src/features/annotate/label-legend.tsx` | Ziffernlegende + Fortschritt |
| `frontend/src/features/annotate/annotate-page.tsx` | Layout, Auswahl, Tastaturbelegung |
| `frontend/src/features/inspector/page-list.tsx` | ergänzt optionale Gold-Statusanzeige (Task 6) |
| `frontend/src/components/page-overlay.tsx` | reicht das Klick-Event durch (Task 6) |
| `frontend/src/app/router.tsx` | ergänzt Route `/annotate` |
| `frontend/src/app/top-nav.tsx` | ergänzt Navigationspunkt |

---

### Task 1: Span-Validierung und Gold-Verzeichnis

**Dateien:**
- Ändern: `magda/config.py` (nach Zeile 25)
- Ändern: `magda/labels.py` (ans Ende anhängen)
- Test: `tests/test_labels.py`

**Schnittstellen:**
- Erzeugt: `config.GOLD_DIR: Path`
- Erzeugt: `labels.validate_spans(spans: list[dict], num_words: int) -> list[str]` — gibt eine Liste von Fehlermeldungen zurück, leer bedeutet gültig. Wirft nicht, weil die API daraus eine 422-Antwort mit allen Fehlern auf einmal baut.

- [ ] **Schritt 1: Failing Test schreiben**

An `tests/test_labels.py` anhängen:

```python
from magda.labels import validate_spans


def test_validate_spans_akzeptiert_gueltige_spans():
    spans = [
        {"start": 0, "end": 1, "label": "BRAND"},
        {"start": 1, "end": 4, "label": "PRODUCT"},
    ]
    assert validate_spans(spans, num_words=10) == []


def test_validate_spans_meldet_index_ausserhalb():
    errors = validate_spans([{"start": 8, "end": 12, "label": "PRICE"}], num_words=10)
    assert len(errors) == 1
    assert "8-12" in errors[0]


def test_validate_spans_meldet_leeren_oder_verdrehten_span():
    errors = validate_spans([{"start": 5, "end": 5, "label": "PRICE"}], num_words=10)
    assert len(errors) == 1


def test_validate_spans_meldet_unbekanntes_label():
    errors = validate_spans([{"start": 0, "end": 1, "label": "FARBE"}], num_words=10)
    assert len(errors) == 1
    assert "FARBE" in errors[0]


def test_validate_spans_meldet_ueberlappung():
    # BIO kann Überlappungen nicht darstellen - was hier durchrutscht, ginge
    # beim Konvertieren still verloren.
    spans = [
        {"start": 0, "end": 3, "label": "PRODUCT"},
        {"start": 2, "end": 5, "label": "QUANTITY"},
    ]
    errors = validate_spans(spans, num_words=10)
    assert len(errors) == 1
    assert "berlappen" in errors[0]


def test_validate_spans_erlaubt_direkt_angrenzende_spans():
    spans = [
        {"start": 0, "end": 2, "label": "BRAND"},
        {"start": 2, "end": 4, "label": "PRODUCT"},
    ]
    assert validate_spans(spans, num_words=10) == []


def test_validate_spans_sammelt_mehrere_fehler():
    spans = [
        {"start": -1, "end": 2, "label": "BRAND"},
        {"start": 3, "end": 4, "label": "UNSINN"},
    ]
    assert len(validate_spans(spans, num_words=10)) == 2
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag prüfen**

Ausführen: `.venv/bin/python -m pytest tests/test_labels.py -v`
Erwartet: FAIL mit `ImportError: cannot import name 'validate_spans'`

- [ ] **Schritt 3: `GOLD_DIR` ergänzen**

In `magda/config.py` direkt nach der Zeile mit `EVAL_DIR` einfügen:

```python
# Handannotierte Referenz. Liegt bewusst außerhalb von data/ und wird
# versioniert: generierte Artefakte sind reproduzierbar, Handarbeit nicht.
GOLD_DIR = PROJECT_ROOT / "gold"
```

- [ ] **Schritt 4: `validate_spans` implementieren**

Ans Ende von `magda/labels.py` anhängen:

```python
def validate_spans(spans: list[dict], num_words: int) -> list[str]:
    """Prüft handannotierte Spans und sammelt alle Fehler ein.

    Gibt Meldungen zurück statt zu werfen, damit die API dem Frontend in einer
    Antwort sagen kann, was alles nicht stimmt. Anders als spans_to_bio() wird
    hier nichts stillschweigend verworfen: Bei Handarbeit ist ein ungültiger
    Span ein Fehler, kein Rauschen.
    """
    errors = []
    occupied: set[int] = set()

    for span in spans:
        start, end, entity = span.get("start"), span.get("end"), span.get("label")

        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"Span {start}-{end}: start und end müssen Zahlen sein.")
            continue
        if start < 0 or end > num_words or start >= end:
            errors.append(
                f"Span {start}-{end} liegt außerhalb von 0-{num_words} oder ist leer."
            )
            continue
        if entity not in ENTITY_TYPES:
            errors.append(f"Span {start}-{end}: unbekanntes Label {entity!r}.")
            continue

        overlap = occupied & set(range(start, end))
        if overlap:
            errors.append(f"Span {start}-{end} überlappen mit einem anderen Span.")
            continue
        occupied |= set(range(start, end))

    return errors
```

- [ ] **Schritt 5: Tests laufen lassen, Erfolg prüfen**

Ausführen: `.venv/bin/python -m pytest tests/test_labels.py -v`
Erwartet: PASS, alle Tests

- [ ] **Schritt 6: Vollständige Suite prüfen**

Ausführen: `.venv/bin/python -m pytest -q`
Erwartet: 44 passed (37 bisherige + 7 neue)

- [ ] **Schritt 7: Committen**

```bash
git add magda/config.py magda/labels.py tests/test_labels.py
git commit -m "Ergänze validate_spans und GOLD_DIR

Prüft handannotierte Spans auf Indexbereich, bekanntes Label und
Überlappung. Sammelt Fehler statt zu werfen, damit die API alle auf
einmal melden kann. Anders als spans_to_bio() wird nichts stillschweigend
verworfen - bei Handarbeit ist ein ungültiger Span ein Fehler."
```

---

### Task 2: Gold-Endpunkte in der API

**Dateien:**
- Ändern: `magda/api.py` (Docstring Zeile 1-9, Importe, neue Endpunkte ans Ende)
- Test: `tests/test_api.py` (Fixture Zeile 27 erweitern, Tests anhängen)

**Schnittstellen:**
- Verbraucht: `config.GOLD_DIR`, `labels.validate_spans` aus Task 1
- Erzeugt: `GET /api/gold`, `GET /api/gold/{page_id}`, `PUT /api/gold/{page_id}`
- Erzeugt: `api._words_hash(words: list[dict]) -> str` — SHA-256 über die Wort-Texte

Antwortform von `GET /api/gold/{page_id}`:

```json
{"page_id": "…", "words_hash": "…", "status": "untouched|in_progress|done",
 "annotator": "", "updated": null, "spans": []}
```

Antwortform von `GET /api/gold`: Liste aus `{page_id, catalog, status, annotator, num_spans}`.

- [ ] **Schritt 1: Fixture um `GOLD_DIR` erweitern**

In `tests/test_api.py` Zeile 27 die Tupel-Liste ergänzen:

```python
    for name in ("RAW_DIR", "WORDS_DIR", "IMAGES_DIR", "LABELED_DIR", "EVAL_DIR", "CHECKPOINTS_DIR", "GOLD_DIR"):
```

- [ ] **Schritt 2: Failing Tests schreiben**

An `tests/test_api.py` anhängen:

```python
def _hash_of(client, page_id: str) -> str:
    return client.get(f"/api/gold/{page_id}").json()["words_hash"]


def test_gold_unberuehrte_seite_liefert_leeren_entwurf(client):
    _write_words("462828_p1")

    body = client.get("/api/gold/462828_p1").json()

    assert body["status"] == "untouched"
    assert body["spans"] == []
    assert body["updated"] is None
    assert len(body["words_hash"]) == 64


def test_gold_unbekannte_seite_gibt_404(client):
    assert client.get("/api/gold/gibtsnicht_p1").status_code == 404


def test_gold_speichern_und_wiederlesen(client):
    _write_words("462828_p1")
    payload = {
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "in_progress",
        "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}],
    }

    assert client.put("/api/gold/462828_p1", json=payload).status_code == 200

    body = client.get("/api/gold/462828_p1").json()
    assert body["status"] == "in_progress"
    assert body["annotator"] == "noah"
    assert body["spans"] == [{"start": 0, "end": 1, "label": "PRODUCT"}]
    assert body["updated"] is not None


def test_gold_speichert_spans_nicht_als_tags(client):
    # Das Speicherformat ist Teil des Vertrags: Spans sind git-diffbar,
    # eine Liste aus 180 "O"-Einträgen ist es nicht.
    _write_words("462828_p1")
    client.put("/api/gold/462828_p1", json={
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "done",
        "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}],
    })

    with open(config.GOLD_DIR / "462828_p1.json") as f:
        stored = json.load(f)

    assert "tags" not in stored
    assert stored["spans"] == [{"start": 0, "end": 1, "label": "PRODUCT"}]


def test_gold_lehnt_ueberlappende_spans_ab(client):
    _write_words("462828_p1")
    resp = client.put("/api/gold/462828_p1", json={
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "in_progress",
        "annotator": "noah",
        "spans": [
            {"start": 0, "end": 2, "label": "PRODUCT"},
            {"start": 1, "end": 2, "label": "BRAND"},
        ],
    })
    assert resp.status_code == 422


def test_gold_lehnt_unbekanntes_label_ab(client):
    _write_words("462828_p1")
    resp = client.put("/api/gold/462828_p1", json={
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "in_progress",
        "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "FARBE"}],
    })
    assert resp.status_code == 422


def test_gold_lehnt_veralteten_hash_mit_409_ab(client):
    # Ändert sich Schritt 02, zeigen die Indizes auf andere Wörter. Der Hash
    # macht das laut, statt die Annotation still zu verfälschen.
    _write_words("462828_p1")
    resp = client.put("/api/gold/462828_p1", json={
        "words_hash": "0" * 64,
        "status": "in_progress",
        "annotator": "noah",
        "spans": [],
    })
    assert resp.status_code == 409


def test_gold_uebersicht_listet_auch_unberuehrte_seiten(client):
    _write_words("462828_p1")
    _write_words("462828_p2")
    client.put("/api/gold/462828_p2", json={
        "words_hash": _hash_of(client, "462828_p2"),
        "status": "done",
        "annotator": "kjell",
        "spans": [{"start": 0, "end": 1, "label": "PRICE"}],
    })

    body = client.get("/api/gold").json()

    assert body == [
        {"page_id": "462828_p1", "catalog": "462828", "status": "untouched",
         "annotator": "", "num_spans": 0},
        {"page_id": "462828_p2", "catalog": "462828", "status": "done",
         "annotator": "kjell", "num_spans": 1},
    ]
```

- [ ] **Schritt 3: Tests laufen lassen, Fehlschlag prüfen**

Ausführen: `.venv/bin/python -m pytest tests/test_api.py -v -k gold`
Erwartet: FAIL, alle Gold-Tests mit 404 (Routen existieren noch nicht)

- [ ] **Schritt 4: Modul-Docstring ehrlich machen**

In `magda/api.py` die Zeilen 1-5 ersetzen durch:

```python
"""API für das Frontend.

Liest data/ direkt von der Platte. Schreiben darf sie ausschließlich nach
gold/ (handannotierte Referenz) - alles andere unter data/ erzeugen die
Pipeline-Skripte. Dieselbe Beschränkung wie beim Runner: eng umrissen statt
allgemein.  Start: uvicorn magda.api:app --reload (Port 8000, das
Frontend-Dev-Setup proxied /api hierhin).
"""
```

- [ ] **Schritt 5: Importe ergänzen**

In `magda/api.py` die Importzeilen anpassen:

```python
import base64
import hashlib
import json
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from magda import config, runner
from magda.labels import ENTITY_TYPES, id2label, validate_spans
from magda.ocr import extract_words, normalize_bbox, render_png
```

- [ ] **Schritt 6: Gold-Endpunkte implementieren**

Ans Ende von `magda/api.py` anhängen:

```python
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
        }
        if gold_file.exists():
            with open(gold_file) as f:
                gold = json.load(f)
            entry["status"] = gold.get("status", "in_progress")
            entry["annotator"] = gold.get("annotator", "")
            entry["num_spans"] = len(gold.get("spans", []))
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
        }

    with open(gold_file) as f:
        gold = json.load(f)
    # Der gespeicherte Hash wird mitgeliefert, nicht der aktuelle: Nur so
    # erkennt das Frontend, dass die Wortliste sich seither geändert hat.
    return {"page_id": page_id, "updated": None, **gold}


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
    with open(config.GOLD_DIR / f"{page_id}.json", "w") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)

    return record
```

- [ ] **Schritt 7: Tests laufen lassen, Erfolg prüfen**

Ausführen: `.venv/bin/python -m pytest tests/test_api.py -v`
Erwartet: PASS, alle Tests inklusive der acht neuen

- [ ] **Schritt 8: Vollständige Suite prüfen**

Ausführen: `.venv/bin/python -m pytest -q`
Erwartet: 52 passed

- [ ] **Schritt 9: Committen**

```bash
git add magda/api.py tests/test_api.py
git commit -m "Ergänze Gold-Endpunkte in der API

GET/PUT auf gold/, mit serverseitiger Prüfung von Indexbereich, Label und
Überlappung. Ein words_hash über die Wort-Texte lehnt Annotationen ab,
deren Wortliste sich seit dem Anlegen geändert hat - sonst zeigen die
Indizes still auf andere Wörter.

Die API ist damit nicht mehr read-only. Der Docstring sagt das jetzt, und
die Schreibfläche bleibt auf gold/ beschränkt."
```

---

### Task 3: `spansToTags` im Frontend

**Dateien:**
- Ändern: `frontend/src/lib/bio.ts`
- Ändern: `frontend/src/lib/types.ts`
- Test: `frontend/src/lib/bio.test.ts`

**Schnittstellen:**
- Erzeugt: `Span` in `types.ts` — `{ start: number; end: number; label: string }`
- Erzeugt: `spansToTags(spans: Span[], wordCount: number): string[]` — Gegenstück zu `spans_to_bio()` in Python, damit `PageOverlay` unverändert bleibt

- [ ] **Schritt 1: Failing Test schreiben**

An `frontend/src/lib/bio.test.ts` anhängen (Import in Zeile 2 auf `import { groupEntities, spansToTags } from "./bio"` erweitern):

```ts
describe("spansToTags", () => {
  it("erzeugt B-/I-Folgen aus Spans", () => {
    const tags = spansToTags(
      [
        { start: 0, end: 1, label: "BRAND" },
        { start: 1, end: 3, label: "QUANTITY" },
      ],
      4,
    )
    expect(tags).toEqual(["B-BRAND", "B-QUANTITY", "I-QUANTITY", "O"])
  })

  it("füllt eine Seite ohne Spans komplett mit O", () => {
    expect(spansToTags([], 3)).toEqual(["O", "O", "O"])
  })

  it("ist der Rundlauf zu groupEntities", () => {
    const words = [{ text: "MAGICO" }, { text: "je" }, { text: "200" }, { text: "g" }]
    const spans = [
      { start: 0, end: 1, label: "BRAND" },
      { start: 1, end: 4, label: "QUANTITY" },
    ]
    const entities = groupEntities(words, spansToTags(spans, words.length))
    expect(entities.map((e) => ({ start: e.start, end: e.end, label: e.type }))).toEqual(spans)
  })
})
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag prüfen**

Ausführen: `cd frontend && npx vitest run src/lib/bio.test.ts`
Erwartet: FAIL mit `spansToTags is not a function`

- [ ] **Schritt 3: `Span` in `types.ts` ergänzen**

An `frontend/src/lib/types.ts` anhängen:

```ts
/** Wort-Span einer Gold-Annotation. end ist exklusiv, wie bei range(). */
export interface Span {
  start: number
  end: number
  label: string
}

export interface GoldAnnotation {
  page_id: string
  words_hash: string
  status: "untouched" | "in_progress" | "done"
  annotator: string
  updated: string | null
  spans: Span[]
}

export interface GoldSummary {
  page_id: string
  catalog: string
  status: "untouched" | "in_progress" | "done"
  annotator: string
  num_spans: number
}
```

- [ ] **Schritt 4: `spansToTags` implementieren**

An `frontend/src/lib/bio.ts` anhängen (und `import type { Span } from "./types"` an den Dateianfang):

```ts
/** Spans -> BIO-Tags. Gegenstück zu labels.spans_to_bio() in Python. */
export function spansToTags(spans: Span[], wordCount: number): string[] {
  const tags: string[] = new Array(wordCount).fill("O")
  for (const span of spans) {
    tags[span.start] = `B-${span.label}`
    for (let i = span.start + 1; i < span.end; i++) tags[i] = `I-${span.label}`
  }
  return tags
}
```

- [ ] **Schritt 5: Tests laufen lassen, Erfolg prüfen**

Ausführen: `cd frontend && npx vitest run src/lib/bio.test.ts`
Erwartet: PASS, 6 Tests

- [ ] **Schritt 6: Committen**

```bash
git add frontend/src/lib/bio.ts frontend/src/lib/bio.test.ts frontend/src/lib/types.ts
git commit -m "Ergänze spansToTags als Gegenstück zu groupEntities

Der Annotator hält Spans, PageOverlay erwartet Tags. Die Umrechnung im
Frontend hält PageOverlay unverändert, statt es um einen zweiten
Datenpfad zu erweitern."
```

---

### Task 4: Auswahl- und Überlappungslogik

**Dateien:**
- Erstellen: `frontend/src/features/annotate/span-editor.ts`
- Test: `frontend/src/features/annotate/span-editor.test.ts`

**Schnittstellen:**
- Verbraucht: `Span` aus `lib/types.ts` (Task 3)
- Erzeugt: `applyLabel(spans, start, end, label): Span[]` — setzt einen Span, überlappende weichen
- Erzeugt: `removeRange(spans, start, end): Span[]` — entfernt alle Spans, die den Bereich schneiden
- Erzeugt: `spanAt(spans, index): Span | null` — findet den Span, der einen Wortindex enthält

- [ ] **Schritt 1: Failing Test schreiben**

`frontend/src/features/annotate/span-editor.test.ts` erstellen:

```ts
import { describe, expect, it } from "vitest"
import { applyLabel, removeRange, spanAt } from "./span-editor"

const spans = [
  { start: 0, end: 2, label: "BRAND" },
  { start: 4, end: 6, label: "PRICE" },
]

describe("applyLabel", () => {
  it("fügt einen Span ein und hält die Liste nach start sortiert", () => {
    expect(applyLabel(spans, 2, 4, "PRODUCT")).toEqual([
      { start: 0, end: 2, label: "BRAND" },
      { start: 2, end: 4, label: "PRODUCT" },
      { start: 4, end: 6, label: "PRICE" },
    ])
  })

  it("verdrängt überlappende Spans - der neue gewinnt", () => {
    expect(applyLabel(spans, 1, 5, "PRODUCT")).toEqual([
      { start: 1, end: 5, label: "PRODUCT" },
    ])
  })

  it("ersetzt einen Span bei identischem Bereich", () => {
    expect(applyLabel(spans, 0, 2, "PRODUCT")).toEqual([
      { start: 0, end: 2, label: "PRODUCT" },
      { start: 4, end: 6, label: "PRICE" },
    ])
  })

  it("lässt direkt angrenzende Spans stehen", () => {
    const result = applyLabel([{ start: 0, end: 2, label: "BRAND" }], 2, 3, "PRICE")
    expect(result).toHaveLength(2)
  })

  it("mutiert die Eingabe nicht", () => {
    const original = [...spans]
    applyLabel(spans, 1, 5, "PRODUCT")
    expect(spans).toEqual(original)
  })
})

describe("removeRange", () => {
  it("entfernt jeden Span, der den Bereich schneidet", () => {
    expect(removeRange(spans, 1, 2)).toEqual([{ start: 4, end: 6, label: "PRICE" }])
  })

  it("lässt alles stehen, wenn nichts überlappt", () => {
    expect(removeRange(spans, 2, 4)).toEqual(spans)
  })
})

describe("spanAt", () => {
  it("findet den Span, der den Index enthält", () => {
    expect(spanAt(spans, 5)).toEqual({ start: 4, end: 6, label: "PRICE" })
  })

  it("gibt null für ein Wort ohne Label", () => {
    expect(spanAt(spans, 3)).toBeNull()
  })

  it("behandelt end als exklusiv", () => {
    expect(spanAt(spans, 2)).toBeNull()
  })
})
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag prüfen**

Ausführen: `cd frontend && npx vitest run src/features/annotate/span-editor.test.ts`
Erwartet: FAIL, Modul nicht gefunden

- [ ] **Schritt 3: Implementieren**

`frontend/src/features/annotate/span-editor.ts` erstellen:

```ts
// Reine Auswahl-Logik des Annotators, bewusst ohne React: Das ist der Teil,
// bei dem sich Fehler still in die Gold-Daten schreiben würden.

import type { Span } from "@/lib/types"

function overlaps(span: Span, start: number, end: number): boolean {
  return span.start < end && start < span.end
}

/** Entfernt jeden Span, der [start, end) schneidet. */
export function removeRange(spans: Span[], start: number, end: number): Span[] {
  return spans.filter((s) => !overlaps(s, start, end))
}

/** Setzt einen Span. Überlappende weichen - eine Regel ohne Sonderfälle. */
export function applyLabel(spans: Span[], start: number, end: number, label: string): Span[] {
  return [...removeRange(spans, start, end), { start, end, label }].sort(
    (a, b) => a.start - b.start,
  )
}

/** Der Span, der einen Wortindex enthält - für Klick auf ein gelabeltes Wort. */
export function spanAt(spans: Span[], index: number): Span | null {
  return spans.find((s) => index >= s.start && index < s.end) ?? null
}
```

- [ ] **Schritt 4: Tests laufen lassen, Erfolg prüfen**

Ausführen: `cd frontend && npx vitest run src/features/annotate/span-editor.test.ts`
Erwartet: PASS, 10 Tests

- [ ] **Schritt 5: Committen**

```bash
git add frontend/src/features/annotate/span-editor.ts frontend/src/features/annotate/span-editor.test.ts
git commit -m "Ergänze Span-Editor-Logik für den Annotator

Setzen, Entfernen und Auffinden von Spans als reine Funktionen ohne React.
Beim Überlappen gewinnt der neue Span - vorhersagbar schlägt clever, wenn
man vierzig Seiten am Stück annotiert."
```

---

### Task 5: API-Client und Annotations-Hook

**Dateien:**
- Ändern: `magda/api.py` (`get_gold`)
- Ändern: `tests/test_api.py`
- Ändern: `frontend/src/lib/api.ts`
- Ändern: `frontend/src/lib/types.ts`
- Erstellen: `frontend/src/features/annotate/use-annotation.ts`

**Schnittstellen:**
- Verbraucht: `GoldAnnotation`, `GoldSummary`, `Span` aus `lib/types.ts` (Task 3); Endpunkte aus Task 2
- Erzeugt: `GET /api/gold/{page_id}` liefert zusätzlich `stale: bool`
- Erzeugt: `api.gold()`, `api.goldPage(id)`, `api.saveGold(id, payload)`
- Erzeugt: `useAnnotation(pageId: string | null, annotator: string)` mit Rückgabe:
  `{ spans, status, saveState, conflict, isPending, setSpans, setStatus, retry }`
  wobei `saveState: "saved" | "saving" | "error"` und
  `status: "untouched" | "in_progress" | "done"`

- [ ] **Schritt 1: `stale`-Flag in `get_gold` ergänzen**

`GET /api/gold/{page_id}` liefert bei vorhandener Gold-Datei den *gespeicherten*
`words_hash`, nicht den aktuellen. Damit erkennt das Frontend eine veraltete
Wortliste erst beim Speichern über den 409 — bis dahin zeigt es stillschweigend
Labels, die auf andere Wörter zeigen. Wer nur liest und nichts ändert, merkt nie
etwas. Genau dieser Fall ist der Grund, warum es den Hash gibt.

Der Server hat beide Werte bereits vorliegen und muss sie nur vergleichen.

In `magda/api.py` in `get_gold` den Rückgabewert für den Fall einer vorhandenen
Gold-Datei ergänzen:

```python
    with open(gold_file) as f:
        gold = json.load(f)
    # Der gespeicherte Hash wird mitgeliefert, nicht der aktuelle - nur so kann
    # das Frontend beim Speichern denselben Wert zurückschicken. stale sagt
    # ihm vorab, dass die Wortliste sich seither geändert hat.
    return {
        "page_id": page_id,
        "updated": None,
        **gold,
        "stale": gold.get("words_hash") != current_hash,
    }
```

Im Zweig für die unberührte Seite `"stale": False` ergänzen.

Test in `tests/test_api.py`:

```python
def test_gold_meldet_veraltete_wortliste_als_stale(client):
    _write_words("462828_p1")
    client.put("/api/gold/462828_p1", json={
        "words_hash": _hash_of(client, "462828_p1"),
        "status": "done",
        "annotator": "noah",
        "spans": [{"start": 0, "end": 1, "label": "PRODUCT"}],
    })
    assert client.get("/api/gold/462828_p1").json()["stale"] is False

    # Schritt 02 lief erneut und die Wortliste hat sich geändert.
    _write_words("462828_p1", {
        "page_id": "462828_p1", "width": 595.28, "height": 841.89,
        "words": [{"text": "Anders", "bbox": [1, 2, 3, 4]}],
    })

    assert client.get("/api/gold/462828_p1").json()["stale"] is True
```

Ausführen: `.venv/bin/python -m pytest tests/test_api.py -v -k gold`
Erwartet: PASS, jetzt 10 Gold-Tests

- [ ] **Schritt 2: API-Client erweitern**

In `frontend/src/lib/types.ts` das Feld an `GoldAnnotation` ergänzen:

```ts
  /** Serverseitig: passt words_hash noch zur aktuellen Wortliste? */
  stale: boolean
```


In `frontend/src/lib/api.ts` den Typimport um `GoldAnnotation, GoldSummary, Span` erweitern und in das `api`-Objekt einfügen:

```ts
  gold: () => fetchJson<GoldSummary[]>("/api/gold"),
  goldPage: (id: string) => fetchJson<GoldAnnotation>(`/api/gold/${id}`),
  saveGold: (
    id: string,
    payload: { words_hash: string; status: "in_progress" | "done"; annotator: string; spans: Span[] },
  ) =>
    fetchJson<GoldAnnotation>(`/api/gold/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
```

- [ ] **Schritt 3: Hook implementieren**

`frontend/src/features/annotate/use-annotation.ts` erstellen:

```ts
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import type { Span } from "@/lib/types"

export type SaveState = "saved" | "saving" | "error"
export type PageStatus = "untouched" | "in_progress" | "done"

/** Annotation einer Seite: laden, im Speicher halten, verzögert sichern.
 *
 * Auto-Speichern darf nicht stillschweigend scheitern - sonst annotiert man
 * zwanzig Minuten ins Leere. Der Fehlerfall bleibt deshalb sichtbar und der
 * ungesicherte Zustand im Speicher, damit ein erneuter Versuch nichts verliert.
 */
export function useAnnotation(pageId: string | null, annotator: string) {
  const queryClient = useQueryClient()
  const [spans, setSpansState] = useState<Span[]>([])
  const [status, setStatusState] = useState<PageStatus>("untouched")
  const [saveState, setSaveState] = useState<SaveState>("saved")
  const [conflict, setConflict] = useState(false)

  const hashRef = useRef<string>("")
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingRef = useRef<{ spans: Span[]; status: PageStatus } | null>(null)

  const query = useQuery({
    queryKey: ["gold", pageId],
    queryFn: () => api.goldPage(pageId!),
    enabled: pageId !== null,
  })

  // Serverzustand in den lokalen Zustand übernehmen, wenn die Seite wechselt.
  useEffect(() => {
    if (!query.data) return
    setSpansState(query.data.spans)
    setStatusState(query.data.status)
    hashRef.current = query.data.words_hash
    setSaveState("saved")
    // Der Server hat den gespeicherten Hash gegen die aktuelle Wortliste
    // geprüft. Ohne das wüssten wir es erst beim ersten Speicherversuch.
    setConflict(query.data.stale)
  }, [query.data])

  const flush = useCallback(async () => {
    if (!pageId || !pendingRef.current) return
    const { spans: s, status: st } = pendingRef.current
    setSaveState("saving")
    try {
      await api.saveGold(pageId, {
        words_hash: hashRef.current,
        // "untouched" ist ein Anzeigezustand, kein speicherbarer.
        status: st === "done" ? "done" : "in_progress",
        annotator,
        spans: s,
      })
      pendingRef.current = null
      setSaveState("saved")
      queryClient.invalidateQueries({ queryKey: ["gold"] })
    } catch (err) {
      if (err instanceof Error && err.message.includes("Wortliste")) setConflict(true)
      setSaveState("error")
    }
  }, [pageId, annotator, queryClient])

  const schedule = useCallback(
    (next: { spans: Span[]; status: PageStatus }) => {
      pendingRef.current = next
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(flush, 300)
    },
    [flush],
  )

  const setSpans = useCallback(
    (next: Span[]) => {
      setSpansState(next)
      const nextStatus: PageStatus = status === "done" ? "done" : "in_progress"
      setStatusState(nextStatus)
      schedule({ spans: next, status: nextStatus })
    },
    [status, schedule],
  )

  const setStatus = useCallback(
    (next: PageStatus) => {
      setStatusState(next)
      schedule({ spans, status: next })
    },
    [spans, schedule],
  )

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current) }, [])

  return {
    spans, status, saveState, conflict,
    isPending: query.isPending && pageId !== null,
    setSpans, setStatus, retry: flush,
  }
}
```

- [ ] **Schritt 4: Typprüfung laufen lassen**

Ausführen: `cd frontend && npx tsc --noEmit`
Erwartet: keine Fehler

- [ ] **Schritt 5: Bestehende Tests prüfen**

Ausführen: `cd frontend && npm test`
Erwartet: alle bisherigen Tests grün

Ausführen: `.venv/bin/python -m pytest -q` (aus dem Projektroot)
Erwartet: 53 passed — die 52 bisherigen plus der neue `stale`-Test

- [ ] **Schritt 6: Committen**

```bash
git add magda/api.py tests/test_api.py frontend/src/lib/api.ts frontend/src/lib/types.ts frontend/src/features/annotate/use-annotation.ts
git commit -m "Ergänze Gold-API-Client und Annotations-Hook

Auto-Speichern nach 300 ms Ruhe. Der Fehlerfall bleibt sichtbar und der
ungesicherte Zustand im Speicher, damit ein Wiederholen nichts verliert.

get_gold liefert jetzt ein stale-Flag: Der Server vergleicht den
gespeicherten words_hash gegen die aktuelle Wortliste. Ohne das merkt das
Frontend eine veraltete Annotation erst beim Speichern - wer nur liest,
sähe stillschweigend Labels, die auf andere Wörter zeigen."
```

---

### Task 6: Annotations-Oberfläche

**Dateien:**
- Ändern: `frontend/src/features/inspector/page-list.tsx`
- Ändern: `frontend/src/components/page-overlay.tsx`
- Erstellen: `frontend/src/features/annotate/label-legend.tsx`
- Erstellen: `frontend/src/features/annotate/annotate-page.tsx`
- Test: `frontend/src/features/annotate/annotate-page.test.tsx`

**Schnittstellen:**
- Verbraucht: `useAnnotation` (Task 5), `applyLabel`/`removeRange`/`spanAt` (Task 4), `spansToTags` und `GoldSummary` (Task 3)
- Erzeugt: `PageList` nimmt optional `goldStatus?: GoldSummary[]` entgegen; ohne die Prop verhält sie sich unverändert, der Inspektor bleibt also unberührt
- Erzeugt: `PageOverlay.onWordClick` bekommt das Maus-Event als zweiten Parameter: `(index: number, event: React.MouseEvent) => void`. Abwärtskompatibel — bestehende Aufrufer ignorieren ihn.
- Erzeugt: `AnnotatePage` — Export der Route `/annotate`

- [ ] **Schritt 1: `PageList` um den Gold-Status erweitern**

Das muss vor der Seite passieren, sonst kennt TypeScript die Prop nicht, die `annotate-page.tsx` in Schritt 3 übergibt.

In `frontend/src/features/inspector/page-list.tsx` den Typimport um `GoldSummary` ergänzen und die Props erweitern:

```tsx
interface PageListProps {
  pages: PageSummary[]
  selected: string | null
  onSelect: (id: string) => void
  /** Wenn gesetzt, zeigt der Punkt den Gold-Status statt "gelabelt". */
  goldStatus?: GoldSummary[]
}
```

In der Komponentensignatur `goldStatus` aufnehmen und vor dem `return` ergänzen:

```tsx
  const goldById = useMemo(
    () => new Map((goldStatus ?? []).map((g) => [g.page_id, g.status])),
    [goldStatus],
  )
```

Das `<span>` mit dem Statuspunkt (aktuell Zeile 72-78) ersetzen durch:

```tsx
                    {goldStatus ? (
                      <span
                        className={cn(
                          "size-2 shrink-0 rounded-full",
                          goldById.get(p.page_id) === "done"
                            ? "bg-[var(--riso-blue)]"
                            : goldById.get(p.page_id) === "in_progress"
                              ? "bg-primary"
                              : "border border-muted-foreground",
                        )}
                        title={goldById.get(p.page_id) ?? "unberührt"}
                      />
                    ) : (
                      <span
                        className={cn(
                          "size-2 shrink-0 rounded-full",
                          p.labeled ? "bg-[var(--riso-blue)]" : "border border-muted-foreground",
                        )}
                        title={p.labeled ? "gelabelt" : "offen"}
                      />
                    )}
```

- [ ] **Schritt 2: `PageOverlay` das Klick-Event durchreichen lassen**

Der Annotator braucht die Shift-Taste, um die Auswahl zu erweitern. `PageOverlay`
reicht bisher nur den Wortindex weiter. Ein optionaler zweiter Parameter löst
das, ohne einen bestehenden Aufrufer zu brechen.

In `frontend/src/components/page-overlay.tsx` die Prop-Deklaration (Zeile 18-19)
ändern:

```tsx
  /** Klick auf eine Box, z. B. um sie in der Liste auszuwählen. */
  onWordClick?: (index: number, event: React.MouseEvent) => void
```

Und den Handler (Zeile 84):

```tsx
              onClick={(e) => onWordClick?.(i, e)}
```

`inspector-page.tsx` bleibt unverändert — `selectWord(wordIdx)` nimmt nur einen
Parameter und ignoriert den zweiten.

- [ ] **Schritt 3: Legende schreiben**

`frontend/src/features/annotate/label-legend.tsx` erstellen:

```tsx
import { entityColor } from "@/lib/entities"
import { cn } from "@/lib/utils"

interface LabelLegendProps {
  entityTypes: string[]
  /** Anzahl fertig annotierter Seiten und Gesamtzahl. */
  done: number
  total: number
}

export function LabelLegend({ entityTypes, done, total }: LabelLegendProps) {
  return (
    <div className="space-y-3 rounded-lg border-2 border-foreground bg-card p-4">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          Fortschritt
        </p>
        <p className="font-mono text-sm font-semibold tabular-nums">
          {done} / {total} Seiten fertig
        </p>
      </div>

      <ul className="space-y-1">
        {entityTypes.map((type, i) => (
          <li key={type} className="flex items-center gap-2">
            <kbd className="w-5 rounded border border-foreground bg-background text-center font-mono text-[11px]">
              {i + 1}
            </kbd>
            <span
              className="size-3 shrink-0 rounded-sm"
              style={{ backgroundColor: entityColor(entityTypes, type) }}
            />
            <span className="font-mono text-xs">{type}</span>
          </li>
        ))}
      </ul>

      <dl className="space-y-0.5 border-t border-border pt-2 font-mono text-[11px] text-muted-foreground">
        {[
          ["Klick", "Wort wählen"],
          ["Shift-Klick", "Auswahl erweitern"],
          ["0 / Entf", "Label entfernen"],
          ["← →", "Seite wechseln"],
          ["f", "Seite fertig"],
        ].map(([key, desc]) => (
          <div key={key} className={cn("flex justify-between gap-2")}>
            <dt className="font-semibold">{key}</dt>
            <dd>{desc}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
```

- [ ] **Schritt 4: Seite schreiben**

`frontend/src/features/annotate/annotate-page.tsx` erstellen:

```tsx
import { useQuery } from "@tanstack/react-query"
import { Check, ChevronLeft, ChevronRight } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { PageOverlay } from "@/components/page-overlay"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { spansToTags } from "@/lib/bio"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { PageList } from "@/features/inspector/page-list"
import { LabelLegend } from "./label-legend"
import { applyLabel, removeRange, spanAt } from "./span-editor"
import { useAnnotation } from "./use-annotation"

const SAVE_LABEL = {
  saved: "gespeichert",
  saving: "speichert…",
  error: "nicht gespeichert",
} as const

export function AnnotatePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selected = searchParams.get("page")
  const [annotator, setAnnotator] = useState(
    () => localStorage.getItem("magda.annotator") ?? "",
  )
  // Auswahl über Wortindizes; anchor = erster Klick, focus = Shift-Klick.
  const [sel, setSel] = useState<{ anchor: number; focus: number } | null>(null)

  const schema = useQuery({ queryKey: ["schema"], queryFn: api.schema })
  const pages = useQuery({ queryKey: ["pages"], queryFn: api.pages })
  const gold = useQuery({ queryKey: ["gold"], queryFn: api.gold })
  const page = useQuery({
    queryKey: ["page", selected],
    queryFn: () => api.page(selected!),
    enabled: selected !== null,
  })

  const ann = useAnnotation(selected, annotator)
  const entityTypes = schema.data?.entity_types ?? []
  const ids = useMemo(() => (pages.data ?? []).map((p) => p.page_id), [pages.data])
  const idx = selected ? ids.indexOf(selected) : -1

  useEffect(() => {
    localStorage.setItem("magda.annotator", annotator)
  }, [annotator])

  function goto(i: number) {
    if (i < 0 || i >= ids.length) return
    setSel(null)
    setSearchParams({ page: ids[i] })
  }

  const range = sel ? { start: Math.min(sel.anchor, sel.focus), end: Math.max(sel.anchor, sel.focus) + 1 } : null

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return
      if (e.key === "ArrowLeft") return goto(idx - 1)
      if (e.key === "ArrowRight") return goto(idx + 1)
      if (ann.conflict) return
      if (e.key === "f") return ann.setStatus(ann.status === "done" ? "in_progress" : "done")
      if (!range) return
      if (e.key === "0" || e.key === "Delete" || e.key === "Backspace") {
        ann.setSpans(removeRange(ann.spans, range.start, range.end))
        return setSel(null)
      }
      const n = Number(e.key)
      if (n >= 1 && n <= entityTypes.length) {
        ann.setSpans(applyLabel(ann.spans, range.start, range.end, entityTypes[n - 1]))
        setSel(null)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  /** Klick auf ein gelabeltes Wort wählt den ganzen Span, sonst das Wort. */
  function onWordClick(i: number, shift: boolean) {
    if (shift && sel) return setSel({ ...sel, focus: i })
    const existing = spanAt(ann.spans, i)
    setSel(existing ? { anchor: existing.start, focus: existing.end - 1 } : { anchor: i, focus: i })
  }

  if (pages.isPending || schema.isPending) return <Skeleton className="h-40 w-full" />

  const data = page.data
  const doneCount = (gold.data ?? []).filter((g) => g.status === "done").length
  const tags = data ? spansToTags(ann.spans, data.words.length) : undefined

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="text-3xl font-extrabold tracking-tight">Annotieren</h1>
          <p className="font-mono text-xs text-muted-foreground">
            {idx >= 0 ? `${idx + 1} / ${ids.length}` : `${ids.length} Seiten`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            value={annotator}
            onChange={(e) => setAnnotator(e.target.value)}
            placeholder="Dein Name"
            className="h-8 w-36"
            aria-label="Annotator"
          />
          <span
            className={cn(
              "font-mono text-[11px] uppercase tracking-widest",
              ann.saveState === "error" ? "text-destructive" : "text-muted-foreground",
            )}
          >
            {SAVE_LABEL[ann.saveState]}
          </span>
          {ann.saveState === "error" && (
            <Button variant="outline" size="sm" onClick={ann.retry}>
              Erneut
            </Button>
          )}
          <Button variant="outline" size="sm" aria-label="Vorherige Seite"
            disabled={idx <= 0} onClick={() => goto(idx - 1)}>
            <ChevronLeft className="size-4" />
          </Button>
          <Button variant="outline" size="sm" aria-label="Nächste Seite"
            disabled={idx >= ids.length - 1} onClick={() => goto(idx + 1)}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      <div className="grid min-w-0 gap-5 lg:grid-cols-[240px_minmax(0,1fr)_260px]">
        <PageList
          pages={pages.data ?? []}
          selected={selected}
          onSelect={(id) => { setSel(null); setSearchParams({ page: id }) }}
          goldStatus={gold.data}
        />

        <div className="min-w-0 space-y-3">
          {!selected && (
            <div className="flex h-96 items-center justify-center rounded-lg border-2 border-dashed border-foreground/30">
              <p className="text-muted-foreground">Seite links auswählen</p>
            </div>
          )}

          {ann.conflict && (
            <Alert variant="destructive">
              <AlertTitle>Wortliste hat sich geändert</AlertTitle>
              <AlertDescription>
                Diese Annotation passt nicht mehr zu den Wortindizes aus Schritt 02
                und wird nicht gespeichert. Die Seite muss neu annotiert werden.
              </AlertDescription>
            </Alert>
          )}

          {selected && (page.isPending || ann.isPending) && (
            <Skeleton className="aspect-[595/842] w-full" />
          )}

          {selected && data && !page.isPending && (
            <>
              <div className="flex items-center justify-between gap-3 rounded-lg border-2 border-foreground bg-card px-4 py-2.5">
                <p className="font-mono text-sm tabular-nums">
                  {ann.spans.length} Spans · {data.words.length} Wörter
                </p>
                <Button
                  size="sm"
                  variant={ann.status === "done" ? "default" : "outline"}
                  disabled={ann.conflict}
                  onClick={() => ann.setStatus(ann.status === "done" ? "in_progress" : "done")}
                >
                  <Check className="size-4" />
                  {ann.status === "done" ? "Fertig" : "Als fertig markieren"}
                </Button>
              </div>

              <PageOverlay
                imageUrl={api.pageImageUrl(selected)}
                width={data.width}
                height={data.height}
                words={data.words}
                tags={tags}
                entityTypes={entityTypes}
                highlight={range}
                onWordClick={(i, e) => onWordClick(i, e.shiftKey)}
              />
            </>
          )}
        </div>

        <div className="lg:sticky lg:top-24 lg:self-start">
          <LabelLegend entityTypes={entityTypes} done={doneCount} total={ids.length} />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Schritt 5: Test schreiben**

`frontend/src/features/annotate/annotate-page.test.tsx` erstellen:

```tsx
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { AnnotatePage } from "./annotate-page"

const PAGE = {
  page_id: "462828_p1",
  width: 100,
  height: 100,
  words: [
    { text: "MAGICO", bbox: [0, 0, 10, 10] },
    { text: "Kaffee", bbox: [12, 0, 22, 10] },
  ],
}

function setup() {
  mockFetch({
    "/api/schema": { entity_types: ["PRODUCT", "BRAND"] },
    "/api/pages/462828_p1": PAGE,
    "/api/pages": [{ page_id: "462828_p1", catalog: "462828", labeled: false }],
    "/api/gold/462828_p1": {
      page_id: "462828_p1", words_hash: "abc", status: "untouched",
      annotator: "", updated: null, spans: [],
    },
    "/api/gold": [{
      page_id: "462828_p1", catalog: "462828", status: "untouched",
      annotator: "", num_spans: 0,
    }],
  })
  return renderWithProviders(<AnnotatePage />, { route: "/annotate?page=462828_p1" })
}

afterEach(() => vi.unstubAllGlobals())

describe("AnnotatePage", () => {
  it("zeigt die Ziffernlegende zu den Entity-Typen", async () => {
    setup()
    expect(await screen.findByText("PRODUCT")).toBeInTheDocument()
    expect(screen.getByText("BRAND")).toBeInTheDocument()
  })

  it("zeigt den Fortschritt über alle Seiten", async () => {
    setup()
    expect(await screen.findByText("0 / 1 Seiten fertig")).toBeInTheDocument()
  })

  it("meldet den Speicherzustand", async () => {
    setup()
    expect(await screen.findByText("gespeichert")).toBeInTheDocument()
  })

  it("setzt per Zifferntaste ein Label auf das gewählte Wort", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText(/2 Wörter/)

    const boxes = document.querySelectorAll("svg rect")
    await user.click(boxes[0])
    await user.keyboard("1")

    await waitFor(() => expect(screen.getByText(/^1 Spans/)).toBeInTheDocument())
  })
})
```

- [ ] **Schritt 6: Tests laufen lassen**

Ausführen: `cd frontend && npx vitest run src/features/annotate/`
Erwartet: PASS, 14 Tests (10 aus span-editor, 4 aus annotate-page)

Ausführen: `cd frontend && npm test`
Erwartet: alle Tests grün — insbesondere `inspector-page.test.tsx` und
`page-overlay.test.tsx`, die `PageList` bzw. `PageOverlay` in der bisherigen
Form nutzen und sich nicht verändert haben dürfen.

- [ ] **Schritt 7: Committen**

```bash
git add frontend/src/features/annotate/ frontend/src/features/inspector/page-list.tsx frontend/src/components/page-overlay.tsx
git commit -m "Ergänze Annotations-Oberfläche

Klick wählt ein Wort oder den ganzen Span darunter, Shift-Klick erweitert,
Ziffer setzt das Label. Pfeiltasten blättern wie im Inspektor. Der
Speicherzustand steht dauerhaft in der Kopfzeile - stilles Scheitern wäre
hier besonders teuer."
```

---

### Task 7: Einbinden — Route, Navigation, Doku

**Dateien:**
- Ändern: `frontend/src/app/router.tsx`
- Ändern: `frontend/src/app/top-nav.tsx`
- Ändern: `CLAUDE.md`, `README.md`
- Erstellen: `gold/.gitkeep`

**Schnittstellen:**
- Verbraucht: `AnnotatePage` (Task 6)
- Erzeugt: erreichbare Route `/annotate` in der Hauptnavigation

- [ ] **Schritt 1: Route und Navigation eintragen**

In `frontend/src/app/router.tsx` den Import ergänzen und die Route hinter `/inspector` einfügen:

```tsx
import { AnnotatePage } from "@/features/annotate/annotate-page"
```
```tsx
      { path: "/annotate", element: <AnnotatePage /> },
```

In `frontend/src/app/top-nav.tsx` die `items`-Liste erweitern:

```tsx
  { title: "Annotieren", url: "/annotate" },
```

- [ ] **Schritt 2: `gold/` anlegen**

```bash
mkdir -p gold && touch gold/.gitkeep
```

Prüfen, dass `gold/` nicht ignoriert wird:

Ausführen: `git check-ignore -v gold/.gitkeep`
Erwartet: keine Ausgabe, Exit-Code 1 (die Datei wird **nicht** ignoriert)

- [ ] **Schritt 3: Alle Tests laufen lassen**

Ausführen: `cd frontend && npm test`
Erwartet: alle Tests grün, inklusive `router.test.tsx`

Ausführen: `.venv/bin/python -m pytest -q`
Erwartet: 52 passed

- [ ] **Schritt 4: Doku ergänzen**

In `CLAUDE.md` unter „Projektwissen, das nicht im Code steht" anhängen:

```markdown
- **`gold/` ist versioniert, `data/` nicht.** Handannotierte Referenzlabels
  sind nicht reproduzierbar – ein verlorenes `data/labeled/` kostet API-Zeit,
  ein verlorenes `gold/` kostet Arbeitstage. Gespeichert werden Spans, nicht
  BIO-Tags: git-diffbar, und `labels.spans_to_bio()` erzeugt die Tags daraus.
- **Der `words_hash` in Gold-Dateien** ist die Absicherung des
  Wortreihenfolge-Vertrags. Ändert sich Schritt 02, zeigen die Span-Indizes
  auf andere Wörter, ohne dass etwas kaputtgeht. Die API lehnt dann mit 409 ab.
- **Die API ist nicht mehr read-only**, schreibt aber ausschließlich nach
  `gold/` – dieselbe enge Beschränkung wie beim Runner.
```

In `README.md` im Abschnitt zum Frontend diesen Absatz ergänzen:

```markdown
### Annotieren

`/annotate` ist das Werkzeug für handgelabelte Referenzdaten. Wort anklicken
(Shift-Klick erweitert die Auswahl), Ziffer `1`–`8` setzt das Label, `0`
entfernt es, `f` markiert die Seite als fertig. Gespeichert wird laufend nach
`gold/` – im Unterschied zu `data/` versioniert, weil Handarbeit sich nicht
neu erzeugen lässt.
```

- [ ] **Schritt 5: Committen**

```bash
git add frontend/src/app/ gold/.gitkeep CLAUDE.md README.md
git commit -m "Binde die Annotationsseite ein

Route, Navigation und Doku. gold/ wird versioniert - der Unterschied zu
data/ ist Absicht und steht jetzt in CLAUDE.md."
```

---

## Nach der Umsetzung

Nicht Teil dieses Plans, aber der logische nächste Schritt: `scripts/06_compare_labels.py`, das die fertigen Gold-Seiten gegen `data/labeled/` hält und beziffert, wie gut Mistral wirklich labelt. Erst diese Zahl beantwortet die Frage, für die das Gold-Set gebaut wurde.

Vor einer Umstellung von `data/splits/split.json` auf den Katalog-Split braucht es die Zustimmung von Bogdan und Kjell (siehe Spec, Abschnitt „Offene Team-Entscheidung").
