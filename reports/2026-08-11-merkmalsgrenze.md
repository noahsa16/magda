# 11.08.2026 — Die Merkmalsgrenze des Paarmodells

Stand: 11.08.2026. Branch `offers/farbmerkmale`.

Schließt an `reports/nachtlauf-2026-08-10.md` an. Dort steht der
ILP-Dekoder-Befund; hier beginnt es bei der Frage, die er offen ließ — welche
Gruppen eigentlich kaputtgehen.

## Kurzfassung

Der Tag hatte ein Ziel — den größten Fehlerblock der Gruppierung schließen —
und endet mit einem Negativbefund, der mehr wert ist als das Ziel: **Von vier
gemessenen Merkmalsblöcken wirkt genau einer.** Die drei Fehlschläge zielten
alle auf dieselbe Lücke und trafen sie nicht. Damit ist Merkmals-Engineering
am Paarmodell ausgereizt, und die verbleibenden Hebel sind mehr Referenz oder
eine andere Aufgabenstellung.

Nebenher wurde eine berichtete Zahl auf ein Drittel korrigiert, eine falsche
Behauptung zurückgenommen und zwei Tests repariert, die nichts geschützt haben.

| | |
|---|---|
| Commits (`9270074`…`f697311`) | 6 |
| Tests | 533 → **549** |
| Platte freigeräumt | **11 GB** (15 → 26 GB frei) |
| Rechenzeit für Messläufe | ~2,5 h |

## 1. Die Variantenblöcke — eine Zahl auf ein Drittel korrigiert

Am 10.08. war berichtet worden: 19 Variantenblöcke tragen 54 % der
Gruppierungsfehler, Recall **0.263** gegen 0.883 sonst. Ein Variantenblock ist
eine Referenzgruppe mit mehr als einem PRICE oder mehr als einer QUANTITY —
`Pfanne: 20 cm 9.99 / 24 cm 14.99 / 28 cm 17.99`.

Die Zahl hatte zwei Mängel, die zusammen ihre Größenordnung erklären: sie war
**auf Dev gemessen** und stammte von einem **Checkpoint, der diese Seiten im
Training hatte**. Dazu kam ein Verstoß gegen die eigene Projektregel: sie stand
nur in einer Notiz, erzeugt von einem Wegwerf-Skript. Gebaut ist jetzt
`magda offers-model variants`.

Out-of-fold über Train+Dev, 75 Seiten, **573 Referenzgruppen, davon 95
Variantenblöcke**:

| Dekoder / Merkmale | alle | ohne Variantenblöcke | Variantenblöcke | Faktor |
|---|---:|---:|---:|---:|
| *Dev, Checkpoint (die alte Zahl)* | *0.656* | *0.738* | *0.211* | *3.4* |
| Union-Find, Basis | 0.417 | 0.425 | 0.379 | 1.12 |
| ILP, Basis | 0.525 | 0.546 | 0.421 | 1.30 |
| ILP, +Geometrie | 0.574 | **0.605** | **0.421** | **1.44** |

**Der Effekt ist real, aber ein Drittel so groß wie berichtet.** Dasselbe
Muster wie bei den Farbmerkmalen: ein Dev-Eindruck über 19 Einheiten hält der
Kreuzvalidierung über 95 nicht stand. Wer die 0.263 weiter zitiert, zitiert
eine In-sample-Zahl.

## 2. Welche Kante ausfällt — und die Kontrolle, die es entscheidet

Mittlere Modellwahrscheinlichkeit auf *zusammengehörigen* Paaren, ILP,
out-of-fold, Basis-Merkmale:

| Typpaar | in Variantenblöcken | sonst | Differenz |
|---|---:|---:|---:|
| **PRICE\|PRICE** | **0.639** (n=172) | – | *nur hier möglich* |
| **QUANTITY\|QUANTITY** | **0.868** (n=123) | – | *nur hier möglich* |
| PRODUCT\|PRODUCT | 0.814 | 0.962 | −0.149 |
| PRICE\|PRODUCT | 0.782 | 0.882 | −0.100 |
| QUANTITY\|UNIT_PRICE | 0.894 | 0.985 | −0.090 |
| BRAND\|PRODUCT | 0.959 | 0.991 | −0.031 |

**`QUANTITY|QUANTITY` ist die Kontrolle, und sie trägt den ganzen Befund.**
Beide Kantenarten existieren *nur* in Variantenblöcken, beide verbinden
gleichartige Entities derselben großen Gruppe (8.74 Entities gegen 5.03 sonst).
Wäre die Gruppengröße die Ursache, müssten beide gleich leiden. Tatsächlich
liegt die Mengenkante bei 0.868, die Preiskante bei 0.639.

