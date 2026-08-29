# Woche 7 — Eine Konstante war der größte Hebel des Projekts

Stand: 29.08.2026

## Kurzfassung

Die Gruppierung stand seit Wochen bei Gruppen-F1 0.66 und ließ sich durch
keinen Merkmalsblock bewegen. Farbe brachte −0.008, Anker −0.021, nur
Geometrie war mit +0.044 ein Befund. Die naheliegende Schlussfolgerung war,
dass die Aufgabe an ihrer Grenze angekommen ist.

Sie war es nicht. Der Engpass war `MAX_COMPONENT` — eine Notbremse gegen
Rechenzeit im ILP-Dekoder, die verhinderte, dass große Zusammenhangs-
komponenten überhaupt optimiert wurden. Von 40 auf 120 angehoben und das
Paarmodell neu kalibriert:

| | Paar-F1 | Gruppen-F1 | Angebote |
|---|---:|---:|---:|
| **Paarmodell, Cap 120** | **0.929** | **0.778** | 429 |
| Paarmodell, Cap 40 | 0.398 | 0.659 | 413 |
| Heuristik | 0.817 | 0.524 | 510 |
| Lehrer (Referenz) | – | – | 422 |

*(56 Dev-Seiten, Schwelle 0.68 out-of-fold über 494 Trainingsseiten
kalibriert, Referenz `data/offer_groups/claude-sonnet-5/`.)*

Dieselbe Architektur, dieselben 35 Merkmale, dasselbe Netz mit 4097
Parametern. Geändert wurde eine Zahl. Der Gewinn ist größer als der jedes
Merkmalsblocks (+0.044) und größer als der Dekoderwechsel Union-Find → ILP
selbst (+0.100), der bis dahin als der große Hebel des Projekts galt.

Vier Dinge stehen am Ende der Woche:

1. **Das Verfahren fragmentiert nicht mehr.** 429 gebildete Angebote gegen
   422 in der Referenz; die Heuristik bildet 510.
2. **Die unabhängige Gegenprobe steigt mit.** Menge × Grundpreis bestätigt
   0.912 gegen 0.833 der Heuristik bei praktisch gleicher Abdeckung.
3. **Die Schwellenwahl ist robust geworden**, wo sie vorher 17 Punkte
   entschied.
4. **Ein naheliegender nächster Schritt ist widerlegt**, bevor Arbeit
   hineinfloss: Typ-Constraints im ILP, von den eigenen Daten. Ein zweiter,
   der Relationskopf auf LiLT, ist in seiner Erwartung korrigiert.
5. **Die Decke ist erstmals gemessen statt geschätzt: Gruppen-F1 0.916**
   zwischen zwei unabhängigen Annotatoren. Über 0.778 liegen damit rund 14
   Punkte Luft — die Arbeit lohnt weiter.

## Wie die Notbremse eine Metrik entschied

`offer_ilp.groups_from_edges_ilp` löst Correlation Clustering exakt: Es
bildet Zusammenhangskomponenten über die Kanten oberhalb der Schwelle und
optimiert jede einzeln. Weil die Kosten allein an der größten Komponente
hängen, gab es eine Kappung: Komponenten über `MAX_COMPONENT` Entities
wurden nicht optimiert, sondern per Union-Find zusammengeworfen.

Der Docstring sagte immer, was das bedeutet — *„Wo sie greift, ist das ILP
Union-Find, und zwar an genau der Stelle, an der es seinen Vorteil
ausspielen sollte"*. Was fehlte, war die Zahl.

Sie wurde sichtbar, als das Paarmodell erstmals auf allen 494 statt 54
Referenzseiten trainiert wurde. Mehr Trainingsdaten hoben die out-of-fold
gewählte Schwelle nicht an, sondern senkten sie von 0.88 auf 0.82. Eine
tiefere Schwelle heißt mehr Kanten, mehr Kanten heißen größere Komponenten
— und bei Cap 40 kappte der Dev-Lauf dadurch **5 von 297 Komponenten**, die
größte mit 111 Entities.

