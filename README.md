# Magda – Information Extraction aus Supermarkt-Prospekten

Semesterprojekt im Kurs *Information Extraction* (SoSe 2026).
Bogdan Roth · Kjell Lavezzari · Noah Samel

Wir extrahieren strukturierte Angebotsdaten (Produkt, Preis, Menge, Rabatt, …)
aus deutschen Supermarkt-Prospekten. Statt die Extraktion einem LLM zu
überlassen, trainieren wir ein eigenes layout-aware Modell (LayoutXLM) und
nutzen das LLM nur, um unsere Trainingsdaten automatisch zu labeln.
Details stehen im [Proposal](docs/proposal/IE_ProjectProposal_Magda.pdf).

## Pipeline

```
Prospekt-PDF ──01──> data/raw/      (eine Seite = ein PDF)
             ──02──> data/words/    (Wörter + Bounding-Boxen, via PDF-Textlayer)
                     data/images/   (gerenderte Seitenbilder)
             ──03──> data/labeled/  (BIO-Tags pro Wort, gelabelt vom LLM)
             ──04──> checkpoints/   (feingetuntes LayoutXLM bzw. GBERT)
             ──05──> Entity-Level P/R/F1 auf dem Test-Split
```

Die Skripte sind bewusst dünne Wrapper – die eigentliche Logik liegt im
`magda/`-Package und ist dort dokumentiert.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # API-Key für die Academic Cloud eintragen
```

Für das LayoutXLM-Training wird zusätzlich detectron2 gebraucht
(visueller Backbone von LayoutLMv2) – siehe Hinweis in `requirements.txt`
und in `scripts/04_train.py`.

## Benutzung

```bash
# 1. Prospekt herunterladen
python scripts/01_download_flyers.py "https://...blaetterkatalog.de/...?catalogId=123456"

# 2. Wörter + Positionen extrahieren
python scripts/02_extract_words.py

# 3. Automatisch labeln (braucht den API-Key aus der .env)
python scripts/03_label_words.py

# 4. Trainieren – beide Varianten für den Vergleich
python scripts/04_train.py gbert
python scripts/04_train.py layoutxlm

# 5. Evaluieren
python scripts/05_evaluate.py gbert
python scripts/05_evaluate.py layoutxlm
```

Alle Skripte sind idempotent: bereits verarbeitete Seiten werden übersprungen,
man kann sie also einfach erneut starten.

## Projektstruktur

```
magda/                  Kern-Package
├── config.py           Pfade, Modellnamen, API-Zugang
├── labels.py           Entity-Schema (BIO), Span-Validierung
├── scraping.py         Download der Penny-Prospektseiten
├── ocr.py              Wörter + Boxen aus dem PDF-Textlayer, Box-Normalisierung
├── labeling.py         LLM-Labeling (Bild + Wortliste -> Spans -> BIO)
├── alignment.py        Wort-Labels -> Subword-Tokens (-100-Maskierung)
├── dataset.py          Laden, Splits, PyTorch-Datasets für beide Modelle
├── evaluation.py       seqeval-Metriken (Entity-Level)
└── blackbox.py         der alte LLM-Prototyp, dient als Vergleichssystem

scripts/                nummerierte Pipeline-Schritte (siehe oben)
tests/                  pytest für Labels und Alignment
data/                   lokale Daten, nicht im Repo (nur .gitkeep)
checkpoints/            trainierte Modelle, nicht im Repo
docs/proposal/          das Projekt-Proposal
```

## Entity-Schema (Entwurf)

`PRODUCT`, `BRAND`, `PRICE`, `OLD_PRICE`, `QUANTITY`, `DISCOUNT`, `VALID` –
im BIO-Format. Wird nach Sichtung der ersten gelabelten Daten finalisiert,
siehe `magda/labels.py`.

## Frontend

Web-Oberfläche für Pipeline-Status, Label-Inspektion, Evaluation und Live-Demo.

```bash
uvicorn magda.api:app --reload    # Backend, Port 8000
cd frontend && npm install && npm run dev
```

Das Frontend läuft auf http://localhost:5173 und proxied `/api` ans Backend.

Die vier Bereiche:

- **Übersicht** – Projektbeschreibung, Zähler pro Pipeline-Stufe und die fünf
  Schritte zum Starten, inklusive Live-Ausgabe des laufenden Skripts.
- **Inspektor** – jede Seite mit den Label-Boxen über dem Prospektbild;
  Entity-Liste und Bild sind in beide Richtungen verknüpft, ← → blättert.
- **Evaluation** – F1 pro Entity-Typ, LayoutXLM gegen GBERT.
- **Demo** – PDF hochladen, das trainierte Modell extrahiert lokal.

Die Schritte laufen als Subprozess auf demselben Rechner wie das Backend
(`magda/runner.py`). Der Runner nimmt nur die fünf bekannten Skripte an –
gedacht für das lokale Setup, nicht für einen offen erreichbaren Server.

### Annotieren

`/annotate` ist das Werkzeug für handgelabelte Referenzdaten. Wort anklicken
(Shift-Klick erweitert die Auswahl), Ziffer `1`–`8` setzt das Label, `0`
entfernt es, `f` markiert die Seite als fertig. Gespeichert wird laufend nach
`gold/` – im Unterschied zu `data/` versioniert, weil Handarbeit sich nicht
neu erzeugen lässt.

## Tests

```bash
pytest                    # Backend + Pipeline
cd frontend && npm test   # Frontend (Vitest)
```

## Offene Punkte

- [ ] Label-Set nach den ersten gelabelten Seiten finalisieren
- [ ] Split über Kataloge statt Seiten? (Angebote wiederholen sich zwischen Wochen)
- [ ] detectron2-Installation klären, sonst Plan B: LayoutLMv3-Architektur
- [ ] Seiten mit >512 Subwords: Truncation reicht oder Sliding Window nötig?
- [ ] Matching-Logik für den Vergleich Modell vs. LLM-Blackbox (Phase 3)
