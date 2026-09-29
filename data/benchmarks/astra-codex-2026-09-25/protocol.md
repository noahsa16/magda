# Ergänzender Codex-Bildvergleich

Vor der Auswertung festgelegtes Vorgehen, 25. September 2026.

- Zielmodell: `gpt-6-astra`, Reasoning `high`, explizit bei Erstellung der Codex-Aufgabe eingestellt.
- Oberfläche: Codex Desktop, neue projektlose Aufgabe ohne bisherige Unterhaltung.
- Aufgabe: `01a0d8ec-3749-7d73-83f1-9d3c8b0242f7`.
- Eingabe: die unveränderten 42 PNG-Dateien aus `data/eval/test_cluster_pages.txt`, in dieser Reihenfolge. SHA-256-Prüfsummen im Eingabemanifest.
- Extraktionsanweisung: `_EXTRACT_PROMPT` aus `src/magda/blackbox.py`, Version 1, unverändert kopiert. Die zusätzliche Arbeitsanweisung zum Ansehen und Speichern steht vollständig in `launch.json`.
- Bereitgestellt werden nur Bilder, Extraktionsprompt und Manifest. Die Aufgabe wurde angewiesen, keine anderen Projektdateien, Referenzen, Modellantworten, OCR-Verfahren oder externen Dienste zu verwenden. Dies ist eine Verfahrensvorgabe und keine technisch erzwungene Zugriffssperre.
- Eine zusammenhängende Aufgabe verarbeitet die Seiten nacheinander. Der Kontext früherer Seiten bleibt erhalten. Das ist ein ergänzender Codex-Vergleich mit Werkzeugnutzung, kein identischer Ersatz für unabhängige API-Anfragen pro Seite.
- Jede Antwort wird nach dem Betrachten der betreffenden Seite gespeichert. Keine spätere inhaltliche Korrektur nach Sichtung anderer Seiten oder der Referenz. Syntaktische JSON-Prüfung und Prüfung der Feldnamen sind erlaubt.
- Alle Antworten werden mit Prüfsummen gesammelt, bevor die Bewertung beginnt. Fehlende Dateien blockieren die Auswertung. Technische Ausfälle werden ausdrücklich dokumentiert, nicht stillschweigend entfernt.
- Hauptvergleich: Astra-Codex gegen die unveränderten Magda-Ausgaben, mit `offer-price-v2`, denselben menschlichen Referenzen und demselben gepaarten Bootstrap wie zuvor. Die Schwelle des Namensvergleichs bleibt 0.6, Preise müssen übereinstimmen. Unvollständige Fragmente werden wie bisher gesondert gezählt.
- Die bereits gespeicherten Qwen3.8-27B-Werte werden zur Einordnung ebenfalls angegeben. Kein neuer Qwen-Lauf und keine Änderung der Referenz.
- Keine Aussage über API-Latenz, Kosten oder eine allgemeine Leistungsobergrenze. Bekannte Referenzfehler und frühere Inspektion von Testseiten bleiben Einschränkungen.

## Reproduktion

Die gespeicherten Antworten können erneut bewertet werden. Eine identische Neugenerierung durch das veränderliche Codex-Modell wird nicht behauptet.

```sh
.venv/bin/python scripts/codex_offer_benchmark.py prepare output/benchmarks/astra-codex-2026-09-25
```

Danach wurde die projektlose Aufgabe mit der in `launch.json` gespeicherten Arbeitsanweisung erstellt. Nach ihrem Abschluss:

```sh
.venv/bin/python scripts/codex_offer_benchmark.py collect output/benchmarks/astra-codex-2026-09-25 --predictions /Users/noahsamel/Documents/Codex/2026-09-25/magda-astra-extraction/predictions --thread-id 01a0d8ec-3749-7d73-83f1-9d3c8b0242f7 --output data/eval/codex_astra_2026-09-25.json
.venv/bin/python scripts/score_runtime_offers.py data/eval/codex_astra_2026-09-25.json --system-name astra_codex --output data/eval/codex_astra_score_2026-09-25.json
```

Die Vorbereitung und Sammlung überschreiben keine vorhandenen Läufe. Zum Wiederholen der Vorbereitung ist ein neuer Verzeichnisname nötig.
