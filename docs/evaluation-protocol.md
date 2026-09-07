# Abschlussmessung und Bedeutung der Zahlen

Stand: 2026-09-07. Dieses Protokoll legt fest, wie die Abschlussmessung gegen
die Handreferenz läuft und was die Zahlen bedeuten. Alte Reports und
Teacherlabels werden nicht überschrieben. Das Blackbox-Protokoll heißt
`offer-price-v2`; die Zahlen in `reports/woche-08.md` stammen aus v1.

## Vor der Messung

Modelle, Schwellen und die Seitenliste `data/eval/test_cluster_pages.txt`
einfrieren. Die Annotationsaufgabe umfasst zusätzliche Seiten; verglichen wird
auf der ausdrücklich angegebenen Liste. Beide Handdateien je Seite müssen
fertig und an die aktuelle Wortreihenfolge gebunden sein.

Der Handeditor lädt keine Lehrergruppen. Fertige menschliche Spans dienen als
Auswahlhilfe beim Gruppieren. Bereits früher mit Vorbelegung erstellte Golddateien
müssen hinsichtlich ihrer Herkunft geprüft werden. Korrektur einer LLM-Ausgabe
ist keine unabhängige Blindannotation. Offene Labelkonventionen und die
Auflösung von Uneinigkeiten im Team vor der Schlussmessung dokumentieren.

Testseiten wurden bereits in früheren Vergleichen betrachtet. Die Goldmessung
ist eine neue Referenzbewertung derselben festgelegten Testmenge, kein bislang
vollständig unberührter Test. Aus ihren Ergebnissen keine weiteren Modell-
oder Schwellenanpassungen ableiten und dann dieselbe Menge als neuen Test nutzen.

## Entity-Ebene

`magda eval` misst vollständige Seiten mit überlappenden Fenstern gegen die
gewählte LLM-Labelquelle. Entity-Micro-F1 verlangt exakte Grenzen und Typen.
Das ist Übereinstimmung mit dem Lehrer. Es ist weder Token-Accuracy noch der
Anteil vollständig korrekter Angebote. Training und Checkpointauswahl verwenden
weiterhin gekürzte Seiten; diese Einschränkung gehört in den Bericht.

```bash
magda eval-gold gbert --pages data/eval/test_cluster_pages.txt
magda eval-gold xlmr --pages data/eval/test_cluster_pages.txt
magda eval-gold lilt --pages data/eval/test_cluster_pages.txt
magda eval-gold layoutxlm --pages data/eval/test_cluster_pages.txt
```

Diese Befehle lesen gespeicherte Vorhersagen und fertige Handspans. Sie schreiben
keine Labels nach `data/labeled/`. Fehlende Handspans brechen ab; `--allow-partial`
ist eine ausdrücklich explorative Teilmessung und gehört nicht in die Haupttabelle.
Die entsprechenden Jobs stehen unter **Pipeline**. Vorhersagen bei Bedarf dort
mit **Modellvorhersagen exportieren** erzeugen, unter Verwendung der eingefrorenen
Checkpoints. Historische Exporte vor einem neuen Lauf separat sichern.

## Angebots-Ebene

Eine Bewertungseinheit ist der Name (Marke plus Produkt) zusammen mit einem
Aktionspreis. Eine Gruppe mit unterschiedlichen Variantenpreisen erzeugt je
Preis eine Zeile. Varianten mit gemeinsamem Preis bleiben innerhalb der Gruppe
eine Zeile. Das entspricht dem gespeicherten Blackbox-Prompt. Fehlende Namen
oder Aktionspreise sind Fragmente und werden getrennt ausgewiesen.

Der Preis muss exakt übereinstimmen. Für den Namen gilt die festgelegte Schwelle
`NAME_SIMILARITY` in `blackbox_eval.py`. Die Ähnlichkeit ist symmetrisiert;
ein maximales bipartites Matching bestimmt die Trefferzahl unabhängig von der
Reihenfolge. Jeder Eintrag kann höchstens einmal treffen. Altpreis, App-Preis,
Menge, Grundpreis, Rabatt und Gültigkeit sind **nicht** Bestandteil dieses
Haupt-F1. Daraus keine vollständige Feldgenauigkeit ableiten.