Fünf Seiten von 56. Der Effekt auf die Metrik war trotzdem beherrschend — Paare
wachsen quadratisch mit der Gruppengröße:

```
5 gekappte Komponenten  →  20903 der 26279 vorhergesagten Paare (80 %)
Referenz                →   7351 Paare
```

Paar-F1 fiel damit auf 0.398, während Gruppen-F1 bei 0.659 stand. Eine
Riesenkomponente zählt als *eine* falsche Gruppe, erzeugt aber tausende
falsche Paare. Die beiden Metriken maßen dieselbe Ausgabe und sagten
Gegensätzliches, weil eine von ihnen quadratisch auf den Fehler reagiert.

**Der Fehler war nicht das Modell, sondern die Erlaubnis.** Ohne Kappung
löst dieselbe 111er-Komponente in 6 bis 28 Sekunden und zerfällt in 15
Gruppen mit höchstens 11 Entities. Das ILP kann den Fall — es durfte ihn
nur nicht anfassen.

## Was der Retrain gekostet und gebracht hat

Ein Lauf über 494 Seiten, 5 Folds, 25 Schwellen, ILP-Dekoder: **76 Minuten**
auf einem MacBook Air M2, ein Kern, 340 MB Arbeitsspeicher. Die vorher
geschätzten 45 Minuten waren zu optimistisch; der Faktor gegenüber Cap 40
liegt bei 3,6 statt 2,7.

```
Seiten            494
Paare          781902
  zusammen      75307
  getrennt     706595
  ohne Urteil   25525   (Referenz schweigt, kein Negativbeispiel)
```

Über alle **64666 Komponenten der Kalibrierung und 245 des Dev-Laufs wurde
keine einzige gekappt** (`LAST_RUN["capped"] = 0`). Die Schwellenkurve ist
damit erstmals durchgehend ein ILP-Ergebnis und nicht teilweise Union-Find.

Die Kurve selbst sieht anders aus als vorher:

| Schwelle | 0.52 | 0.60 | 0.68 | 0.76 | 0.84 | 0.92 | 0.96 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Paar-F1 | 0.872 | 0.884 | 0.897 | 0.903 | 0.900 | 0.875 | 0.833 |
| Gruppen-F1 | 0.678 | 0.684 | **0.689** | 0.677 | 0.645 | 0.563 | 0.433 |

Zwei Beobachtungen dazu, und die zweite ist die wichtigere.

**Die Schwelle fällt erneut**, von 0.82 auf 0.68. Das ist dasselbe Muster,
das schon den ILP-Gewinn erklärte: Der Dekoder verdient seinen Vorteil
nicht dadurch, dass er bei gleicher Schwelle besser dekodiert, sondern
dadurch, dass er eine tiefere *erlaubt*.

**Der Gegensatz zwischen den Kriterien ist verschwunden.** Vorher standen
sich das Paar-F1-Optimum (0.96, dort Gruppen-F1 0.429) und das
Gruppen-F1-Optimum (0.82, dort Paar-F1 0.518) unvereinbar gegenüber; die
Wahl zwischen ihnen entschied 17 Punkte. Jetzt liegen die Optima bei 0.80
und 0.68 dicht beieinander, beide Metriken sind über eine breite Spanne
gleichzeitig hoch, und Gruppen-F1 bildet zwischen 0.52 und 0.76 ein Plateau
statt einer Spitze. Die offene Teamentscheidung „welche Zahl trägt das
Projekt" kostet damit noch zwei Punkte statt siebzehn.

Rückblickend war der scheinbar tiefe Konflikt der beiden Metriken kein
Wesenszug der Aufgabe, sondern ein Artefakt der Kappung.

## Die unabhängige Gegenprobe

Menge × Grundpreis beweist sich selbst und ist kein Merkmal des Modells —
der einzige unbestechliche Richter im System.