Das Modell findet also **mehrere Größenangaben eines Blocks zusammen, mehrere
Preise nicht**. Die Erklärung steht seit Woche 1 im Projektwissen: Penny setzt
Mengen untereinander in den Fließtext und jeden Preis in einen eigenen gelben
Kasten. Für zwei Preise sagt die Geometrie „getrennt", und global hat sie damit
fast immer recht — zwei Preise sind fast immer zwei Angebote.

**Nebenbefund für alle künftigen Kantendiagnosen: die mittlere
Wahrscheinlichkeit lesen, nicht den Recall.** Im Union-Find-Lauf sah
`PRICE|PRICE` unauffällig aus, weil die Schwelle 0.94 so hoch abschneidet, dass
alle Kanten gleichmäßig durchfallen und die Rangfolge verschwindet. Erst bei
der tieferen ILP-Schwelle (0.80–0.88) wird sichtbar, welche Kante das Modell
wirklich schwach bewertet. Der Recall ist eine Aussage über die Schwelle.

## 3. Die Kontextmerkmale wirken an der Lücke vorbei

Derselbe Lauf mit 35 statt 30 Merkmalen:

| Merkmale | alle | ohne Variantenblöcke | Variantenblöcke |
|---|---:|---:|---:|
| Basis (30) | 0.525 | 0.546 | 40/95 = 0.421 |
| +Geometrie (35) | 0.574 | **0.605** | 40/95 = 0.421 |
| Differenz | +0.049 | **+0.059** | **±0.000** |

Der einzige Merkmalsblock mit belegtem Effekt (+0.044, p = 0.018) hebt alles
außer den Variantenblöcken. Die Preiskante bewegt sich um **+0.001**
(0.639 → 0.639), während `QUANTITY|QUANTITY` +0.016 gewinnt.

*Einschränkung: gleiche Anzahl Treffer (40 von 95) heißt nicht zwingend
dieselben Gruppen — der Report hielt zunächst nur Summen fest. Er schreibt die
getroffenen Gruppen jetzt einzeln mit, damit die Frage künftig beantwortbar
ist. Die Aussage hängt nicht daran: die +0.001 auf der Kante genügen.*

Das folgt aus der Bauart der Merkmale: `products_between`, `closer_rivals` und
`distance_ratio` sind **Trennmerkmale** — sie beantworten „steht etwas
dazwischen" und „gibt es einen näheren Kandidaten". Ein Variantenblock braucht
das Gegenteil: eine Verbindung *trotz* Distanz und *trotz* näherer Konkurrenz.

**Die Lücke wächst dadurch**, von Faktor 1.30 auf 1.44. Je besser das Modell im
Normalfall wird, desto deutlicher fallen Variantenblöcke heraus.

## 4. Das Ankermerkmal — gebaut, gemessen, durchgefallen

Aus dem Befund folgte ein Merkmal, das die Sternform eines Angebots trifft:
**zeigen beide Entities auf denselben nächsten Produktanker?** Eine
Anker-Entity ist ihr eigener Anker, dadurch deckt `shared_anchor` beide
Relationen ab — die Speiche (Produkt↔Preis) und die Geschwisterkante
(Preis↔Preis). Dazu zwei Abstände als Sicherheitsmaß. Weder Text noch
Arithmetik, damit der Richter unbeteiligt bleibt.

**Das Akzeptanzkriterium stand vor dem Lauf fest**, im Repo festgeschrieben:
Variantenblock-Treffer müssen steigen *und* die Gesamtzahl darf nicht fallen.
Erwartet wurden bei vollem Erfolg 95/573 × (0.605 − 0.421) ≈ **+0.03**.

Out-of-fold über 75 Seiten in 68 Clustern, ILP, gepaart:

| Variante | Merkmale | Paar-F1 | Gruppen-F1 | Angebote |
|---|---:|---:|---:|---:|
| geometrie | 35 | **0.569** | **0.553** | 588 |
| anker | 38 | 0.448 | 0.532 | 529 |

| Bereich | Differenz | Intervall | p |
|---|---:|---|---:|
| alle Paare | −0.021 | [−0.060, +0.021] | 0.318 |
| blinder Fleck | −0.026 | [−0.084, +0.044] | 0.398 |
| prüfbar | −0.014 | [−0.068, +0.036] | 0.624 |

