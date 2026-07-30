# Woche 3 — Vollständige Annotation und die erste belastbare Trainingszahl

**Stand: 30.07.2026**

## Kurzfassung

Alle 196 Prospektseiten sind annotiert, drei Labeling-Modelle sind über den
gesamten Korpus gelaufen, und beide Modellvarianten wurden zum ersten Mal
vollständig trainiert und evaluiert.

| | Woche 1 | Woche 3 |
|---|---:|---:|
| Trainingsseiten | 32 | 158 |
| Testseiten | 4 | 19 |
| Test-F1 GBERT | 0.333 | **0.929** |
| Test-F1 LayoutXLM | — (nie gelaufen) | **0.930** |
| F1 BRAND | 0.10 | 0.951 |
| F1 PRODUCT | 0.08 | 0.803 |

Der Sprung kommt nicht vom Modell. Er kommt von den Labels.

Diese Zahlen stehen über einem Zufallssplit, und der leckt (Abschnitt 6). Nach
dem Wechsel auf einen **Wochen-Split** — KW30 lernen, KW31 testen, kein
gemeinsamer Katalog — bleibt GBERT bei **0.908** und LayoutXLM fällt auf
**0.895** (Abschnitt 7). Das ist die Zahl, die wir berichten.

---

## 1. Von drei annotierten Seiten auf 196

Der Engpass war nie das Training, sondern die Referenz. Zu Beginn der Woche
gab es drei handannotierte Seiten — zu wenig, um irgendetwas zu messen, und
viel zu wenig, um darauf zu trainieren.

Die Vorannotation hat Claude übernommen, aufgeteilt auf parallel arbeitende
Agenten mit einer gemeinsamen, schriftlich fixierten Anweisung. Jede Seite
durchläuft dieselben vier Schritte: Seitenbild ansehen, Wortliste mit Indizes
lesen, Spans setzen, Kontrollausgabe gegen das Bild prüfen.

**Ergebnis: 8630 Spans auf 193 Seiten, im Schnitt 44,6 je Seite.**

| Label | Spans |
|---|---:|
| PRODUCT | 1677 |
| PRICE | 1610 |
| QUANTITY | 1336 |
| UNIT_PRICE | 1196 |
| BRAND | 1067 |
| OLD_PRICE | 765 |
| DISCOUNT | 739 |
| VALID | 183 |
| APP_PRICE | 57 |

Zwei Verhältnisse sind Plausibilitätsprüfungen, die aufgehen: PRODUCT (1677)
und PRICE (1610) liegen fast gleichauf — bei Prospektangeboten gehört zu jedem
Produkt genau ein Preis. VALID kommt 183-mal bei 196 Seiten vor, also fast
exakt einmal pro Seite, was dem Gültigkeitsbanner im Seitenkopf entspricht.

BRAND liegt mit 1067 deutlich unter PRODUCT. Das ist kein Annotationsfehler,
sondern eine harte Grenze unseres Ansatzes: **Marken, die nur als Logo im Bild
stehen** — Russell Hobbs, KESPER, Krups, die Bierlogos — haben im PDF-Textlayer
kein einziges Wort. Es gibt keinen Wortindex, auf den ein Span zeigen könnte.
Solange wir ausschließlich den Textlayer nutzen, sind diese Marken für unser
Modell unsichtbar, und zwar prinzipiell.

### Was der Status `in_progress` bedeutet

Alle 193 Seiten tragen `status: "in_progress"` und den Urheber
`sonnet-5 (vorannotiert, ungeprueft)`. `gold.load_gold_pages()` akzeptiert nur
`status == "done"`. Die Seiten zählen damit **für keine einzige Messung gegen
Gold**, bis ein Mensch sie im Annotator freigibt. Referenz sind weiterhin die
drei von Hand annotierten Seiten.

