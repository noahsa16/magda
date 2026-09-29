# Ergänzender GPT-6-Astra-Vergleich, 25. September 2026

Bewertet wurden dieselben 42 Seiten gegen 279 menschlich annotierte Referenzdatensätze. Ein Treffer betrifft Produktname und regulären Preis, nicht die vollständige Richtigkeit aller Angebotsfelder.

| System | Bewertete Ausgaben | Referenztreffer | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Magda | 281 | 212 | 0.7544 | 0.7599 | 0.7571 |
| Qwen3.8-27B, TH Lübeck API | 349 | 240 | 0.6877 | 0.8602 | 0.7643 |
| GPT-6 Astra, Codex, high reasoning | 315 | 241 | 0.7651 | 0.8638 | 0.8114 |

## Einordnung

Astra findet 29 mehr Referenzdatensätze als Magda. Gegenüber Qwen beträgt der Unterschied 1 Referenztreffer bei 34 weniger bewerteten Ausgaben. Der höhere F1-Punktwert gegenüber Qwen entsteht damit vor allem durch höhere Precision.

74 Astra-Ausgaben lassen sich nach dem festen Bewertungskriterium keinem Referenzdatensatz zuordnen. Bei Qwen sind es 109. Das macht diese Ausgaben nicht automatisch inhaltlich falsch oder zu Dubletten. Referenzfehler, unterschiedliche Angebotsgrenzen und abweichende Namen können ebenfalls zu fehlenden Treffern führen.

Die F1-Differenz Astra minus Magda beträgt +0.0543. Das gepaarte 95-%-Bootstrap-Intervall beträgt [-0.0308, +0.1547]. Es enthält null. Der numerische Vorsprung belegt daher in diesem Vergleich weder eine verlässliche Überlegenheit noch Gleichwertigkeit. Für Astra gegen Qwen wurde hier kein weiterer gepaarter Test durchgeführt.

## Ablauf und Grenzen

- Eine frische projektlose Codex-Aufgabe wurde explizit mit `gpt-6-astra` und Reasoning `high` gestartet. Die bisherige Unterhaltung wurde nicht übernommen.
- Bereitgestellt wurden bytegleiche Seitenbilder und der bisherige Extraktionsprompt in Version 1. Die zusätzliche Anweisung zum Lesen und Speichern ist in `launch.json` dokumentiert.
- Die Aufgabe verarbeitete alle Seiten in einem gemeinsamen Gesprächskontext und verwendete Bildanzeige und Dateischreibwerkzeuge. Das unterscheidet sich von den separaten API-Anfragen an Qwen. Die Ergebnisse sind ein ergänzender Codex-Vergleich.
- Laut Abschlussmeldung wurden keine gespeicherten Vorhersagen nachträglich überarbeitet oder überschrieben. Die Aufgabe erhielt keine Referenzantworten und war angewiesen, keine anderen Projektdateien oder externen Dienste zu verwenden.
- Alle 42 Dateien waren lesbar und entsprachen dem verlangten JSON-Feldschema. Gespeichert wurden 315 Datensätze mit 0 unbewerteten Fragmenten und 0 technischen Seitenausfällen.
- Die Aufgabe meldete, dass Kategorieaktionen mit ausschließlich prozentualem Rabatt ohne konkreten Zahlenpreis ausgelassen wurden. Solche Aktionen erfüllen auch nicht das hier verwendete Kriterium eines Datensatzes mit Name und regulärem Preis.
- Alle Antworten wurden vor der Bewertung mit SHA-256-Prüfsummen gesichert. Das bestehende Auswertungsskript wurde lediglich um einen frei wählbaren Systemnamen erweitert. Die bisherige Qwen-Auswertung wurde damit unverändert reproduziert.
- Der gepaarte Vergleich verwendet die vorhandenen Seitencluster, 10000 Bootstrap-Ziehungen und Seed 42. Er berücksichtigt weder die Streuung zwischen erneuten Modellläufen noch mögliche Kontexteffekte zwischen Seiten und korrigiert keine Fehler der Referenz.
- Bekannte Annotationsfehler und die frühere Inspektion von Testseiten bleiben Einschränkungen. API-Laufzeit oder API-Kosten lassen sich aus diesem Codex-Lauf nicht ableiten.

## Artefakte und Reproduktion

- Eingabemanifest, Arbeitsanweisung, Abschlussmeldung und Originalantworten: `data/benchmarks/astra-codex-2026-09-25/`.
- Eingefrorene Antworten: `data/eval/codex_astra_2026-09-25.json`.
- Auswertung: `data/eval/codex_astra_score_2026-09-25.json`.
- Codex-Aufgabe: `01a0d8ec-3749-7d73-83f1-9d3c8b0242f7`.

```sh
.venv/bin/python scripts/score_runtime_offers.py data/eval/codex_astra_2026-09-25.json --system-name astra_codex --output data/eval/codex_astra_score_2026-09-25.json
.venv/bin/python scripts/summarize_astra_benchmark.py
```

Die Bewertung ist aus den gespeicherten Antworten reproduzierbar. Eine bitgleiche erneute Modellausgabe wird nicht behauptet.
