# Magda: Lernen aus LLM-Labels für die Angebotsextraktion

## Kurzfassung

Dieses Projekt untersucht eine lokal ausführbare Pipeline zur Extraktion strukturierter Angebotsdaten aus deutschen Penny-Prospekten. Auf automatisch erzeugten Labels trainierte Tokenklassifikatoren werden mit menschlichen Entity-Annotationen verglichen. Eine weitere Stufe gruppiert Entities zu Angeboten. Die vollständige Pipeline wird auf der gemeinsamen Feldmenge aus Name und regulärem Preis mit gespeicherten Vision-LLM-Ausgaben verglichen.

**Arbeitsstand: explorative Fallstudie.** Die Berechnung ist reproduzierbar. Die unabhängige Kontrollannotation und die Klärung der Referenzhinweise sind als eigene Arbeitsschritte ausgewiesen. Die folgenden Werte gelten für die gegenwärtige Referenzversion; sie tragen noch keine abschließende Aussage über Systemüberlegenheit.

Auf dieser Referenz erreicht LayoutXLM Strict Entity-F1 0.7170, die Textbaseline GBERT 0.7032. Die lokale Pipeline erzielt Angebots-F1 0.7571 auf Name und Preis. Die gepaarten Differenzintervalle und die Einschränkungen dieser Punktwerte stehen bei den jeweiligen Vergleichstabellen.

## 1. Fragestellung und Beitrag

Untersucht werden (1) Entity-Erkennung, (2) die Gruppierung vorgegebener Entities und (3) die Ausgabe von Angebotsname und Preis. Der eigene Lernbeitrag liegt im Fine-Tuning der Tokenklassifikatoren sowie dem trainierten Paarmodell. Das LLM dient zur Trainingsannotation und als Vergleichssystem. Die Güte des Lehrers und die Güte gegenüber menschlichen Annotationen sind unterschiedliche Größen.

Der Umfang folgt dem Projektantrag: trainiertes Ende-zu-Ende-System, Entity-P/R/F1, Textbaseline, Fehleranalyse und LLM-Vergleich mit Diskussion der praktischen Grenzen. Für einen guten Bericht ist kein bestimmter Gewinner erforderlich.

## 2. Daten und Referenz

Der eingefrorene Split enthält 494 Trainings-, 56 Entwicklungs- und 116 Testseiten. Die feste Vergleichsliste umfasst 42 Seiten in 42 ausgewerteten Vorlagenclustern. Das Skript prüft die Zugehörigkeit zum Test und disjunkte Seiten-IDs der drei Splits.

Die PDFs besitzen einen Textlayer. Wörter und Koordinaten stammen aus PyMuPDF; die Studie bewertet somit keine OCR-Qualität auf eingescannten Dokumenten. Der Goldstandard speichert Wortspans und Angebotsgruppen getrennt. Hashprüfungen schützen die Bindung der Indizes an diese Wortlisten.

**Kontrollannotation:** `awaiting_two_human_submissions`. Das getrennte Prüfpaket zieht Vorlagen unabhängig von Modellausgaben. Zwei Originalabgaben, frühere Einsicht und ein anschließender gemeinsamer Abgleich werden getrennt festgehalten. Solange diese Abgaben fehlen, wird keine Inter-Annotator-Übereinstimmung angegeben.

Die Herkunft der Entity- und Gruppierungsannotation wird je Seite in `reference-audit.json` festgehalten. Menschlich geprüfte KI-Vorschläge gelten nicht als unabhängige Blindannotation. Eine Prüfung der Gruppierung belegt keine vollständige semantische Prüfung der zugrunde liegenden Entity-Labels.

## 3. Modelle und Auswertung

GBERT und XLM-R verarbeiten Text, LiLT zusätzlich Layout, LayoutXLM außerdem Bildinformation. Die Architekturen unterscheiden sich auch im Vortraining. Ein Vergleich ihrer Ergebnisse isoliert daher keine kausale Wirkung einer einzigen Eingabekomponente. Für diese Studie bleiben die vorhandenen Ausgaben und die Schwelle des Paarmodells unverändert.

