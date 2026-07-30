# Woche 3 — Vollständige Annotation, erstes echtes Training

Stand: 30.07.2026

## Kurzfassung

Alle 196 Prospektseiten sind annotiert, drei Labeling-Modelle sind über den
gesamten Korpus gelaufen, und beide Modellvarianten wurden zum ersten Mal
trainiert und evaluiert.

| | Woche 1 | Woche 3 |
|---|---:|---:|
| Trainingsseiten | 32 | 81 |
| Testseiten | 4 | 107 |
| Test-F1 GBERT | 0.333 | 0.908 |
| Test-F1 LayoutXLM | nie gelaufen | 0.895 |
| F1 BRAND | 0.10 | 0.938 |
| F1 PRODUCT | 0.08 | 0.807 |

Der Sprung kommt von den Labels, nicht vom Modell. Die Zahlen stehen über
einem Split, der KW30 trainiert und KW31 testet; ein Zufallssplit über Seiten
lieferte 0.929 und 0.930, war aber undicht (siehe Training).

Layout bringt nach wie vor nichts. Das ist der Befund, um den es im Proposal
geht, und er fällt gegen die Erwartung aus.

## Annotation

Zu Beginn der Woche gab es drei handannotierte Seiten. Das reicht weder zum
Messen noch zum Trainieren, und der Engpass war damit nie das Training,
sondern die Referenz.

Die Vorannotation hat Claude übernommen, aufgeteilt auf parallel arbeitende
Agenten mit einer gemeinsamen schriftlichen Anweisung. Jede Seite durchläuft
dieselben vier Schritte: Seitenbild ansehen, Wortliste mit Indizes lesen,
Spans setzen, Kontrollausgabe gegen das Bild prüfen. Herausgekommen sind 8630
Spans auf 193 Seiten, im Schnitt 44,6 je Seite.

| Label | Spans | | Label | Spans |
|---|---:|---|---|---:|
| PRODUCT | 1677 | | DISCOUNT | 739 |
| PRICE | 1610 | | VALID | 183 |
| QUANTITY | 1336 | | APP_PRICE | 57 |
| UNIT_PRICE | 1196 | | | |
| BRAND | 1067 | | | |
| OLD_PRICE | 765 | | | |

Zwei Verhältnisse taugen als Plausibilitätsprüfung und gehen auf. PRODUCT und
PRICE liegen fast gleichauf, was zu Prospektangeboten passt: zu jedem Produkt
gehört genau ein Preis. VALID kommt 183-mal bei 196 Seiten vor, also fast
genau einmal je Seite, was dem Gültigkeitsbanner im Seitenkopf entspricht.

BRAND liegt mit 1067 deutlich unter PRODUCT, und das ist kein
Annotationsfehler, sondern eine Grenze des Ansatzes. Marken, die nur als Logo
im Bild stehen — Russell Hobbs, KESPER, Krups, die Bierlogos — haben im
PDF-Textlayer kein einziges Wort, auf das ein Span zeigen könnte. Solange wir
ausschließlich den Textlayer nutzen, sind diese Marken prinzipiell unsichtbar.

Alle 193 Seiten tragen `status: "in_progress"` und den Urheber
`sonnet-5 (vorannotiert, ungeprueft)`. `gold.load_gold_pages()` akzeptiert nur
`status == "done"`, die Seiten zählen also für keine Messung gegen Gold, bis
ein Mensch sie im Annotator freigibt. Referenz sind weiterhin die drei von
Hand annotierten Seiten. Wer eine maschinelle Vorannotation zum Goldstandard
erklärt und dann Modelle dagegen misst, misst im Kreis.

## Prüfung der Vorannotation

Geprüft wurde auf zwei Wegen, weil sie verschiedene Fehlerarten finden.

Mechanisch über alle 8630 Spans: kein Span enthält das Wort `oder`, kein
Zahl-Label steht ohne Ziffer, es gibt keine Überlappungen und kein unbekanntes
Label. Ein einziger Treffer bei der Grundpreisklammer, und der sagt mehr über
unseren Guard als über die Annotation: `Besteckkasten* (o.Abb.),` heißt „ohne
Abbildung", enthält aber eine öffnende Klammer, an der `trim_spans()` jeden
Nicht-UNIT_PRICE-Span abschneidet. Gemessen an 322 verhinderten echten
Verstößen ist das ein akzeptabler Preis, den man aber kennen sollte. Die
Prüfung misst ohnehin nur Regelkonformität; ein durchgehend falsch, aber
konsistent gesetztes Label bestünde sie mühelos.

