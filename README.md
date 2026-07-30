# Magda – Information Extraction aus Supermarkt-Prospekten

Semesterprojekt im Kurs *Information Extraction* (SoSe 2026).
Bogdan Roth · Kjell Lavezzari · Noah Samel

Aus deutschen Penny-Prospekten werden strukturierte Angebotsdaten extrahiert:
Produkt, Marke, Preis, Streichpreis, Menge, Grundpreis, Rabatt, Gültigkeit,
App-Preis. Die Trainingsdaten labelt ein LLM automatisch, trainiert wird ein
eigenes Modell. Die Projektfrage ist, wie viel Layout-Information dabei
bringt: LayoutXLM kennt die Position jedes Wortes, GBERT nur den Text.

Grundlage ist das [Proposal](docs/proposal/IE_ProjectProposal_Magda.pdf), der
Stand steht in [reports/](reports/).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env       # API-Key für die GWDG Academic Cloud eintragen
```

LayoutXLM braucht zusätzlich detectron2 (visueller Backbone von LayoutLMv2).
Die Installation ist plattformabhängig; für das Training auf einer gemieteten
GPU siehe [docs/runpod.md](docs/runpod.md).

## Pipeline

```
Prospekt-PDF ──00/01──> data/raw/      eine Seite = ein PDF
             ──02─────> data/words/    Wörter + Boxen aus dem PDF-Textlayer
                        data/images/   gerenderte Seitenbilder
             ──06─────> data/excluded.json   Beinah-Duplikate aussortiert
             ──03─────> data/labeled/  BIO-Tags pro Wort, vom LLM gelabelt
             ──04─────> checkpoints/   feingetuntes LayoutXLM bzw. GBERT
             ──05─────> data/eval/     Entity-Level P/R/F1 auf dem Test-Split
```

```bash
python scripts/00_harvest_week.py          # laufende Woche, alle 44 Regionen
python scripts/02_extract_words.py
python scripts/06_check_duplicates.py --apply
python scripts/03_label_words.py
python scripts/12_make_split.py --strategy week
python scripts/04_train.py gbert           # bzw. layoutxlm
python scripts/05_evaluate.py gbert --split test
```

Jeder Schritt liest vom Vorgänger über die Platte und überspringt, was schon
verarbeitet ist – ein Lauf über mehrere tausend Seiten beginnt nach einem
Abbruch nicht von vorn. Skripte immer aus dem Projektroot starten, sie lesen
und schreiben relativ dazu.

Daneben gibt es Vergleichsarme und Auswertungen: `07_flair_baseline.py`
(fertiges deutsches NER-Modell, misst nur BRAND), `08_compare_labels.py`
(Labeling-Modelle gegen `gold/`), `09_agreement.py` (Labeling-Modelle
gegeneinander).

## Struktur

```
src/magda/     Kern-Package: die gesamte Logik, inklusive api.py
scripts/       nummerierte Pipeline-Schritte, dünne CLI-Wrapper
frontend/      React-SPA (Vite, Tailwind, shadcn), liest data/ über die API
tests/         pytest
gold/          handannotierte Referenz – versioniert, weil nicht reproduzierbar
data/          Arbeitsstände, gitignored
checkpoints/   trainierte Modelle, gitignored
docs/          Proposal, RunPod-Anleitung, Ursprungs-Prototyp
reports/       Wochenberichte
```

## Frontend

```bash
uvicorn magda.api:app --reload    # Backend, Port 8000
cd frontend && npm install && npm run dev
```

Läuft auf http://localhost:5173 und proxied `/api` ans Backend. Vier Bereiche:
**Übersicht** (Datenstand und F1 je Variante), **Pipeline** (Schritte starten,
Live-Ausgabe, Lauf-Historie), **Daten** (Label-Quellen als Ordner, darunter
Inspektor und Annotator) und **Ergebnis** (F1 pro Entity-Typ).

Der Annotator unter `/annotate` erzeugt die Referenzdaten in `gold/`: Wort
anklicken, Shift-Klick erweitert, Ziffer `1`–`9` setzt das Label, `0` entfernt
es, `f` markiert die Seite als fertig.

Die Pipeline-Schritte laufen als Subprozess auf demselben Rechner wie das
Backend. Startbar sind nur die in `src/magda/jobs.py` deklarierten Jobs mit
ihren deklarierten Parametern – gedacht für das lokale Setup, nicht für einen
offen erreichbaren Server.

## Tests

```bash
.venv/bin/python -m pytest        # Backend und Pipeline
cd frontend && npm test           # Frontend (Vitest)
```

## Offene Punkte

- [ ] Vorannotation von Hand freigeben; bis dahin messen die F1-Werte
      Konsistenz mit dem Labeling-LLM, nicht Richtigkeit
- [ ] PRODUCT-Konvention schärfen: wo endet die Sorte, wo beginnt der Werbetext
- [ ] Seiten über 512 Subwords werden abgeschnitten – Sliding Window nötig?
- [ ] Vergleich gegen die LLM-Blackbox (`src/magda/blackbox.py`)