Die Tokenklassifikatoren verwenden BIO-Zielgrößen und eine Klassifikationsschicht über den Encoderrepräsentationen. Beim Subword-Alignment trägt der erste Subword das Wortlabel; Fortsetzungen sind vom Loss ausgeschlossen. Der Trainingscode wählt den Checkpoint anhand des Entwicklungs-F1. Training kürzt lange Eingaben, während die Inferenz überlappende Fenster unterstützt. Diese unterschiedliche Verarbeitung ist eine Einschränkung. Die historischen Exporte belegen keine vollständig rekonstruierbare Trainingskonfiguration.

Der eingesetzte Gruppierer ist ein MLP mit verdeckten Schichten 64 → 32. Sein gespeicherter Merkmalsvertrag enthält 43 Merkmale aus types, geometry_base, geometry_plus, lexical. Für jedes Entity-Paar wird die gemeinsame Angebotszugehörigkeit geschätzt. Ein anschließender Dekoder (`ilp`) bildet daraus konsistente Gruppen; die gespeicherte Schwelle beträgt 0.68. Die vollständige Merkmalsliste und die Herkunft des Checkpoints stehen in `study.json`.

Der Gruppierungscheckpoint deklariert als Trainingsquelle `claude-sonnet-5` und Split `train`. Das ist gespeicherte Trainingsherkunft; ohne historische Seitenliste samt Splithash ist sie kein nachträglicher vollständiger Beweis der Trainingszusammensetzung.

### 3.1 Entity-Erkennung

Primär wird Strict Entity-Micro-F1 verwendet: Grenze und Typ müssen stimmen. Exact ignoriert den Typ, Partial berücksichtigt Teilüberlappung, Type verlangt einen passenden Typ bei Überlappung. Alle vier Schemata werden gemeinsam berichtet [1]. `nervaluate` ist auf Version 1.2.1 festgelegt; die Endindizes werden explizit umgerechnet. Ein Adapter stellt sicher, dass ein einziges gemeinsames Wort auch bei langen Spans als Überlappung zählt. Strict-F1 wird unabhängig mit seqeval gegengeprüft.

| Modell | Precision strict | Recall strict | F1 strict | Exact | Partial | Type | Strict 95-%-KI |
|---|---:|---:|---:|---:|---:|---:|---|
| gbert | 0.7053 | 0.7010 | 0.7032 | 0.7202 | 0.8066 | 0.8688 | [+0.6390; +0.7556] |
| xlmr | 0.7157 | 0.7071 | 0.7114 | 0.7252 | 0.8082 | 0.8720 | [+0.6473; +0.7651] |
| lilt | 0.7066 | 0.6961 | 0.7013 | 0.7184 | 0.8033 | 0.8654 | [+0.6379; +0.7537] |
| layoutxlm | 0.7210 | 0.7131 | 0.7170 | 0.7281 | 0.8081 | 0.8720 | [+0.6514; +0.7716] |

Die Zähler werden pro Vorlage resampelt und vor der F1-Berechnung summiert. Bei den gepaarten Differenzen sehen beide Systeme dieselben Ziehungen. Die Bonferroni-Intervalle berücksichtigen die vier angegebenen NER-Vergleiche als eigene explorative Familie [2].

| Differenz A − B | ΔF1 | 95-%-Intervall | Bonferroni-Intervall |
|---|---:|---|---|
| xlmr − gbert | 0.0082 | [-0.0075; +0.0286] | [-0.0109; +0.0355] |
| lilt − xlmr | -0.0101 | [-0.0236; +0.0010] | [-0.0275; +0.0031] |
| layoutxlm − lilt | 0.0157 | [+0.0015; +0.0325] | [-0.0015; +0.0374] |
| layoutxlm − gbert | 0.0139 | [-0.0036; +0.0367] | [-0.0070; +0.0440] |

### 3.2 Entity-Typen