Das ist Absicht und keine Formalie: Wer eine maschinelle Vorannotation zum
Goldstandard erklärt und dann Modelle dagegen misst, misst im Kreis.

---

## 2. Prüfung der Vorannotation

Zwei unabhängige Prüfungen, weil sie verschiedene Fehlerarten finden.

### Mechanisch, über alle 8630 Spans

| Prüfung | Verstöße |
|---|---:|
| Span enthält das Wort `oder` | **0** |
| Grundpreisklammer in Nicht-UNIT_PRICE-Span | 1 |
| Zahl-Label ohne jede Ziffer | **0** |
| Überlappende Spans | **0** |
| Unbekanntes Label | **0** |

Der eine Klammertreffer ist `Besteckkasten* (o.Abb.),` — „ohne Abbildung", kein
Grundpreis. Das ist ein Befund über unseren eigenen Guard: `trim_spans()`
schneidet jeden Nicht-UNIT_PRICE-Span an der öffnenden Klammer ab, weil dort
fast immer der Grundpreis steht. Bei `(o.Abb.)` liegt er falsch. Gemessen an
322 verhinderten echten Verstößen ist das ein akzeptabler Preis — aber man
sollte wissen, dass man ihn zahlt.

Diese Prüfung misst **Regelkonformität, nicht Richtigkeit.** Ein durchgehend
falsch, aber konsistent gesetztes Label bestünde sie mühelos.

### Inhaltlich, an sechs Seiten gegen die Bilder

Ein separater Agent hat sechs Seiten Span für Span gegen das Seitenbild
geprüft, inklusive Nachrechnen der Grundpreise. **Ein belastbarer Fund:**

Auf `1347411_p42` ist `1-l-Sonderedition` als QUANTITY markiert, obwohl die
Füllmenge `1 l` bereits separat erfasst ist. Belegt wurde das nicht durch
Behauptung, sondern durch Duplikatvergleich: die fast identische Seite
`1347387_p46` enthält denselben Wortlaut korrekt ohne Label.

Zwei weitere Punkte wurden ausdrücklich als Auslegungsgrenzfälle gemeldet,
nicht als Fehler: `SMIRNOFF No 21` (endet BRAND bei `SMIRNOFF`?) und
`HOME IDEAS Living` (gehört `Living` zur Marke?).

**Methodischer Hinweis, aus einem Fehler der Vorwoche gelernt:** Zahlen von
Subagenten werden nachgerechnet, bevor sie in einen Bericht kommen. In Woche 2
meldete ein Prüfagent „100 % F1 gegen Gold"; die eigene Nachmessung ergab
0.306. Günstige Zahlen sind genau die, die man prüfen muss.

---

## 3. Drei vollständige Labeling-Arme

`data/labeled/` ist nach Modell getrennt — flach gespeichert überschriebe der
zweite Lauf den ersten, und die Frage „labelt Qwen näher am Goldstandard als
Mistral?" wäre danach nicht mehr beantwortbar.

| Ordner | Seiten | F1 gegen Gold (3 Seiten) |
|---|---:|---:|
| `qwen3.5-397b-a17b` | 196 | 0.836 |
| `sonnet-5` | 196 | 0.816 |
| `mistral-medium-3.5-128b` | 196 | 0.788 |
| `mistral-…-promptv1` | 196 | 0.306 |

Die letzte Zeile ist der alte Prompt, absichtlich aufbewahrt. Der Abstand
0.306 → 0.788 bei identischem Modell ist die Wirkung der Prompt-Überarbeitung
aus Woche 2, und er ist größer als jeder Unterschied zwischen den Modellen.

**Drei Seiten sind eine schmale Basis.** Große Unterschiede sind
aussagekräftig, kleine nicht. Der Abstand zwischen Qwen (0.836) und Claude
(0.816) ist kein Befund.

### Der GWDG-Lauf und sein Kontingent

