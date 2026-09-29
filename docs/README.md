# Dokumentation

## Start und Reproduktion

- [Installation und Oberfläche](../README.md)
- [Bericht und Reproduktionsanleitung](report/README.md)
- [Abgeschlossene Studie](finish-study.md) und [Bewertungsprotokoll](evaluation-protocol.md)
- [GPU-Training](runpod.md) und [Rohdatenarchiv](archive/README.md)

## Projektstruktur

| Pfad | Inhalt |
|---|---|
| `src/magda/` | Python-Package: Extraktion, Modelle, Evaluation, API und CLI |
| `frontend/` | React-Oberfläche mit eigenen Tests und npm-Lockfile |
| `tests/` | Python-Tests |
| [`scripts/`](../scripts/README.md) | Reproduktions- und Diagnoseskripte |
| [`data/`](../data/README.md) | Datensatz, feste Splits, Vorhersagen und Messbelege |
| `gold/` | Menschliche Entity- und Angebotsreferenz |
| [`reports/`](../reports/README.md) | Ergebnisberichte und historische Wochenberichte |
| `docs/report/` | LaTeX-Bericht, Tabellenexport und Reproduktion |
| `docs/screenshots/` | Abbildungen für die README |
| `docs/archive/` | Rohdatenmanifest und historische Entwicklungsunterlagen |
| `checkpoints/`, `output/` | Lokale Modellgewichte bzw. erzeugte Arbeitsdateien |

`catalog_meta.json` bleibt im Projektroot: Die Pipeline verwendet diesen
versionierten Katalogindex. Datenpfade und Wortreihenfolge sind Teil des
Reproduktionsprotokolls.

## Methoden und Hintergrund

- [Projektproposal](proposal/IE_ProjectProposal_Magda.pdf)
- [Studienprotokoll](study-protocol-v1.md)
- [Handannotation](annotation-task.md) und [Entwurf zur unabhängigen Prüfung](annotation-guidelines-v1.md)
- [Extraktionsprompt](blackbox-extraction-prompt.md) und [Gruppierungsprompt](offer-teacher-prompt.md)
- [Historische Entwicklungsunterlagen](archive/development/README.md) und [ursprünglicher Prototyp](archive/prototype/README.md)

Änderungen gehen über Feature-Branches und Pull Requests nach `development`,
anschließend gesammelt nach `main`. Erledigte Feature-Branches werden entfernt.