| | bestätigt | widerlegt | Genauigkeit | Abdeckung |
|---|---:|---:|---:|---:|
| Paarmodell | 238 | 23 | **0.912** | 0.548 |
| Heuristik | 210 | 42 | 0.833 | 0.529 |

Die widerlegten Preise fallen von 42 auf 23, bei fast identischer Abdeckung.
Das entkräftet den naheliegenden Einwand, gröbere Gruppen schmeichelten der
Prüfung: Wäre das Modell nur großzügiger, stiege die Abdeckung mit.

Die Zahl der Heuristik ist dabei milder zu lesen als die des Modells:
`cluster_page` ordnet teilweise selbst arithmetisch zu, der Richter ist dort
also nicht unbeteiligt. Beim Paarmodell ist er es.

**Was die Gegenprobe nicht sagt:** 162 der 476 Preise tragen keinen
Grundpreis und bleiben unbeurteilbar — das ist im Wesentlichen Non-Food,
also der Bereich, in dem die Gruppierung am schwächsten ist. Die 0.912
gelten für die prüfbare Hälfte.

## Zwei Wege, vorher geprüft — einer verworfen, einer eingeordnet

Nach dem Dekoder-Befund lag nahe, weiter am Dekoder zu arbeiten. Zwei
Kandidaten wurden geprüft, bevor Arbeit hineinfloss. Der erste ist von den
eigenen Daten widerlegt; der zweite ist nicht erledigt, sondern in seiner
Erwartung korrigiert — und wird durch die Deckenmessung weiter unten
wieder gestärkt.

### Typ-Constraints: von den eigenen Daten widerlegt

„Höchstens ein PRODUCT je Gruppe" als hartes ILP-Constraint klingt
zwingend und ist falsch. Ausgezählt über die Referenz:

```
Referenzgruppen gesamt:  5491
  mit >=2 PRODUCT:         982  (0.179)
  mit >=2 PRICE/APP_PRICE: 952  (0.173)
  mittlere Gruppengroesse: 5.97 Entities
```

Jede fünfte bis sechste Gruppe hat mehrere Produktnamen — Sortenzeilen und
Variantenblöcke. Das Constraint wäre auf 18 % der Gruppen nachweislich
falsch und zementierte genau den Plättungsfehler, den `offer_ilp.py` für
PRICE schon als Begründung führt. Als weiche Strafe wäre es redundant: Die
Typ-One-Hots geben dem MLP diese Information bereits.

Die 5,97 Entities je Gruppe sind nebenbei die Einordnung, die zu jeder
Nennung von Gruppen-F1 gehört. Bei einer Entity-Trefferquote von 0.95 liegt
exakte Gruppengleichheit rechnerisch bei 0.95⁶ ≈ 0.74. Gruppen-F1 ist
alles-oder-nichts über sechs Zuordnungen, nicht „zwei Drittel richtig".

### Relationskopf auf LiLT: von der Literatur eingeordnet

Der zweite Kandidat war grundsätzlicher: Das Projekt gruppiert mit einem
MLP über 35 handgebaute Merkmale, hat aber drei trainierte Dokumentmodelle
im Haus (`checkpoints/lilt`, `layoutxlm`, `xlmr`) und setzt keines davon auf
die Relationsaufgabe an. LiLT wurde für genau diese Aufgabe gebaut.

Die publizierten Zahlen dieser Architektur dämpfen die Erwartung:

| Modell | Aufgabe | F1 |
|---|---|---:|
| LiLT[InfoXLM] | FUNSD Relation Extraction | 0.6276 |
| LayoutXLM | dieselbe | 0.5483 |
| LiLT / LayoutXLM | XFUND, acht Sprachen | 0.6781 / 0.6432 |
| GeoLayoutLM | FUNSD RE | 0.8945 |

