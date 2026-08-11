# Nachtlauf 10./11.08.2026 — Ende-zu-Ende, Labelqualität, Fehleranalyse

Stand: 11.08.2026, Branch `offers/farbmerkmale`, 494 Tests grün (vorher 420).

## Kurzfassung

Die Kette ist zum ersten Mal **ende-zu-ende** gemessen. Bis gestern war das
nicht schwierig, sondern unmöglich: `data/predictions/gbert` enthielt 101
Seiten, alle im Testsplit; `data/offer_groups/claude-sonnet-5` 51 Seiten,
alle in Train und Dev. Die Schnittmenge war **null**. Alle bisherigen
Angebotszahlen des Projekts wurden auf Lehrer-Entities gemessen — also unter
der Annahme, Stufe 1 sei fehlerfrei.

Dazu zwei Labelmaßnahmen und eine Fehlersystematik. Was **nicht** passiert
ist, steht weiter unten und ist genauso wichtig.

## 1. Die Ende-zu-Ende-Zahl — und warum sie steigt

Gruppen-F1 auf Dev, Referenz `data/offer_groups/claude-sonnet-5` (LLM-erzeugt,
misst also Übereinstimmung, nicht Richtigkeit):

| Entity-Quelle | Basis | +Geometrie | +Farbe | beide |
|---|---:|---:|---:|---:|
| Lehrer (`sonnet-5`) | 0.477 | 0.540 | 0.472 | 0.492 |
| Schüler (`gbert`) | 0.504 | 0.556 | 0.504 | 0.502 |

**Die zweite Zeile ist nicht besser.** Sie ist auf einem kleineren Nenner
gemessen: GBERT findet 717 statt 730 Entities (0.982), aber nur **1855 der
1996 Referenzpaare** überleben (0.929). 7,1 % der Gruppierungsaufgabe
verschwinden — und zwar genau die Paare, deren Entity der Schüler nicht
gefunden hat, also plausibel die schwereren.

