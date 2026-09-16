# Abschluss mit bestehender Referenz

Die explorative Auswertung ist innerhalb des vereinbarten Studienumfangs
abgeschlossen. Es erfolgt keine weitere Labelrunde. Die nachträgliche
Umfangsentscheidung steht im [Methodenprotokoll](../docs/study-protocol-v1.md).

- [Aktueller Bericht](../data/eval/study-2026-09-16/report.md)
- [Ergebnisse und Fingerabdrücke](../data/eval/study-2026-09-16/study.json)
- [Diagnostischer Referenzanhang](../data/eval/study-2026-09-16/reference-diagnostics.md)
- [Abschluss und Reproduktion](../docs/finish-study.md)

## Änderungen

Der Standardlauf erzeugt keine neue Annotationsaufgabe. Kontrollannotation
wird als `not_performed` mit `scores: null` festgehalten. Der Status
`completed_exploratory` gilt für die Auswertung, nicht für eine Validierung
der Referenz. Angebotsdefinition, Mehrdeutigkeiten der Gruppierung, bekannte
Referenzfehler und fehlende unabhängige Doppelannotation sind im Bericht
ausdrücklich erklärt. README und Abschlussdokumentation verlinken diese Fassung.
Der vorherige Arbeitsbericht und das unbenutzte Prüfpaket bleiben erhalten.

## Verifikation am 16.09.2026

```bash
.venv/bin/python -m pytest -q -rs
.venv/bin/python scripts/check_study_mutations.py
.venv/bin/magda study-eval --output data/eval/study-2026-09-16
.venv/bin/python scripts/check_study_completion.py
git diff --check
```

**765 Tests bestanden, vier übersprungen.** Die übersprungenen LiLT-Forward-
Tests benötigen ein Basismodell, das lokal nicht im Cache liegt; Hugging Face
war im Testlauf nicht erreichbar. Die Studie verwendet die vorhandenen
LiLT-Vorhersagen und benötigt dafür keinen Download.

Die drei in separaten Prozessen injizierten Fehler werden durch ihre
Regressionstests erkannt: falscher Span-Endindex, festgehaltene Bootstrap-
Ziehungen und ungefragt gestartete Kontrollannotation. Die Tests hinterlassen
keine veränderten Daten oder Quellen.

Der vollständige Abschlusslauf war erfolgreich. `check_study_completion.py`
bestätigt gegenüber dem Lauf vom 15.09.2026 unveränderte NER-, Gruppierungs-
und Angebotswerte einschließlich Intervalle, Vorhersagen, Referenzprojektion,
Seitenliste und Modellparameter. Die Gold-Dateien stimmen bytegenau mit dem
gesicherten Stand `blackbox_gold_ready_2026-09-15.json` überein. Eingabe- und
Codehashes der neuen Fassung wurden geprüft. `git diff --check` meldet keine
Whitespacefehler.

Es wurden keine neuen Labels, Modellgewichte oder Blackbox-Antworten erzeugt.
Die Änderungen liegen auf dem Feature-Branch `codex/blackbox-gold-comparison`;
Commit, Pull Request und Merge sind nicht Bestandteil dieses Abschlusslaufs.

## Bericht für Leser ohne ML-Vorkenntnisse überarbeitet

Der Bericht erklärt jetzt den Datenweg anhand eines Angebotsbeispiels und
eines Ablaufdiagramms. Die Methodenübersicht unterscheidet Entity-Erkennung,
Heuristik, Paarmodell, ILP-Gruppierung und generative LLM-Extraktion. Begriffe
wie BIO, Token, Subword, Fine-Tuning, Inferenz, Checkpoint und Kalibrierung
werden im jeweiligen Zusammenhang eingeführt.

Precision, Recall und F1 werden mit Formeln und den tatsächlichen Zählern der
lokalen Pipeline erklärt. SemEval-Schemata, Paar-F1, Gruppen-F1, Angebots-F1
und Unsicherheitsintervalle erhalten jeweils eine verständliche Einordnung.
Interpretationen stehen unmittelbar bei den Ergebnissen. Der Abgleich mit
Seite 3 des Proposals ordnet jeder der fünf Anforderungen Umsetzung und
Nachweis zu. Abweichungen vom Plan (Textlayer statt OCR, andere
Blackbox-Modelle als der ursprüngliche Gemini-Prototyp) bleiben ausdrücklich
benannt; die Kostenabwägung wird als qualitativ ausgewiesen.

Validierung der Berichtsfassung:

```bash
.venv/bin/python -m pytest -q tests/test_study_scope.py tests/test_semeval.py tests/test_resampling.py
.venv/bin/magda study-eval --output data/eval/study-2026-09-16
.venv/bin/python scripts/check_study_completion.py
```

Die 30 gezielten Tests und der vollständige Studienlauf waren erfolgreich.
Die Abschlussprüfung bestätigt erneut unveränderte Messwerte, Intervalle
und Referenzdateien sowie passende aktuelle Code- und Eingabehashes.

## Vorbereitung der Integration nach development und main

Auf Anweisung des Teams werden Goldstand, Auswertung und Bericht über einen
Feature-PR nach `development` und anschließend einen Release-PR nach `main`
integriert. Die Gold-Ergänzungen sind separat in `ebdab23` gesichert; der
Auswertungscode steht in `6126155`. Lokale Playwright-Screenshots und
Browser-Snapshots bleiben als Bedienprüfungsartefakte vom Repository ausgeschlossen.

Die erneute Prüfung vor dem Push ergab **766 bestandene Python-Tests und vier
übersprungene LiLT-Forward-Tests** aus dem bereits beschriebenen Cache-Grund.
Zusätzlich bestanden **240 Frontend-Tests**; `npm run build` war erfolgreich.
Die vier gezielten Fehlermutationen in `scripts/check_study_mutations.py`
werden von den Regressionstests erkannt.

Die nachträgliche Snapshot-Prüfung erlaubt nun einen neuen Commit oder Merge
bei identischem Quelleninhalt. Sie prüft weiterhin sämtliche Daten- und
Quellenhashes. Während einer laufenden Messung muss zusätzlich die Git-Revision
unverändert bleiben. Damit macht das Versionieren des Berichts seine eigene
Reproduktionsprüfung nicht ungültig.
