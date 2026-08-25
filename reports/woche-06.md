# Woche 6 — Was Layout wirklich beiträgt: die Ablationskette

Stand: 25.08.2026

## Kurzfassung

Drei Wochen lang stand in diesem Projekt der Satz: *„Zum Layout-Vorteil ist
kein Effekt nachweisbar – in keine Richtung."* Er stimmte, und er hat sich
diese Woche als **unterbestimmt** herausgestellt. Nicht falsch — nur eine
Antwort auf eine Frage, die zwei Ursachen gleichzeitig enthielt.

Vier Dinge stehen am Ende der Woche:

1. **Der Testsatz ist KW35, und alle 666 Seiten sind im Split.** Bisher kannte
   `split.json` nur 296 der gelabelten Seiten; KW33–35 fehlten vollständig.
   Trainingsmenge von 175 auf **494 Seiten**.
2. **Es gibt zwei neue Arme, und sie zerlegen die alte Frage.** `xlmr` und
   `lilt` sitzen zwischen GBERT und LayoutXLM, sodass zwischen benachbarten
   Armen genau *eine* Zutat liegt.
3. **Layout bringt nichts, das Seitenbild bringt etwas.** Beides erstmals
   getrennt messbar — und die Antworten fallen entgegengesetzt aus.
4. **Zwei Messfehler sind unterwegs aufgefallen**, einer davon hätte eine um
   100 Trainingsseiten geschönte Zahl produziert, ohne eine Zeile Warnung.

## Warum die alte Frage nicht beantwortbar war

Bis zu dieser Woche verglich das Projekt zwei Modelle:

| | Textencoder | Layout | Bild |
|---|---|---|---|
| GBERT | gbert-base (deutsch) | – | – |
| LayoutXLM | XLM-R (mehrsprachig) | ✓ | ✓ |

Zwischen den beiden liegen **drei** Unterschiede, nicht einer. Eine Differenz
zwischen ihnen ist deshalb keiner Ursache zuschreibbar. Dass sie über drei
Läufe hinweg die Null überdeckte, hat das verdeckt: Wo kein Effekt ist, fragt
niemand, aus welchen Teilen er sich zusammensetzt.

Der Ausweg ist eine Kette, in der jeder Schritt genau eine Zutat hinzufügt:

```
xlmr  ──+Layout──▶  lilt  ──+Bild──▶  layoutxlm
```

Alle drei teilen sich XLM-R als Textencoder. `nielsr/lilt-xlm-roberta-base`
ist deshalb gewählt und nicht der englische SCUT-Checkpoint — LiLT ist der
*Language-Independent Layout Transformer*, sein Layout-Teil ist getrennt
vortrainiert und mit jedem RoBERTa kombinierbar. `gbert` steht daneben als
Projektbaseline, nicht als Glied der Kette.

**Verworfen:** LiLT mit GBERT zusammenzubauen. `LiltTextEmbeddings` berechnet
die Positionen nach der RoBERTa-Formel (ab `padding_idx + 1`, daher 514 statt
512 Positionen); GBERT ist BERT mit 512. Der Zusammenbau ginge mechanisch,
verschöbe aber jedes Positions-Embedding um zwei und liefe am Tabellenende
über. Ein Fehler, der nicht abstürzt, sondern still schlechter wird.

## Datenlage

Der Wochen-Split ist neu gezogen (`magda split --strategy week --force`).
KW32 war Testwoche, ist jetzt Trainingswoche; getestet wird auf KW35.

| Woche | Zeitraum | Seiten | Rolle |
|---|---|---:|---|
| KW30 | 20.–25.7. | 89 | Train/Dev |
| KW31 | 27.7.–1.8. | 107 | Train/Dev |
| KW32 | 3.–8.8. | 100 | Train/Dev *(vorher Test)* |
| KW33 | 10.–15.8. | 126 | Train/Dev |
| KW34 | 17.–22.8. | 128 | Train/Dev |
| KW35 | 24.–29.8. | 116 | **Test** |