**Die Gesamtzahl fällt, das Kriterium ist verfehlt.** Die
Variantenblock-Zahl braucht deshalb gar nicht mehr erhoben zu werden — sie
könnte den zweiten Teil nicht heilen.

**Was das Merkmal tatsächlich tut, ist ablesbar:** Die kalibrierten Schwellen
sinken (0.76–0.86 gegen 0.86–0.88), es entstehen weniger Angebote (529 gegen
588), und Paar-F1 bricht deutlich stärker ein als Gruppen-F1. Es macht das
Verschmelzen mutiger — wie beabsichtigt —, aber es verschmilzt das Falsche. Auf
einer Penny-Seite steht fast immer *irgendein* Produktname in der Nähe; ein
gemeinsamer nächster Anker trennt zu wenig.

Der Code bleibt als optionaler Block (`ANCHOR_BLOCKS`, nicht im Default), damit
der Negativbefund reproduzierbar ist — dieselbe Begründung wie bei
`blackbox.py`.

## 5. Vier Blöcke, einer wirkt

| Block | Differenz | Intervall | p |
|---|---:|---|---:|
| **+Geometrie** (gegen Basis) | **+0.044** | [+0.009, +0.082] | **0.018** |
| +Farbe (gegen Basis) | −0.008 | [−0.036, +0.023] | 0.596 |
| Farbe auf Geometrie, blinder Fleck | −0.051 | [−0.103, −0.001] | 0.042 |
| +Anker (gegen Geometrie) | −0.021 | [−0.060, +0.021] | 0.318 |

Alle out-of-fold über 68 Duplikat-Cluster, gepaart auf der Differenz.

**Genau einer von vier hat gewirkt, und die drei Fehlschläge zielten alle auf
den blinden Fleck bzw. die Variantenblöcke** — also genau dorthin, wo die Lücke
gemessen ist. Dreimal danebengetroffen ist kein Zufall mehr, sondern eine
Aussage über die Aufgabe: **Was der Gruppierung fehlt, ist keine weitere Zahl
je Entity-Paar.**

*Einschränkung, die mitgehört: rund zehn Vergleiche ohne Korrektur für
multiples Testen, und die Bereiche sind nicht unabhängig (alle Paare = blind +
prüfbar). Richter bleibt ein LLM-Lehrer; gemessen wird Übereinstimmung, nicht
Richtigkeit.*

## 6. Der Stand der Daten — zwei Label-Ebenen, nicht eine

Bei der Frage „können wir auf der neuen Woche trainieren?" kam heraus, dass
zwei verschiedene Label-Ebenen leicht verwechselt werden:

| Woche | extrahiert | **Span-Labels** | **Gruppen-Labels** |
|---|---:|---:|---:|
| KW30 | 89 | 89 | 38 |
| KW31 | 107 | 107 | 37 |
| KW32 | 100 | 100 | **0** |
| KW33 | 126 | **0** | **0** |
| | **422** | **296** | **75** |

- **Span-Labels** (`data/labeled/sonnet-5/`): *„dieses Wort ist ein Preis."*
  Darauf trainiert GBERT.
- **Gruppen-Labels** (`data/offer_groups/claude-sonnet-5/`): *„dieser Preis
  gehört zu jenem Produkt."* Darauf trainiert das Paarmodell.

Gruppen-Labels nach Split: **train 54, dev 21, test 0.**

Daraus folgen zwei Dinge, die für den Bericht zählen:

1. **Die Gruppierung wurde noch nie auf dem Testsplit gemessen.** Alle
   bisherigen Zahlen sind Dev-Zahlen — und Dev stammt aus den Trainingswochen,
   ist also in-distribution-optimistisch.
2. **Das Paarmodell trainiert auf 54 Seiten.** Ob das reicht, ist ungeprüft:
   für GBERT existiert eine Lernkurve (sättigt bei 100 Seiten), für das
   Paarmodell nicht.

## 7. Erster Lauf auf der frischen Woche

KW33 kam gestern herein: 126 Seiten in **42 Duplikat-Clustern** — statistisch
fast identisch zum heutigen Testsatz (100 Seiten, 43 Cluster). Die volle Kette
lief darüber: GBERT → Paarmodell + ILP → Angebote. Gemessen mit der
arithmetischen Gegenprobe, weil es für KW33 keine Referenz gibt.

| | Genauigkeit | Abdeckung | Seiten |
|---|---:|---:|---:|
| KW30–32 (teils im Training) | 0.650 | 0.563 | 296 |
| **KW33 (nie gesehen)** | **0.683** | 0.427 | 126 |