```bash
magda blackbox-eval --pages data/eval/test_cluster_pages.txt \
  --reference-groups gold --predictions layoutxlm --grouper pair-model \
  --blackbox-from data/eval/blackbox_test_gemma-4-31b-it_pair-model_ref-teacher.json
```

Analog die gespeicherten Qwen- und Mistral-Reports auswählen. Der Job **Blackbox
gegen Handreferenz** bietet denselben Weg im UI. Replay bewertet dieselben
Antworten neu, ohne API-Aufruf; API-Fehler im ursprünglichen Lauf bleiben
Teil seiner Zuverlässigkeitsbilanz. Alle Systeme werden auf derselben Liste
bewertet. Unfertige Gold-Seiten dürfen die Haupttabelle nicht verkleinern.

Neue Reports speichern Bewertungsversionskennung, Matchingregeln, angeforderte
und tatsächlich verwendete Seiten, eigene und Referenzangebote, Rohantworten,
Fingerabdrücke und Codeversion. Ihre Dateinamen tragen `offer-price-v2`.
Historische v1-Ergebnisse sind nicht direkt mit v2 vergleichbar.

## Gruppierung

Paar- und exakte Gruppen-F1 bewerten die Gruppierung der vorhandenen Entities.
Bei vorhergesagten Entities ist diese Aufgabe bedingt auf die Ausgabe des NER.
Deshalb Entity-F1, überlebende Referenzpaare und Gruppierungs-F1 gemeinsam nennen;
Gruppen-F1 allein ist kein vollständiger Ende-zu-Ende-Score (siehe die Kette
in `CLAUDE.md`, „Die Kette kostet fast nichts").

Wie die Ablationskette `xlmr → lilt → layoutxlm` im Bericht zu deuten ist
(kontrollierte Ablation oder Architekturvergleich), ist eine Teamentscheidung
und hier nicht festgelegt. Die Zahlen und ihre Einschränkungen stehen in
`reports/woche-06.md`.

## Unsicherheit, Herkunft und Laufzeit

Ein Cluster-Bootstrap resampelt Vorlagen statt Regionalduplikate. Er misst bei
festen Modellen die Stichprobenunsicherheit, nicht die Variation durch neue
Trainingsseeds. Mehrere Vergleiche als explorativ kennzeichnen oder ihre
Fehlerrate korrigieren. Ein Intervall mit null beweist keine Gleichwertigkeit.
Ohne berechnetes Intervall bleibt eine Differenz eine Punktschätzung.

Neue NER-Reports und Exporte tragen Referenz-/Checkpoint-Fingerabdrücke und
Codeversion. Die Oberfläche verbindet Konfidenzintervalle nur bei passenden
Metadaten, Protokollen und Punktwerten. Historische Reports ohne diese Belegkette
werden nicht nachträglich mit dem heutigen Checkpoint identifiziert. Die
Seedsetzung vor Kopf-Initialisierung betrifft künftige Trainingsläufe; sie
ändert keine vorhandenen Gewichte.

Blackbox-Laufzeit umfasst Rendern, API und Wiederholungen. `own_grouping` misst
nur die eigene Gruppierung, weder Referenzerzeugung noch NER oder Modellladen.
Replay erzeugt keine neue Blackbox-Laufzeit. Einen Ende-zu-Ende-Speedup nur aus
einem gemeinsamen Benchmark mit festgelegter Hardware, Warm-/Kaltstart,
Parallelität und denselben Seiten berichten. Die Zeitkonstanten auf der Übersicht
(0,264 s gegen 44,8 s je Seite) vergleichen Inferenz gegen Labeling, nicht zwei
vollständige Wege bis zum Angebot.
