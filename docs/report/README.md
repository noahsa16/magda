# Magda-Projektbericht in LaTeX

Englischer Bericht im schlichten Paper-Stil der bereitgestellten
ML4SCS-Vorlage. Einstieg: `main.tex`, Text unter `sections/`, Literatur in
`references.bib`. Kein Inhalt wird beim PDF-Build aus den ursprünglichen PDFs
benötigt. Repository: <https://github.com/noahsa16/magda>.
Die Anleitung unterscheidet den PDF-Build, den Tabellenexport und die
erneute Auswertung gespeicherter Vorhersagen. Keiner dieser Schritte
startet Training oder neue API-Aufrufe.

## PDF bauen

Aus dem Projektroot:

```bash
mkdir -p output/pdf
tectonic --keep-logs --outdir output/pdf docs/report/main.tex
cp output/pdf/main.pdf output/pdf/Magda_Project_Report_EN.pdf
```

Alternativ in Overleaf den Inhalt dieses Verzeichnisses hochladen,
`main.tex` als Hauptdatei und **XeLaTeX** als Compiler wählen. Mit einer
vollständigen lokalen TeX-Installation funktioniert auch
`latexmk -xelatex main.tex` aus diesem Verzeichnis.

TeX Gyre Termes wird bevorzugt, auf macOS fällt die Vorlage bei fehlender
Schrift auf Times New Roman zurück. Tectonic lädt fehlende TeX-Pakete bei
Bedarf; mit vollständigem Cache ist `--only-cached` möglich.

## Tabellen und Abbildungen aktualisieren

Die generierten Dateien liegen bei, damit der LaTeX-Ordner selbstständig
kompilierbar ist. Zum erneuten Export aus den gespeicherten Messungen:

```bash
.venv/bin/python docs/report/generate_assets.py
```

Der Export benötigt die Projektumgebung und Matplotlib. Nach dem Setup
aus der Haupt-README lässt sich Matplotlib bei Bedarf mit
`.venv/bin/python -m pip install matplotlib` ergänzen.
Der Export führt keine neue Evaluation durch.
Er liest ausschließlich:

- `data/eval/study-2026-09-16/study.json`
- `data/eval/offers_grid_dev_ilp.json`
- `data/eval/offers_grid_dev_cv_union-ilp.json`
- `data/eval/runtime_thl_qwen3.8-27b_score_2026-09-24.json`
- `data/eval/codex_astra_score_2026-09-25.json`

`generated/sources.json` dokumentiert Pfade und SHA256-Fingerabdrücke.
Der Export prüft zusätzlich die F1-Werte gegen die gespeicherten Zähler.
Tabellen und Grafiken sind generiert; Fließtext und Abstract werden
redaktionell gepflegt und müssen bei einem anderen Ergebnisstand ebenfalls
angepasst werden. Keine Studien-, Gold- oder Labeldatei wird verändert.

## Hauptstudie nachrechnen

Grundlage ist `data/eval/study-2026-09-16/study.json`. Dort stehen die
Eingabe- und Code-Fingerabdrücke, Einstellungen, Paketversionen,
Einzelergebnisse und Zähler. Die untersuchte Code-Revision lautet
`61261557b7e2cc02c2cc4d44098b347fd395a8be`. Sie bezeichnet die
Evaluationsimplementierung, nicht den später überarbeiteten Bericht.

Voraussetzungen sind Python ab 3.11 und das Setup aus der Haupt-README.
Der vollständige Studienlauf benötigt die gespeicherten Vorhersagen unter
`data/predictions/`, die Referenzen unter `gold/` und `gold/offers/`, die
Wortlisten, den eingefrorenen Split, die Testseitenbilder und die
ursprünglichen Blackbox-Antworten unter `data/eval/`. Die Seiten- und
Antwortdateien sind im Studienartefakt einzeln mit Prüfsummen erfasst.

Zusätzlich ist der **ursprüngliche Paarmodell-Checkpoint**
`checkpoints/offer_pairs/model.pt` erforderlich. Er ist nicht in Git und
muss aus dem archivierten Projektstand beim Team bezogen werden. Sein
erwarteter Hash steht unter `pair_checkpoint_sha256` in `study.json`.
Ein neu trainiertes Modell ist kein Ersatz für eine exakte Wiederholung.
Die vollständige Gruppierung kann ohne diese Datei nicht neu berechnet
werden. PDF-Build, Tabellenexport und die unten beschriebenen zusätzlichen
Record-Auswertungen benötigen sie dagegen nicht.

Mit allen Originaldateien prüft folgender Befehl den gespeicherten Stand,
ohne eine neue Auswertung auszuführen:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from magda.evaluation_study import verify_snapshot