Das Labeling der fehlenden 115 Mistral-Seiten scheiterte zunächst an HTTP 429.
Ein einzelner Ping gegen beide Modelle zeigte, dass die Sperre auf Kontoebene
lag, nicht am einzelnen Modell. Der Wiederholungsplan wurde daraufhin von
Sekunden auf bis zu 300 Sekunden über fünf Anläufe gestreckt. Der spätere Lauf
ging über 115 Seiten mit **null Fehlschlägen** durch.

---

## 4. Wo Claude und Qwen sich widersprechen

Über alle 196 Seiten stimmen die beiden Arme zu **82,2 % der Wörter** überein.
Interessanter als die Zahl ist die Struktur der Abweichung — sie ist kein
Rauschen, sondern hat genau eine Ursache.

Wörter, die **nur Qwen** labelt:

| Label | Häufigste Wortlaute |
|---|---|
| QUANTITY | `je`×176, `x`×134, `B`/`H`/`T`/`L`×182, `cm`×88, `ca.`×57, `Ø`×16 |
| PRODUCT | `je`×195, `Kl.`×26, `I,`×22, `Haltungsform`×26, `100%`×20, `vol,`×18 |
| BRAND | `Living`×10 |

Das sind **exakt die Regeln, die in der Annotationsanweisung stehen, aber nie
in den Labeling-Prompt übernommen wurden**: `Kl. I` und Werbetext gehören nicht
ins PRODUCT (Teamentscheidung), `je` und `ca.` nicht in die Menge, Abmessungen
und Leistung sind keine Füllmenge.

Qwen macht innerhalb seines eigenen Regelwerks keinen Fehler. Es befolgt ein
*anderes* Regelwerk. Die beiden Konventionen sind auseinandergelaufen.

Daraus folgt auch: **Qwens 0.836 gilt gegenüber der Referenz, gegen die
gemessen wurde** — drei Seiten aus der Zeit vor diesen Festlegungen. Gegen die
heutige Konvention gemessen fiele der Wert niedriger aus.

Zwei Konsequenzen, noch offen:
1. Den Prompt in `labeling.py` an die Anweisung angleichen.
2. Der mechanisch entscheidbare Teil gehört in `trim_spans()` statt in den
   Prompt — `je`, `ca.`, `Kl.`, `Haltungsform` sind feste Wortlisten. Eine
   Prompt-Regel senkt die Fehlerrate, ein Guard setzt sie auf null.

---

## 5. Training

Trainiert wurde auf `data/labeled/sonnet-5/`, also auf der Claude-Annotation.
Aufteilung 158 / 19 / 19 Seiten, 10 Epochen, Lernrate 5e-5, Batch 8.

### Ergebnis auf dem Test-Split (19 Seiten, 712 Entitäten)

| Label | GBERT | LayoutXLM | Δ | n |
|---|---:|---:|---:|---:|
| UNIT_PRICE | 0.995 | 0.995 | ±0 | 95 |
| DISCOUNT | 0.993 | 0.993 | ±0 | 73 |
| QUANTITY | 0.981 | 0.964 | −0.017 | 103 |
| VALID | 0.957 | 1.000 | +0.043 | 11 |
| BRAND | 0.951 | 0.952 | +0.001 | 83 |
| OLD_PRICE | 0.932 | 0.988 | +0.056 | 79 |
| PRICE | 0.929 | 0.920 | −0.009 | 124 |
| PRODUCT | 0.803 | 0.794 | −0.009 | 139 |
| APP_PRICE | 0.500 | 0.000 | −0.500 | 5 |
| **micro avg** | **0.929** | **0.930** | **+0.001** | 712 |
| macro avg | 0.893 | 0.845 | −0.048 | 712 |

Beide Dev-Kurven laufen ab Epoche 3 flach bei 0.95–0.96. Zehn Epochen sind
großzügig; fünf hätten gereicht.

### Einschränkung: die beiden Zahlen stehen nicht über derselben Menge