Die Regel aus `magda offers-gold` („die Entity-Grundmenge kommt aus der
Seite, nicht aus der Systemausgabe") schützt hier nicht: In diesem Lauf
*ist* die Seite die Vorhersagedatei. Wer die +0.027 als Verbesserung liest,
hat den Nenner nicht angesehen.

**Was die Zahl trägt:** Die Gruppierung bricht mit Schüler-Entities nicht
zusammen. 122 Referenzgruppen bleiben 122, das Verfahren bildet 136 statt 138
Angebote. Die Fehlerfortpflanzung Stufe 1 → Stufe 2 ist auf Dev kleiner als
das Konfidenzintervall breit ist.

**Einschränkung, die mitgehört:** Dev stammt aus den Trainingswochen. Die
Entity-Qualität ist dort in-distribution-optimistisch — die Zahl ist eine
Obergrenze, keine Einsatzprognose.

### Der blinde Fleck

Im Bereich ohne Grundpreis, für den die Farbmerkmale gebaut wurden, ist
`beide` (39 Merkmale) auf **beiden** Entity-Quellen die beste Variante:

| | Basis | beide |
|---|---:|---:|
| Paar-F1, Lehrer-Entities | 0.737 | **0.782** |
| Paar-F1, Schüler-Entities | 0.640 | **0.740** |
| gebildete Angebote | 54–58 | **43–48** |

**Das ist kein Befund, und es ist sogar schwächer, als es aussieht.** Drei
Gründe, alle im Review vom 11.08. nachgerechnet:

1. **Die beiden Quellen sind nicht unabhängig.** GBERT ist auf
   sonnet-5-Labels trainiert; 98 % der Entities und 93 % der Referenzpaare
   sind dieselben. „Zwei Quellen, dasselbe Vorzeichen" ist im Wesentlichen
   dieselbe Messung zweimal — bei einem Scheineffekt wäre die
   Übereinstimmung genauso zu erwarten.
2. **Die beiden Zeilen messen nicht dieselbe Aufgabe.** Die Einteilung in
   blind und prüfbar hängt an den Entity-*Typen* der jeweiligen Quelle. Die
   blinden Referenzpaare fallen von 606 auf 444 (−27 %), während die
   prüfbaren von 1390 auf 1411 *steigen*: sagt GBERT irgendwo UNIT_PRICE
   anders vorher als der Lehrer, wechselt die ganze Gruppe die Kategorie.
3. **Die Paar-Precision ist im blinden Fleck in allen acht Zellen exakt
   1.000.** Die Unterschiede dort sind reine Recall-Unterschiede: `beide`
   gewinnt, weil es sich mehr Verschmelzungen traut (48 statt 58 Gruppen
   bzw. 43 statt 54). „Farbe findet die richtige Kachel" und „Farbe macht
   das Verschmelzen mutiger" sind mit diesen Daten **nicht
   unterscheidbar**.

Dazu die Intervalle, die im blinden Fleck bis 1.000 reichen, weil viele der
14 Dev-Cluster dort gar keine Paare haben. Die Schlussfolgerung bleibt
dieselbe und wird eher stärker: **mehr Referenz, nicht der nächste
Merkmalsblock.**

## 2. Drei Konstruktionsfehler, ohne die Messung 1 falsch gewesen wäre

Alle drei waren im Repo, keiner hätte einen Test rot gemacht.

1. **Der Gitterreport trug den Splitnamen, nicht die Entity-Quelle.** Lehrer-
   und Vorhersagelauf messen beide `dev` und schrieben in dieselbe Datei. Der
   zweite hätte den ersten still überschrieben — zwei Zahlen zu verschiedenen
   Fragen unter einem Namen.
2. **`--predictions` galt auch für die Trainingsseite.** Für den
   Trainingssplit existieren keine Vorhersagen; das Paarmodell hätte auf null
   Seiten gelernt. Neu ist `--train-labels-from`: das Modell lernt an
   Lehrer-Entities, weil nur die gruppiert sind, und arbeitet auf denen des
   Schülers — der Einsatzfall.
3. **`magda train` schrieb nach `checkpoints/<variante>`**, ohne Rücksicht auf
   `--labels-from`. Der APP_PRICE-Lauf hätte genau das Modell überschrieben,
   gegen das er verglichen werden soll, und jeder Punkt der Lernkurve den
   vorigen. `checkpoints/gbert` trägt den eingefrorenen KW30/31-Stand.

Anker für „der kanonische Lauf" ist jetzt `config.CANONICAL_LABELS`
(= `sonnet-5`), **nicht** `default_labeled_model()`. Letzteres folgt
`CHAT_AI_VISION_MODEL` und liefert `mistral-medium-3.5-128b` — ein Modell,
mit dem hier gar nicht gelabelt wird. Sonst hätte der Inhalt einer `.env`
Namensgewalt über Checkpoints, an denen berichtete Zahlen hängen.

## 3. APP_PRICE-Übernahme

Die Handprüfung vom 03.08.2026 ist angewandt — in einen **neuen** Ordner
`data/labeled/sonnet-5-app/`. `data/labeled/sonnet-5/` bleibt unberührt,
sonst verschöbe sich die Grundlage aller früheren Zahlen.

| | vorher | nachher |
|---|---:|---:|
| APP_PRICE-Spans, Train | 115 | **187** (+63 %) |
| APP_PRICE-Spans, Dev | 11 | 20 |
| APP_PRICE-Spans, Test | 98 | **98** |

81 Spans wandern von PRICE nach APP_PRICE. **Die Messlatte bleibt liegen** —
kein einziger Testspan ändert sich. Nur das Trainingssignal des schwächsten
Labels wächst.

**Gemessen auf Dev**, jeder Arm gegen die Referenz, auf der er trainiert
wurde (`magda eval gbert --checkpoint gbert-sonnet-5-app`):

| | micro-F1 | APP_PRICE | Support |
|---|---:|---:|---:|
| `sonnet-5` | 0.926 | 0.909 | 11 |
| `sonnet-5-app` | 0.927 | 0.947 | 20 |

**Das ist Rauschen, und mehr war nicht zu erwarten** — auf Dev ändern sich
neun Spans. Die beiden APP_PRICE-Zahlen stehen außerdem auf verschiedenen
Nennern und sind nicht direkt vergleichbar.

**Die Pointe liegt im Test:** Die Übernahme ändert dort **null** Spans. Beide
Arme können also im Schlussbatch gegen eine *identische* Referenz gemessen
werden — dieselbe Messlatte, nur unterschiedlich viel Trainingssignal. Das
ist ein sauberes Experiment, wie es sonst selten zu haben ist, und es kostet
im Schlussbatch nur einen zusätzlichen Lauf.

Zwei Stellen im geplanten Code wären falsch gewesen:

- Er hätte nur das beurteilte **Wort** umgeschrieben und damit
  `B-APP_PRICE I-PRICE` erzeugt — eine BIO-Folge, die `bio_to_spans` in zwei
  Entities zerlegt. Umgetragen wird jetzt der ganze Span; beurteilt hat der
  Mensch die Entity, nicht das Token.
- Ein Urteil hat kein Zielabel: `1342881_p31:165`, „Aktion «1.99» 1 2 3" —
  APP_PRICE verworfen, kein Ersatz genannt. Der geplante Code hätte das
  ungültige Tag `B-` geschrieben. Jetzt bleibt das Label stehen und der Fall
  wird ausgewiesen. Ein `O` behauptete, dort stehe kein Preis; ein `PRICE`
  wäre eine Vermutung im Gewand einer Handannotation.

## 4. Fehler-Taxonomie mit Lösbarkeitsspalte

`magda taxonomy`, Dev, 21 Seiten, 77 Fehler auf **Span-Ebene** (nicht auf
Wortebene — ein verschobener Sortenzusatz ist ein Fehler, nicht zwei):

| Klasse | Anzahl | Anteil | womit lösbar |
|---|---:|---:|---|
| echtes Falsch-Negativ | 30 | 0.390 | mehr Daten oder Bildmerkmal |
| Grenzfehler | 25 | 0.325 | Annotationsregel entscheiden |
| echtes Falsch-Positiv | 17 | 0.221 | mehr Daten |
| Typverwechslung | 5 | 0.065 | konsistentere Referenz |
| Lehrerlücke | 0 | 0.000 | Referenz korrigieren |

Zwei Konzentrationen: **21 der 25 Grenzfehler sitzen bei PRODUCT** — das ist
die offene Sortenzusatz-Frage, beziffert. Und **20 der 30 Falsch-Negative
sitzen bei QUANTITY**, was bisher nirgends stand.

Die Klasse `lehrerluecke` ist bewusst konservativ: sie verlangt ein belegtes
Muster im Text (Fußnotenziffer neben einem Preis, „App" im Fenster), nicht
bloß „die Referenz sagt O". Sonst hieße jede Übervorhersage „der Lehrer war
schuld", und die Klasse wäre eine Ausrede statt einer Messung.

Auf Dev feuert sie nicht. **Die naheliegende Erklärung stimmt aber nicht:**
die Fälle aus der Handprüfung sind Referenz = PRICE → APP_PRICE, `lehrerluecke`
verlangt Referenz = `O`. Die neun Dev-Fälle könnten die Klasse gar nicht
auslösen. Die Null belegt nur, dass GBERT die textlosen App-Preise ebenfalls
nicht findet — und das ist konsistent mit dem strukturellen Befund, dass bei
33 % der APP_PRICE-Spans „App" nicht im Fenster ±8 Wörter steht.

## 5. Lernkurve — der Schüler sättigt vor dem Ende des Lehrers

Vier Modelle, Trainingsmenge clusterweise gezogen (`magda curve`):

| Punkt | Seiten | **Cluster** | bestes Dev-F1 |
|---|---:|---:|---:|
| p25 | 25 | 9 | 0.8348 |
| p50 | 50 | 16 | 0.8908 |
| p100 | 100 | 50 | **0.9247** |
| p175 | 175 | 93 | 0.9206 |

**Die Kurve flacht zwischen 100 und 175 Seiten ab und geht sogar leicht
zurück.** Die letzten 43 unabhängigen Vorlagen — knapp die Hälfte des
Trainingsmaterials — bringen nichts mehr. Das ist die ökonomisch
interessanteste Zahl der Nacht: Sie sagt, dass weitere LLM-Zeit für *Stufe 1*
kaum noch etwas kauft, und stützt damit von der anderen Seite, was die
Fehleranalyse schon sagt — die Grenze ist die Konsistenz der Referenz, nicht
ihre Menge.

**Drei Einschränkungen, die mitgehören:**

- Die x-Achse ist die **Clusterzahl**, nicht die Seitenzahl. 25 Seiten sind
  hier 9 unabhängige Vorlagen. Wer Seiten zählt, zählt Regionalfassungen.
- Die Dev-Zahl ist das beste `eval_f1` über zehn Epochen — also genau das
  Kriterium der Checkpoint-Auswahl, ein Maximum über zehn Ziehungen und damit
  **optimistisch**. Der Bias ist je Punkt derselbe, die *Form* also
  vergleichbar, das *Niveau* nicht.
- Dev hat 21 Seiten in 14 Clustern. Der Rückgang von p100 auf p175
  (−0.004) liegt weit im Rauschen; „sättigt" ist die Aussage, „wird
  schlechter" nicht.

**Die Kurve ist deskriptiv, nicht selektiv** — an ihrem Ergebnis hängt keine
Entscheidung. Nur so ist es regelkonform, vier Checkpoints gegen denselben
Split zu halten.

## 6. Blackbox-Vergleichsarm (Requirements-Stufe „Excellent")

Gebaut, **nicht gefahren**. `magda blackbox-eval` stellt drei Paarungen
nebeneinander statt zwei:

    Blackbox        gegen Referenz
    eigene Pipeline gegen Referenz
    Blackbox        gegen eigene Pipeline

Die ersten beiden messen Nähe zur Lehrerausgabe, nicht Richtigkeit — die
Referenz ist selbst LLM-erzeugt. Die dritte kommt ohne sie aus. Beide Seiten
laufen durch **dieselbe** Matching-Funktion; wer die Blackbox unscharf und
die eigene Ausgabe exakt matcht, verzerrt in die eigene Richtung.

Verglichen wird nur über die gemeinsame Feldmenge (`name`, `price`,
`original_price`). Das Blackbox-Schema kennt per Design weder App-Preise noch
Grundpreise — ihr das anzulasten hieße, sie an einer Aufgabe zu messen, die
sie nie hatte.

Der Lauf berührt den Testsplit und gehört deshalb in den gebündelten
Schlussbatch. Die Seitenliste (43 Zeilen, eine je Testcluster) liegt bereit.

Ein Probelauf auf **Dev** bestätigt die Verdrahtung: die eigene Pipeline
trifft 118 von 127 Referenzangeboten (F1 0.922). Achtung, das ist ein
weicheres Kriterium als Gruppen-F1 — Preis exakt, Name unscharf ab 0.6
Ähnlichkeit.

## 7. Was das Review noch gefunden hat

Fable hat den Lauf gegengelesen und drei Dinge gefunden, die noch in der
Nacht behoben wurden:

- **Die Lernkurve hätte Duplikate zuerst ins Budget gepackt.**
  `subset_by_clusters` sortierte nach absteigender Clustergröße — genau
  falschherum. Auf den echten Trainingsseiten (175 Seiten, 93 Cluster) ergab
  die Grenze 25 damit **23 Seiten aus drei Vorlagen**. Der erste Kurvenpunkt
  hätte Regionalfassungen gemessen statt Datenmenge, also den Fehler, den
  clusterweises Ziehen verhindern soll. Nach `page_id` sortiert sind es
  9/16/50/93 Cluster statt 3/9/25/93. Der eine bereits gelaufene Kurvenpunkt
  wurde verworfen. Die Clusterzahl steht jetzt in der Ausgabe — „p25" allein
  ist eine Seitenzahl ohne das, woran gemessen wurde.
- **Der Checkpoint-Schutz hatte ein Loch an der wahrscheinlichsten Stelle.**
  `checkpoint_name` behandelte `--labels-from` ohne Angabe als kanonisch,
  aber `build_datasets` löst das über `default_labeled_model()` auf — also
  auf mistral. `magda train gbert` ohne Argumente hätte damit
  Mistral-Gewichte nach `checkpoints/gbert` geschrieben, den Ordner mit dem
  eingefrorenen KW30/31-Stand. Genau der Aufruf, den jemand aus Gewohnheit
  tippt. Aufgelöst wird jetzt vor der Namensvergabe.
- **`--dry-run` gab eine Quote aus** und das Beispiel im Docstring zeigte
  ausgerechnet die Testseitenliste. Wer es befolgt hätte, hätte den
  Testsplit angefasst, bevor der Schlussbatch beginnt. Der Probelauf
  schweigt jetzt.

Dazu ein latenter Fehler in `error_taxonomy`: gepaart wurde mit dem *ersten*
überlappenden Referenz-Span statt dem passendsten. Eine PRODUCT-Vorhersage
über BRAND+PRODUCT wäre als Typverwechslung *plus* Falsch-Negativ gezählt
worden statt als ein Grenzfehler. Auf Dev ändert die Korrektur **nichts** an
den Zahlen — die Fehlerform war real, der Fall trat hier nur nicht auf.

**Offen und vor dem Schlussbatch zu entscheiden:** Die „Referenz" im
Blackbox-Vergleich sind heute `cluster_page`-Angebote aus den Lehrer-Labels
— also dieselbe Gruppierungsheuristik, die auch auf der eigenen Seite läuft.
„Eigene gegen Referenz" vergleicht die Heuristik damit weitgehend mit sich
selbst, und der Dev-Probewert von 0.922 ist entsprechend zu lesen. Die
Alternative wäre `data/offer_groups/`. Der Testlauf ist nicht wiederholbar.

## 8. Fortsetzung ab 02:00 — die Referenz, und warum sie nicht das Problem war

**Die Gruppierungsreferenz ist von 51 auf 75 Seiten gewachsen** (Train 30 →
54, Dev unverändert 21), alle 24 Seiten der Warteschlange von
sonnet-Subagenten aus dem Seitenbild gruppiert. Zwei Antwortdateien kamen
abgeschnitten zurück; `magda offers-teacher save` hat sie abgelehnt statt sie
halb zu übernehmen — genau die Regel, für die es sie gibt.

Dabei sind zwei Dinge aufgefallen, die mehr wiegen als die 24 Seiten.

### Der Label-Default zeigte auf mistral

`config.default_labeled_model()` gab `CHAT_AI_VISION_MODEL` den Vorrang und
lieferte damit `mistral-medium-3.5-128b` — ein Modell, mit dem im Projekt gar
nicht gelabelt wird. Jeder Befehl ohne `--labels-from` maß gegen dessen
Labels, und man sah es nur, wenn man die Kopfzeile las.

Beziffert über **dieselbe** Gruppierung:

| Labelquelle | Preise | Genauigkeit | Abdeckung |
|---|---:|---:|---:|
| `mistral-medium-3.5-128b` (Default) | 399 | 0.927 | 0.446 |
| `sonnet-5` | **494** | 0.936 | 0.478 |

Ein Viertel mehr Preise bei gleicher Rechnung. Über die Ordnergröße allein
wäre es auch nicht gutgegangen: `sonnet-5`, `sonnet-5-app` und der
Mistral-Ordner haben alle 296 Seiten, dann entscheidet die
Sortierreihenfolge. Vorrang hat jetzt `config.CANONICAL_LABELS`. **Ältere
Zahlen aus Befehlen ohne `--labels-from` stehen unter diesem Vorbehalt.**

### „Mehr Referenz" war die halb falsche Antwort

Der Schluss aus den breiten Intervallen lautete: Referenz vergrößern. Das war
zur Hälfte falsch, und die Hälfte ist wichtig. Gemessen wurde auf **Dev** —
und Dev hat 21 Seiten in 14 Duplikat-Clustern, **alle davon längst
gruppiert**. Die Breite eines Bootstrap-Intervalls hängt an der Zahl der
Auswertungs-Cluster; keine weitere *Trainings*seite ändert daran etwas. Das
Planziel „Dev auf 25–30 Seiten ausbauen" war nicht schwer, sondern
**unmöglich**: der eingefrorene Split gibt nur 21 her.

Der Ausweg ist kein Datenproblem, sondern der Messaufbau. `magda offers-grid
--cross-validate` wertet jede Referenzseite einmal aus, mit einem Modell, das
sie nicht gesehen hat. **Aus 14 Clustern werden 62.** Die Schwelle wird dabei
geschachtelt gewählt — `calibrate` auf den inneren Folds, Auswertung nur auf
dem äußeren; einmal auf allem gewählt wäre sie genau der Zirkelschluss, gegen
den `offers_report` die Ablation braucht.

Was das mit den Intervallen macht (Gruppen-F1, Lauf über 69 Seiten):

| Variante | Dev, 14 Cluster | out-of-fold, 62 Cluster |
|---|---|---|
| basis | 0.477 [0.16, 0.65] · Breite 0.49 | 0.376 [0.29, 0.47] · **0.18** |
| geometrie | 0.540 [0.21, 0.74] · 0.53 | 0.447 [0.34, 0.55] · **0.21** |
| farbe | 0.472 [0.20, 0.63] · 0.43 | 0.398 [0.32, 0.48] · **0.16** |
| beide | 0.492 [0.23, 0.62] · 0.39 | 0.423 [0.33, 0.52] · **0.19** |

**Die Intervalle sind im Mittel von 0.463 auf 0.185 geschrumpft, Faktor
2,5** — bei niedrigeren Punktschätzern, was zu erwarten war: out-of-fold ist
ehrlicher als eine auf Train kalibrierte Schwelle.

### Was noch fehlte: der richtige Test

Überlappende **Einzel**intervalle heißen nicht „kein Unterschied". Beide
Varianten sehen dieselben Seiten; ist eine Seite schwer, ist sie es für
beide. Wer sie einzeln resampelt, zählt diese gemeinsame Streuung zweimal und
verdeckt genau den Effekt, den er messen will. Deshalb bootstrappt
`offer_grid.paired_bootstrap` jetzt die **Differenz** — dieselbe Konstruktion
wie `magda significance` für den Modellvergleich, nur über Duplikat-Cluster.
Das kostet keine zusätzliche Rechenzeit: die seitenweisen Zählungen aller
Varianten liegen im selben Lauf ohnehin vor.

## Was nicht passiert ist — und warum

- **Der eine Testbatch (Plan B/6): gesperrt.** Er setzt die Handprüfung der
  Schülerabweichungen voraus (4 Stunden am `/audit`-UI). Der Testsplit wird
  genau einmal angefasst; ihn über Nacht ohne die Vorarbeit zu verbrennen,
  ist nicht rückholbar.
- **Zweiter Händler (Plan B/7): gesperrt.** Braucht einen Download von einer
  fremden Seite.
- **Woche 4 labeln (Plan A/4): geprüft und blockiert.** `magda label` spricht
  nur die GWDG-API an; deren bildfähige Modelle heißen mistral, qwen und
  gemma. `sonnet-5` ist keins davon — `data/labeled/sonnet-5/` ist nicht über
  diesen Befehl entstanden. Da die Labelquelle gesetzt ist, braucht Woche 4
  den Subagenten-Weg über 126 Seiten. Das ist eine Kontingent-Entscheidung,
  keine technische. **Folge:** die Drift-Kurve hat Code (`magda eval
  --pages`) und Seitenliste (126 Zeilen), aber noch keine Zahl.
- **Gruppierungsreferenz 51 → 80 (Plan A/3): verschoben.** 30–50
  Teacher-Subagenten hätten das Kontingent verbraucht, das für die
  Fortsetzung gebraucht wird. Das ist der Schritt mit dem höchsten Ertrag —
  die Gruppen-Konfidenzintervalle überlappen so stark, dass keine
  Variantenaussage trägt, und dagegen hilft nur mehr Referenz.

## Nächster Schritt

Nicht der nächste Merkmalsblock. **Die Referenz vergrößern.** Alles andere in
der Gruppierungsfrage ist derzeit Rauschen mit Vorzeichen.