Strict-F1 je Typ, mit dem Referenzumfang. Seltene Typen sind weniger präzise beurteilbar; die Gesamtzahl ersetzt diese Auflösung nicht.

| Typ | Referenzentities | GBERT | XLM-R | LiLT | LayoutXLM |
|---|---:|---:|---:|---:|---:|
| APP_PRICE | 62 | 0.7368 | 0.6078 | 0.5657 | 0.5743 |
| BRAND | 254 | 0.8612 | 0.8800 | 0.8737 | 0.9138 |
| DISCOUNT | 140 | 0.9474 | 0.9474 | 0.9474 | 0.9333 |
| OLD_PRICE | 120 | 0.8537 | 0.8816 | 0.8468 | 0.8908 |
| PRICE | 291 | 0.8643 | 0.8719 | 0.8586 | 0.8826 |
| PRODUCT | 322 | 0.5208 | 0.5385 | 0.5310 | 0.5651 |
| QUANTITY | 337 | 0.3711 | 0.3726 | 0.3662 | 0.3639 |
| UNIT_PRICE | 255 | 0.7787 | 0.7802 | 0.7802 | 0.7802 |
| VALID | 42 | 0.8293 | 0.9024 | 0.8675 | 0.8000 |

### 3.3 Gruppierung

Die erste Messung gibt beiden Gruppierern dieselben Goldentities. Die dritte Zeile verwendet LayoutXLM-Entities. Paar-F1 zählt zusammengehörige Entity-Paare, Gruppen-F1 exakt rekonstruierte Entity-Gruppen. Die Grundmenge unterscheidet sich zwischen Gold- und Modellentities; diese Werte sind daher bedingte Diagnosen und kein direktes E2E-F1.

| Eingabe / Gruppierer | Paar-F1 | 95-%-KI | Exakte Gruppen-F1 | 95-%-KI | Nicht zuordenbare Entities | Referenzgruppen ohne Entity |
|---|---:|---|---:|---|---:|---:|
| heuristic_on_gold | 0.7291 | [+0.6281; +0.8523] | 0.4164 | [+0.3094; +0.5329] | 49 | 0 |
| pair_model_on_gold | 0.9168 | [+0.8804; +0.9508] | 0.7112 | [+0.5977; +0.8090] | 49 | 0 |
| pair_model_on_layoutxlm | 0.9267 | [+0.8846; +0.9583] | 0.7264 | [+0.6197; +0.8180] | 212 | 0 |

### 3.4 Vergleich der Angebotsausgaben

Der unveränderte Score `offer-price-v2` verlangt denselben regulären Preis und symmetrische Zeichenähnlichkeit des Namens von mindestens 0.6. Ein maximales Eins-zu-eins-Matching verhindert Mehrfachtreffer. Die Zeichenähnlichkeit ist keine semantische Ähnlichkeit. Die Blackbox liefert keine Textpositionen; SemEval-Spanmetriken sind auf diese Ausgaben ohne zusätzliche, fehlerbehaftete Ausrichtung nicht unmittelbar anwendbar.

| System | Treffer | Ausgaben | Referenzeinträge | Precision | Recall | F1 | 95-%-KI | Fehlende Antworten |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| layoutxlm_pair_model | 212 | 281 | 279 | 0.7544 | 0.7599 | 0.7571 | [+0.6551; +0.8521] | 0 |
| gemma-4-31b-it | 200 | 272 | 279 | 0.7353 | 0.7168 | 0.7260 | [+0.6344; +0.8088] | 5 |
| qwen3.6-35b-a3b | 231 | 328 | 279 | 0.7043 | 0.8280 | 0.7611 | [+0.6817; +0.8330] | 0 |
| mistral-medium-3.5-128b | 207 | 340 | 279 | 0.6088 | 0.7419 | 0.6688 | [+0.5842; +0.7504] | 3 |

