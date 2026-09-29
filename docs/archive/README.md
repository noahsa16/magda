# Rohdaten und Seitenbilder

Wortlisten, automatische Labels, Splits, menschliche Referenzen und gespeicherte
Vorhersagen liegen im Repository. Die Original-PDFs und der Großteil der
Seitenbilder sind separat archiviert; Zugriff gibt es über Noah.
Modellgewichte liegen ebenfalls separat beim Team.

Für die [Auswertung gespeicherter Antworten](../report/README.md) sind weder
das Rohdatenarchiv noch Modellgewichte nötig. Die Bilder der Handannotation
liegen bereits unter `data/images/` bei. Für LayoutXLM-Training und neue
Inferenz werden die jeweiligen Seitenbilder benötigt; LayoutXLM erfordert
zusätzlich detectron2 ([GPU-Setup](../runpod.md)).

## Bilder wiederherstellen

Den Ordner `data/raw/` aus dem Projektarchiv ins Projektroot übernehmen, dann:

```bash
shasum -a 256 -c docs/archive/data-raw.sha256
.venv/bin/magda extract --render-missing
```

`--render-missing` erzeugt fehlende Seitenbilder und lässt die vorhandenen
Wortlisten unverändert. Der normale Extraktionslauf überspringt Seiten mit
vorhandenen Wortdateien, auch wenn das Bild fehlt.

`data/words/` nicht löschen oder neu sortieren: Alle Span-Labels beziehen sich
auf die gespeicherte Wortreihenfolge. Seitenbilder nicht verkleinern, da auch
Farbmerkmale aus ihnen berechnet werden.
