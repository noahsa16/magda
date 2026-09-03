# Handannotation des Testkatalogs 1364390

Für Kjell und Bogdan, abgesprochen am 2026-09-03. Welche Seiten dran sind,
steht in `data/annotation_task.json`; der Annotator im Frontend liest die
Datei und hebt die Seiten hervor.

## Warum

Alle Zahlen im Blackbox-Vergleich (`reports/woche-08.md`) messen
Übereinstimmung mit `claude-sonnet-5`, nicht Richtigkeit. Sowohl die
Entities (`data/labeled/sonnet-5/`) als auch die Angebotsgruppen
(`data/offer_groups/claude-sonnet-5/`) stammen von einem LLM. Erst eine
handannotierte Referenz sagt, ob die eigene Pipeline *richtiger* ist als
Gemma oder nur *ähnlicher zu Sonnet*.

Katalog 1364390 stellt 39 der 116 Testseiten und 38 der 42
Cluster-Vertreter, über die der Blackbox-Vergleich läuft. Dazu kommen die
vier übrigen Vertreter (`1364393_p15`, `1364393_p25`, `1364411_p9`,
`1364420_p8`). Zusammen 43 Seiten, und damit ist der ganze Vergleich
abgedeckt.

## Aufsetzen

```bash
git fetch && git switch data/kw34-labeln
.venv/bin/pip install -e '.[dev]'      # falls noch nicht geschehen
cd frontend && npm install && cd ..
magda serve --frontend                  # API 8000, Oberfläche 5173
```

Dann http://localhost:5173/annotate öffnen. Oben steht ein blauer Kasten
„Aufgabe für Kjell und Bogdan" mit Fortschritt und dem Knopf **Nächste
offene Seite**. Die Katalogkachel 1364390 ist blau umrandet, in der
Seitenliste stehen die Aufgabenseiten mit blauer Kante ganz oben.

## Zwei Durchgänge je Seite

Erst alle Seiten unter `/annotate`, dann alle unter `/group`. Beide lesen
dieselbe Aufgabe und zeigen ihren eigenen Fortschritt.

**1. Spans (`/annotate`)** – was ein Wort ist.

- Namen oben rechts eintragen, er landet in jeder gespeicherten Datei.
- Wort anklicken, Shift-Klick erweitert die Auswahl, Ziffer 1–8 vergibt
  das Label aus der Legende rechts, 0 oder Backspace löscht.
- `f` markiert die Seite als fertig, Pfeiltasten wechseln die Seite.
- Gespeichert wird bei jeder Änderung nach `gold/<seite>.json`.

**2. Angebote (`/group`)** – wozu ein Wort gehört.

- Ein Klick nimmt die ganze Entity ins aktive Angebot, `n` beginnt ein
  neues, Backspace löscht das aktive.
- Kleingedrucktes, Seitenkopf und Druckkennung gehören zu keinem Angebot
  und bleiben ungruppiert.
- `f` markiert die Seite als fertig, gespeichert wird nach
  `gold/offers/<seite>.json`.

## Regeln, die zählen

- **Aus dem Seitenbild annotieren, nicht die Modellausgabe korrigieren.**
  Der Annotator zeigt bewusst keine Vorbelegung. Wer die Sonnet-Labels
  daneben aufmacht, ankert daran, und die Messung misst hinterher das
  Ankern mit.
- Was ein Label bedeutet, steht in der Legende und in `labeling.py`
  (`_PROMPT`); die offenen Konventionsfragen (Sortenangaben ins PRODUCT,
  Gebinde-Komposita) stehen in `CLAUDE.md`. Im Zweifel die Sortenangabe
  mitnehmen (Teamentscheidung vom 2026-07-30).
- Eine Seite mit dem Hinweis „Wortliste hat sich geändert" nicht
  bearbeiten, sondern melden – dann passt Schritt 02 nicht mehr zur
  Aufgabe.

## Abgeben

`gold/` ist versioniert. Am Ende:

```bash
git add gold/ && git commit -m "data(gold): annotate catalog 1364390 by hand"
git push
```

Oder die Dateien unter `gold/1364390_*.json` und `gold/offers/1364390_*.json`
schicken. Gemessen wird danach mit `magda gold` (Labels) und `magda
offers-gold` (Gruppierung); für den Blackbox-Vergleich fehlt noch ein
`--reference-groups gold` in `blackbox_eval.py`, das kommt, sobald die
Referenz da ist.