| Split | Seiten | Duplikat-Cluster | Entities |
|---|---:|---:|---:|
| train | 494 | 210 | 24 900 |
| dev | 56 | 25 | 2 584 |
| test | 116 | **42** | 5 973 |

Die Wochengruppierung leitet sich aus Abständen der Katalog-IDs ab, nicht aus
den Daten selbst. Sie wurde gegen die Gültigkeitszeiträume im Textlayer
gegengeprüft — jede Gruppe trägt einen konsistenten Zeitraum, kein
Fremdkatalog ist eingesickert.

**Leck-Kontrolle** (maximale Jaccard-Ähnlichkeit je Seite zum Training):

| | n | Median | Max | ≥ 0.7 | ≥ 0.9 |
|---|---:|---:|---:|---:|---:|
| test | 116 | 0.297 | 0.778 | 2 | 0 |
| dev | 56 | 0.360 | 0.695 | 0 | 0 |

Die zwei Testseiten über 0.7 sind der bekannte harmlose Fall: Rückseiten mit
rechtlichem Kleingedruckten, das sich wöchentlich wiederholt.

Nachgerechnet ohne eigenes Kommando:

```python
import json, statistics
from magda.config import SPLITS_DIR
from magda.dataset import load_page_words
from magda.dedupe import normalize, similarity

s = json.load(open(SPLITS_DIR / "split.json"))
w = load_page_words([p for v in s.values() for p in v])
sets = {p: set(normalize(v)) for p, v in w.items()}
train = [p for p in s["train"] if p in sets]
for name in ("test", "dev"):
    sims = [max(similarity(sets[p], sets[b]) for b in train) for p in s[name] if p in sets]
    print(name, len(sims), round(statistics.median(sims), 3), round(max(sims), 3),
          sum(x >= 0.7 for x in sims), sum(x >= 0.9 for x in sims))
```

**Dev ist erstmals brauchbar dimensioniert.** 25 statt 14 Cluster. Die
Checkpoint-Auswahl stand bisher auf einer Basis, die für zehn Kandidaten
knapp war.

**Nebenbefund:** APP_PRICE hat im Training jetzt 582 Spans statt 187. Die
Verteilungsverschiebung aus KW30–32 (2 → 57 → 98) ist ausgelaufen; Penny hat
den App-Preis fertig ausgerollt.

## Ergebnis

Alle vier Arme, 10 Epochen, identische Hyperparameter, Referenz `sonnet-5`.
Primärmetrik ist `windowed` — das misst, was `magda predict` ausliefert.

| Arm | Sieht | micro-F1 | Precision | Recall |
|---|---|---:|---:|---:|
| gbert | Text (deutsch) | 0.9084 | 0.915 | 0.902 |
| xlmr | Text (XLM-R) | 0.9143 | 0.922 | 0.907 |
| lilt | + Layout | 0.9140 | 0.923 | 0.905 |
| **layoutxlm** | + Bild | **0.9236** | 0.932 | 0.915 |

Gepaart über die 42 Duplikat-Cluster gebootstrappt (10 000 Resamples). Die
Tabelle zeigt *später minus früher*, also den Gewinn des jeweiligen Schritts;
die Dateien unter `data/eval/significance_<a>_<b>.json` speichern `a − b` und
tragen deshalb das umgekehrte Vorzeichen:

| Schritt | Zutat | Differenz | 95 %-KI | p |
|---|---|---:|---|---:|
| gbert → xlmr | anderer Encoder | +0.0059 | [−0.0015, +0.0156] | 0.165 |
| **xlmr → lilt** | **Layout** | **−0.0003** | [−0.0063, +0.0058] | **0.925** |
| **lilt → layoutxlm** | **Bild** | **+0.0096** | [+0.0033, +0.0182] | **0.019** |
| gbert → layoutxlm | alle drei | +0.0152 | [+0.0074, +0.0262] | 0.008 |

Zwei Sätze, die sich vorher nicht trennen ließen:

> **Wortkoordinaten allein bringen nichts.** Der Layout-Schritt liegt bei
> −0.0003 mit einem Intervall von ±0.006 — das ist keine schwache Wirkung,
> sondern die präziseste Null des ganzen Projekts.

