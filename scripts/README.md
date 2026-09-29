# Reproduktion und Diagnose

Aus dem Projektroot mit `.venv/bin/python scripts/<datei>.py` ausführen.
Installation und vollständige Befehle stehen in der
[Reproduktionsanleitung](../docs/report/README.md).
Die eigentliche Pipeline ist über `magda --help` erreichbar.

| Aufgabe | Skripte |
|---|---|
| Gespeicherte Qwen-/Astra-Antworten bewerten | `score_runtime_offers.py` |
| Ergänzenden Astra-Bericht erstellen | `summarize_astra_benchmark.py` |
| Datensatzumfang nachzählen | `count_sonnet_entities.py` |
| Studienstand und Änderungen prüfen | `check_study_completion.py`, `check_study_mutations.py` |
| Blackbox-Vergleich prüfen und aufschlüsseln | `check_blackbox_gold.py`, `summarize_blackbox_gold.py`, `blackbox_decompose.py` |
| Ausgabe- und Gruppierungsdiagnostik | `review_offer_outputs.py`, `check_offer_groups.py` |
| Neue Laufzeit- oder Codex-Versuche vorbereiten | `benchmark_offer_runtime.py`, `codex_offer_benchmark.py` |
| Manuelle Annotationen zusammenführen | `merge_gold_spans.py` |

Neue Versuche und Änderungen an Annotationen gehören nicht zum Nachrechnen
gespeicherter Ergebnisse. Dafür separate Ausgabepfade verwenden.
Der Tabellenexport für LaTeX liegt direkt beim Bericht unter
`docs/report/generate_assets.py`.
