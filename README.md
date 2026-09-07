# Magda – Information Extraction aus Supermarkt-Prospekten

Semesterprojekt im Kurs *Information Extraction* (SoSe 2026).
Bogdan Roth · Kjell Lavezzari · Noah Samel

Aus deutschen Penny-Prospekten werden strukturierte Angebotsdaten extrahiert:
Produkt, Marke, Preis, Streichpreis, Menge, Grundpreis, Rabatt, Gültigkeit,
App-Preis. Ein großes Vision-LLM labelt die Trainingsdaten, darauf trainieren
wir ein eigenes, kleines Modell.

Zwei Fragen stehen dahinter. Erstens: **Wie viel von dem, was ein LLM kann,
passt in ein Modell, das man selbst betreibt?** Gemessen erreicht GBERT F1
0.908 gegen die LLM-Labels, bei 0,264 statt 44,8 Sekunden je Seite — 109 Mio.
Parameter, lokal auf CPU, ohne Netz und API-Kontingent. Zweitens: **Wie viel
bringt Layout-Information?** Mit vier Armen getrennt gemessen (KW35): der
Layout-Schritt `xlmr → lilt` bringt −0.0003 [−0.0063, +0.0058] — nichts, und
das ist die präziseste Null des Projekts. Das *Seitenbild* bringt dagegen
+0.0096 [+0.0033, +0.0182]. Wortkoordinaten sagen, wo ein Wort steht, nicht wie
es gesetzt ist.

Grundlage ist das [Proposal](docs/proposal/IE_ProjectProposal_Magda.pdf), der
Stand steht in [reports/](reports/).

**Neu im Team?** [docs/onboarding.md](docs/onboarding.md) ist die kurze
Einführung, gedacht zum Vorlegen an Claude Code.

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

## Rohdaten

Die Original-PDFs (`data/raw/`) und die gerenderten Seitenbilder
(`data/images/`) liegen **nicht im Repo**, sondern in einem geteilten
Google-Drive-Ordner – zusammen 1,57 GB gegen ~32 MB für alles andere unter
`data/`. Wer trainiert oder auswertet, braucht sie nicht: `data/words/` und
`data/labeled/` bleiben versioniert.

Eine Ausnahme liegt doch im Repo: die 43 Seitenbilder der Handannotation
(`docs/annotation-task.md`). Wer nur annotiert, braucht das Archiv also gar
nicht.

```bash
shasum -a 256 -c docs/archive/data-raw.sha256   # heruntergeladenes Archiv prüfen
magda extract --render-missing                  # Seitenbilder daraus neu rendern
```

**`--render-missing` ist hier Pflicht, nicht Geschmack.** Der normale Lauf
überspringt eine Seite an ihrer vorhandenen Wortdatei – und `data/words/` ist
versioniert. Ohne die Option rendert `magda extract` in einem frischen Klon
kein einziges Bild und meldet trotzdem Erfolg („0 Seiten verarbeitet, 666 schon
vorhanden"). Die Option lässt die Wortlisten unangetastet; ihre Reihenfolge ist
der Vertrag, an dem alle Label-Indizes hängen.

Details, Begründung und der Weg zum Ordner: [docs/archive/](docs/archive/README.md).

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
data/          versioniert, außer data/raw und data/images (siehe Rohdaten)
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

## Abschluss

- Handspans und Handgruppen vollständig annotieren; Anleitung:
  [docs/annotation-task.md](docs/annotation-task.md).
- Unter **Pipeline** die Studentenvorhersagen gegen Handspans und die gespeicherten
  Blackbox-Antworten gegen Handangebote auswerten.
- Die endgültigen Tabellen aus dem versionierten Bewertungsprotokoll erstellen,
  einschließlich Referenz, Seitenliste, Modellstand und Einschränkungen.

Sliding Window ist für die aktuelle Inferenz implementiert. Training und
Checkpointauswahl verwenden weiterhin das erste Fenster einer Seite.