study = json.loads(Path("data/eval/study-2026-09-16/study.json").read_text())
verify_snapshot(study, require_same_revision=False)
print("Eingaben und Evaluationscode stimmen mit dem Studienstand überein.")
PY
```

`require_same_revision=False` erlaubt reine Berichts-Commits nach der
Messung. Die Inhalts-Hashes von Evaluationscode, Modell und Eingaben
werden weiterhin geprüft. Bei einer Abweichung zuerst die Originaldateien
wiederherstellen, statt Referenzen oder Messwerte anzupassen.

Der folgende Lauf berechnet Erkennungs-, Gruppierungs- und Record-Metriken
sowie die Bootstrap-Intervalle neu. Die Gruppierung wird mit dem
gespeicherten Paarmodell ausgeführt, die Erkennungsmodelle werden nicht
erneut aufgerufen. Als Ausgabe einen separaten Ordner verwenden:

```bash
.venv/bin/magda study-eval \
  --pages data/eval/test_cluster_pages.txt \
  --output /tmp/magda-study-reproduction \
  --resamples 10000 --seed 42
```

Der Lauf schreibt `study.json`, `report.md` und Referenzdiagnostik in den
neuen Ordner. Die historischen Ergebnisdateien bleiben erhalten. Die
Grenzen einer Wiederholung der früheren Feature- und Decoderläufe sind
weiter unten unter „Frühere Gruppierungsexperimente“ dokumentiert.

## Spätere Qwen- und Astra-Auswertungen

Der spätere Vergleich mit Qwen3.8-27B liegt als gespeicherter API-Lauf in
`data/eval/runtime_thl_qwen3.8-27b_2026-09-24.json`. Die lokale Laufzeit
steht in `data/eval/runtime_local_2026-09-24.json`. Beide wurden mit
`scripts/benchmark_offer_runtime.py` auf der festen 42-Seiten-Liste
gemessen. Die F1-Werte und das gepaarte Intervall lassen sich ohne neue
API-Aufrufe nachrechnen:

```bash
.venv/bin/python scripts/score_runtime_offers.py \
  data/eval/runtime_thl_qwen3.8-27b_2026-09-24.json \
  --output /tmp/magda-qwen38-score.json
```

Der gespeicherte Score liegt in
`data/eval/runtime_thl_qwen3.8-27b_score_2026-09-24.json`.
Die ergänzende Sichtprüfung steht in
`reports/offer_output_visual_review_2026-09-24.md` und ist keine zweite
unabhängige Goldannotation.

Die Astra-Antworten stehen in `data/eval/codex_astra_2026-09-25.json`, die
Auswertung in `data/eval/codex_astra_score_2026-09-25.json`. Derselbe
Auswertungscode berechnet sie mit einem eigenen Systemnamen:

```bash
.venv/bin/python scripts/score_runtime_offers.py \
  data/eval/codex_astra_2026-09-25.json \
  --system-name astra_codex \
  --output /tmp/magda-astra-score.json