FUNSD-RE ist Key-Value-Linking, also eine *einfachere* Relation als unsere
Angebote — meist 1:1 und räumlich benachbart — gemessen gegen eine
*handannotierte* Referenz. Die Zahlen sind deshalb nicht direkt mit unseren
vergleichbar; was sie sagen, ist, dass ein blanker bi-affiner Kopf auf LiLT
keine Architektur ist, die eine Aufgabe dieser Art mühelos löst. Der Sprung
auf 0.8945 kommt bei GeoLayoutLM ausdrücklich vom relationsspezifischen
Pretraining, und das baut in einem Semester niemand nach.

**Der direkte Sprung zum end-to-end-Relationskopf ist damit nicht der
nächste Schritt — der Weg als solcher aber sehr wohl.** Als diese Recherche
entstand, lag die geschätzte Decke bei 0.70–0.75, und ein Encoder hätte
danach um wenige Punkte gekämpft. Die gemessene Decke von 0.916 (nächster
Abschnitt) ändert diese Rechnung: Es sind rund 14 Punkte zu holen, und der
Fehlermodus, auf den ein Textencoder zielt, ist belegt.

**Was trotzdem fehlt, ist real:** In den 35 Merkmalen steckt keine einzige
lexikalische Information. Der belegte Legendenfall `1347387_p31` („④
Pflanztopf-Set … je Set 8.99" / „⑤ Fensterdoppelrollo … je Stück 9.99")
hängt an einem Textmarker, den kein Merkmal sehen kann. Der billige Weg
dorthin sind eingefrorene LiLT-Span-Embeddings als zusätzlicher
Merkmalsblock — einmal je Seite vorrechnen und cachen, dann lernt nur der
Kopf. Der Messaufbau mit fünf Folds bleibt unverändert, und alles bleibt
lokal. End-to-end hieße fünf Fold-Finetunings je Gitterzelle; die GPU
bräuchte man dann für die Messung, nicht fürs Training.

## Einordnung gegen die Literatur

Die DocILE-Baselines für Line Item Recognition liegen bei F1 0.594–0.721
(LayoutLMv3 0.721), und im ICDAR-2023-Wettbewerb blieb alles unter 0.80 —
auf einem größeren, handannotierten Datensatz.

**Die Zahlen sind trotzdem nicht direkt vergleichbar, und das gehört
dazugesagt.** DocILE-LIR ist micro-F1 über *Felder* unter maximalem
Line-Item-Matching: teilrichtige Zeilen zählen anteilig. Das ist deutlich
nachsichtiger als unser `group_f1` mit exakter Mengengleichheit und liegt
näher an unserem Paar-F1 (0.929). Wer 0.778 strikt neben 0.721 nachsichtig
stellt, vergleicht zwei Protokolle — dieselbe Schema-Falle wie `strict`
gegen `type` beim NER, nur in die andere Richtung.

## Die Decke ist gemessen — und liegt weit über der Schätzung

Nach dem Sprung auf 0.778 war die naheliegende Frage, wie viel überhaupt
noch geht. Die Antwort war bis dahin eine Rechnung: 5,97 Entities je Gruppe,
exakte Mengengleichheit verlangt, also bei 0.95 Trefferquote je Entity
0.95⁶ ≈ 0.74. Danach wäre 0.778 praktisch am Anschlag.

Die Rechnung ist falsch, und zwar messbar. Drei unabhängige Zweit-Annotatoren
(anderes Modell als der Erst-Teacher, anderer Prompt, ohne Einsicht in die
bestehende Gruppierung) haben 26 Dev-Seiten neu gruppiert — je eine pro
Duplikat-Cluster. Gemessen mit der dafür neu gebauten Option `magda
offers-gold --groups-from`:

| | Paar-F1 | Gruppen-F1 |
|---|---:|---:|
| **Teacher gegen Teacher (Decke)** | **0.970** | **0.916** |
| Paarmodell (56 Dev-Seiten) | 0.929 | 0.778 |
| Heuristik (dieselben 26 Seiten) | 0.851 | 0.566 |