Inhaltlich hat ein separater Agent sechs Seiten Span für Span gegen das
Seitenbild geprüft, inklusive Nachrechnen der Grundpreise. Ein belastbarer
Fund: auf `1347411_p42` ist `1-l-Sonderedition` als QUANTITY markiert, obwohl
die Füllmenge `1 l` bereits separat erfasst ist. Belegt ist das über den
Duplikatvergleich — die fast identische Seite `1347387_p46` enthält denselben
Wortlaut korrekt ohne Label. Zwei weitere Punkte kamen ausdrücklich als
Auslegungsgrenzfälle zurück: `SMIRNOFF No 21` (endet BRAND bei `SMIRNOFF`?)
und `HOME IDEAS Living` (gehört `Living` zur Marke?).

Zahlen von Subagenten werden inzwischen nachgerechnet, bevor sie in einen
Bericht kommen. In Woche 2 meldete ein Prüfagent „100 % F1 gegen Gold", die
eigene Nachmessung ergab 0.306. Günstige Zahlen sind die, die man prüfen muss.

## Drei Labeling-Arme

`data/labeled/` ist nach Modell getrennt. Flach gespeichert überschriebe der
zweite Lauf den ersten, und die Frage, ob Qwen näher am Goldstandard labelt
als Mistral, wäre danach nicht mehr zu beantworten.

| Ordner | Seiten | F1 gegen Gold (3 Seiten) |
|---|---:|---:|
| `qwen3.5-397b-a17b` | 196 | 0.836 |
| `sonnet-5` | 196 | 0.816 |
| `mistral-medium-3.5-128b` | 196 | 0.788 |
| `mistral-…-promptv1` | 196 | 0.306 |

Die letzte Zeile ist der alte Prompt, absichtlich aufbewahrt. Der Abstand von
0.306 auf 0.788 bei identischem Modell ist die Wirkung der
Prompt-Überarbeitung aus Woche 2 und größer als jeder Unterschied zwischen den
Modellen. Umgekehrt sind drei Seiten eine schmale Basis: der Abstand zwischen
Qwen und Claude ist innerhalb dieser Basis kein Befund.

Das Labeling der fehlenden Mistral-Seiten scheiterte zunächst an HTTP 429. Ein
Ping gegen beide Modelle zeigte, dass die Sperre auf Kontoebene lag und nicht
am einzelnen Modell; der Wiederholungsplan wurde daraufhin von Sekunden auf
bis zu 300 Sekunden über fünf Anläufe gestreckt, und der spätere Lauf ging
über 115 Seiten ohne Fehlschlag durch.

### Wo Claude und Qwen sich widersprechen

Über alle 196 Seiten stimmen die beiden Arme zu 82,2 % der Wörter überein.
Interessanter als die Zahl ist, dass die Abweichung genau eine Ursache hat.
Wörter, die nur Qwen labelt:

| Label | Häufigste Wortlaute |
|---|---|
| QUANTITY | `je`×176, `x`×134, `B`/`H`/`T`/`L`×182, `cm`×88, `ca.`×57 |
| PRODUCT | `je`×195, `Kl.`×26, `I,`×22, `Haltungsform`×26, `100%`×20 |
| BRAND | `Living`×10 |

Das sind die Regeln, die in der Annotationsanweisung stehen, aber nie in den
Labeling-Prompt übernommen wurden: `Kl. I` und Werbetext gehören nicht ins
PRODUCT, `je` und `ca.` nicht in die Menge, Abmessungen und Leistung sind
keine Füllmenge. Qwen macht innerhalb seines eigenen Regelwerks keinen Fehler,
es befolgt ein anderes. Die beiden Konventionen sind auseinandergelaufen.

Daraus folgt auch, dass Qwens 0.836 gegenüber einer Referenz aus der Zeit vor
diesen Festlegungen gilt. Gegen die heutige Konvention gemessen fiele der Wert
niedriger aus. Offen bleibt, den Prompt an die Anweisung anzugleichen und den
mechanisch entscheidbaren Teil in `trim_spans()` zu verlegen: `je`, `ca.`,
`Kl.`, `Haltungsform` sind feste Wortlisten, und ein Guard setzt die
Fehlerrate auf null, wo eine Prompt-Regel sie nur senkt.

