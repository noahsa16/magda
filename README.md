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

```bash
magda harvest                  # laufende Woche, alle 44 Regionen  -> data/raw/
magda extract                  # Wörter + Boxen, Seitenbilder      -> data/words/, data/images/
magda dedupe --apply           # Beinah-Duplikate aussortieren     -> data/excluded.json
magda label                    # BIO-Tags vom Vision-LLM           -> data/labeled/<modell>/
magda split --strategy week    # Train/Dev/Test einfrieren         -> data/splits/split.json
magda train gbert              # bzw. layoutxlm                    -> checkpoints/
magda eval gbert --split test  # Entity-Level P/R/F1               -> data/eval/
```

`magda --help` listet alle Schritte in dieser Reihenfolge auf, `magda <schritt>
--help` die Optionen eines einzelnen. Jeder Schritt liest vom Vorgänger über
die Platte und überspringt, was schon verarbeitet ist – ein Lauf über mehrere
tausend Seiten beginnt nach einem Abbruch nicht von vorn. Immer aus dem
Projektroot starten, die Schritte lesen und schreiben relativ dazu.

Daneben gibt es Vergleichsarme und Auswertungen: `magda flair` (fertiges
deutsches NER-Modell, misst nur BRAND), `magda gold` (Labeling-Modelle gegen
`gold/`), `magda agreement` (Labeling-Modelle gegeneinander).

## Struktur

```
src/magda/     Kern-Package: die gesamte Logik, inklusive api.py
    cli/       ein Modul je Pipeline-Schritt, Einstieg über `magda`
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
magda serve --frontend      # API auf 8000, Oberfläche auf 5173
```

Beides in einem Befehl; `magda serve` allein startet nur die API. Wer die
Prozesse getrennt haben will, nimmt zwei Terminals:

```bash
magda serve
cd frontend && npm run dev
```

Nicht `uvicorn magda.api:app` – das `uvicorn` im PATH gehört meist zu einer
anderen Python-Installation, in der `magda` nicht liegt, und der Start endet
in `ModuleNotFoundError`.

Die Oberfläche läuft auf http://localhost:5173 und proxied `/api` ans Backend.
Vier Bereiche:
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

- [ ] Vorannotation von Hand freigeben (`magda queue` nennt die nächsten
      Seiten); bis dahin messen die F1-Werte Konsistenz mit dem Labeling-LLM,
      nicht Richtigkeit
- [ ] PRODUCT-Konvention schärfen: wo endet die Sorte, wo beginnt der Werbetext
- [ ] Seiten über 512 Subwords werden abgeschnitten – Sliding Window nötig?
- [ ] Vergleich gegen die LLM-Blackbox (`src/magda/blackbox.py`)
