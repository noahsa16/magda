# Farb- und Kontextmerkmale für das Angebots-Paarmodell

Entwurf vom 10.08.2026. Beteiligt: Noah, Claude, ein Fable-Subagent als
Gegenlesung.

## Problem

`magda offers-model` klassifiziert Entity-Paare („gehören zum selben
Angebot?") und schlägt die Heuristik auf Dev — Paar-F1 0.742 gegen 0.683,
Gruppen-F1 0.477 gegen 0.436. Sein blinder Fleck ist gemessen und benannt:
Wo kein Grundpreis steht, kann die arithmetische Gegenprobe nicht urteilen.
Die Abdeckung liegt bei 0.589, und die fehlende Hälfte deckt sich mit
Non-Food — also mit genau dem Bereich, für den die Gruppierung gebraucht
wird.

Die Ursache ist ein fehlendes Merkmal, kein zu kleines Netz: Wo eine Kachel
endet, steht in Rahmen, Hintergrundfarbe und gelbem Sticker — **im Bild,
nicht in den Wortkoordinaten**. Die 30 heutigen Merkmale sehen nur
Koordinaten und Entity-Typen.

## Nicht-Ziele

- **Die Rechnung Menge × Grundpreis bleibt draußen.** Sie ist das einzige
  Signal, das sich selbst beweist, und damit der einzige unbestechliche
  Richter über eine Gruppierung. Als Eingabe gefüttert bewertete
  `magda offers-verify` hinterher die eigene Ausgabe des Modells. Dazu
  kommt ein praktisches Argument: Sie greift nur, wo ein Grundpreis steht —
  also dort, wo das Modell mit 0.864 ohnehin gut ist — und im blinden Fleck
  täte sie nichts. `test_offer_pairs.py` hält das über die Merkmalsnamen
  fest.
- **Kein visueller Backbone.** LayoutXLM hat gezeigt, dass 49 globale
  Bildtoken für eine ganze Seite hier nichts bringen; eine Gitterzelle deckt
  142 × 251 px ab. Gebraucht wird lokale Wort-Bild-Verknüpfung, und die
  liefern vier gezielte Zahlen billiger als ein Backbone.
- **Der Testsplit bleibt unangetastet.** Entwickelt und gemessen wird auf
  Train und Dev.

## Die Stichprobe bestimmt das Merkmalsbudget

Der wichtigste Befund der Gegenlesung betrifft nicht die Merkmale, sondern
die Datenmenge. Die effektive Stichprobe sind **nicht die ~51 000 Paare**,
sondern die Duplikat-Cluster: Dev hat 21 Seiten in 14 Clustern, Train
entsprechend ~20 unabhängige Vorlagen.

Daraus folgt eine Trennlinie, die jede Merkmalsentscheidung vorentscheidet:

- Ein Merkmal, das **innerhalb** einer Seite variiert, hat tausende
  (korrelierte) Beobachtungen.
- Ein Merkmal, das **je Seite konstant** ist — Seitendichte, Entity-Zahl,
  „ist das Non-Food?", „hat die Seite ein Bild?" — hat effektiv **zwanzig**.
  Solche Merkmale memorieren Vorlagen, statt Regeln zu lernen.

**Budget: 8–10 neue Merkmale, Gesamtvektor ≤ 40.** Alle vorgeschlagenen
Merkmale variieren paarweise innerhalb der Seite.

## Merkmale

Zehn neue, 30 → 40. Drei Blöcke, weil sie getrennt gemessen werden (siehe
*Messung*).

### Block `geometry` (5)

| Name | Definition | Normierung |
|---|---|---|
| `products_between` | PRODUCT/BRAND-Entities, deren Mittelpunkt im umschließenden Rechteck des Paares liegt | Entity-Zahl der Seite |
| `closer_rivals_i` | Entities vom Typ *i*, die näher an *j* liegen als *i* | Anzahl dieses Typs auf der Seite |
| `closer_rivals_j` | Entities vom Typ *j*, die näher an *i* liegen als *j* | Anzahl dieses Typs auf der Seite |
| `distance_ratio` | `distance(i,j)` geteilt durch den Abstand von *i* zur nächsten Alternative vom Typ *j* | gekappt bei 5, dann durch 5 |
| `words_between` | Wörter im umschließenden Rechteck, die zu keiner der beiden Entities gehören | Wortzahl der Seite |

**Warum `products_between` und nicht „`entities_between` typisiert":** Ein
Angebot ist ein Stern um genau **einen** Produktanker. Ein zweiter Anker im
Rechteck ist das stärkste Trennsignal ohne Bild — und es löst zwei Fälle
gleichzeitig: den Legendenversatz (zwischen Preis ⑤ und Produkt ④ liegt
Produkt ⑤) und den Variantenblock (zwischen „Pfanne" und dem dritten Preis
liegt *kein* zweites Produkt, der Block darf zusammenbleiben).

**Warum Konkurrenz statt „nächster Nachbar":** Der Legendenversatz ist per
Definition ein **Margenproblem** — der falsche Name ist nur *knapp* näher.
Ein Ja/Nein-Merkmal verliert genau diese Information. Und der gelbe
Preiskasten, der räumlich am Nachbarangebot klebt, ist der Fall, in dem
`distance` allein systematisch lügt: Die Frage ist nie „wie weit?", sondern
„wie weit im Vergleich zu den Alternativen?".

**Warum `words_between`:** 54,5 % aller Wörter sind `O`, und das
Kleingedruckte steht räumlich *zwischen* den Angeboten. Für alle 30
heutigen Merkmale ist es unsichtbar — zwei Entities mit Weißraum dazwischen
und zwei mit einem dichten LEGAL-Block dazwischen haben heute **identische
Merkmalsvektoren**.

### Block `color` (4)

| Name | Definition | Normierung |
|---|---|---|
| `bg_distance` | RGB-Abstand der beiden Hintergrundfarben | √(3·255²) |
| `color_crossings` | deutliche Farbwechsel auf der Verbindungslinie | gekappt bei 5, dann durch 5 |
| `bg_offpage_i` | Abstand des Hintergrunds von *i* zur Median-Hintergrundfarbe der Seite | √(3·255²) |
| `bg_offpage_j` | dito für *j* | √(3·255²) |

Die Hintergrundfarbe je Entity kommt aus `label_audit.background_color` —
Median der Randpixel um die Box, weil innerhalb der Box Schrift steht. Die
Funktion ist erprobt: Bei der App-Preis-Handprüfung traf sie in der Gruppe
„fehlt vermutlich" zu 97,6 % (81 von 83).

Zwei Festlegungen, die leicht falsch gemacht werden:

- **Die Linie läuft zwischen den nächstliegenden Boxrändern**, nicht
  zwischen den Mittelpunkten. Mittelpunktslinien laufen bei großen Boxen
  mitten durch das Produktfoto und zählen dessen Kanten als Kachelgrenzen.
- **Beide Zahlen werden gekappt.** Ungekappt fittet das MLP Ausreißer auf
  Fotoflächen.

„Median-Hintergrundfarbe der Seite" heißt: der Median über die
Hintergrundfarben *aller* Entities der Seite. Damit bleibt auch dieses
Merkmal relativ und braucht keine Annahme über Penny-Weiß.

**Absolute RGB-Werte wurden verworfen.** Bei ~20 unabhängigen Vorlagen
lernte das Modell „Penny-Gelb = (255, 212, 0)" auswendig — eine Regel über
eine Hausfarbe, nicht über Angebote. Dazu steht die Typinformation schon im
One-Hot: Dass eine Entity ein PRICE ist, weiß das Modell bereits.

### Zurückgestellt: Legendenmarker

Die Idee, freistehende Ziffern vor beiden Entities abzugleichen, ist
geprüft und **zurückgestellt**. Die Marker ④⑤ stehen nicht als Glyphen im
Textlayer; PyMuPDF liefert nackte Ziffern. Freistehende Ziffern neben
Preisen sind aber der bekannte Fehlgriff der Fußnotenregel
(`Aktion 1.99 1 2 3`). Dazu feuert das Merkmal fast nur auf der
`_p30`/`_p31`-Familie — sein Gewicht käme aus ein bis zwei Duplikat-Clustern.
Erst bauen, wenn die Fehleranalyse zeigt, dass die Legendenseiten trotz der
Geometrieblöcke kippen.

### Ebenfalls verworfen

- **Absolute Positionen, Winkel `atan2(dy,dx)`, Boxbreiten, `same_type`:**
  Umrechnungen aus vorhandenen Merkmalen. Ein MLP mit zwei Hidden-Layern
  leistet das selbst.
- **Kantenbündigkeit** `|x0_i − x0_j|`: nicht rein redundant, aber der
  Zusatznutzen ist klein und die Konkurrenzmerkmale decken den Spaltenfall
  besser ab. Fällt der Sparsamkeit zum Opfer.
- **`prices_between`:** Preis-Badges schweben frei; ein fremder Preis im
  Rechteck ist gerade *kein* verlässliches Trennsignal. Nur der Produktanker
  trennt zuverlässig.
- **Raster-Index per Clustering der Mittelpunkte:** bringt eigene
  Hyperparameter mit, die an denselben 30 Seiten eingestellt würden —
  versteckte Überanpassung.
- **Schrift-/Fettdruckmerkmale:** stehen nicht in `data/words`; sie zu holen
  hieße Schritt 02 anfassen, und die Wortreihenfolge ist ein Vertrag.
  `height_i/j` trägt den Großteil dieser Information schon.
- **GBERT-Embeddings je Entity:** hunderte Merkmale bei ~20 effektiven
  Vorlagen — das Gegenteil dessen, was 4097 Parameter und 16,8 s
  CPU-Training zur Stärke dieses Ansatzes macht.
- **Seitenglobale Merkmale:** je Seite konstant, effektive Stichprobe ~20.

## Architektur

### Merkmalsblöcke

`offer_pairs` bekommt eine Blockstruktur, weil die Messung einzelne Blöcke
an- und abschalten muss. **Vier Blöcke:**

| Block | Inhalt | Merkmale |
|---|---|---|
| `types` | One-Hot des Entity-Typs für i und j | 18 |
| `geometry_base` | die heutigen zwölf Geometriemerkmale | 12 |
| `geometry_plus` | die fünf neuen Kontextmerkmale | 5 |
| `color` | die vier Farbmerkmale | 4 |

```python
FEATURE_BLOCKS = {"types": [...], "geometry_base": [...],
                  "geometry_plus": [...], "color": [...]}
DEFAULT_BLOCKS = ("types", "geometry_base")   # exakt die heutigen 30
def feature_names(blocks) -> list[str]
def page_pairs(page, assignment=None, *, pixels=None, blocks=DEFAULT_BLOCKS)
```

`DEFAULT_BLOCKS` ergibt exakt die heutigen 30 Merkmale, damit bestehende
Aufrufer und Tests unverändert laufen. Die Blockreihenfolge ist fest, weil
sie im Checkpoint steckt — ein Modell, das auf einer anderen Reihenfolge
trainiert wurde, rechnet sonst mit vertauschten Spalten weiter und fällt
durch keine Prüfung auf.

### Bilder

`page_pairs` nimmt `pixels` als optionales numpy-Array entgegen. Fehlt es
und ist der `color`-Block aktiv, **bricht der Aufruf ab** mit einem Hinweis
auf `magda extract`.

Kein Sentinel, kein `has_image`-Flag. Drei Gründe:

1. In der echten Pipeline existiert das Bild immer — `cli/extract.py:92`
   schreibt es. Ein Abbruch kostet betrieblich nichts.
2. Ein Sentinel wäre **seitenkonstant** und damit genau die Falle aus dem
   Abschnitt *Stichprobe*: Das Modell lernte „Seiten ohne Bild sehen anders
   aus".
3. Es entspricht dem Hausbrauch: `get_or_create_splits` und
   `significance.test_clusters` brechen ab, statt zu schätzen.

Seit PR #22 liegt `data/images/` nicht mehr im Repo. Ein frischer Clone hat
die Bilder also nicht — der Abbruch nennt deshalb ausdrücklich
`magda extract` als Abhilfe (was seinerseits `data/raw/` aus dem
Drive-Archiv braucht).

### Checkpoint

`PairClassifier` speichert zusätzlich zu `feature_names` die aktiven
`blocks`. Der bestehende Vergleich beim Laden bleibt: Weichen die
Merkmalsnamen ab, wird das Laden mit „Neu trainieren" verweigert. Das alte
Modell wird durch diese Änderung ungültig — by design, nicht aus Versehen.

## Messung

### 2×2-Gitter, keine Leiter

| Variante | Blöcke | Merkmale |
|---|---|---|
| Basis | types + geometry_base | 30 |
| +Geometrie | + geometry_plus | 35 |
| +Farbe | + color | 34 |
| +beide | alle | 40 |

Eine Leiter (erst Geometrie, dann Farbe obendrauf) schriebe der Farbe nur
den *Rest*-Beitrag zu. Räumen `products_between` und die
Konkurrenzmerkmale die Legendenfälle schon ab, sähe Farbe insgesamt nutzlos
aus — während sie in Non-Food womöglich allein trägt. Bei 16,8 s Training
je Variante ist das Gitter geschenkt.

Für **alle** Varianten gilt: Schwelle out-of-fold über 5 Folds auf Train
kalibriert, Kriterium `group_f1`, Folds über ganze Duplikat-Cluster. Die
bestehende Offenlegung bleibt gültig — die Wahl von `group_f1` fiel,
nachdem beide Kriterien auf Dev gemessen waren, die Dev-Zahl ist dadurch
leicht optimistisch.

### Aufschlüsselung nach blindem Fleck

Das ist die Kennzahl dieses Vorhabens, deshalb präzise:

> Ein Paar zählt als **blind**, wenn **keine der beiden Referenzgruppen
> einen UNIT_PRICE enthält.**

Ohne Grundpreis in der Gruppe ist keine Rechnung möglich. Paar-F1 und
Gruppen-F1 werden zusätzlich getrennt für blinde und prüfbare Paare
ausgewiesen. Ohne diese Trennung berichteten wir einen Zugewinn, ohne zu
wissen, ob er aus dem Bereich kommt, für den das Merkmal gebaut wurde.

### Unsicherheit

**Cluster-Bootstrap über die 14 Dev-Cluster**, resampelt werden Cluster,
nicht Seiten. Ohne Intervall gilt: Unterschiede zwischen Varianten sind
**keine Behauptung**. Der Layout-Vergleich ist die Mahnung — +0.013 sah nach
einem Ergebnis aus, bis das Intervall die Null überdeckte und im Folgelauf
das Vorzeichen drehte.

### Unabhängige Gegenprobe

`magda offers-verify` läuft für jede Variante weiter. Die Arithmetik bleibt
draußen und richtet genau deshalb unbestechlich. Berichtet wird immer
`accuracy` **zusammen mit** `coverage`.

## Test

- **Farbmerkmale gegen gemalte numpy-Arrays.** Zwei Kacheln → `bg_distance`
  groß, `color_crossings` feuert. Eine Kachel → beide klein. Das ist der
  Grund für den `pixels`-Parameter: kein Bild von der Platte nötig.
- **Geometriemerkmale gegen synthetische Seiten**, wie die bestehenden Tests.
- **`products_between` am Legendenfall**: eine Seite mit zwei Produkten und
  zwei Preisen über Kreuz.
- **Abbruch bei fehlendem Bild**, wenn `color` aktiv ist.
- **Der Verboten-Test bleibt** und deckt die neuen Namen mit ab.
- **Konstanten-Pins werden gegengeprüft:** Kappung bei 5 und die
  Farbtoleranz werden nach dem Schreiben des Tests einmal verstellt, und es
  wird nachgesehen, ob wirklich etwas rot wird. Beim letzten Mal waren vier
  von sieben Pins wirkungslos.
- Der Schwellwert für „deutlicher Farbwechsel" wird **einmal auf Train**
  gesetzt, nicht gegen Dev iteriert. Startwert ist die erprobte
  `COLOR_TOLERANCE = 60`.

## Offen

- Ob die Farbmerkmale im blinden Fleck wirklich tragen, ist die Frage, die
  das Gitter beantworten soll — nicht eine Annahme dieses Entwurfs.
- Eine Handstichprobe über 5–10 Non-Food-Seiten bliebe die einzige Zahl in
  diesem Bereich, die nicht „Übereinstimmung mit einem LLM" heißt. Nicht
  Teil dieses Vorhabens, aber die logische Fortsetzung.