## Training

Trainiert wurde auf `data/labeled/sonnet-5/`, 10 Epochen, Lernrate 5e-5,
Batch 8. Zuerst über einen Zufallssplit (158/19/19), dann über einen
Wochen-Split (81/8/107), nachdem sich der erste als undicht erwiesen hatte.

### Das Leck im Zufallssplit

Penny gibt je Woche 44 fast identische Regionalausgaben heraus, und die
Entdopplung greift erst ab Jaccard 0.95. Seiten bei 0.939 oder 0.949
überleben sie um Haaresbreite und landen dann auf verschiedenen Seiten des
Splits. Für jede Testseite die ähnlichste Trainingsseite gesucht: Median
0.851, sechs von 19 Testseiten mit einem Zwilling ab 0.9, zwölf ab 0.7.

Der Effekt lässt sich beziffern, indem man dasselbe Modell nach Nähe getrennt
auswertet. Testseiten mit nahem Zwilling kommen auf F1 0.944, die sieben ohne
auf 0.886. Das Leck schönt die Zahl um fünf bis sechs Punkte, erklärt sie aber
nicht — auswendiggelernt sähe eher nach 0.99 gegen 0.55 aus.

### Der Wochen-Split

Der Korpus enthält zwei Erscheinungswochen, KW30 (Kataloge 1342812–1342929)
und KW31 (1347375–1347504). KW30 lernt, KW31 testet, kein Katalog kommt in
beiden vor. Die Woche steht nirgends in den Daten, ist aber aus dem Abstand
der Katalog-IDs ableitbar: innerhalb einer Woche liegen sie höchstens 24
auseinander, zwischen den Wochen klaffen 4446. `dataset.group_by_week()`
schneidet bei einer Lücke über 200; feste ID-Bereiche wären beim nächsten
Erntelauf veraltet.

| | Seiten-Split | Wochen-Split |
|---|---:|---:|
| train / dev / test | 158 / 19 / 19 | 81 / 8 / 107 |
| Median-Ähnlichkeit Test ↔ Lernmenge | 0.851 | 0.257 |
| Testseiten mit Zwilling ≥ 0.9 | 6 von 19 | 0 von 107 |
| ≥ 0.7 | 12 von 19 | 3 von 107 |

Die drei Restfälle liegen bei höchstens 0.824 und sind keine
Regionalzwillinge, sondern wiederkehrende Seitentypen — die Obst-und-
Gemüse-Seite sieht jede Woche ähnlich aus.

### Ergebnis auf 107 Testseiten

| Label | GBERT | LayoutXLM | Δ | n |
|---|---:|---:|---:|---:|
| DISCOUNT | 0.998 | 1.000 | +0.002 | 321 |
| UNIT_PRICE | 0.985 | 1.000 | +0.015 | 514 |
| QUANTITY | 0.951 | 0.933 | −0.018 | 606 |
| BRAND | 0.938 | 0.939 | +0.001 | 508 |
| OLD_PRICE | 0.924 | 0.874 | −0.050 | 292 |
| PRICE | 0.899 | 0.882 | −0.017 | 724 |
| VALID | 0.885 | 0.905 | +0.020 | 93 |
| PRODUCT | 0.807 | 0.783 | −0.024 | 786 |
| APP_PRICE | 0.000 | 0.000 | ±0 | 57 |
| micro avg | **0.908** | **0.895** | −0.013 | 3901 |
| macro avg | 0.821 | 0.813 | −0.008 | 3901 |

Mit 45 % weniger Trainingsdaten und ohne Leck fällt GBERT von 0.929 auf 0.908.
Die Leckmessung hatte eher 0.89 als Untergrenze nahegelegt; auswendiggelernt
war hier nichts. Auseinanderhalten lassen sich die beiden Effekte nicht,
weniger Daten und kein Leck wirken gleichzeitig. Der Testsatz ist dafür von 19
auf 107 Seiten gewachsen, die Zahl also erheblich besser abgestützt.

