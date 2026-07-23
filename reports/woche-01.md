# Woche 1 — Setup und erster Durchlauf

**Stand: 23.07.2026**

## Was wir gemacht haben

Projektstruktur aufgesetzt und die Pipeline aus dem Proposal einmal komplett
durchlaufen lassen. Das Ziel war nicht, gute Zahlen zu bekommen, sondern zu
prüfen, ob die Kette überhaupt hält: Prospekt rein, F1-Wert raus.

Sie hält.

## Aufbau

Das Repo ist in ein Package (`magda/`) und nummerierte Skripte (`scripts/`)
geteilt. Die Logik liegt im Package, die Skripte parsen nur Argumente und
schreiben Dateien. Jeder Pipeline-Schritt liest vom Vorgänger über die Platte:

```
01_download_flyers  →  data/raw/      Prospektseiten als PDF
02_extract_words    →  data/words/    Wörter + Bounding-Boxen
                       data/images/   gerenderte Seitenbilder
03_label_words      →  data/labeled/  BIO-Tags, gelabelt vom LLM
04_train            →  checkpoints/   trainiertes Modell
05_evaluate         →  data/eval/     Precision/Recall/F1
```

Das hat sich schon in Woche 1 ausgezahlt: Als das Labeling zweimal abbrach,
mussten wir nicht von vorne anfangen. Alle Skripte überspringen, was schon
verarbeitet ist.

## Daten

Getestet mit Katalog 1342881 (Penny Lüneburg, Woche 20.–25.7.):

- 40 Seiten heruntergeladen, ~11 Sekunden
- 7216 Wörter mit Positionen extrahiert
- 4796 Wörter gelabelt (66 %)

Wichtigste Erkenntnis hier: **Wir brauchen kein OCR.** Die Penny-PDFs haben
einen Textlayer, PyMuPDF liefert Wörter und Koordinaten direkt. Das ist
schneller und fehlerfrei. Sollten später Händler mit reinen Bild-PDFs
dazukommen, brauchen wir an der Stelle einen Tesseract-Fallback.

Verteilung der Entitäten über alle 40 Seiten:

| Entität | Anzahl |
|---|---|
| QUANTITY | 1954 |
| PRODUCT | 1141 |
| BRAND | 520 |
| PRICE | 394 |
| OLD_PRICE | 378 |
| DISCOUNT | 284 |
| VALID | 125 |

## LLM-Labeling

Wir nutzen die GWDG Academic Cloud. Von den 16 verfügbaren Modellen nehmen nur
drei Bilder an. Wir haben alle drei auf echten Prospektseiten getestet:

| Modell | erfolgreich | Wörter getaggt |
|---|---|---|
| mistral-medium-3.5-128b | 3/3 | 67–89 % |
| qwen3-omni-30b-a3b | 2/3 | 49–53 % |
| gemma-4-31b-it | 1/3 | 4 % |

Mistral ist jetzt der Default.

Dazu eine Lehre, die uns fast in die Irre geführt hätte: Auf einer kleinen
Testseite mit 23 Wörtern sah gemma am besten aus. Erst auf echten Seiten mit
150–400 Wörtern zeigte sich, dass es dort 50–80 Spans am Stück ausgeben muss
und dabei zusammenbricht. Modellwahl an Spielzeugbeispielen zu treffen führt
zum falschen Ergebnis.

## Erstes Ergebnis (GBERT-Baseline)

Trainiert auf 32 Seiten, evaluiert auf 4. Entity-Level-Metriken via seqeval:

| Entität | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| OLD_PRICE | 0.875 | 0.700 | 0.778 | 20 |
| PRICE | 0.700 | 0.519 | 0.596 | 27 |
| DISCOUNT | 1.000 | 0.417 | 0.588 | 24 |
| QUANTITY | 0.217 | 0.208 | 0.213 | 48 |
| BRAND | 0.118 | 0.083 | 0.098 | 24 |
| PRODUCT | 0.095 | 0.065 | 0.077 | 31 |
| VALID | 0.000 | 0.000 | 0.000 | 4 |
| **micro avg** | **0.388** | **0.292** | **0.333** | 178 |

Die absoluten Zahlen sind bei 32 Trainingsseiten nicht belastbar. VALID hat
4 Instanzen im Testsplit, die 0.000 dort sind Rauschen.

Interessant ist aber das Muster: Preise, Streichpreise und Rabatte
funktionieren (F1 0.59–0.78), Produkte und Marken nicht (F1 0.08–0.10).

Das ist plausibel. `-42%` und `5.99` erkennt man am Textmuster allein, dafür
braucht ein Modell keine Layout-Information. Ob „GÉRAMONT" die Marke und
„Käsescheiben Natur" das Produkt ist, ergibt sich dagegen erst aus der Position
auf der Seite — Marke steht fett darüber, Beschreibung kleiner darunter. Genau
diese Information fehlt GBERT.

**Daraus folgt unsere Hypothese für LayoutXLM:** deutliche Verbesserung bei
PRODUCT und BRAND, ungefähr gleiche Werte bei PRICE und DISCOUNT. Wenn das
eintritt, ist die Forschungsfrage des Proposals sauber beantwortet.

## Probleme, die wir gelöst haben

- **Antworten wurden abgeschnitten.** `max_tokens` war nicht gesetzt, das
  Server-Default kappte das JSON mitten im Satz. Skaliert jetzt mit der
  Wortzahl der Seite.
- **Endlosschleife bei `temperature=0`.** Auf einer Seite wiederholte das
  Modell rund 600-mal `" a "`, bis das Token-Limit griff. Greedy Decoding ist
  dafür anfällig. Jetzt 0.2.
- **Prosa um das JSON herum.** Trotz gegenteiliger Anweisung im Prompt kamen
  Einleitungssätze und angehängte Zusammenfassungen zurück, in einem Fall auf
  Koreanisch. Wir schneiden das Array jetzt per Klammerzählung heraus.
- **Steuerdaten im Textlayer.** Die PDFs enthalten unsichtbare Tokens wie
  `json://…gif;0.000;…`, mit denen der Web-Viewer Animationen platziert. Die
  wurden als Wörter mitgezählt und werden jetzt gefiltert.
- **transformers 5.x lädt GBERT nicht.** deepset liefert nur das alte
  `vocab.txt`-Format, in 5.x sind die Slow-Tokenizer entfernt. Auf `<5` gepinnt.

## Umgebung

detectron2 baut auf Apple Silicon durch, LayoutXLM lädt und rechnet einen
Forward-Pass. Auf dem Mac läuft der visuelle Backbone allerdings auf CPU, für
richtiges Training ist das zu langsam. Wir haben Zugang zu einer RunPod-GPU;
`scripts/setup_runpod.sh` richtet einen Pod ein und beschreibt den Datentransfer
über R2.

## Nächste Schritte

- [ ] LayoutXLM trainieren und gegen GBERT vergleichen (Hauptexperiment)
- [ ] Mehr Kataloge sammeln — 40 Seiten sind zu wenig für belastbare Zahlen
- [ ] Annotationsrichtlinie schärfen: Ist „Bio" eine Marke oder Teil des
      Produktnamens? Gehört „statt" zum OLD_PRICE oder nicht? Solange der
      Prompt das offen lässt, rät das LLM und wir trainieren auf Rauschen.
- [ ] Kleine handgelabelte Kontrollmenge (20–30 Seiten), um die Qualität der
      LLM-Labels selbst beziffern zu können statt sie anzunehmen
- [ ] Split über Kataloge statt Seiten prüfen — Angebote wiederholen sich
      zwischen Wochen, das könnte vom Train- in den Test-Split leaken
