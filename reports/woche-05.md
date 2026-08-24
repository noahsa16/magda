# Woche 5 — Von Entities zu Angeboten: die zweite Stufe

Stand: 11.08.2026

## Kurzfassung

Woche 4 endete mit dem Satz, dass die Modelle an der Konsistenzgrenze ihres
Lehrers angekommen sind und mehr Daten dort nichts bringen. Woche 5 hat
deshalb die Stufe darüber angefasst: **aus getaggten Wörtern wieder Angebote
machen.** Das ist die Frage, die das Projekt am Ende beantworten muss — ein
Preis ohne sein Produkt ist keine Datenbankzeile.

Vier Dinge stehen am Ende der Woche:

1. **Das Clustering ist erstmals ehrlich messbar.** Vorher wurde es an dem
   Kriterium gemessen, nach dem es selbst zuordnet. Die Ablation trennt das.
2. **Es gibt eine Gruppierungsreferenz** — 75 Seiten, von einem Vision-Modell
   erzeugt, nicht von Hand. Ohne sie ist keine Variante messbar, auch die
   bestehende Heuristik nicht.
3. **Ein gelerntes Paarmodell schlägt die Heuristik, und der Dekoder schlägt
   alles.** Correlation Clustering per ILP bringt **+0.100 Gruppen-F1
   [+0.067, +0.133] bei p = 0.000** — mehr als jeder Merkmalsblock.
4. **Merkmals-Engineering am Paarmodell ist ausgereizt.** Vier Blöcke gemessen,
   genau einer wirkt.

Dazu wurde die vierte Erscheinungswoche geerntet (126 Seiten), die Kette
erstmals ende-zu-ende gemessen und das Repo von 1 GB PDFs befreit.

Details zu den letzten beiden Tagen in `reports/nachtlauf-2026-08-10.md` und
`reports/2026-08-11-merkmalsgrenze.md`.

## Datenlage

| Woche | extrahiert | **Span-Labels** | **Gruppen-Labels** |
|---|---:|---:|---:|
| KW30 | 89 | 89 | 38 |
| KW31 | 107 | 107 | 37 |
| KW32 | 100 | 100 | 0 |
| KW33 *(neu)* | 126 | 0 | 0 |
| | **422** | **296** | **75** |

Zwei Label-Ebenen, und sie werden leicht verwechselt:

- **Span-Labels** (`data/labeled/sonnet-5/`) sagen *„dieses Wort ist ein
  Preis"*. Darauf trainiert GBERT.
- **Gruppen-Labels** (`data/offer_groups/claude-sonnet-5/`) sagen *„dieser
  Preis gehört zu jenem Produkt"*. Darauf trainiert das Paarmodell.

BIO-Tags können die zweite Frage grundsätzlich nicht ausdrücken — ein
Tag-Vokabular enthält keine Relation. Deshalb die getrennten Ordner.

Der Split ist unverändert **175/21/100** über KW30–KW32. KW33 steht in keinem
Split; die Gruppen-Labels liegen sämtlich in Train und Dev.

## 1. Das Clustering ließ sich nicht ehrlich messen

Der Ausgangspunkt der Woche war ein Messfehler, kein Modellfehler. Die Frage
„wie oft landet ein Preis bei einem Produkt" zählt **Fragmentierung, nicht
Korrektheit** — ein Preis am *falschen* Produkt geht als Erfolg durch.

Der naheliegende Ausweg trägt nicht: die Zuordnungen nach arithmetisch und
geometrisch zu trennen und die Rechnung über die geometrischen Fälle urteilen
zu lassen, ergibt garantiert „falsch". `_match_badges` betritt den
geometrischen Zweig **nur, wenn kein Block arithmetisch gepasst hat** — das
Urteil steht fest, bevor es gefällt wird.

Die Lösung ist eine **Ablation**: `cluster_page(page, arithmetic=False)`
schaltet die Rechnung zum Messen ab, die Geometrie ordnet allein zu, und erst
danach wird nachgerechnet.

> **Das allgemeine Muster, das die ganze Woche trägt: halte das Merkmal
> zurück, mit dem du hinterher richten willst.**

Ergebnis über Train + Dev (196 Seiten): Der geometrische Rückfall trifft in
**0,56 bis 0,68** der prüfbaren Fälle und trägt dabei 652 von 1373
Zuordnungen. Zwei Zahlen statt einer, weil eine Definitionsfrage offen ist und
beide Antworten vertretbar sind — eine davon zur richtigen zu erklären hieße,
eine Genauigkeit zu behaupten, die die Messung nicht hergibt.

