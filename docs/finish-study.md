# Abschluss der Magda-Fallstudie

Stand: 16.09.2026. Der Studienumfang verwendet die vorhandenen Annotationen.
Es ist keine weitere Labelrunde vorgesehen. Fehlende unabhängige
Doppelannotation, mehrdeutige Angebotszuordnung und Fehler der bestehenden
Referenz sind Einschränkungen der Studie und keine noch offenen Arbeitsaufträge.

## Ergebnisse und Reproduktion

- [Abschlussbericht](../data/eval/study-2026-09-16/report.md)
- [Maschinenlesbare Ergebnisse](../data/eval/study-2026-09-16/study.json)
- [Diagnostischer Referenzanhang](../data/eval/study-2026-09-16/reference-diagnostics.md)
- [Methodenprotokoll und Umfangsentscheidung](study-protocol-v1.md)

Der Bericht ist für Leser ohne ML-Vorkenntnisse aufgebaut: Abschnitt 1 und 2
führen Aufgabe und Daten ein, Abschnitt 3 erklärt die untersuchten Verfahren,
Abschnitt 4 die Bewertungsgrößen einschließlich einer F1-Rechnung aus den
tatsächlichen Ergebnissen. Abschnitt 5 und 6 ordnen Messwerte und Fehler ein.
Abschnitt 8 stellt jeder der fünf Anforderungen des Proposals einen Nachweis
gegenüber und erklärt die Änderungen gegenüber dem ursprünglichen Plan.

Aus dem Projektroot mit der Projektumgebung ausführen:

```bash
.venv/bin/magda study-eval --output /tmp/magda-study-reproduction
```

Der ursprüngliche Paarmodell-Checkpoint wird dafür zusätzlich benötigt;
Voraussetzungen stehen in der [Reproduktionsanleitung](report/README.md).
Der Befehl wertet vorhandene Vorhersagen und gespeicherte Blackbox-Antworten
aus. Er ruft keine LLM-API auf, trainiert kein Modell und verändert keine
Annotation. Ohne ausdrücklich angegebenes `--review-packet` erzeugt er keine
neue Annotationsaufgabe. Für einen späteren separaten Lauf einen neuen
Ausgabeordner wählen, damit historische Ergebnisse erhalten bleiben.

`completed_exploratory` bezeichnet den Abschluss der Auswertung innerhalb
dieses Umfangs. Der Status bestätigt keine fehlerfreie Referenz.
`review-status.json` hält `not_performed` und `scores: null` fest: Es wurde
keine zusätzliche Kontrollannotation durchgeführt und keine Übereinstimmung
zwischen unabhängigen Personen berechnet.

## Was der Bericht abdeckt

- Entity-Erkennung: Strict als Primärmetrik, dazu Exact, Partial und Type
  nach SemEval sowie Precision, Recall und Ergebnisse je Label.
- Gruppierung: Paar- und exakte Gruppenmetriken mit ausdrücklich benannter
  Entity-Grundmenge.
- Angebotsvergleich: lokale Pipeline und gespeicherte LLM-Läufe auf Name
  und regulärem Preis, einschließlich fehlgeschlagener Antworten.
- Gepaarte Cluster-Intervalle, dokumentierte Fehlerfälle, Referenzdiagnostik
  und Eingabe-/Code-Fingerabdrücke zur Reproduktion.

## Aussagen, die diese Studie nicht trägt

Die gespeicherten Wortgruppen und ihre Projektion auf Name und PRICE legen
fest, was für die Rechnung als Angebot zählt. Gemeinsame Preise, Varianten,
Mehrfachkäufe und App-Bedingungen können anders plausibel abgegrenzt werden.
Die Auswirkungen solcher alternativen Definitionen wurden nicht gemessen.
Dazu kommen uneinheitliche Labels und bekannte Referenzfehler. Deshalb ist
nicht jede Abweichung gegenüber Gold ein Modellfehler. Die Intervalle bilden
diese systematische Unsicherheit nicht ab.

Der Architekturvergleich belegt keine isolierte Wirkung von Layout oder
Bildinformation. Die bereits betrachtete Testwoche trägt keine unabhängige
Bestätigung nachträglicher Modellverbesserungen. Training oder Schwellenwahl
anhand dieser Ergebnisse gehören nicht zum Abschluss.

## Das frühere Prüfpaket

Der Entwurf `annotation-guidelines-v1.md` und das vorbereitete Paket unter
`data/audit/independent-review-v1/` bleiben als unbenutzte Vorarbeiten erhalten.
Ihre Regeln wurden nicht nachträglich auf die bestehende Referenz angewendet.
Die Datei `src/magda/templates/independent_review.html` ist eine unbefüllte
Vorlage und kein fertiger Editor mit Seiten. Für diesen Studienabschluss
muss keine dieser Dateien bearbeitet werden.

Der historische Arbeitsbericht unter `data/eval/study-2026-09-15/` dokumentiert
den vorherigen Plan. Maßgeblich ist der oben verlinkte Abschlussbericht.
