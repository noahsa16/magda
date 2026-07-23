# Frontend für Magda — Design

Datum: 2026-07-23
Status: vom Team (Noah) freigegeben

## Ziel

Ein Web-Frontend für das Forschungsprojekt, das die Pipeline sichtbar macht:
Labels prüfen, Metriken vergleichen, Fortschritt sehen, Modell demonstrieren.
Vier Bereiche in einer App, gebaut so, dass spätere Erweiterungen (weitere
Händler, Sliding-Window-Analyse, Blackbox-Vergleich) andocken können.

## Architektur

Zwei Teile im bestehenden Repo:

| Teil | Technologie | Ort |
|---|---|---|
| SPA | Vite, React, TypeScript, Tailwind v4, shadcn/ui, TanStack Query, React Router, Recharts | `frontend/` |
| API | FastAPI, read-only auf `data/`, Inference-Endpoint | `magda/api.py` |

- Start Backend: `uvicorn magda.api:app --reload` (Port 8000).
- Start Frontend: `npm run dev` in `frontend/`; Vite proxied `/api` → `localhost:8000`.
- Keine Datenbank, keine Datenkopien: die API liest `data/` direkt von der
  Platte. Die Pipeline-Skripte bleiben die einzige Schreibquelle.

## API-Endpunkte

| Endpoint | Antwort |
|---|---|
| `GET /api/schema` | `{entity_types: [...]}` aus `magda/labels.py` — Frontend leitet Farben/Legenden daraus ab |
| `GET /api/status` | Zählungen pro Pipeline-Stufe und Katalog: `{catalogs: [{id, raw, words, images, labeled}], totals: {...}}` |
| `GET /api/pages` | Liste `[{page_id, catalog, labeled: bool}]` aus `data/words/` |
| `GET /api/pages/{page_id}` | Words-JSON (`width`, `height`, `words[]`) plus `tags[]` aus `data/labeled/`, falls vorhanden |
| `GET /api/pages/{page_id}/image` | PNG aus `data/images/` |
| `GET /api/evaluation` | Inhalte aller `data/eval/*.json`, gruppiert nach Variante und Split; `[]` wenn leer |
| `POST /api/inference` | PDF-Upload → `{width, height, words[], tags[]}`; `503` mit Meldung, wenn kein Checkpoint unter `checkpoints/layoutxlm/best` existiert |

Fehlerverhalten: unbekannte `page_id` → 404. Leere Verzeichnisse sind kein
Fehler, sondern liefern leere Listen — die Empty States sind Sache des Frontends.

## Pipeline-Ergänzung (einzige Änderung an Bestandscode)

`scripts/05_evaluate.py` schreibt zusätzlich zum gedruckten Report eine Datei
`data/eval/{variant}_{split}.json` mit dem seqeval-Report als Dict
(`classification_report(..., output_dict=True)`) plus Metadaten
(Variante, Split, Seitenzahl, Zeitstempel). `data/eval/` wird in
`magda/config.py` als `EVAL_DIR` ergänzt.

## Frontend-Struktur

```
frontend/src/
  app/               Shell (Sidebar-Navigation), Router, Query-Provider
  components/ui/     shadcn-Komponenten (generiert)
  features/
    overview/        Pipeline-Übersicht
    inspector/       Label-Inspektor
    evaluation/      Metriken-Dashboard
    demo/            Live-Demo
  lib/               API-Client, Typen, Entity-Farbzuordnung
```

Jedes Feature hält seine Komponenten, Hooks und Hilfslogik selbst; geteilt
wird nur über `components/` und `lib/`. Die Overlay-Ansicht (Seite + Boxen)
lebt als wiederverwendbare Komponente, weil Inspektor und Demo sie beide
brauchen.

## Die vier Bereiche

### Pipeline-Übersicht (`/`)

Stat-Karten (Seiten gesamt, extrahiert, gelabelt), darunter eine Tabelle pro
Katalog mit Fortschrittsbalken. Zeigt bei fehlenden Daten, welches
Pipeline-Kommando als Nächstes dran ist.

### Label-Inspektor (`/inspector`)

Das Herzstück, Werkzeug zur Finalisierung des Label-Sets:

- Linke Spalte: durchsuchbare Seitenliste, gruppiert nach Katalog,
  Badge „gelabelt/ungelabelt".
- Hauptansicht: Seiten-PNG mit SVG-Overlay der Wort-Bounding-Boxen, gefärbt
  nach Entity-Typ, `O`-Wörter dezent grau. Hover → Tooltip mit Wort + BIO-Tag.
- Koordinaten: bboxes sind PDF-Punkte, das PNG ist 150-dpi-Render. Das
  SVG nutzt `viewBox="0 0 {pdfWidth} {pdfHeight}"` über dem Bild — damit
  übernimmt der Browser die Skalierung und es gibt keinen manuellen Faktor.
- Rechte Spalte: Entities gruppiert (zusammenhängende B-/I-Folgen als ein
  Eintrag), Filter nach Entity-Typ, Klick scrollt/highlightet die Box.

### Evaluation (`/evaluation`)

- Karten: Gesamt-F1 je Variante (GBERT, LayoutXLM) und Delta — der
  Layout-Gewinn ist das zentrale Messergebnis.
- Balkendiagramm: F1 (umschaltbar P/R) pro Entity-Typ, beide Varianten
  nebeneinander.
- Tabelle: vollständiger Report inkl. Support.
- Empty State: Hinweis auf `python scripts/05_evaluate.py <variant>`.

### Live-Demo (`/demo`)

Dropzone für ein einseitiges PDF → Inference-Ergebnis in derselben
Overlay-Ansicht wie im Inspektor plus Entity-Liste. Nur PDF (die Pipeline hat
kein OCR für Bild-Input). Ohne Checkpoint: erklärender Zustand statt Fehler.

## Empty States

`data/` ist zu Projektbeginn leer. Jede Ansicht behandelt „keine Daten" als
normalen Zustand erster Klasse: kurze Erklärung + das konkrete Kommando
(`python scripts/01_download_flyers.py …`). Kein Spinner-Deadlock, keine
Fehlerseite.

## Entity-Farben

Eine feste, farbenblind-taugliche Palette in `lib/`, positionsbasiert auf
`entity_types` aus `/api/schema` gemappt. Neue Typen (Anfügen hinten, wie in
`labels.py` vorgeschrieben) bekommen automatisch die nächste Farbe.

## Tests

- **Frontend (Vitest + Testing Library):** BIO-Tags → Entity-Gruppen
  (reine Funktion), Entity-Farbzuordnung, Rendering der Overlay-Komponente
  mit Beispieldaten.
- **Backend (pytest):** API-Endpunkte gegen ein temporäres Datenverzeichnis
  (Fixtures mit Mini-Words/Labeled-JSONs); 404- und Leer-Fälle.
- Bestehende Tests bleiben unberührt.

## Nicht in v1 (bewusst)

- Label-*Editieren* im Inspektor (erst sinnvoll, wenn das Label-Set steht;
  die Architektur — Seitenpanel + Overlay — ist darauf vorbereitet).
- Zoom/Pan in der Seitenansicht (fit-to-width reicht für Prospektseiten).
- Blackbox-Vergleich im Dashboard (Matching-Logik ist laut Proposal noch offen).
- Auth/Deployment (läuft lokal im Team).
