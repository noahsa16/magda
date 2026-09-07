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
Seitenliste stehen die Aufgabenseiten mit blauer Kante ganz oben. Für die Abgabe zählen Spans und Gruppen gleichermaßen.

## Beide Durchgänge sind verpflichtend

Zuerst alle Spans unter `/annotate`, danach die Angebote unter `/group`.
Der Abschlussvergleich benötigt auf jeder ausgewählten Seite **beide Dateien
mit `status: done`**. Die Gruppierung beginnt leer; nur fertige menschliche
Spans dienen als Klickhilfe. Ohne fertige Spans erfolgt die Auswahl wortweise.
Sonnet-Gruppen werden im Handeditor nicht vorgeladen.

Die folgenden Bedienhinweise beschreiben beide Werkzeuge:

**Angebote (`/group`)** – wozu ein Wort gehört.

- Namen oben rechts eintragen, er landet in jeder gespeicherten Datei.
- Ein Klick nimmt die ganze Entity ins aktive Angebot, Shift-Klick einen
  Wortbereich, `n` beginnt ein neues Angebot, Backspace löscht das aktive.
- Kleingedrucktes, Seitenkopf und Druckkennung gehören zu keinem Angebot
  und bleiben ungruppiert.
- `f` markiert die Seite als fertig, Pfeiltasten wechseln die Seite,
  gespeichert wird nach `gold/offers/<seite>.json`.

**Spans (`/annotate`)** – was ein Wort ist.

- Wort anklicken, Shift-Klick erweitert die Auswahl, Ziffer 1–9 vergibt
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

`gold/` ist versioniert. Am Ende – auf einem eigenen Branch, nie direkt auf
`development` oder `main`:

```bash
git switch -c data/gold-1364390
git add gold/ && git commit -m "data(gold): annotate catalog 1364390 by hand"
git push -u origin data/gold-1364390
```

Danach auf GitHub einen Pull Request nach `development` aufmachen. Zwischendrin
committen ist ausdrücklich erwünscht: 43 Seiten sind mehrere Sitzungen, und ein
Zwischenstand im Branch ist sicherer als 43 ungespeicherte Seiten.

Auch die vier Regionalvertreter gehören zur Abgabe, nicht nur Dateien mit
Präfix `1364390`. Gebraucht werden jeweils `gold/<seite>.json` und
`gold/offers/<seite>.json` für die gesamte Aufgabe.

Danach auf `/pipeline`:

1. **Student gegen Handspans** für die gewünschten trainierten Modelle.
2. **Blackbox gegen Handreferenz** mit den gespeicherten Reports für Gemma,
   Qwen und Mistral; dadurch entstehen keine neuen API-Kosten.

Die feste Vergleichsliste `data/eval/test_cluster_pages.txt` enthält je einen
Clustervertreter. Sie ist eine Teilmenge der Annotationsaufgabe. Die zusätzlichen
Annotationsseiten werden nicht stillschweigend in den Testvergleich aufgenommen.
Details und CLI-Aufrufe: [evaluation-protocol.md](evaluation-protocol.md).

Vor Beginn werden offene Konventionen (insbesondere Gebinde-Komposita) im Team
festgelegt und dokumentiert. Unklare Fälle werden gesammelt, nicht pro Seite
anders entschieden. Einen Teil der Seiten unabhängig doppelt annotieren und
Abweichungen vor der Endauswertung gemeinsam auflösen. Bereits früher aus
Sonnet-Vorbelegungen gespeicherte Gruppen gelten nicht nachträglich als blind
annotiert; ihre Herkunft muss geprüft und im Bericht genannt werden.