> **Das Seitenbild bringt etwas.** +0.0096, Intervall vollständig über der
> Null.

Das ist die Umkehrung des bisherigen Befunds — allerdings nicht seine
Widerlegung. Der alte Satz galt für 175 Trainingsseiten; auf dieser Menge war
LayoutXLM tatsächlich nicht besser (−0.0014, p = 0.843). Mit 494 Seiten kippt
es. Der visuelle Backbone hat 368 Mio. Parameter — dass er mehr Daten braucht
als der Rest, ist die naheliegendste Erklärung.

## Woher der Bildgewinn kommt

F1 je Label, und die letzte Spalte ist der Bildschritt:

| Label | Support | gbert | xlmr | lilt | layoutxlm | lilt→layoutxlm |
|---|---:|---:|---:|---:|---:|---:|
| PRODUCT | 1246 | 0.778 | 0.778 | 0.781 | 0.810 | **+0.028** |
| PRICE | 1015 | 0.958 | 0.963 | 0.961 | 0.962 | +0.000 |
| QUANTITY | 981 | 0.875 | 0.883 | 0.874 | 0.884 | +0.010 |
| UNIT_PRICE | 782 | 0.990 | 0.992 | 0.992 | 0.992 | +0.000 |
| BRAND | 757 | 0.931 | 0.940 | 0.944 | 0.970 | **+0.026** |
| DISCOUNT | 511 | 0.992 | 0.992 | 0.992 | 0.992 | +0.000 |
| OLD_PRICE | 428 | 0.947 | 0.958 | 0.957 | 0.968 | +0.011 |
| APP_PRICE | 139 | 0.844 | 0.886 | 0.906 | 0.882 | **−0.025** |
| VALID | 114 | 0.947 | 0.991 | 0.987 | 0.911 | **−0.076** |

Der Gewinn sitzt **fast vollständig bei PRODUCT und BRAND** — also genau bei
den beiden Labels, für die das Proposal Positionsinformation vermutet hatte.
Die Vermutung war richtig; die Annahme, Wortkoordinaten würden sie liefern,
war falsch. Die vier Preis- und Rabattlabels bewegen sich um null: Preise
erkennt man am Textmuster, und das war schon in Woche 1 so.

**Der interessanteste Wert ist der negative.** APP_PRICE ist der dokumentierte
rein visuelle Fall: bei 33 % der Spans steht „App" nicht im Textfenster, die
Kennzeichnung ist ein türkisblauer Kasten (rgb(0, 124, 132)). Wenn das Bild
irgendwo helfen müsste, dann hier. Es tut das Gegenteil — LiLT ohne Bild ist
mit 0.906 der beste Arm für dieses Label, LayoutXLM mit 0.882 der schlechtere
von beiden.

Die Erklärung steht seit Woche 4 in der Architektur und wird hier bestätigt:
`image_feature_pool_shape` ist `[7, 7, 256]`, also **49 visuelle Token für die
ganze Seite**. Eine Gitterzelle deckt 142 × 251 px ab, der App-Kasten misst
etwa 230 × 80 px und fällt mit Produktfoto und Nachbarpreis in dieselbe Zelle.
Dazu hängen die 49 Token als *globale* Sequenz an — es gibt keine Verknüpfung
„dieses Wort steht auf blauem Grund". Der Backbone liefert also **grobe
Seitenstruktur**, und davon profitieren PRODUCT und BRAND: wo auf der Kachel
ein Wort steht, ob im Fettdruck-Block oben oder in der Beschreibungszeile.
Feine lokale Farbe liefert er nicht.

VALID (−0.076 bei 114 Instanzen) ist zu dünn für eine Deutung; eine einzelne
Instanz bewegt dort 0.9 Punkte.

## Was es kostet

Die Projektfrage ist Kosten, nicht Perfektion.

| Arm | `best/` | Training (RTX 3090) |
|---|---:|---:|
| gbert | 437 MB | 130 s |
| xlmr | 1110 MB | 202 s |
| lilt | 1134 MB | 322 s |
| layoutxlm | 1476 MB | 308 s |