**Der Grund für die Abweichung ist, dass die Fehlerpotenz die falsche
Annahme trifft.** 0.95⁶ setzt voraus, dass sich zwei Annotatoren an jeder
Entity unabhängig irren. Tatsächlich sehen beide dasselbe Bild: Die meisten
Kacheln sind eindeutig, und wo eine schwierig ist, ist sie es für beide.
Die Fehler sind stark korreliert, und die Decke liegt entsprechend höher.
Wer sie über eine Potenz schätzt, unterschätzt sie systematisch.

**Damit ist die eigentliche Aussage der Woche eine andere als der Sprung
selbst:** Über 0.778 liegen rund **14 Punkte Luft**, nicht null bis acht.
Die Arbeit an der Gruppierung lohnt weiter, und es gibt jetzt einen
Vergleichspunkt, gegen den jede künftige Verbesserung gemessen werden kann.

### Wie die Messung aufgebaut ist

Die Sperre ist der Kern: Die Zweit-Annotatoren durften
`data/offer_groups/claude-sonnet-5/` nicht ansehen, weder direkt noch über
`offers-teacher view` oder die Reports unter `data/eval/`. Wer die erste
Gruppierung kennt, ankert daran, und die gemessene Übereinstimmung wäre eine
Aussage über das Ankern statt über die Aufgabe.

`--groups-from` misst nur dort, wo *beide* Seiten gruppiert haben. Eine dem
System fehlende Seite als leere Ausgabe zu werten hieße „alles falsch" statt
„nicht gemessen" — derselbe Fehler, den `load_reference` für die Referenz
schon vermeidet. `test_offers_gold_groups_from.py` hält das fest; der Test
wurde durch Ausbau der Filterzeile auf Wirksamkeit geprüft und wird dabei
rot.

### Zwei Lücken, die dabei aufgefallen sind

**`offer_teacher.PROMPT_VERSION` ist eine Nummer ohne Text.** Der Prompt, mit
dem die gesamte Referenz `claude-sonnet-5` entstand, ist nirgends gespeichert
— er lebte in der Konversation. Die Referenz ist damit nicht reproduzierbar,
und ein zweiter Lauf nicht exakt vergleichbar. Ab Version 2 steht der Prompt
in `docs/offer-teacher-prompt.md`.

**Die Konstante ist nicht pro Lauf setzbar.** Die neuen
`claude-opus-5`-Dateien tragen deshalb `prompt_version: 1`, obwohl sie mit
dem neuen Prompt entstanden. Wer Versionen auseinanderhalten will, muss über
`provenance.model` gehen.

## Einschränkungen

- **56 Dev-Seiten in 25 Duplikat-Clustern, kein Konfidenzintervall.** Für
  die Differenz Paarmodell gegen Heuristik wäre ein gepaarter Bootstrap
  über Cluster fällig; `offer_grid.paired_bootstrap` kann das, ist hier aber
  nicht gelaufen.
- **Dev stammt aus den Trainingswochen.** Gemessen wird In-Distribution-Fit,
  nicht Generalisierung über die Zeit. Der Testsplit ist unangetastet.
- **Der Richter ist ein LLM.** `data/offer_groups/claude-sonnet-5/` ist
  maschinell erzeugt; die Zahl heißt Übereinstimmung, nicht Richtigkeit.
  Wie groß der Eigenfehler des Lehrers ist, ist unbekannt — die
  arithmetische Gegenprobe legt auf der prüfbaren Hälfte rund 7 % nahe.
- **Die Schwellenwahl `--objective group_f1` fiel, nachdem beide Schwellen
  auf Dev gemessen waren.** Die Dev-Zahl ist dadurch leicht optimistisch.
  Mit dem neuen Plateau wiegt das weniger als vorher, verschwindet aber
  nicht.
