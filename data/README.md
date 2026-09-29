# Daten und Messbelege

| Verzeichnis | Inhalt |
|---|---|
| `words/` | Extrahierte Wörter mit Koordinaten; Reihenfolge unveränderlich |
| `labeled/sonnet-5/` | Kanonische automatisch erzeugte Entity-Labels |
| `labeled_archive/` | Abgeschlossene Labeling-Vergleichsarme |
| `splits/` | Eingefrorene Aufteilung in Training, Entwicklung und Test |
| `offer_groups/` | Automatisch erzeugte Angebotsgruppen |
| `predictions/` | Gespeicherte Vorhersagen der trainierten Modelle |
| `eval/` | Auswertungen, Vergleichsantworten und Studien-Fingerabdrücke |
| [`benchmarks/`](benchmarks/README.md) | Originalprotokolle und Einzelantworten ergänzender Versuche |
| `audit/` | Prüfurteile und Referenzdiagnostik |
| `images/`, `raw/` | Seitenbilder und PDFs; überwiegend separat archiviert |

Die menschlichen Referenzen liegen separat unter [`gold/`](../gold/).
Für die Reproduktion weder Labels noch Wortlisten oder Splits verändern.
Die [Reproduktionsanleitung](../docs/report/README.md) nennt die benötigten
Artefakte je Auswertung; das [Rohdatenarchiv](../docs/archive/README.md)
erklärt die Wiederherstellung fehlender Bilder.