**Und wo kein Grundpreis steht, ist die Zuordnung nicht nur schlechter,
sondern unprüfbar.** 532 bis 678 der Urteile lauten „nicht beurteilbar", und
das deckt sich fast mit Non-Food. Dort ist die Geometrie alleinige Instanz
*und* ohne Kontrolle. Diese Lücke schließt kein Schwellwert, sondern nur eine
Referenz.

## 2. Die Gruppierungsreferenz — und warum sie kein Gold ist

Geplant waren 30–50 Seiten Handannotation. Das sprengt den Projektrahmen,
deshalb die Teamentscheidung vom 06.08.: **ein Vision-Modell gruppiert.**

Das Ergebnis liegt in `data/offer_groups/<quelle>/` und **nicht** in
`gold/offers/`, mit `provenance: {"kind": "llm", …}` in jeder Datei. Der
getrennte Pfad ist der eigentliche Punkt: gemessen wird damit
**Übereinstimmung, nicht Richtigkeit** — dieselbe Einschränkung wie bei
`magda agreement`, und die Ausgabe sagt es dazu.

Was den Vergleich trotzdem tragfähig macht, sind die verschiedenen
Informationsquellen: **die Heuristik kennt nur Wortkoordinaten, das Modell
sieht den gelben Preiskasten.**

Zwei Konstruktionsentscheidungen, die leicht falsch getroffen werden:

- **Die Referenz gruppiert Wortindizes, keine Entity-Spans.** Ein Span gehört
  immer einem Labelordner; eine Referenz darüber wäre nach dem nächsten
  Labeling-Lauf wertlos und könnte die GBERT-Vorhersagen gar nicht beurteilen,
  weil deren Spans anders liegen.
- **Annotiert wird aus dem Seitenbild, nicht durch Korrigieren der Heuristik.**
  Eine vorbefüllte Gruppierung wäre bequem und wiederholte genau den Fehler,
  gegen den die Ablation gebaut wurde.

Umfang am Ende der Woche: **75 Seiten** (von 51 zu Wochenmitte).

### Der erste Vergleich, und er fällt deutlich aus

Über 33 Train/Dev-Seiten, Richter ist beide Male die Rechnung Menge ×
Grundpreis, und sie ist an beiden Zuordnungen unbeteiligt:

| | Trefferquote | beurteilte Preise |
|---|---|---|
| Heuristik, Geometrie allein (Ablation) | 0.463 – 0.620 | 100 – 134 |
| **LLM, sieht das Seitenbild** | **0.925** | 159 |

Übereinstimmung insgesamt: **Paar-F1 0.723, Gruppen-F1 0.331.** Die Lücke
zwischen beiden ist die Aussage — Teile eines Angebots trifft die Heuristik
oft, das vollständige Angebot nur bei knapp jedem dritten.

**Die Heuristik fragmentiert messbar: 417 Angebote gegen 296.** Das erklärt
auch, warum das LLM *mehr* beurteilbare Fälle hat: wo ein Preis als Bruchstück
liegen bleibt, entsteht keine Rechnung, die man prüfen könnte. Ein Verfahren,
das seltener zuordnet, sieht in einer Genauigkeitszahl besser aus, als es ist
— deshalb gehört die Zahl der Zuordnungen daneben.

## 3. Der Machbarkeitstest für OFFER — und was er wirklich sagt

Vor der Frage „zweiter Modellkopf?" stand die Frage, ob eine flache
BIO-Sequenz ein Angebot überhaupt fassen kann. Nachgerechnet über 293 Seiten:

- Von 3066 Angeboten sind **2080 ein einziger zusammenhängender Lauf: 0.678**
- Ohne die Preis-Badges: **2530 von 2637, also 0.959**

**Die Differenz ist die ganze Aussage.** Penny setzt den Preis in einen gelben
Kasten, und der steht im Textlayer weit weg vom Produktnamen — auf
`1342815_p21` liegt der Preis bei Wort 6, sein Produkt bei Wort 166. Ein
flacher Span kann beide nicht fassen, ohne alles dazwischen mitzunehmen.

Das ersetzt die frühere Zahl 92,7 % nicht, sondern korrigiert ihre Einheit:
jene zählte *visuelle Wortgruppen*, für die OFFER-Frage zählt die Einheit
„Angebot". Dort ist 0.678 die Obergrenze, nicht 0.927.

