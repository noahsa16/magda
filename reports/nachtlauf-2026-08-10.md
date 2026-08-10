# Nachtlauf 10./11.08.2026 — Ende-zu-Ende, Labelqualität, Fehleranalyse

Stand: 11.08.2026, Branch `offers/farbmerkmale`, 489 Tests grün (vorher 420).

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

Zwei unabhängige Entity-Quellen mit demselben Vorzeichen sind mehr als ein
Zufallstreffer. **Ein Befund ist es trotzdem nicht:** die Intervalle im
blinden Fleck reichen bis 1.000, weil viele der 14 Dev-Cluster dort gar keine
Paare haben. Der nächste Schritt ist eine größere Referenz, nicht der nächste
Merkmalsblock.

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

Zwei Stellen, an denen der geplante Code falsch gewesen wäre:

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
schuld", und die Klasse wäre eine Ausrede statt einer Messung. Auf Dev feuert
sie nicht — was zur Handprüfung passt: von 81 fehlenden App-Preisen lagen 72
in Train und 9 in Dev.

## 5. Blackbox-Vergleichsarm (Requirements-Stufe „Excellent")

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
