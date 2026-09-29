# Einstieg

Installation und Start stehen in der [Projekt-README](../README.md).
Die [Reproduktionsanleitung](report/README.md) erklärt, wie die berichteten
Ergebnisse aus gespeicherten Vorhersagen nachgerechnet werden.

## Orientierung

| Pfad | Inhalt |
|---|---|
| `src/magda/` | Extraktion, Training, Evaluation und API |
| `frontend/` | Weboberfläche und Annotation |
| `data/words/`, `data/labeled/` | Extrahierte Wörter und automatische Labels |
| `data/predictions/`, `data/eval/` | Vorhersagen und gespeicherte Auswertungen |
| `gold/`, `gold/offers/` | Menschliche Entity- und Gruppenreferenz |
| `docs/report/` | LaTeX-Bericht und Reproduktion |
| `reports/` | Historische Wochenberichte |

## Daten erhalten

Wortreihenfolge, Referenzlabels und `data/splits/split.json` bei der
Reproduktion unverändert lassen. Fehlende Seitenbilder ausschließlich mit
`magda extract --render-missing` aus den archivierten PDFs ergänzen
([Rohdaten](archive/README.md)). Modellgewichte sind separat beim Team erhältlich.

Die [Annotationsanleitung](annotation-task.md) dokumentiert die frühere
Handannotation. Neue Annotationen sind für das Nachrechnen nicht erforderlich.
Änderungen erfolgen auf Feature-Branches mit Pull Request nach `development`.