**Die frische Woche ist nicht schlechter, sondern minimal besser.** Die
niedrigere Abdeckung ist kein Qualitäts-, sondern ein Sortimentssignal: KW33
enthält mehr Non-Food, dort steht kein Grundpreis, also schweigt die Rechnung.

**Beide Zahlen sind Untergrenzen und nicht berichtsreif.** Der verwendete
Checkpoint trägt Schwelle 0.94, kalibriert für Union-Find, während der Lauf mit
ILP dekodierte (kalibriert wären 0.80–0.88); außerdem nur 30 statt 35 Merkmale.
Eine zu hohe Schwelle unter ILP lässt Gruppen zerfallen, und genau das zählt
die Prüfung als widerlegt. Zum Vergleich: auf Dev mit passender Schwelle waren
es 0.883. Der Lauf ist zu wiederholen, sobald das Paarmodell sauber neu
trainiert ist.

## 8. Handwerkliches

**Zwei Tests repariert, die nichts geschützt haben.** Beide fielen erst beim
vorgeschriebenen Konstanten-Verstellen auf:

- `test_kein_fold_modell_sieht_seine_eigenen_seiten` prüfte nur, dass die
  gehaltenen Seiten untereinander disjunkt sind. Als der Trainingsaufruf
  versuchsweise *alle* Seiten bekam, blieb er grün — er behauptete eine
  Eigenschaft, die er nicht prüft. Jetzt prüft er, was in `train` und
  `calibrate` hineingeht.
- `ANCHOR_GAP_CAP` war um das Sechsfache verstellbar, ohne dass ein Test
  reagierte.

**Eine Behauptung zurückgenommen.** „In Variantenblöcken exakt *dieselben* 40
von 95" war ein Vergleich zweier Zählungen, nicht zweier Mengen. Korrigiert und
der Report um die einzelnen Gruppen erweitert.

**Eine stille Änderung verhindert.** `ALL_BLOCKS = BLOCK_ORDER` hätte die
Merkmalsvariante „beide" mit dem neuen Block automatisch von 39 auf 42
Merkmale erweitert — jeder Vergleich gegen eine ältere Zahl hätte dann
stillschweigend etwas anderes gemeint.

**Zwei Dateinamens-Kollisionen behoben.** Reports tragen jetzt Entity-Quelle
*und* Merkmalsvariante im Namen; sonst überschreibt ein Lauf den anderen und
der Vergleich zeigt zwei Kopien derselben Zahl.

**Neu: `--all-pages` für `offers-model predict`.** Bisher konnte die
Gruppierung nur auf Splitseiten mit vorhandener Referenz laufen — also nur
dort, wo die Antwort schon bekannt ist. Der Einsatzfall braucht beides nicht.

**Aufgeräumt:** die vier Lernkurven-Checkpoints (11 GB) entfernt; ihre Zahlen
liegen versioniert in `data/eval/learning_curve_gbert.json`. Frei: 15 → 26 GB.
Der Code selbst ist nicht überladen — 32 CLI-Module, alle registriert, keine
losen Skripte, `data/eval` unter 300 KB.

## 9. Bewertung externer Vorschläge

Drei Vorschläge von außen (Gemini) wurden gegen die Messungen gehalten:

- **Domänendifferenz reduzieren** (Paarmodell auf GBERT-Entities trainieren):
  **abgelehnt mit Messung.** Die Kantenqualität ist auf GBERT-Entities sogar
  höher (AUC 0.984 gegen 0.981), und Stufe 1 → Stufe 2 kostet weniger als das
  Konfidenzintervall breit ist. Eine Lösung für ein Problem, das die Daten
  nicht zeigen.
- **Semantische Textmerkmale:** durch das Ankermerkmal ersetzt, weil dieses die
  gemessene Struktur direkter trifft. Textgleichheit hätte nur identische
  Preise gefangen; der belegte Fall (`4.99 | 4.99 | 5.99 | 7.99`) hat
  überwiegend verschiedene. Nach dem Ankerergebnis ist von Textmerkmalen erst
  recht nichts zu erwarten.
- **1:n-Varianten-Schema:** die tragfähige Idee, und eine Teamentscheidung.
  Siehe unten.

## 10. Das 1:n-Schema — vier Wirkstellen, keine davon eine Zahl

```
offer(id, page_id, product, brand, ...)
variant(offer_id, position, quantity, price, old_price, unit_price)
```