Dazu die Inferenz auf dem Entwicklungsrechner (MacBook, CPU, 56 Dev-Seiten
je ein Aufruf von `magda predict <arm> --split dev`, Wanduhrzeit **inklusive
Modellladen** — deshalb nicht mit der früher berichteten Zahl von 0,264 s je
Seite vergleichbar, die den Ladevorgang nicht enthielt):

| Arm | 56 Seiten | je Seite |
|---|---:|---:|
| gbert | 32 s | 0,57 s |
| lilt | 64 s | 1,14 s |
| xlmr | 73 s | 1,30 s |
| layoutxlm | 103 s | 1,84 s |

LayoutXLM kostet gegenüber GBERT das **3,4-fache an Modellgröße und das
3,2-fache an Inferenzzeit** für +0.0152 F1. Ob das ein guter Tausch ist, ist eine Produktentscheidung und keine
Messfrage — aber sie sollte mit diesen beiden Zahlen nebeneinander getroffen
werden, nicht mit dem F1 allein. Der Pod-Lauf für alle vier Arme
inklusive Evaluation und Export kostete rund 40 Minuten auf einer
Karte für $0,50/h.

## Nebenbefund: der Tokenizer entscheidet über die Fenstergrenze

Der Fenstereffekt fällt bei GBERT doppelt so groß aus wie bei den drei
XLM-R-Armen:

| Arm | windowed | ohne Fenster | Differenz | Entities im 512er-Fenster |
|---|---:|---:|---:|---:|
| gbert | 0.9084 | 0.8913 | +0.0171 | 5711 von 5973 |
| xlmr | 0.9143 | 0.9070 | +0.0073 | 5831 |
| lilt | 0.9140 | 0.9074 | +0.0066 | 5831 |
| layoutxlm | 0.9236 | 0.9159 | +0.0077 | 5831 |

GBERT verliert ohne Fenster **262 Entities**, die XLM-R-Arme nur 142. Die
Ursache ist die Tokenisierung: GBERTs WordPiece zerlegt deutsche Komposita in
mehr Subwords als XLM-Rs SentencePiece, also passt weniger Seite in dieselben
512 Positionen. Das erklärt einen Teil des Vorsprungs von `xlmr` gegenüber
`gbert` — und der Rest dieses Schritts ist mit p = 0.165 ohnehin nicht
belegbar.

## Zwei Messfehler, die unterwegs auffielen

**1. `magda significance` verglich über Trainingsseiten.** Der Befehl nahm die
Schnittmenge der beiden Vorhersageordner. `data/predictions/` ist aber ein
Archiv, kein Abbild des aktuellen Splits: Nach dem Wechsel der Testwoche lagen
in `gbert` noch 101 und in `layoutxlm` noch 100 Seiten des Vorlaufs. Die
Schnittmenge war **216 statt 116 Seiten, und 100 davon hatte das Modell
inzwischen im Training gesehen.** Der Bootstrap hätte daraus ein
Konfidenzintervall gebaut — die Zahl wäre schlicht zu gut gewesen und hätte
wie ein Ergebnis ausgesehen.

Eingeschränkt wird jetzt auf den Testsplit, und die Zahl der verworfenen
Seiten steht in der Ausgabe (`shared_test_pages`, zwei Tests). Die alten
Vorhersagen liegen als `data/predictions/<arm>.kw32-split/` daneben.

**2. Das Pod-Bootstrap installierte torchvision nicht.** Das neuere
RunPod-Image bringt torch und torchaudio mit, torchvision nicht. detectron2
übersetzt trotzdem durch und lässt sich importieren — erst `detectron2.layers`
zieht torchvision, und das passiert im Trainer. Der Lauf starb also nach zwei
fertigen Armen, mitten in der Mietzeit.

Beim Nachinstallieren lauerte die zweite Falle: `pip install torchvision` zog
torch von 2.9.1 auf **2.11.0** hoch, gegen 2.9.1 war detectron2 aber schon
übersetzt. `import detectron2.modeling` lief danach noch durch; gestorben wäre
erst der erste Aufruf einer kompilierten Op — wieder mitten im Training. Im
Bootstrap steht jetzt die torch-Version gepinnt und ein
`import detectron2.modeling` als Sichtprüfung vor allen vier Läufen.