Die Support-Spalte ist bei GBERT **712**, bei LayoutXLM **728**. Das ist kein
Rundungsfehler, sondern ein Unterschied in den Eingabedaten.

Beide Modelle schneiden Seiten über 512 Subwords ab (`truncation=True`), aber
sie tokenisieren verschieden: GBERT nutzt BERT-WordPiece, LayoutXLM das
SentencePiece von XLM-RoBERTa, das deutsche Komposita sparsamer zerlegt. Über
die 19 Testseiten gemessen:

| | Seiten über 512 Subwords | abgeschnittene Wörter |
|---|---:|---:|
| GBERT | 7 von 19 | **531** |
| LayoutXLM | 7 von 19 | **368** |

LayoutXLM sieht also 163 Wörter mehr und wird entsprechend über 16 Entitäten
mehr bewertet. Beide werden nur auf dem bewertet, was sie sehen — keines wird
für das Abgeschnittene bestraft. Aber die Mengen sind nicht identisch, und der
Abstand von 0.001 ist ohnehin zu klein, um daraus etwas abzuleiten.

Für die offene Sliding-Window-Frage ist das das zweite Argument nach dem
Flair-Befund: **531 Wörter auf 19 Testseiten sind für GBERT schlicht
unsichtbar** — im Betrieb wären das verlorene Angebote, die in keiner Metrik
auftauchen.

### Der zentrale Befund: Layout bringt nichts

**0.929 gegen 0.930.** Der Unterschied liegt weit innerhalb dessen, was bei 19
Testseiten Rauschen ist.

Das trifft die Hypothese des Projekts. Die Erwartung aus Woche 1 lautete:
Preise erkennt man am Textmuster, **Marke gegen Produktname aber erst an der
Position auf der Seite** — genau dafür sollte LayoutXLM da sein. BRAND lag
damals bei F1 0.10.

Heute erreicht BRAND **0.951 — ohne jede Layout-Information.** Das lag also nie
am fehlenden Layout. Es lag an den Labels.

Die einzige Stelle, an der LayoutXLM deutlich gewinnt, ist OLD_PRICE
(+0.056). Das ist plausibel: ob eine Zahl der Streichpreis ist, zeigt sich an
ihrer Position und Größe relativ zum Aktionspreis. Aber es ist ein Label von
neun, und macro avg fällt sogar.

**APP_PRICE 0.000 bei LayoutXLM ist kein Befund** — fünf Instanzen im
Testsplit. Bei so wenigen entscheidet ein einziger Treffer über 0.0 oder 0.5.

### PRODUCT bleibt das Schlusslicht

0.803 bei beiden Varianten, der einzige Wert deutlich unter 0.9. Das ist
dieselbe Grenze, an der sich auch die Annotations-Agenten reihum gerieben
haben: Wo endet die Sorte, wo beginnt der Werbetext? `Löslicher Kaffee
Classic,` gehört dazu, `Zu 100% aus Hartweizen` nicht — aber
`Gewürzt, Paprika,`? `4-lagig,`? `10% vol,`?

Das ist keine Modellschwäche. Das ist eine Konventionslücke, die sich in die
Labels und von dort ins Modell fortpflanzt.

---

## 6. Was die Zahlen nicht sagen

Die wichtigste Einschränkung des ganzen Berichts:

**0.929 misst, wie gut GBERT die Claude-Annotation reproduziert — nicht, wie
gut es Prospekte versteht.** Trainiert und getestet wurde gegen dieselbe
Label-Quelle, und diese Quelle ist von keinem Menschen freigegeben. Die
Obergrenze dieser Zahl ist die Qualität der Vorannotation.

Das ist übliches Vorgehen und kein Fehler, aber jede Nennung der Zahl muss die
Einschränkung mittragen. Belastbar wird sie erst, wenn ein Teil der 193 Seiten
im Annotator durchgesehen und auf `done` gesetzt ist.