**Es hebt keine einzige Zahl von selbst.** Die Referenz gruppiert flach, und
`group_f1` prüft die flache Gruppe. Wer das Schema ändert und eine bessere
Zahl erwartet, wird enttäuscht. Wirken würde es an vier anderen Stellen:

1. **Ein ILP-Constraint würde legal.** Kardinalität („höchstens ein PRICE je
   Gruppe") ist heute bewusst nicht eingebaut, weil sie für Variantenblöcke
   falsch ist. Auf *Variantenebene* ist sie richtig. Das erlaubte zweistufiges
   Dekodieren: erst Angebotsblöcke ohne Kardinalität, dann Varianten mit.
2. **Die Aufgabe hat zwei Relationen, das Modell kennt nur eine.** Heute lernt
   `offer_pairs` ein einziges „gehören zusammen?" für alle Typpaare. Tatsächlich
   sind es eine Stern-Relation (Produkt↔Preis) und eine Geschwister-Relation
   (Preis↔Preis). Die Messung passt genau dazu: die Geschwisterkante
   funktioniert bei Mengen (0.868) und scheitert bei Preisen (0.639).
3. **Die positionsweise Variantenpaarung hat heute keinen Ort.** Sie ist
   gemessen und funktioniert (26 von 43 Blöcken, **0 in anderer Reihenfolge**),
   lässt sich aber nirgends ablegen.
4. **Die 506 Bruchstücke.** Von 1283 Datensätzen haben nur 777 Produkt *und*
   Preis.

Aufwand: Schema in `offers.py`, Referenzformat **unverändert**, Metrik
**unverändert**.

## Was offen ist

**Sofort und ohne Entscheidung machbar:**

- **Paarmodell sauber neu trainieren** — ILP als Dekoder, 35 Merkmale,
  kalibrierte Schwelle. Der aktuelle Checkpoint ist für Union-Find kalibriert
  und trägt nur 30 Merkmale; jede Zahl aus Abschnitt 7 hängt daran.
- **Lernkurve für das Paarmodell** — beantwortet „reichen 54 Seiten?" mit einer
  Zahl statt einer Vermutung. Nach vier Merkmalsexperimenten die naheliegendste
  verbleibende Frage. Kostet Minuten, das Modell hat 4097 Parameter und
  trainiert in ~17 s auf CPU.

**Braucht eine Entscheidung über Kontingent:**

- **KW32 gruppieren** — ohne Gruppen-Labels im Testsplit gibt es nie eine
  Testzahl für die Gruppierung. Werkzeug existiert (`magda offers-teacher`).
- **KW33 labeln** (Spans, 126 Seiten) — Werkzeug existiert **nicht**;
  `offers-teacher` deckt nur die Gruppierung ab, `magda label` nur die
  GWDG-Modelle. Das Gegenstück für Spans müsste gebaut werden.

**Teamentscheidungen, unverändert offen:**

- 1:n-Varianten-Schema (Issue #6)
- Farb- und Ankerblock behalten oder entfernen
- Paar-F1 oder Gruppen-F1 als Primärzahl

## Einordnung

Der Tag hat nicht geliefert, was er sollte. Das Ankermerkmal war sorgfältig aus
einer Messung abgeleitet, nicht geraten — und es ist trotzdem durchgefallen.
Das ist der Normalfall bei Merkmalsarbeit und wäre unauffällig geblieben, wenn
nicht vorher zwei ähnliche Versuche dasselbe Ergebnis gehabt hätten.

Der Wert liegt in der Kombination: **drei gezielte Merkmalsblöcke, alle auf
dieselbe gemessene Lücke gerichtet, alle wirkungslos.** Das ist ein Argument,
das ein einzelner Fehlschlag nicht trägt, und es verschiebt die Priorität
weg von „das nächste Merkmal" hin zu „mehr Referenz oder eine andere
Aufgabenstellung".

Methodisch war die zweite Lehre wichtiger als die erste: **Eine Dev-Zahl über
19 Einheiten hat hier zum zweiten Mal in die Irre geführt.** Beim
Farbmerkmalsblock drehte sich das Vorzeichen unter Kreuzvalidierung, bei den
Variantenblöcken schrumpfte der Effekt auf ein Drittel. Der Aufwand für
`--cross-validate` (68 statt 14 Auswertungseinheiten) hat sich damit zum
zweiten Mal ausgezahlt — und beide Male hätte man ohne ihn eine falsche
Entscheidung getroffen.