22 Referenzfragmente und 106 Fragmente der lokalen Pipeline haben keinen auswertbaren Namen oder PRICE. Sie stehen vollständig in `study.json`. Altpreis, App-Preis, Menge, Grundpreis, Rabatt, Gültigkeit und Kaufbedingungen sind außerhalb dieses Hauptscores. Eine Referenzgruppe kann mehrere Preisvarianten enthalten und dadurch mehrere Einträge erzeugen.

Alle angeforderten Seiten bleiben im Vergleich. Fehlgeschlagene API-Seiten haben leere Ausgaben. Die drei LLM-Vergleiche bilden eine zweite explorative Familie für die Bonferroni-Intervalle.

| Differenz A − B | ΔF1 | 95-%-Intervall | Bonferroni-Intervall |
|---|---:|---|---|
| gemma-4-31b-it − layoutxlm_pair_model | -0.0312 | [-0.1450; +0.0908] | [-0.1703; +0.1177] |
| qwen3.6-35b-a3b − layoutxlm_pair_model | 0.0040 | [-0.0892; +0.1126] | [-0.1067; +0.1376] |
| mistral-medium-3.5-128b − layoutxlm_pair_model | -0.0883 | [-0.2024; +0.0392] | [-0.2225; +0.0685] |

## 4. Fehleranalyse und Referenzprüfung

Abweichungen werden zunächst als Unterschiede gegenüber der derzeitigen Referenz bezeichnet. Bei ungeklärten Goldlabels lässt sich daraus nicht automatisch ein Modellfehler ableiten. Die folgende Taxonomie zählt nicht exakt getroffene Referenzentities; zusätzliche Vorhersagen sind über Precision und die vollständigen Systemzähler erfasst.

| Modell | Keine überlappende Vorhersage | Falscher Typ bei exakten Grenzen | Grenzen / Zusammenfassung abweichend |
|---|---:|---:|---:|
| gbert | 127 | 31 | 387 |
| xlmr | 136 | 25 | 373 |
| lilt | 144 | 31 | 379 |
| layoutxlm | 141 | 20 | 362 |

### Regelbasierte Hinweise

Diese Prüfung verwendet ausschließlich Referenzdateien und Quellwörter. Die Zahlen sind Anzahlen von Hinweisen, keine bestätigten Fehlerquoten. Ein Fall kann mehrere Hinweise auslösen. Alle Fälle mit Wortindizes und Text stehen in `reference-audit.json` und `reference-review.md`.

| Hinweis | Anzahl |
|---|---:|
| entity_not_fully_grouped | 21 |
| numeric_without_digit | 119 |
| price_group_without_name | 2 |
| product_group_without_regular_price | 16 |
| quantity_campaign_text | 2 |
| quantity_prefix | 132 |
| regular_price_marked_old | 1 |

Konkreter Prüffall: 1364390_p3, Wort 229, „2.69“ nach „ohne PENNY App“ trägt OLD_PRICE. Wenn die zugehörige Gruppe keinen PRICE enthält, verschwindet das Angebot aus der Referenzprojektion. Solche Fälle werden vor der abschließenden Interpretation am Bild geklärt.

Korrekturen werden erst nach dem gemeinsamen Abgleich als neue Referenzversion ausgewertet. Dieselbe geklärte Regel gilt dabei systematisch für alle betroffenen Seiten.

## 5. Aussagegrenzen und praktische Einordnung

- Menschliche Doppelannotation und Klärung der Referenzhinweise stehen aus.
- Testseiten wurden bereits betrachtet; Modell- und Schwellenwahl wird hier nicht optimiert.
- Ein Händler und eine Testwoche; keine allgemeine Aussage über neue Händler oder Wochen.
- Ein gespeicherter Lauf je System; Bootstrap misst keine Trainings- oder API-Seed-Streuung.
- NER-Exporte enthalten teilweise keine Checkpoint-Fingerabdrücke; heutige Gewichte werden ihnen nicht zugeschrieben.
- Architekturvergleich mit unterschiedlichen Vortrainingsverfahren; keine kontrollierte kausale Layout-/Bildablation.
- Blackbox sieht Bilder und kann Logos ohne PDF-Text erkennen; lokale Ausgaben sind an Textlayer-Wörter gebunden.
- Name und PRICE sind die gemeinsamen Felder; keine vollständige Feldgenauigkeit und kein gemessener Ende-zu-Ende-Speedup.

