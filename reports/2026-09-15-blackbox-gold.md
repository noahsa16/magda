# Vorläufiger Blackbox-Vergleich gegen die Goldreferenz

**Status: explorativ.** Vollständigkeit, Dateihashes und Nachrechnung der Scores sind geprüft. Die fachliche Qualität der Referenz ist noch nicht ausreichend abgesichert; bei der Nachprüfung wurden Unstimmigkeiten in den Entity-Labels gefunden. Die Tabelle eignet sich derzeit nicht für eine abschließende Aussage über die Überlegenheit oder Gleichwertigkeit der Systeme.

Vollständige Vergleichsliste: **42 Seiten**, **279 auswertbare Referenzeinträge**. Protokoll: `offer-price-v2`.

| System | Treffer | Ausgaben | Precision | Recall | F1 | Seiten ohne Antwort |
|---|---:|---:|---:|---:|---:|---:|
| qwen3.6-35b-a3b | 231 | 328 | 0.7043 | 0.8280 | 0.7611 | 0/42 |
| LayoutXLM + Paarmodell | 212 | 281 | 0.7544 | 0.7599 | 0.7571 | 0/42 |
| gemma-4-31b-it | 200 | 272 | 0.7353 | 0.7168 | 0.7260 | 5/42 |
| mistral-medium-3.5-128b | 207 | 340 | 0.6088 | 0.7419 | 0.6688 | 3/42 |

## Was diese Zahlen bedeuten

Ein Treffer verlangt denselben Aktionspreis und die festgelegte Namensähnlichkeit von mindestens 0.6. Je Preisvariante entsteht ein Eintrag. Altpreis, App-Preis, Menge, Grundpreis, Rabatt und Gültigkeit gehören nicht zum Haupt-F1.

22 Referenzgruppen und 106 Gruppen der eigenen Pipeline konnten nicht auf Name und Aktionspreis abgebildet werden und sind separat als Fragmente ausgewiesen. Der Score bewertet damit keine vollständig korrekten Datensätze über alle Felder.

Die Blackbox-Antworten wurden ohne erneute API-Aufrufe wiederverwendet. Fehlgeschlagene Seiten aus den ursprünglichen Läufen bleiben mit leerer Ausgabe im Vergleich; keine Seite wurde wegen eines Blackbox-Fehlers aus der Referenz entfernt.

Es sind Punktschätzungen ohne berechnetes Konfidenzintervall. Eine Rangfolge beweist keinen statistisch gesicherten Unterschied. Die Testseiten wurden schon in früheren Vergleichen betrachtet; dies ist eine Neubewertung gegen die neue Referenz. Modelle, Schwellen und Seitenliste wurden für diesen Lauf nicht geändert.

Replay liefert keine neue Blackbox-Laufzeit. Die gespeicherte eigene Zeit umfasst nur die Gruppierung. Daraus wird kein Ende-zu-Ende-Speedup abgeleitet. Die historischen v1-Ergebnisse sind wegen des anderen Bewertungsprotokolls nicht direkt vergleichbar.

## Herkunft und Abschluss der Referenz

Handspans und vorhandene Handgruppen stammen aus der Abgabe `origin/gold` bei `c606a17`, einschließlich der dort bereits vorgenommenen Span-Normalisierung durch `scripts/merge_gold_spans.py`.

Die Gruppierung von `1364390_p3` wurde KI-gestützt ergänzt und anschließend von Noah im Annotator geprüft und ausdrücklich bestätigt. Der versehentlich abgetrennte Salatname wurde auf seine Bestätigung wieder mit dem Preis verbunden. Die Gruppierung ist menschlich geprüft und wurde mit KI-Unterstützung erstellt. Diese Prüfung belegt keine vollständige Prüfung der bestehenden Entity-Labels.

Für `1364390_p15` und `1364390_p23` wurden leere Gruppen aus den fertig bestätigten leeren Handspans abgeleitet. Die Seitenbilder zeigen reine Werbung. Bei `1364390_p25` und `1364420_p8` wurden die offenen Abschlussmarkierungen auf Grundlage von Noahs Angabe zum fertigen Annotationsstand gesetzt; deren Gruppeninhalte blieben unverändert.

Dateihashes und Herkunft je Seite: [blackbox_gold_ready_2026-09-15.json](../data/eval/blackbox_gold_ready_2026-09-15.json). Der alte Vorprüfungsbericht beschreibt den Stand vor diesen Abschlüssen.

## Reproduzieren

```bash
.venv/bin/magda blackbox-eval --pages data/eval/test_cluster_pages.txt \
  --reference-groups gold --predictions layoutxlm --grouper pair-model \
  --blackbox-from data/eval/blackbox_test_gemma-4-31b-it_pair-model_ref-teacher.json
.venv/bin/magda blackbox-eval --pages data/eval/test_cluster_pages.txt \
  --reference-groups gold --predictions layoutxlm --grouper pair-model \
  --blackbox-from data/eval/blackbox_test_qwen3.6-35b-a3b_pair-model_ref-teacher.json
.venv/bin/magda blackbox-eval --pages data/eval/test_cluster_pages.txt \
  --reference-groups gold --predictions layoutxlm --grouper pair-model \
  --blackbox-from data/eval/blackbox_test_mistral-medium-3.5-128b_pair-model_ref-teacher.json
```

Die Tabellenwerte werden aus den folgenden Reports geladen und mit `scripts/summarize_blackbox_gold.py` nachgerechnet:

- [blackbox_test_gemma-4-31b-it_pair-model_ref-gold_offer-price-v2.json](../data/eval/blackbox_test_gemma-4-31b-it_pair-model_ref-gold_offer-price-v2.json)
- [blackbox_test_qwen3.6-35b-a3b_pair-model_ref-gold_offer-price-v2.json](../data/eval/blackbox_test_qwen3.6-35b-a3b_pair-model_ref-gold_offer-price-v2.json)
- [blackbox_test_mistral-medium-3.5-128b_pair-model_ref-gold_offer-price-v2.json](../data/eval/blackbox_test_mistral-medium-3.5-128b_pair-model_ref-gold_offer-price-v2.json)

```bash
.venv/bin/python scripts/summarize_blackbox_gold.py \
  --inputs data/eval/blackbox_gold_ready_2026-09-15.json \
  data/eval/blackbox_test_gemma-4-31b-it_pair-model_ref-gold_offer-price-v2.json \
  data/eval/blackbox_test_qwen3.6-35b-a3b_pair-model_ref-gold_offer-price-v2.json \
  data/eval/blackbox_test_mistral-medium-3.5-128b_pair-model_ref-gold_offer-price-v2.json
```

Code-Commit: `c606a175b047530df2bd792a8ebcf52cd1e8f71b`. Paarmodell-SHA256: `2cc9c2f8336244158bc0afe9c7e9407688ef71caef531933a982309c65ba117b`.