**Einordnung aus der Literatur** (Recherche 06.08.): Das Problem heißt *Line
Item Recognition* und ist der Kern des DocILE-Benchmarks (ICDAR 2023). DocILE
kennt zwei Standardlösungen — die OFFER-Tag-Folge ist eine davon, paarweise
Relationsklassifikation die andere. Wichtig für die Aufwandsfrage: **FUNSD
trainiert mit 149 Dokumenten**; die Sorge, 196 Seiten seien zu wenig, ist
literaturseitig unbegründet.

## 4. Das Paarmodell

Gebaut wurde die zweite Standardlösung: jedes Entity-Paar wird klassifiziert
(„gehören die zusammen?"), die Kanten oberhalb einer Schwelle werden zu
Gruppen verschmolzen. **4097 Parameter, 16,8 s Training auf CPU** — eine GPU
lohnt hier nicht, der Grund für RunPod war LayoutXLMs RAM-Bedarf.

Stand Dev, 21 Seiten:

| | Paar-F1 | Gruppen-F1 | Angebote |
|---|---|---|---|
| **Paarmodell** | **0.742** | **0.477** | 138 |
| Heuristik | 0.683 | 0.436 | 185 |
| Lehrer (Referenz) | – | – | 122 |

Das Modell ist in beiden Zahlen vorn *und* fragmentiert weniger.

**Zwei Konstruktionsregeln, die den Rest der Woche geprägt haben:**

- **Die Rechnung Menge × Grundpreis ist bewusst kein Merkmal.** Sie ist das
  einzige Signal, das sich selbst beweist, und damit der einzige unbestechliche
  Richter. Als Eingabe gefüttert bewertete sie sich hinterher selbst. Ein Test
  hält das fest, indem er die Merkmalsnamen prüft.
- **Die Schwelle wird out-of-fold kalibriert, nicht geraten — und 0.5 ist grob
  falsch.** `pos_weight` gleicht die Schieflage aus (4553 positive gegen 46359
  negative Paare) und schiebt alle Wahrscheinlichkeiten nach oben: bei 0.5
  entstanden 83 Gruppen statt 268. Die beiden Kriterien wählen dabei
  verschiedene Schwellen — Paar-F1 ist bei 0.98 maximal, aber Gruppen-F1
  bricht dort auf 0.175 ein. Paar-F1 belohnt Vorsicht, weil kleine Gruppen
  wenige Paare zu verlieren haben.

## 5. Der größte Einzelbefund: der Dekoder

`groups_from_edges` verschmilzt A–B und B–C zu einer Gruppe, auch wenn A–C
weit unter der Schwelle liegt. Correlation Clustering per ILP erzwingt
stattdessen Transitivität und kappt die schwächste Kante eines Widerspruchs.

Out-of-fold über 75 Seiten in 68 Duplikat-Clustern, mit geschachtelter
Schwellenwahl:

| Dekoder | Gruppen-F1 |
|---|---:|
| Union-Find | 0.453 |
| **ILP** | **0.553** |
| **Differenz** | **+0.100 [+0.067, +0.133], p = 0.000** |

Zum Vergleich: `+Geometrie`, der beste Merkmalsblock, lag bei +0.044.

**Die Wirkungskette ist die eigentliche Aussage:** Der Gewinn kommt nicht
daher, dass das ILP bei gleicher Schwelle besser dekodiert, sondern dass es
eine **niedrigere erlaubt** — die Kalibrierung wählte out-of-fold 0.868 statt
0.956, ohne Vorgabe. Union-Find muss so hoch drehen, weil eine einzige
durchgerutschte Kante eine ganze Legendenspalte verschmilzt.

**Drei Dinge gehören zu jeder Nennung:** Im CV-Lauf *fällt* Paar-F1 (0.569
gegen 0.715), weil die tiefere Schwelle mehr Paare vorhersagt — belastbar ist
die CV-Zahl. Die Komponentenkappung griff bei 1611 von 37367 Komponenten;
dort *ist* das ILP Union-Find, der Effekt also eher unter- als überschätzt.
Und beide Dekoder wurden auf `group_f1` kalibriert — **wer Paar-F1 zur
Primärzahl macht, dreht den Teilbefund um.**

Die arithmetische Gegenprobe stützt das Ergebnis (0.883 gegen 0.845 bei
*identischer* Abdeckung 0.589). Sie ist hier unbefangen, weil die Rechnung
bewusst kein Constraint des ILP ist.

## 6. Die Kette erstmals ende-zu-ende

Bis zum 10.08. war das unmöglich: `data/predictions/gbert` hatte 101 Seiten
(alle Test), `data/offer_groups/claude-sonnet-5` 51 (alle Train/Dev),
**Schnittmenge null**. Nach `magda predict gbert --split dev` treffen sich
beide auf 21 Seiten.

| Entities | Basis | +Geometrie | +Farbe | beide |
|---|---|---|---|---|
| Lehrer (sonnet-5) | 0.477 | 0.540 | 0.472 | 0.492 |
| Schüler (gbert) | 0.504 | 0.556 | 0.504 | 0.502 |

**Die zweite Zeile ist nicht besser, sie ist auf einem kleineren Nenner
gemessen.** GBERT findet 717 statt 730 Entities (0.982), aber nur **1855 der
1996 Referenzpaare** überleben (0.929) — 7,1 % der Gruppierungsaufgabe
verschwinden, und zwar die Paare, deren Entity der Schüler nicht gefunden hat.
Wer die +0.027 als Verbesserung liest, hat den Nenner nicht angesehen.

**Was die Zahl trägt:** Die Gruppierung bricht mit Schüler-Entities nicht
zusammen. Stufe 1 → Stufe 2 kostet auf Dev weniger als das Konfidenzintervall
breit ist. Mehr sagt sie nicht — Dev stammt aus den Trainingswochen, die Zahl
ist eine Obergrenze.

Mit dem ILP als Dekoder liegt die Kette auf Dev bei **Paar-F1 0.878,
Gruppen-F1 0.729**: 98 von 122 Angeboten exakt gebildet (Recall 0.803) bei
147 gebildeten Gruppen (Precision 0.667). Die 49 überzähligen sind keine
erfundenen Angebote, sondern die Bruchstücke der 24 zerfallenen.

## 7. Die Merkmalsgrenze

Am Ende der Woche wurde die Fehleranalyse auf Gruppenebene gezogen und daraus
ein Merkmal abgeleitet. Beides ist im Tagesbericht ausführlich; hier das
Ergebnis:

| Block | Differenz | Intervall | p |
|---|---:|---|---:|
| **+Geometrie** | **+0.044** | [+0.009, +0.082] | **0.018** |
| +Farbe | −0.008 | [−0.036, +0.023] | 0.596 |
| Farbe auf Geometrie, blinder Fleck | −0.051 | [−0.103, −0.001] | 0.042 |
| +Anker | −0.021 | [−0.060, +0.021] | 0.318 |

**Genau einer von vier wirkt, und die drei Fehlschläge zielten alle auf
dieselbe gemessene Lücke.** Das ist ein Argument, das ein einzelner
Fehlschlag nicht trägt: Was der Gruppierung fehlt, ist keine weitere Zahl je
Entity-Paar.

Die Lücke selbst ist präzise lokalisiert. In Variantenblöcken (`Pfanne: 20 cm
9.99 / 24 cm 14.99`) liegt die Kante `PRICE|PRICE` bei mittlerer
Wahrscheinlichkeit **0.639**, während `QUANTITY|QUANTITY` — dieselbe
Konstruktion, dieselben großen Gruppen — bei **0.868** liegt. Nicht die
Gruppengröße ist die Ursache, sondern dass Penny Mengen untereinander in den
Fließtext setzt und jeden Preis in einen eigenen Kasten.

## 8. Infrastruktur

- **Woche 4 geerntet:** alle 44 Regionen, 126 neue Seiten nach der
  Entdopplung. `raw = words + excluded + pending` gilt weiter.
- **PDFs und Seitenbilder ins Drive-Archiv ausgelagert.** Das Repo trug ~1 GB
  Originaldateien, die sich aus den Katalog-IDs jederzeit wiederbeschaffen
  lassen.
- **Lernkurve für GBERT gefahren:** p25 0.835 / p50 0.891 / p100 **0.925** /
  p175 0.921 (bestes Dev-F1). **Die Kurve sättigt zwischen 100 und 175
  Seiten** — mehr LLM-Zeit für Stufe 1 kauft kaum noch etwas. Deckt sich mit
  dem Befund aus Woche 4: die Grenze ist die Konsistenz der Referenz, nicht
  ihre Menge. Die vier Checkpoints (11 GB) sind gelöscht, ihre Zahlen liegen
  versioniert in `data/eval/learning_curve_gbert.json`.
- **Blackbox-Vergleichsarm gebaut**, bewusst noch nicht auf Test gefahren —
  die Referenzfrage ist offen und der Testlauf nicht wiederholbar.
- **Checkpoint-Namen getrennt.** `magda train` schrieb nach
  `checkpoints/<variante>` ohne Rücksicht auf `--labels-from`; jeder Nebenlauf
  hätte den eingefrorenen KW30/31-Stand gelöscht.
- **Der Label-Default zeigte auf ein Modell, mit dem hier gar nicht gelabelt
  wird.** `default_labeled_model()` gab `CHAT_AI_VISION_MODEL` den Vorrang und
  lieferte Mistral. Beziffert: über *dieselbe* Gruppierung fand
  `magda offers-verify` mit Mistral-Labels 399 Preise, mit sonnet-5 dagegen
  **494**. Ältere Zahlen aus Befehlen ohne `--labels-from` stehen unter diesem
  Vorbehalt.
- Tests: 420 → **549**.

## Was offen ist

**Sofort machbar, ohne Entscheidung:**

- **Paarmodell sauber neu trainieren** — der ausgelieferte Checkpoint ist für
  Union-Find kalibriert (Schwelle 0.94) und trägt nur 30 Merkmale. Jede Zahl
  aus einem Lauf mit ILP hängt daran.
- **Lernkurve für das Paarmodell** — beantwortet „reichen 54 Trainingsseiten?"
  mit einer Zahl statt einer Vermutung. Kostet Minuten.

**Braucht eine Entscheidung über Kontingent:**

- **KW32 gruppieren.** Die Gruppen-Labels liegen sämtlich in Train und Dev;
  **der Testsplit hat null.** Das heißt: die Gruppierung wurde noch nie auf dem
  Testsplit gemessen, jede berichtete Zahl ist eine Dev-Zahl. Werkzeug
  existiert.
- **KW33 labeln** (Spans, 126 Seiten in 42 Clustern). Werkzeug existiert
  **nicht** — `offers-teacher` deckt nur die Gruppierung ab, `magda label` nur
  die GWDG-Modelle.

**Teamentscheidungen:**

- **1:n-Varianten-Schema** (Issue #6). Es hebt keine Zahl von selbst — die
  Referenz gruppiert flach, die Metrik prüft flach. Wirken würde es an vier
  anderen Stellen, darunter: im 1:n-Modell wird ein Kardinalitäts-Constraint
  legal, der heute falsch ist.
- **Farb- und Ankerblock behalten oder entfernen.** Beide gemessen wirkungslos.
- **Paar-F1 oder Gruppen-F1 als Primärzahl.** Nicht kosmetisch: die Wahl dreht
  den Dekoder-Teilbefund um.
- Sortenangaben und Gebinde-Komposita, Sliding Window im Training, LiLT als
  dritter Arm — unverändert aus Woche 4.

## Einordnung

Woche 4 endete mit einer Zahl (F1 0.894) und der Erkenntnis, dass sie nicht
weiter steigen wird. Woche 5 hat deshalb nicht versucht, sie zu steigern,
sondern die nächste Stufe messbar gemacht — und das war mehr Arbeit als
erwartet, weil das Clustering sich vorher **selbst benotet** hat.

Der methodische Ertrag ist größer als der numerische. Dreimal in dieser Woche
war die naheliegende Messung die falsche:

- Die Trefferquote des Clusterings zählte Fragmentierung statt Korrektheit.
- Der Farbmerkmalsblock sah auf Dev gut aus und drehte unter Kreuzvalidierung
  das Vorzeichen.
- Die Variantenblock-Zahl schrumpfte out-of-fold auf ein Drittel.

**Zweimal davon hätte man ohne `--cross-validate` eine falsche Entscheidung
getroffen** — eine Dev-Zahl über 14 bis 19 Einheiten trägt hier nicht. Der
Aufbau, aus 14 Auswertungsclustern 68 zu machen, indem jede Referenzseite
einmal von einem Modell ohne sie bewertet wird, ist der wichtigste
Einzelbaustein der Woche.

Für die Projektfrage — günstige Alternative zum LLM — bleibt die Aussage
unverändert und wird um eine Stufe erweitert: Stufe 1 kostet 0,264 s je Seite
gegen 44,8 s beim LLM, Stufe 2 kommt mit 4097 Parametern und 17 s Training
hinzu. **Was am Ende herauskommt, ist keine Tag-Folge mehr, sondern eine
Angebotstabelle** — auf Dev mit 98 von 122 exakt gebildeten Angeboten. Was
fehlt, um diese Zahl berichtsreif zu machen, ist keine Modellarbeit, sondern
eine gruppierte Testwoche.