APP_PRICE bricht auf 0.000 ein, und das ist der interessanteste Nebenbefund.
Das Label hat in KW30 zwei Spans auf einer Seite und in KW31 57 Spans auf 46
Seiten: Penny hat den App-Preis dazwischen breit ausgerollt. Das Modell hat
ihn nie gesehen und sagt ihn kein einziges Mal voraus. Ohne APP_PRICE läge
GBERT bei 0.914 und LayoutXLM bei 0.902. Ein Zufallssplit hätte die 57 Spans
über Train und Test verteilt und eine passable Zahl geliefert — der Befund
wäre unsichtbar geblieben. Genau dafür ist ein zeitlicher Split da: er misst
Generalisierung über die Zeit, und das ist der Einsatzfall.

### Layout bringt nichts

Im Zufallssplit lagen GBERT und LayoutXLM gleichauf (0.929 gegen 0.930), über
Wochen getrennt liegt GBERT 1,3 Punkte vorn. OLD_PRICE, das einzige Label mit
klarem Layout-Vorteil im ersten Lauf (+0.056), dreht auf −0.050.

Das trifft die Hypothese des Projekts. Die Erwartung aus Woche 1 lautete:
Preise erkennt man am Textmuster, Marke gegen Produktname aber erst an der
Position auf der Seite. BRAND lag damals bei 0.10 und erreicht heute 0.938,
ohne jede Positionsinformation. Der Unterschied lag also nie am Layout,
sondern an den Labels.

Zu Vorsicht mahnt, dass 81 Trainingsseiten für ein Modell mit zusätzlichem
visuellen Backbone knapp sind. Gestützt wird die These davon aber nicht.

PRODUCT bleibt mit 0.807 das Schlusslicht und der einzige Wert deutlich unter
0.9. Das ist dieselbe Grenze, an der sich auch die Annotations-Agenten reihum
gerieben haben: wo endet die Sorte, wo beginnt der Werbetext? `Löslicher
Kaffee Classic,` gehört dazu, `Zu 100% aus Hartweizen` nicht — aber
`Gewürzt, Paprika,`? `4-lagig,`? Das ist eine Konventionslücke, die sich in
die Labels und von dort ins Modell fortpflanzt.

## Was die Zahlen nicht sagen

Die wichtigste Einschränkung: 0.908 misst, wie gut GBERT die Claude-Annotation
reproduziert, nicht wie gut es Prospekte versteht. Trainiert und getestet wird
gegen dieselbe Label-Quelle, und die ist von keinem Menschen freigegeben. Die
Obergrenze der Zahl ist die Qualität der Vorannotation. Das ist übliches
Vorgehen und kein Fehler, aber jede Nennung muss es mittragen. Kein Split
behebt es, nur die menschliche Freigabe.

Der Testsatz ist außerdem in sich redundant. Die 107 Seiten bilden bei Jaccard
0.7 nur 66 Cluster, der größte umfasst elf Seiten. Nichts davon steckt im
Training, es ist also kein Leck — aber eine Seite aus dem elfer Cluster zählt
elffach ins Ergebnis. Die effektive Stichprobe sind rund 66 unabhängige
Seiten, und das Konfidenzintervall ist breiter, als 3901 Entitäten suggerieren.
Der Dev-Split ist mit acht Seiten zu klein für Modellauswahl; bei zwei Wochen
ist das der Preis dafür, dass Dev aus den Trainingswochen kommen muss.

Seiten über 512 Subwords werden abgeschnitten, und die beiden Varianten
tokenisieren verschieden: GBERT nutzt BERT-WordPiece, LayoutXLM das
SentencePiece von XLM-RoBERTa, das deutsche Komposita sparsamer zerlegt. Auf
den 19 Testseiten des ersten Splits verlor GBERT dadurch 531 Wörter,
LayoutXLM 368. Keines der Modelle wird für das Abgeschnittene bestraft, aber
die Mengen sind nicht identisch, und im Betrieb wären das verlorene Angebote,
die in keiner Metrik auftauchen. Zusammen mit dem Flair-Befund aus Woche 2 ist
das das zweite Argument für ein Sliding Window.

## Infrastruktur

Trainiert wurde auf gemieteten Pods (erst eine NVIDIA L4, dann eine RTX A5000
für 0,27 $/h). Der Grund ist nicht Rechenzeit — GBERT braucht 96 Sekunden,
LayoutXLM 254 — sondern Arbeitsspeicher: auf einem 8-GB-Mac füllt LayoutXLM
den Swap und die Maschine wird unbenutzbar. Gesamtkosten beider Trainingsrunden
rund 0,45 $.