Die lokale Pipeline benötigt nach dem Training für ihre Inferenz keine externe LLM-Antwort. Dazu kommen eigener Hardware-, Installations- und Trainingsaufwand. Die Blackbox spart diese Modellpflege, benötigt aber einen erreichbaren Dienst und muss dessen Wartezeiten und Fehler behandeln. Aus dem Replay werden keine neuen Laufzeit- oder Kostenwerte abgeleitet. Die im Projekt gespeicherte Gruppierungszeit deckt nicht den vollständigen Weg vom PDF bis zum Angebot ab.

Ein Intervall, das null enthält, belegt keine Gleichwertigkeit. Auch ein von null getrenntes Intervall beseitigt weder systematische Referenzfehler noch frühere Einsicht in den Test. Die Intervalle gelten bei festen Gewichten und erfassen keine Streuung über Trainingsseeds.

## 6. Abschluss und nächste Modellarbeit

Die vorhandene Implementierung deckt die technische Auswertung des Projektantrags ab. Für abschließende Qualitätsaussagen bleibt die menschliche Referenzprüfung erforderlich: Regeln vor der Kontrollannotation bestätigen, beide Originalabgaben sichern, Übereinstimmung berechnen, Unterschiede und die Prüfliste am Bild klären, einen neuen Referenzstand sichern und dieselben Ausgaben erneut auswerten.

Für zusätzliche Modellarbeit wird zuerst eine konkrete Hypothese an Train/Dev geprüft, beispielsweise zu Preisbedingungen oder langen Seiten. Änderungen bleiben eigene Läufe. Eine danach neu erhobene Testwoche prüft die Übertragbarkeit; der vorhandene Split bleibt unverändert. Ein behaupteter Gewinn auf den bereits zur Entwicklung betrachteten Testseiten wäre kein unabhängiger Nachweis.

## 7. Reproduzierbarkeit

```bash
.venv/bin/magda study-eval --pages data/eval/test_cluster_pages.txt --output data/eval/study-2026-09-15 --review-packet data/audit/independent-review-v1 --resamples 10000 --seed 42
```

`study.json` enthält alle Zähler, Ausgaben, Intervalle, Vorlagen, Referenzprüfungen und Laufmetadaten. Die Originalantworten der Blackbox werden über ihre Dateihashes referenziert. Die Ausgabe benötigt keine neuen API-Aufrufe und verändert weder Modellgewichte noch Trainingslabels.

- Quellcode-Commit: `c606a175b047530df2bd792a8ebcf52cd1e8f71b`
- Quellcode-SHA256 einschließlich lokaler Änderungen: `637b8cdc2a9b0fa7eae9713ba9f6682645d5b34795bffa27ff547f61d753b5b2`
- Split-SHA256: `7d4f3edda7ae3b085b2511cd0db1b3c882663d67abccf21f4938b665ad586093`
- Referenzinventar-SHA256: `7a4240d65266223822c25529e3c84fcddfc465ad65d592efbe3ee756b7a1bd8f`
- Paarmodell-SHA256: `2cc9c2f8336244158bc0afe9c7e9407688ef71caef531933a982309c65ba117b`
- Bootstrap: 10000 Ziehungen, Seed 42.

## Literatur

1. [Segura-Bedmar et al. (2013): SemEval-2013 Task 9](https://aclanthology.org/S13-2056/), Abschnitt 3.1.
2. [Dror et al. (2018): The Hitchhiker’s Guide to Testing Statistical Significance in NLP](https://aclanthology.org/P18-1128/).
3. [Bender & Friedman (2018): Data Statements for NLP](https://aclanthology.org/Q18-1041/).
4. [nervaluate: Implementierung der Entity-Metriken](https://github.com/MantisAI/nervaluate), verwendete Version 1.2.1.
