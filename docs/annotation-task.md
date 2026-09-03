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
git clone https://github.com/noahsa16/magda.git && cd magda
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cd frontend && npm install && cd ..
magda serve --frontend                  # API 8000, Oberfläche 5173
```

Mehr ist nicht nötig. **Kein Google Drive, kein `.env`, kein `magda extract`:**
die 43 Seitenbilder dieser Aufgabe liegen im Repo, alles andere unter `data/`
ohnehin. Wer das Repo schon hat, holt sich den Stand mit
`git switch development && git pull`.

Dann http://localhost:5173/group öffnen. Oben steht ein blauer Kasten
„Aufgabe für Kjell und Bogdan" mit Fortschritt und dem Knopf **Nächste
offene Seite**. Die Katalogkachel 1364390 ist blau umrandet, in der
Seitenliste stehen die Aufgabenseiten mit blauer Kante ganz oben. Bei der Abgabe zählen zuerst
die Dateien unter `gold/offers/`.

## Reihenfolge: erst Angebote, dann Spans

**Die Gruppierung ist das, worauf es ankommt.** Der Blackbox-Vergleich
misst Angebote (Name plus Preis), und die Frage ist, was zusammengehört.
Deshalb zuerst alle 43 Seiten unter `/group`; die Spans unter `/annotate`
sind der zweite Durchgang, falls Zeit bleibt. `/group` braucht keine
handannotierten Spans: gruppiert werden Wortindizes, der Klick nimmt nur
zur Bequemlichkeit die Sonnet-Entity mit. Stimmt ein Span nicht, mit
Shift-Klick wortweise korrigieren.

**1. Angebote (`/group`)** – wozu ein Wort gehört.

- Namen oben rechts eintragen, er landet in jeder gespeicherten Datei.
- Ein Klick nimmt die ganze Entity ins aktive Angebot, Shift-Klick einen
  Wortbereich, `n` beginnt ein neues Angebot, Backspace löscht das aktive.
- Kleingedrucktes, Seitenkopf und Druckkennung gehören zu keinem Angebot
  und bleiben ungruppiert.
- `f` markiert die Seite als fertig, Pfeiltasten wechseln die Seite,
  gespeichert wird nach `gold/offers/<seite>.json`.

**2. Spans (`/annotate`)** – was ein Wort ist.

- Wort anklicken, Shift-Klick erweitert die Auswahl, Ziffer 1–8 vergibt
  das Label aus der Legende rechts, 0 oder Backspace löscht.
- `f` markiert die Seite als fertig, gespeichert wird nach
  `gold/<seite>.json`.

Beide Werkzeuge lesen dieselbe Aufgabe und zeigen ihren eigenen
Fortschritt.

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