- **Die Decke ist auf 26 Seiten gemessen, das Modell auf 56.** Nicht
  dieselbe Menge. Die Heuristik als gemeinsamer Bezugspunkt steht auf den
  26 Seiten bei 0.566 gegen 0.524 auf den 56 — die Vertreterseiten sind
  also eher etwas leichter. Ein Konfidenzintervall für die 0.916 gibt es
  nicht.
- **Der Zweit-Annotator variierte Modell und Prompt gleichzeitig.** Gemessen
  ist damit die Übereinstimmung zweier Annotatoren, nicht der
  Modellunterschied allein. Für eine Obergrenze ist das konservativ: ein
  abweichender Prompt senkt die Übereinstimmung eher, als dass er sie hebt.
- **`MAX_COMPONENT = 120` deckt die größte beobachtete Komponente mit
  Reserve, ist aber keine Garantie.** Ob der Wert reicht, sagt
  `LAST_RUN["capped"]` in jedem Report — steht dort etwas anderes als 0,
  ist die Kurve wieder nur teilweise ein ILP-Ergebnis.

## Was daraus für die Arbeitsweise folgt

**Eine Notbremse gegen Rechenzeit ist keine neutrale Optimierung.** Sie
greift bevorzugt dort, wo das Verfahren gebraucht wird — bei den großen,
schwierigen Komponenten — und *verbessert* dabei scheinbar die Laufzeit.
Ein Parameter, den niemand als Modellparameter liest, war über Wochen der
größte Hebel auf die Ergebnisqualität.

**Sichtbar wurde es nur, weil ein Zähler mitlief.** `offer_ilp.LAST_RUN`
zählt Kappungen seit jeher, aber der Report von `magda offers-model` gab
ihn bis zum 29.08.2026 nicht aus, obwohl der eigene Docstring ihn „in jedem
Report" verlangt. Er steht jetzt in der Kalibrierung wie in der Auswertung.
Ein Zähler, den kein Report ausgibt, ist keiner.

**Und die Lehre für die Suche nach Verbesserungen:** Vor der nächsten
Merkmals- oder Architekturidee lohnt der Blick auf die Konstanten, die
zwischen Modell und Metrik stehen. Die Antwort auf „das muss doch besser
gehen" lag nicht im Modell.

## Offen

- **Die Deckenmessung auf mehr Seiten wiederholen** und ein
  Konfidenzintervall dazu rechnen. 26 Seiten tragen die Richtung, nicht die
  zweite Nachkommastelle.
- **Konfidenzintervall für den Dev-Vorsprung** über einen gepaarten
  Bootstrap über die 25 Cluster.
- **Die Ablationen auf der vollen Referenz wiederholen.** Die Null-Befunde
  zu Farbe und Anker stammen aus einem Lauf über 75 Seiten; die Referenz
  hat inzwischen 666. Ein echter +0.02-Effekt läge in beiden Intervallen
  unentdeckt. Dazu kommt, dass beide mit gekapptem ILP gemessen wurden.
- **Lexikalische Merkmale** als neuer Block — `FEATURE_BLOCKS` ist genau
  dafür gebaut. Legendenmarker, Ordnungsrelationen über Preiswerte,
  „Aktion" als Grenzsignal. Durch die gemessene Decke ist das kein
  Griff ins Blaue mehr: 14 Punkte Luft, und der Zielfehler ist belegt.
- **Eingefrorene LiLT-Span-Embeddings** als weiterer Block, danach. Einmal
  je Seite vorrechnen und cachen, dann lernt nur der Kopf — lokal, im
  bestehenden Messaufbau. Erst wenn das trägt, lohnt die Frage nach
  end-to-end und damit nach der GPU.
- **Der Endvergleich gegen die LLM-Blackbox.** `magda blackbox-eval` ist
  gebaut und ungefahren; drei Entscheidungen sind getroffen (kein neutraler
  Richter, beste lokale Konfiguration, `sonnet-5` als Baseline), das Design
  steht aus. Der Testlauf ist nicht wiederholbar.