### Nahezu doppelte Seiten lecken vom Train- in den Testsplit

Der Split trennt Seiten, nicht Kataloge — und Penny gibt je Woche 44 fast
identische Regionalausgaben heraus. Für jede Testseite wurde die ähnlichste
Trainingsseite gesucht (Jaccard über normalisierte Wortmengen):

| | |
|---|---|
| Median-Ähnlichkeit der ähnlichsten Trainingsseite | **0.851** |
| Testseiten mit Zwilling ≥ 0.9 | 6 von 19 (max. 0.949) |
| Testseiten mit Zwilling ≥ 0.7 | 12 von 19 |
| Kataloge in Train *und* Test | 9 von 11 |

Die Entdopplung greift erst ab Jaccard 0.95. Seiten bei 0.939 oder 0.949
überleben sie um Haaresbreite und landen dann auf verschiedenen Seiten des
Splits.

**Wie groß ist der Effekt?** Dasselbe Modell, getrennt nach Nähe ausgewertet:

| Testseiten | Anzahl | F1 | Entitäten |
|---|---:|---:|---:|
| alle | 19 | 0.929 | 712 |
| mit nahem Zwilling (≥ 0.7) | 12 | **0.944** | 529 |
| ohne nahen Zwilling (< 0.7) | 7 | **0.886** | 183 |

**Das Leck schönt die Zahl, erklärt sie aber nicht.** Auswendiggelernt sähe
anders aus — eher 0.99 gegen 0.55. Der Aufschlag beträgt fünf bis sechs
Punkte; die ehrliche Schätzung für unbekannte Seiten ist **~0.89**. Auf den
sauberen sieben Seiten bleiben UNIT_PRICE 0.98, QUANTITY 0.95 und BRAND 0.91;
es fallen PRICE (0.79) und PRODUCT (0.76) — dieselben Labels wie überall, nur
deutlicher.

Einschränkung: die sieben sauberen Seiten sind auch inhaltlich die
ungewöhnlicheren (überwiegend Non-Food), der Unterschied ist also nicht rein
ein Duplikat-Effekt. Und 183 Entitäten sind eine schmale Basis.

**Ein Split über Kataloge würde das nicht beheben.** `1347375_p30` und
`1347396_p34` sind verschiedene Kataloge mit Jaccard 0.939 — zwei
Regionalausgaben derselben Woche. Sauber wäre ein Gruppen-Split über die
Duplikat-Cluster: `dedupe.group()` mit Schwelle um 0.7 laufen lassen und ganze
Cluster geschlossen einer Seite zuordnen. Bleibt Teamentscheidung.

### Weiter gilt

- 19 Testseiten sind wenig. Labels mit n < 20 (VALID, APP_PRICE) sind Rauschen.
- Seiten über 512 Subwords werden abgeschnitten — siehe oben, für GBERT sind
  das 531 Wörter auf 19 Testseiten.

---

## 7. Der Wochen-Split: dieselbe Messung ohne Leck

Auf die Leckmessung aus Abschnitt 6 folgte die naheliegende Konsequenz: nicht
Seiten trennen, sondern **Erscheinungswochen**. Der Korpus enthält zwei —
KW30 (Kataloge 1342812–1342929) und KW31 (1347375–1347504). KW30 lernt, KW31
testet. Keine Seite aus KW31 hat einen Katalog im Training.

Die Woche steht nirgends in den Daten. Ableitbar ist sie aus dem Abstand der
Katalog-IDs: innerhalb einer Woche liegen sie höchstens 24 auseinander,
zwischen den Wochen klaffen 4446. `dataset.group_by_week()` schneidet bei
einer Lücke über 200 — großzügig, aber ohne feste Nummern, die beim nächsten
Erntelauf veraltet wären.