```

Beide Befehle gleichen die aktuelle menschliche Referenz mit der
gespeicherten Studie ab und verwenden Magdas dort gespeicherte Angebote.
Sie benötigen weder Modellgewichte noch API-Zugang. Die vollständigen
Ausgabe-JSONs lassen sich mit den jeweiligen gespeicherten Scores
vergleichen. Bei der Prüfung am 26.09.2026 waren Zähler, Scores und
Bootstrap-Ergebnisse identisch. Im älteren Qwen-Bericht fehlen lediglich
die später ergänzten Metadatenfelder `system` und `source_protocol`.

`scripts/codex_offer_benchmark.py` dokumentiert Vorbereitung und Sammlung
des Astra-Laufs. Protokoll, Eingabemanifest und Originalantworten liegen unter
`output/benchmarks/astra-codex-2026-09-25/`. Die dort ursprünglich kopierten
Eingabebilder liegen bytegleich unter `data/images/`; sie werden nicht doppelt
versioniert. Der lesbare Vergleich steht in
`reports/astra_codex_benchmark_2026-09-25.md` und wird aus den gespeicherten
Scores mit `scripts/summarize_astra_benchmark.py` erzeugt. Die zusätzliche
visuelle Prüfung verwendet
`data/audit/offer_output_review_2026-09-24.json` und
`scripts/review_offer_outputs.py`.

Neue API- oder Codex-Antworten wären ein neuer Versuch. Sie sind nicht
nötig, um die berichteten Scores nachzurechnen. Auch die gespeicherten
Laufzeitwerte gelten nur für den damaligen Aufbau. Ein neuer Zeitvergleich
wäre eine neue Messung und keine Wiederholung identischer Antworten.

## Technische Details zur Gruppierung

Abschnitt 4.3 erklärt die in der Feature-Tabelle benannten Blöcke Base, Geometry,
Lexical, Anchor und Colour. Das gespeicherte Studienartefakt nennt für den
finalen MLP die Blöcke `types`, `geometry_base`, `geometry_plus` und
`lexical`, zusammen 43 Merkmale. Anchor und Colour gehören zu zusätzlich
geprüften Varianten. Die Merkmale sind Eingaben für das lernende MLP,
keine festen Gruppierungsentscheidungen.

Die Vergleichsheuristik ist nicht rein geometrisch. Der bewertete Aufruf
`offers.cluster_page` nutzt standardmäßig `arithmetic=True`, auch in der
im Studienartefakt genannten Code-Revision. Beschreibungsfelder und
Preis-Badges werden zunächst separat räumlich gruppiert. Die Zuordnung
nutzt passende Menge-mal-Grundpreis-Werte, andernfalls räumliche Nähe.
Die Gruppierungstabelle nennt sie deshalb Rule-based und trennt die Methode von ihrer
Entity-Eingabe. Alle drei Zeilen nutzen menschlich annotierte Angebotsgruppen
als Bewertungsreferenz. Nur die ersten beiden erhalten zusätzlich die
menschlich annotierten Entities als Eingabe.

Abschnitt 4.4 erklärt die Decoder kurz. Die vollständige Umsetzung steht in
`src/magda/offer_pairs.py` und `src/magda/offer_ilp.py`. Das ILP maximiert
die Summe von `(logit(p_ij) - logit(threshold)) * x_ij` mit binären
Gruppenzuordnungen und den Transitivitätsbedingungen
`x_ij + x_jk - 1 <= x_ik` samt Permutationen. Die Scores werden vor der
Logit-Transformation begrenzt. Positive Verbindungen bilden die Komponenten,
innerhalb derer optimiert wird. Zu große Komponenten bleiben ungeteilt.
Es gibt weder eine feste Anzahl von Produkten oder Preisen pro Gruppe noch
eine arithmetische Preisbedingung als harte Nebenbedingung.

Der am 25.09.2026 geprüfte Checkpoint `checkpoints/offer_pairs/model.pt`
verwendet den ILP-Decoder und den auf Trainingsfolds kalibrierten Schwellenwert
0.68. Historische Decoderläufe haben eigene Schwellen und Komponentenlimits.
Die Quellen Tarjan (1975) und Grötschel und Wakabayashi (1989) belegen die
Grundverfahren, nicht unsere Modellgewichte oder die Kalibrierung.

## Technische Details zur Evaluation

Abschnitt 5.2 bündelt Entity-, Gruppen- und Record-Metriken. Die
Entity-Auswertung in `src/magda/semeval.py` verwendet `nervaluate 1.2.1`
mit einem Adapter für wortbasierte Überlappung. Die Studienauswertung
gleicht Strict zusätzlich gegen `seqeval` ab. Partial vergibt bei überlappenden, nicht identischen
Spans halbe Treffer, unabhängig von ihrem prozentualen Überlappungsumfang.
Die Gesamtmetriken werden aus summierten Zählern berechnet. Dadurch haben
häufige Entity-Typen mehr Gewicht, weshalb die Ergebnistabelle auch die
Anzahl der Referenzentities und Werte je Typ ausweist.

Die Paar- und Gruppenmetriken berücksichtigen die Zuordnung zur
Gruppierungsreferenz. Nicht zuordenbare Entities werden gesondert gezählt.
Bei vorhergesagten Entities verändert sich damit die Population der
bewertbaren Paare gegenüber der Bewertung mit Referenz-Entities.

Das Record-Protokoll heißt `offer-price-v2` und ist in
`src/magda/blackbox_eval.py` implementiert. Der Name kombiniert Marke und
Produktbeschreibung. `_similar()` vergleicht kleingeschriebene Namen mit
`SequenceMatcher` in beiden Richtungen und mittelt die Ergebnisse.
Eine mögliche Zuordnung erfordert einen Wert von mindestens 0.6 und einen
exakt gleichen regulären Preis. Maximales bipartites Matching bestimmt die
größte Zahl gültiger Zuordnungen ohne doppelte Verwendung eines Datensatzes.
Die Namensschwelle ist eine praktische Zeichenvergleichsregel, kein Test
semantischer Gleichwertigkeit. Der Wert 0.6 soll Unterschiede in der
Formulierung zulassen und wurde nicht als optimaler Wert kalibriert.
Ebenso sind Jaccard 0.95 für nahezu identische Seiten und 0.7 für breitere
regionale Vorlagengruppen heuristische Festlegungen, keine kalibrierten
Optima. Davon zu unterscheiden ist die oben beschriebene, auf
Trainingsfolds kalibrierte Schwelle des MLP-Decoders.

Menge, Grundpreis, Altpreis, App-Preis, Rabatt, Gültigkeit und sonstige
Kaufbedingungen sind keine Felder des Record-F1. Unvollständige Fragmente
ohne brauchbaren Namen oder regulären Preis werden auf beiden Seiten
ausgeschlossen und gesondert gezählt. Fehlgeschlagene externe Antworten
bleiben dagegen als leere Ausgaben für die betreffenden Seiten enthalten.

Abschnitt 5.3 erklärt das Bootstrap-Verfahren mit einem kleinen Beispiel.
Die Hauptauswertung verwendet `src/magda/resampling.py`: 10.000
Cluster-Resamples, Seed 42, gepaarte Perzentilintervalle. Cluster ähnlicher
regionaler Seiten entstehen im Testsplit mit Jaccard 0.7. Die ausgewählten
42 Seiten vertreten 42 Cluster, deshalb entspricht das Ziehen dieser
Vertreter hier dem Ziehen der Cluster. Dieselben Stichprobengewichte gelten
für beide Systeme. F1 wird aus den pro Resample summierten Treffer-,
Vorhersage- und Referenzzahlen berechnet, nicht aus gemittelten Seiten-F1.

Die Bonferroni-Korrektur gilt getrennt für vier NER-Kontraste und drei
ursprüngliche API-Vergleiche gegen Magda. Qwen3.8 und der spätere
Astra-Codex-Lauf verwenden dieselben Seiten, dieselbe menschliche Referenz,
`offer-price-v2` und das gleiche gepaarte Bootstrap-Verfahren. Ihre
explorativen Intervalle stehen außerhalb der ursprünglichen
Drei-System-Familie. Der Bootstrap hält Antworten und Referenz fest. Er
erfasst weder Label-Fehler oder alternative Angebotsdefinitionen noch
Trainingsvariation, neue API-Antworten oder den Einfluss des gemeinsamen
Gesprächskontexts im Codex-Lauf. Er garantiert auch keine Unabhängigkeit der
Vorlagen und keine Übertragbarkeit auf neue Händler.

## Frühere Gruppierungsexperimente

Der frühere Abschnitt 5.4 wurde aufgelöst. Seine Versuchsbedingungen stehen
bei den entsprechenden Ergebnissen, technische Einzelheiten bleiben hier.

- `data/eval/offers_grid_dev_ilp.json`: Featurevergleich mit 494
  Trainingsseiten und 56 Entwicklungsseiten in 25 Clustern. Referenz sind
  automatisch erzeugte Angebotsgruppen. Klassifikatorkonfiguration und
  ILP-Decoder bleiben fest, jedes Feature-Set wird neu trainiert und seine
  Schwelle auf Trainingsfolds kalibriert. Benannte Varianten ergänzen teils
  mehrere Blöcke und sind daher nicht durchweg Einzelblock-Ablationen.
- `data/eval/offers_grid_dev_cv_union-ilp.json`: früherer Decodervergleich
  mit einer geometriebasierten Konfiguration auf 75 Out-of-Fold-Seiten in
  68 Clustern. Union-Find und ILP werden separat kalibriert. Gemessen wird
  damit das jeweilige Verfahren samt Kalibrierung. Die vollständige
  historische Seitenliste fehlt. Aktuelle Splits rekonstruieren die frühere
  Population nicht zuverlässig.
- Beide Berichte verwenden die Bootstrap-Implementierung des
  Gruppierungsmoduls mit 1.000 Resamples. Die Intervalle sind explorativ
  und nicht für mehrere Vergleiche korrigiert. Gespeicherte
  `p_two_sided`-Werte schätzen einen verdoppelten Anteil der Differenzen im
  gegenüberliegenden Vorzeichenbereich. Null bedeutet lediglich, dass in
  den Resamples kein entsprechender Vorzeichenwechsel beobachtet wurde.
  Es ist keine exakte Nullwahrscheinlichkeit und kein bestätigter Befund.
- Die Strata `blind` und `checkable` richten sich nach dem Vorhandensein
  eines UNIT_PRICE-Labels in den Referenzgruppen. Bei Paaren betrifft dies
  die zugehörigen Referenzgruppen, bei Gruppen deren eigene Referenz.
  Die Namen beschreiben eine potenziell verfügbare Information. Sie
  garantieren weder passende Mengen und Einheiten noch eine erfolgreiche
  arithmetische Prüfung und bezeichnen keine räumlichen Seitenbereiche.

Die mittleren historischen Decoderschwellen betragen 0.956 für Union-Find
und 0.868 für ILP. Beide Verfahren wurden für Exact Group F1 kalibriert.
Der gespeicherte ILP-Lauf zählt 1.611 Komponenten am Größenlimit über den
gesamten Lauf einschließlich Kalibrierung. Daraus lässt sich keine
Fallback-Rate allein für die finale Bewertung ableiten.

## Darstellung der Ergebnisse

Kapitel 6 bündelt die Ergebnisse in vier Abschnitten: Entity Recognition,
Gruppierung und Komponentenversuche, Gesamtpipeline und Modellvergleich,
Fehleranalyse. Die zusätzliche Ergebnisgrafik und die Grafik nach
Grundpreisverfügbarkeit entfallen im Manuskript. Die vollständigen Strict-F1-Werte
pro Entity-Typ aus `generated/labels.tex` stehen in Abschnitt 6.1 direkt nach
dem Gesamtvergleich. Die Spalte `Reference spans` zählt die menschlich
annotierten Entities des jeweiligen Typs. Die Decoder-Tabelle und die
aggregierten Fehlerkategorien werden weiterhin nach `generated/decoder.tex`
und `generated/errors.tex` exportiert und bleiben in den Eingabe-JSONs erhalten.

`generated/offers_all.tex` enthält die ursprünglichen API-Läufe und die
ergänzenden Qwen3.8- und Astra-Läufe als getrennte Blöcke. Der Export liest
die gespeicherten Auswertungen, prüft ihre Studien-Fingerabdrücke, das
Bewertungsprotokoll, Seiten- und Referenzzahl sowie Magdas Vergleichszähler.
Es werden keine Antworten neu erzeugt oder Referenzen verändert. Die
zusätzlichen Eingabedateien stehen in `generated/sources.json`.

Die Beispieltabelle ist anhand folgender gespeicherter Belege verfasst:

- `study.json`, `error_analysis.layoutxlm.cases`, Seite `1364390_p1`,
  Wortindizes 23 und 24: getrennte QUANTITY-Referenzspans für „500“ und „g“,
  überlappende Vorhersage `[23, 25)` für „500 g“.
- `reports/offer_output_visual_review_2026-09-24.md`, Seite
  `1364390_p22`: Magdas Philadelphia-Record mit 3.49 statt 2.29.
- Derselbe Bericht, Seite `1364390_p21`: Qwen-Ausgaben 09 und 10
  wiederholen „Tempo Taschentücher“ zum Preis 2.99.
- Referenzaudit der Hauptstudie, Seite `1364390_p3`, Wort 229:
  regulärer Preis „2.69“ nach „ohne PENNY App“ als OLD_PRICE annotiert.

Die visuelle Einzelprüfung stammt von Codex. Sie ist keine unabhängige
menschliche Nachannotation und liefert keine zusätzliche Genauigkeitsquote.

## Inhaltliche Grundlage

Im Fließtext werden keine Semikolons und keine Gedankenstriche verwendet.
Gedanken werden mit natürlichen Sätzen, Punkten und Kommas verbunden.
Das gilt auch für Abstract und Bildunterschriften. Bindestriche in
Modellnamen, mathematische Minuszeichen und technische Syntax bleiben erhalten.

Zielumfang sind 13 bis 14 Seiten einschließlich Literatur und Anhang.
Die Seitenzahl nach einem Build lässt sich mit folgendem Befehl prüfen:

```bash
pdfinfo output/pdf/Magda_Project_Report_EN.pdf
```

Das Kapitel „Background and Related Work“ verbindet die Originalarbeiten
mit ausgewählten Vorlesungsinhalten. Der BibTeX-Eintrag `iecourse2026`
fasst die bereitgestellten Foliensätze zusammen. Verweise nennen die Woche
im Satz oder im Zitat sowie die PDF-Seite. Da die Unterlagen keine
vollständigen Autorennamen nennen, verwendet der Eintrag den neutralen
Zitierschlüssel „IE course“. Die Folien müssen für den Build nicht vorliegen.

Die englische Ausgangsfassung wurde neu gegliedert, sprachlich überarbeitet
und gegen Abschlussauswertung, Implementierung und Originalpublikationen
geprüft. Historische Messungen bleiben von der Hauptauswertung getrennt.
Die berichteten Einschränkungen stehen im Limitations-Kapitel des Berichts.
