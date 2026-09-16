# Methodik und Validierung der ergänzten Fallstudie

## Implementiert

- `magda study-eval`: gemeinsame Rechnung aus der eingefrorenen Seitenliste,
  vier NER-Ausgaben, Paarmodell und drei gespeicherten Blackbox-Läufen.
- SemEval Strict, Exact, Partial und Type über `nervaluate==1.2.1`, mit
  expliziter Endindex- und Überlappungsbehandlung sowie Strict-Gegenprüfung
  durch seqeval. Labelauflösung und Seitenzähler bleiben gespeichert.
- Gruppierung auf Goldentities mit Heuristik und Paarmodell sowie auf
  LayoutXLM-Entities mit Paarmodell. Bedingte Grundmengen und nicht zuordenbare
  Entities stehen im Ergebnis.
- Gepaarte Cluster-Perzentilintervalle und Bonferroni-Intervalle für die
  angegebenen explorativen Vergleichsfamilien. Keine Gleichwertigkeitsbehauptung.
- Regelbasierte Referenzhinweise, ein von Modellausgaben unabhängig
  gezogenes Prüfpaket, zwei getrennte leere Editoren und ein Auswerter für
  die tatsächlichen menschlichen Originalabgaben.
- Die API erhält beim Speichern von Spans und Gruppen bestehende Herkunft
  und Notizen. Neue Editorannotation behauptet keine unabhängige Blindarbeit.
- Ein reproduzierbarer Bericht mit explizitem Geltungsbereich und
  Modelldokumentation. Die zu starken Kausal- und Laufzeitaussagen am Anfang
  der README wurden eingegrenzt; historische Messdateien bleiben erhalten.

## Validierung

```bash
.venv/bin/python -m pytest -q -rs
.venv/bin/python scripts/check_study_mutations.py
.venv/bin/magda study-eval --output data/eval/study-2026-09-15
```

Gesamtlauf am 15.09.2026: **759 Tests bestanden, 4 übersprungen**. Die vier
Übersprünge betreffen LiLT-Forward-Tests: Das benötigte Basismodell ist nicht
im lokalen Cache verfügbar, und der Testlauf konnte Hugging Face nicht erreichen.
Die vorhandenen LiLT-Ausgaben wurden vollständig in die Studie aufgenommen.

Der Gesamtlauf deckte zunächst einen bestehenden instabilen Upload-Test auf:
Er verglich die Länge zweier neu erzeugter PDFs, deren Metadaten variieren.
Der Test prüft jetzt Länge und Inhalt genau der übergebenen Bytes.

Die beiden gezielten Mutationen verändern ausschließlich separate
Python-Prozesse im Speicher: Ein falscher Endindex sowie festgehaltene
Bootstrap-Ziehungen lassen jeweils den vorgesehenen Regressionstest scheitern.
Damit ist belegt, dass die betreffenden Tests diese Fehler erkennen.

Bedienprüfung des separaten Blindeditors mit Playwright: Seitenbild lädt,
Wortauswahl, Labelzuweisung und Angebotszuordnung funktionieren; eine
unvollständige Abgabe wird gesperrt. Rückgängig stellt die leere Annotation
wieder her. Es wurde keine menschliche Abgabe erzeugt. Der einzige
beobachtete Browserfehler war ein fehlendes optionales Favicon.

Die neue Angebotsprojektion wurde gegen die bereits gespeicherten v2-Ausgaben
geprüft: eigene und Referenzangebote stimmen überein. Eingabe- und Codehashes
werden am Ende jedes Studienlaufs erneut geprüft. Wortlisten, eingefrorener
Split, Trainingslabels und Checkpoints wurden für diese Ergänzungen nicht geändert.

## Aktualisierter Studienumfang vom 16.09.2026

Nach den ersten ergänzenden Ergebnissen wurde beschlossen, keine weitere
Annotation durchzuführen. Die bestehende Referenz bleibt erhalten. Fehlende
unabhängige Doppelannotation, offene Angebotsabgrenzung, uneinheitliche Labels
und bekannte Referenzfehler werden als Limitationen berichtet. Das erzeugte
Prüfpaket ist unbenutzte Vorarbeit und keine durchgeführte menschliche Prüfung.

Der Standardlauf von `study-eval` erzeugt keine neue Annotationsaufgabe mehr.
Sein Abschlussstatus gilt für die explorative Auswertung und bestätigt keine
fehlerfreie Referenz. Der historische Arbeitsbericht bleibt erhalten; die
aktuelle Fassung steht unter `data/eval/study-2026-09-16/report.md`.
Reproduktion und Geltungsbereich: [finish-study.md](../docs/finish-study.md).