Erzeugt wird die Aufteilung mit `scripts/12_make_split.py --strategy week`.
Das Skript weigert sich, einen bestehenden Split zu überschreiben, und legt
beim erzwungenen Ersetzen eine Sicherung daneben.

### Wie sauber ist es jetzt?

| | Seiten-Split | Wochen-Split |
|---|---:|---:|
| Aufteilung train / dev / test | 158 / 19 / 19 | **81 / 8 / 107** |
| Median-Ähnlichkeit Test ↔ Lernmenge | 0.851 | **0.257** |
| Testseiten mit Zwilling ≥ 0.9 | 6 von 19 | **0 von 107** |
| ≥ 0.8 | — | 1 von 107 |
| ≥ 0.7 | 12 von 19 | 3 von 107 |
| ≥ 0.5 | — | 5 von 107 |

Die drei Restfälle liegen bei höchstens 0.824. Das sind keine Regionalzwillinge,
sondern wiederkehrende Seitentypen — die Obst-und-Gemüse-Seite sieht jede Woche
ähnlich aus. Das ist kein Leck, das ist die Aufgabe.

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
| **micro avg** | **0.908** | **0.895** | **−0.013** | 3901 |
| macro avg | 0.821 | 0.813 | −0.008 | 3901 |

**Der Befund hält.** Mit 45 % weniger Trainingsdaten *und* ohne Leck fällt
GBERT von 0.929 auf 0.908 — nicht auf 0.85, wie die Leckmessung als Untergrenze
nahegelegt hatte. Auswendiggelernt war hier nichts. Der Testsatz ist zugleich
von 19 auf 107 Seiten gewachsen, die Zahl also erheblich besser abgestützt.

Auseinanderhalten lassen sich die beiden Effekte nicht: weniger Daten drückt,
kein Leck drückt, und beide wirken gleichzeitig. Die 2,1 Punkte sind die Summe.

### APP_PRICE bricht auf 0.000 ein — und das ist der interessanteste Befund

Nicht Rauschen, sondern ein **Verteilungsunterschied zwischen den Wochen**:

| | KW30 (train) | KW31 (test) |
|---|---:|---:|
| APP_PRICE-Spans | **2** | **57** |
| davon auf … Seiten | 1 | 46 |