`magda bundle` packt Code, Labels, Split und Seitenbilder in
ein Tar von 17 MB. Der Code kommt per `git ls-files` statt `git clone` — der
lokale Stand war 109 Commits vor GitHub, ein Klon hätte den Stand von
vorletzter Woche trainiert. Ohne `split.json` bricht der Export ab, weil die
fremde Maschine sonst klaglos einen eigenen Split würfelt und die Zahlen nicht
mehr vergleichbar sind. Die Bilder gehen auf 224×224 herunter, mit demselben
bilinearen Filter, den `LayoutLMv2ImageProcessor` ohnehin anwendet.

Fünf Fehler standen dazwischen, alle inzwischen behoben:

1. `get_or_create_splits()` würfelte über die Seiten, für die es gerade Labels
   gab. Ein Training bei 141 von 196 Seiten hätte einen Split für 141 Seiten
   eingefroren — dauerhaft, denn er wird genau einmal gezogen — und die 55
   nachgelieferten wären sämtlich im Training gelandet.
2. LayoutXLM war nie trainierbar. `LayoutDataset` lieferte nur Wörter und
   Boxen, aber der visuelle Backbone von LayoutLMv2 ist Teil des
   Vorwärtsdurchlaufs. Der Fehler war noch dazu nichtssagend (`'NoneType'
   object has no attribute 'tensor'`, tief im Backbone) und nie aufgefallen,
   weil diese Variante schlicht noch nie gestartet worden war. Gefunden hat
   ihn ein Forward-Pass mit Batch-Größe 1 vor dem Mieten: 40 Sekunden CPU
   statt einer Pod-Stunde Fehlersuche.
3. PEP 668. Die Python-Installation gängiger GPU-Images ist als „externally
   managed" markiert, pip verweigert dort jede Installation, und das Bootstrap
   starb in der ersten Zeile.
4. detectron2 importiert `torch` schon in seiner `setup.py`, um gegen die
   richtige CUDA-Version zu übersetzen. In pips Build-Sandbox gibt es kein
   torch, auf einer Maschine, auf der torch längst installiert ist.
   `--no-build-isolation` behebt es.
5. Zwei Pods meldeten `torch.cuda.is_available() == True` und brachen bei der
   ersten Allokation ab. `nvidia-smi` zeigte 0 MiB belegt, keine Prozesse und
   100 % Auslastung: ein Nachbarcontainer hielt die Karte. Der dritte Pod
   landete auf demselben Host und scheiterte identisch. Die Prüfung im
   Bootstrap fasst die Karte jetzt wirklich an (`torch.zeros(8,
   device="cuda")`), statt sie nur zu fragen — sonst schlägt der Fehler erst
   nach der zehnminütigen detectron2-Übersetzung mitten im Trainer auf.

## Offen

- Vorannotation von Hand freigeben. Bis dahin ist 0.908 eine Zahl über
  Konsistenz, nicht über Richtigkeit. Priorität eins.
- PRODUCT-Konvention schärfen: Sorte gegen Beschreibungstext, mit
  Beispielliste. Einziges Label unter 0.9 und häufigste Rückfrage der
  Annotation.
- Labeling-Prompt an die Anweisung angleichen, mechanisch Entscheidbares in
  `trim_spans()`.
- Den bestätigten Annotationsfehler korrigieren (`1347411_p42`,
  `1-l-Sonderedition`).
- Prüfen, ob APP_PRICE in KW30 wirklich fehlte oder ob die Annotation ihn dort
  übersehen hat. Das entscheidet, ob die 0.000 ein Verteilungsbefund oder ein
  Datenfehler sind.
- Dritte Woche ernten. Acht Dev-Seiten sind zu wenig, und 107 Testseiten
  enthalten nur 66 unabhängige Cluster.
- Team-Entscheidungen weiter offen: Sliding Window für Seiten über 512
  Subwords, endgültiges Label-Set. Erledigt ist die Frage nach einem Split
  über Kataloge — der Wochen-Split beantwortet sie schärfer, als sie gestellt
  war.
- Marken ohne Textlayer bleiben eine prinzipielle Grenze. Wer sie erfassen
  will, kommt an echtem OCR auf dem Seitenbild nicht vorbei.