Beide gehören in dieselbe Familie wie `torch.cuda.is_available()`, das eine
belegte Karte als verfügbar meldet: **Eine Prüfung, die nichts anfasst, prüft
auch nichts.**

## Einschränkungen

Diese gehören zu jeder Nennung der Zahlen oben.

- **Vier Vergleiche, keine Korrektur für multiples Testen.** Bei Bonferroni
  (α = 0.05/4 = 0.0125) hält nur `gbert → layoutxlm` (p = 0.008). Der
  Bildschritt liegt mit p = 0.019 darüber. Die Bereiche sind zudem nicht
  unabhängig — die Gesamtdifferenz ist die Summe der drei Schritte. Belastbar
  ist damit: *LayoutXLM schlägt GBERT*, und *innerhalb dieser Differenz ist
  der Layout-Schritt nachweislich null*. Dass der Bildschritt allein trägt,
  ist ein starker Hinweis, kein abgesichertes Einzelergebnis.
- **Gemessen wird Übereinstimmung mit dem Lehrer, nicht Richtigkeit.**
  Referenz ist `data/labeled/sonnet-5/`. 0.92 heißt „92 % dessen, was das
  große Modell liefert", nicht „92 % richtig".
- **42 unabhängige Einheiten.** Die 116 Testseiten bilden bei Jaccard 0.7 nur
  42 Cluster. Alle Intervalle oben sind darüber gezogen; über Seiten gerechnet
  wären sie zu eng.
- **Die Zahlen sind nicht mit den KW32-Werten vergleichbar.** Anderer
  Testsatz, andere Trainingsmenge. Die alten Zahlen (GBERT 0.8938, LayoutXLM
  0.8952, p = 0.843) bleiben als eigener Messpunkt gültig und werden nicht
  fortgeschrieben. Checkpoints und Vorhersagen dazu liegen unter
  `*.kw32-split`.
- **Ein Lauf je Arm, kein Seed-Mittel.** Die Streuung zwischen zwei
  Trainingsläufen desselben Arms ist nicht gemessen. Bei Differenzen von
  0.01 ist das die nächstliegende Gegenprobe.

## Was das Proposal betrifft

Die Hypothese des Proposals lautete: *Marke und Produktname erkennt man erst
an der Position auf der Seite, deshalb ein layout-aware Modell.* Nach dieser
Woche lässt sie sich präziser fassen:

- **Der Teil über Marke und Produkt stimmt.** PRODUCT +0.028 und BRAND +0.026
  sind praktisch der gesamte Effekt.
- **Der Teil über die Position stimmt nicht.** Wortkoordinaten liefern ihn
  nicht (−0.0003). Was ihn liefert, ist das Seitenbild.

Für den Bericht heißt das: Der Layout-Arm ist nicht mehr der Arm, der
„konsistent verliert, aber nicht nachweisbar". Er ist der Arm, der gewinnt —
und die Kette sagt, an welchem seiner Bestandteile das liegt.

## Offen

- **Angebots-KPIs sind noch nicht nachgezogen.** `offers-grid`, das Paarmodell
  und die Schwellenkalibrierung wurden gegen den alten Train/Dev-Schnitt
  gerechnet. Die Gruppierungsreferenz deckt inzwischen alle 666 Seiten ab,
  eine Neuberechnung ist also möglich und steht aus.
- **Seed-Streuung.** Siehe Einschränkungen.
- **Sortenangaben und Gebinde-Komposita.** Unverändert offen und weiterhin die
  größte einzelne Fehlerquelle bei PRODUCT (0.810 ist der schlechteste Wert
  aller Labels über 400 Instanzen).
- **Weg B für APP_PRICE** — die Farbe an der Wortposition als Merkmal — ist
  durch diese Woche eher gestärkt als erledigt: Der visuelle Backbone löst den
  Fall nachweislich nicht, und vier Zahlen je Wort wären ungleich billiger als
  1476 MB Modell.