Penny hat den App-Preis in KW31 breit ausgerollt. Das Modell hat ihn nie
gesehen und sagt ihn folgerichtig kein einziges Mal voraus (seqeval: „no
predicted samples"). Ohne APP_PRICE läge GBERT bei **0.914**, LayoutXLM bei
**0.902**.

Der Zufallssplit hätte diesen Fall verdeckt — er hätte die 57 Spans über Train
und Test verteilt und eine passable Zahl geliefert. Genau dafür ist ein
zeitlicher Split da: Er misst nicht nur Generalisierung über Seiten, sondern
über die Zeit, und das ist der Einsatzfall. Prospekte ändern ihr Format.

### LayoutXLM verliert jetzt sichtbar

Im Zufallssplit lagen die beiden gleichauf (0.929 / 0.930). Über Wochen
getrennt liegt GBERT **1,3 Punkte vorn**, und OLD_PRICE — das einzige Label,
bei dem LayoutXLM zuvor deutlich gewann (+0.056) — dreht auf **−0.050**.

Das ist mit Vorsicht zu lesen: 81 Trainingsseiten sind für ein Modell mit
zusätzlichem visuellen Backbone knapp, und LayoutXLM hat mehr Parameter zu
füllen. Aber die These „Layout hilft" wird davon nicht gestützt, sondern
weiter geschwächt.

### Was auch der Wochen-Split nicht behebt

**Der Testsatz ist in sich redundant.** Die 107 Seiten bilden bei Jaccard 0.7
nur **66 Cluster**; der größte umfasst 11 Seiten. Nichts davon steckt im
Training — es ist kein Leck. Aber eine Seite aus dem 11er-Cluster zählt elffach
ins Ergebnis. Die effektive Stichprobe sind **~66 unabhängige Seiten, nicht
107**, und das Konfidenzintervall ist entsprechend breiter, als n = 3901
Entitäten suggeriert.

**Der Dev-Split ist mit 8 Seiten zu klein.** Modellauswahl über
`load_best_model_at_end` entscheidet damit auf dünner Basis. Bei zwei Wochen
ist das der Preis dafür, dass Dev aus den Trainingswochen kommen muss — aus der
Testwoche gezogen wäre es Auswahl auf der Messmenge.

**Wiederkehrende Produkte sind kein Leck.** MÜHLENHOF und Coca-Cola stehen in
beiden Wochen, und das soll so sein: ein produktiv eingesetztes Modell hätte
diese Marken auch schon gesehen.

**Die Grenze aus Abschnitt 6 gilt unverändert.** Train- und Testlabels kommen
aus derselben Quelle mit denselben Konventionen. Gemessen wird weiterhin
„reproduziert Claude", nicht „versteht Prospekte". Kein Split der Welt behebt
das — nur die menschliche Freigabe der Vorannotation.

---

## 8. Infrastruktur: fünf Fehler auf dem Weg zur fremden GPU

Trainiert wurde auf gemieteten Pods (erst NVIDIA L4, 23 GB, 0,39 $/h; für den
Wochen-Split eine RTX A5000 für 0,27 $/h). Nicht wegen der Rechenzeit — GBERT
braucht **96 Sekunden**, LayoutXLM **254** — sondern wegen des
Arbeitsspeichers: auf einem 8-GB-Mac füllt LayoutXLM den Swap, und die Maschine
wird unbenutzbar (Load 67 bei 100 MB freiem RAM).

Fünf Fehler standen dazwischen, alle fünf inzwischen im Repository behoben:

**1. Der eingefrorene Split hing am Labeling-Fortschritt.**
`get_or_create_splits()` würfelte über die Seiten, für die es *gerade* Labels
gab. Ein Training bei 141 von 196 Seiten hätte einen Split für 141 Seiten
eingefroren — dauerhaft, denn er wird genau einmal gezogen — und die 55
nachgelieferten wären sämtlich im Training gelandet. Jetzt wird über alle
extrahierten Seiten gewürfelt.

**2. LayoutXLM war nie trainierbar.**
`LayoutDataset` lieferte nur Wörter und Bounding-Boxen. LayoutXLM ist aber eine
LayoutLMv2-Architektur, und deren visueller Backbone ist Teil des
Vorwärtsdurchlaufs, kein Extra. Der Fehler war noch dazu nichtssagend:
`'NoneType' object has no attribute 'tensor'`, tief im Backbone. Aufgefallen
ist es nie, weil diese Variante schlicht noch nie gestartet worden war — in
`checkpoints/` lag nur `gbert`.

*Gefunden durch einen Forward-Pass mit Batch-Größe 1 vor dem Mieten. Kosten: 40
Sekunden CPU statt einer Pod-Stunde Fehlersuche.*

**3. PEP 668.** Die Python-Installation gängiger GPU-Images ist als „externally
managed" markiert; pip verweigert dort jede Installation, und das Bootstrap
starb in der ersten Zeile.

**4. detectron2 und die Build-Isolation.** detectron2 importiert `torch` schon
in seiner `setup.py`, um gegen die richtige CUDA-Version zu übersetzen. In
pips Build-Sandbox gibt es kein torch — auf einer Maschine, auf der torch
längst installiert ist. `--no-build-isolation` behebt es.

**5. Eine gemeldete GPU ist keine benutzbare GPU.** Der zweite Pod meldete
`torch.cuda.is_available() == True`, brach aber bei der ersten Allokation ab:
„CUDA-capable device(s) is/are busy or unavailable". `nvidia-smi` zeigte
gleichzeitig **0 MiB belegt, keine Prozesse und 100 % Auslastung** — die Karte
war von einem Nachbarcontainer beschlagnahmt, für uns unsichtbar. Der dritte
Pod landete auf **demselben Host** (66.92.198.138) und scheiterte identisch;
erst der vierte, auf anderer Hardware, lief.

Die Prüfung im Bootstrap fasst die Karte deshalb jetzt wirklich an
(`torch.zeros(8, device="cuda").sum()`), statt sie nur zu fragen. Ohne das
wäre der Fehler nach der zehnminütigen detectron2-Übersetzung mitten im
HF-Trainer aufgeschlagen. **Verfügbarkeit abfragen und Verfügbarkeit benutzen
sind zwei verschiedene Dinge** — der Unterschied kostete hier zwei Pods.

### Das Trainingsbündel

`scripts/11_export_bundle.py` packt Code, Labels, Split und Seitenbilder in ein
Tar (16,7 MB). Drei Entscheidungen darin:

- **Der Code kommt per `git ls-files`, nicht per `git clone`.** Der lokale
  Stand war 109 Commits vor GitHub; ein Klon hätte den Stand von vorletzter
  Woche trainiert.
- **`split.json` muss mit, sonst bricht der Export ab.** Ohne die Datei würfelt
  die fremde Maschine klaglos einen eigenen Split, das Training läuft durch,
  und die F1-Zahl ist mit den lokalen nicht vergleichbar — die
  unauffälligste Fehlerquelle des ganzen Vorgangs.
- **Die Bilder gehen auf 224×224 herunter**, mit demselben bilinearen Filter,
  den `LayoutLMv2ImageProcessor` ohnehin anwendet. Aus 390 MB werden 17 MB,
  ohne dass sich am Modelleingang ein Pixel ändert.

Das Bootstrap bricht ab, wenn die GPU fehlt *oder* nichts annimmt (Fehler 5).
Der teuerste denkbare Fehler auf einem Mietpod ist ein Training, das
stillschweigend auf der CPU läuft, während die bezahlte Karte danebensteht.

Gesamtkosten beider Trainingsläufe (Zufalls- und Wochen-Split, je zwei
Varianten): **rund 0,45 $.**

---

## 9. Offen

- **Vorannotation freigeben.** Bis dahin ist 0.908 eine Zahl über Konsistenz,
  nicht über Richtigkeit. Priorität eins.
- **PRODUCT-Konvention schärfen.** Sorte gegen Beschreibungstext, mit
  Beispielliste. Es ist das einzige Label unter 0.9 und die häufigste
  Rückfrage der Annotation.
- **Labeling-Prompt an die Anweisung angleichen**, mechanisch Entscheidbares in
  `trim_spans()`.
- **Den einen bestätigten Annotationsfehler korrigieren**
  (`1347411_p42`, `1-l-Sonderedition`).
- **APP_PRICE in KW30 nachtragen?** 2 Spans gegen 57 — zu prüfen wäre, ob der
  App-Preis in KW30 wirklich fehlte oder ob die Annotation ihn dort übersehen
  hat. Das entscheidet, ob 0.000 ein Verteilungsbefund oder ein Datenfehler ist.
- **Dritte Woche ernten.** Acht Dev-Seiten sind zu wenig für Modellauswahl, und
  der Testsatz aus 107 Seiten enthält nur 66 unabhängige Cluster.
- **Team-Entscheidungen unverändert offen:** Sliding Window für Seiten über 512
  Subwords, endgültiges Label-Set. *Erledigt:* Split über Kataloge statt Seiten
  — der Wochen-Split (Abschnitt 7) beantwortet die Frage schärfer, als sie
  gestellt war.
- **Marken ohne Textlayer.** Prinzipielle Grenze des reinen Textlayer-Ansatzes.
  Wenn wir sie erfassen wollen, führt kein Weg an echtem OCR auf dem
  Seitenbild vorbei.
