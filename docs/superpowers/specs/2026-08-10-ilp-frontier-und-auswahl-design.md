# ILP-Dekoder, Efficiency Frontier und widerspruchsbasierte Auswahl — Design

Drei Arbeitspakete aus der Ideenrunde vom 10.08.2026, plus ein vorgemerkter
Kandidat. Alle drei sind klein; keines braucht eine GPU, ein neues Label oder
einen neuen Modellkopf.

Der gemeinsame Nenner: Sie greifen an drei verschiedenen Stellen dieselbe
Lücke an — **die Gruppierung ist der Flaschenhals, nicht die
Wortklassifikation** (Wort-F1 0.894 gegen Gruppen-F1 0.477).

| Teil | Was | Aufwand | Hängt ab von |
|---|---|---|---|
| 1 | ILP-Dekoder statt Zusammenhangskomponenten | ~1 Tag | nichts |
| 2 | Efficiency-Frontier-Abbildung | ~0,5 Tage | Blackbox-Lauf (Aufgabe 1) |
| 3 | Widerspruch als drittes Auswahlkriterium | ~2 Stunden | vor dem Referenzausbau |
| 4 | Bildobjekt-Rechtecke als Paarmerkmal | vorgemerkt | nach dem Referenzausbau |

**Teil 3 ist zeitkritisch.** Er verändert, welche 30–50 Seiten der Lehrer als
Nächstes gruppiert. Wer erst annotiert und dann das Kriterium ändert, hat die
Referenz nach dem alten Kriterium und kann das nicht nachholen.

## Globale Randbedingungen

- **Der Testsplit bleibt unangetastet.** Alle drei Teile werden auf Train/Dev
  entwickelt und gemessen. Der einzige Testkontakt läuft im Schlussbatch
  (Aufgabe 6 des Vertiefungsplans) mit.
- **Jede berichtete Zahl mit Cluster-Intervall.** Dev hat 21 Seiten in 14
  Clustern; Punktschätzer-Vergleiche sind dort Rauschen. Gilt besonders für
  Teil 1, wo der Vergleich Union-Find ↔ ILP genau in diesem Rauschen liegen
  könnte.
- **Nach jedem Teil: volle Suite grün** (`.venv/bin/python -m pytest -q`,
  aktuell 420 Tests).
- **Keine Zahl ohne das Skript, das sie erzeugt** — gilt auch für die
  Abbildung in Teil 2.

## Ausdrücklich nicht Teil dieses Specs

Diese Dinge sehen nach Fortschritt aus und sind hier keiner:

- **Arithmetik als ILP-Constraint.** Menge × Grundpreis ist der einzige
  unbestechliche Richter (`offers-verify`). Als Nebenbedingung im Solver
  bewertete sie sich hinterher selbst — derselbe Zirkelschluss, gegen den
  `offers_report` die Ablation braucht. Begründung ausführlich in Teil 1.
- **Kardinalitäts-Constraints** („maximal ein PRICE je Angebot"). Bei Penny
  falsch: Variantenblöcke tragen legitim mehrere Preise (`Pfanne: 20 cm 9.99 /
  24 cm 14.99 / 28 cm 17.99`, Issue #6). Ein harter Constraint zementierte den
  Plättungsfehler.
- **Weitere Paar-Merkmale.** `beide` (39 Merkmale) liegt unter der Basis (30).
  Erst Referenz vergrößern, dann Merkmale — deshalb ist Teil 4 vorgemerkt und
  nicht gebaut.
- **Ein Self-Training-Kreislauf**, der arithmetisch gefundene Fehler
  automatisch ins Training zurückspielt. Verbrennt den Richter und ist bei
  ~126 ungelabelten Seiten ohnehin datenlos.
- **CO₂-Zahlen** in Teil 2, aus demselben Grund wie im Vertiefungsplan.

---

# Teil 1: ILP-Correlation-Clustering als Dekoder

## Warum

`offer_pairs.groups_from_edges` benennt sein eigenes Problem im Docstring:

> „Der bekannte Preis dieses Verfahrens ist die Transitivität: A-B und B-C
> verschmelzen zu einer Gruppe, auch wenn A-C weit unter der Schwelle liegt.
> Bei einer Legendenspalte kann das eine ganze Seite zu einem Angebot machen."

Das ist keine Randnotiz, sondern erklärt die Kalibrierungszahlen. Die Schwelle
landet bei **0.94 bzw. 0.96**, weit über dem natürlichen Schnitt; bei 0.5
entstanden 83 Gruppen statt 268. Union-Find hat gegen eine einzelne
durchgerutschte Kante nur einen Hebel: **alle** Kanten pessimistischer machen.
Deshalb muss die Kalibrierung so weit nach oben drehen, und deshalb zerfallen
danach Angebote, deren Kanten legitim mittelstark sind.

Correlation Clustering hat einen zweiten Hebel: Es darf die schwächste Kante
eines widersprüchlichen Dreiecks kappen, statt alle zu bestrafen.

## Was gebaut wird

Neues Modul `src/magda/offer_ilp.py` mit einer Funktion, die
signaturkompatibel zu `groups_from_edges` ist:

```python
def groups_from_edges_ilp(
    count: int,
    edges: dict[tuple[int, int], float],
    threshold: float,
    cannot_link: set[tuple[int, int]] | None = None,
) -> list[list[int]]:
```

**Zielfunktion.** Für jedes Paar eine Binärvariable `z_ij` (1 = selbe Gruppe).
Maximiert wird `Σ w_ij · z_ij` mit

```
w_ij = logit(p_ij) − logit(threshold)
```

Der Offset ist der wichtige Teil und in Fables Vorschlag nicht enthalten. Ohne
ihn liegt der Nullpunkt bei p = 0.5, und das ILP bekäme eine völlig andere
Arbeitsschwelle als die out-of-fold kalibrierte. Mit dem Offset gilt: `w_ij > 0`
genau dann, wenn `p_ij > threshold` — **derselbe Nullpunkt wie bei Union-Find**.
Damit ist der Vergleich der beiden Dekoder bei gleicher Schwelle sauber
definiert, und der Unterschied liegt allein in der Transitivitätsbehandlung.

`p` wird auf `[1e-6, 1 − 1e-6]` geklippt, sonst erzeugt `p → 1` ein unendliches
Gewicht.

**Nebenbedingungen.** Ausschließlich Transitivität, für jedes Tripel
`(i, j, k)`:

```
z_ij + z_jk − z_ik ≤ 1
z_ij + z_ik − z_jk ≤ 1
z_jk + z_ik − z_ij ≤ 1
```

Optional `cannot_link` als harte Nullsetzung `z_ij = 0` — vorbereitet, aber in
diesem Spec **nicht befüllt**. Der Parameter existiert, damit ein späterer
Regelversuch (etwa `products_between ≥ 1` → cannot-link) keinen Eingriff in die
Signatur braucht.

**Solver.** PuLP mit dem mitgelieferten CBC. `pulp` wandert wie `flair` **nicht**
in `requirements.txt`: Wer nur trainiert, soll es nicht installieren müssen.
Fehlt es, bricht der Aufruf mit einem Hinweis ab statt still auf Union-Find
zurückzufallen — ein stiller Rückfall wäre genau die Sorte Fehler, die man
später an einer Zahl nicht mehr sieht.

**Skalierung.** Die Constraints sind `n(n−1)(n−2)/2`. Bei 48 Entities sind das
~52 000 Ungleichungen (für CBC unkritisch), bei 100 schon ~485 000. Deshalb:

```python
MAX_ENTITIES_EXACT = 60
```

Darüber werden nur Tripel gebildet, in denen mindestens eine Kante über
`threshold` liegt. Das ist eine **Näherung, und sie wird ausgewiesen** — der
Report führt `approximated_pages` mit. Stilles Kappen von Abdeckung ist genau
das, was hinterher wie Vollständigkeit aussieht.

## Wie gemessen wird

`magda offers-model eval` bekommt `--decoder {union,ilp}` (Default `union`,
damit alle bisherigen Zahlen reproduzierbar bleiben).

**Die Schwelle muss für das ILP neu kalibriert werden.** `calibrate()` bekommt
denselben Schalter. Wer die für Union-Find gewählte 0.94 auf das ILP anwendet,
vergleicht ein kalibriertes gegen ein unkalibriertes System — und zwar zu
Ungunsten des ILP, weil dessen ganzer Vorteil darin besteht, bei *niedrigeren*
Schwellen nicht zu zerfallen.

Berichtet wird auf denselben 21 Dev-Seiten:

| Größe | Warum |
|---|---|
| Gruppen-F1 + Cluster-CI | Primärzahl („die Zeile in der Datenbank stimmt") |
| Paar-F1 + Cluster-CI | Vergleichbarkeit mit der Line-Item-Literatur |
| Zahl der Angebote | Der Verschmelzungseffekt zeigt sich hier zuerst |
| `offers-verify` accuracy **und** coverage | Unabhängige Gegenprobe |
| Sekunden je Seite | Geht in Teil 2 ein |

**Die falsifizierbare Vorhersage** — und der eigentliche Erkenntniswert des
Teils, unabhängig davon, ob das ILP gewinnt:

> Trägt man Gruppen-F1 über die Schwelle auf, muss die Union-Find-Kurve links
> der kalibrierten Schwelle **steil abfallen** (Verschmelzung), die ILP-Kurve
> **flacher**. Ist sie das nicht, ist die Transitivitäts-Hypothese widerlegt —
> dann liegt der Fehler in den Kantenwahrscheinlichkeiten, nicht im Dekoder.

Diese Kurve wird mitgeschrieben (`data/eval/offers_decoder_dev.json`), auch
wenn das ILP verliert. Ein Negativbefund an dieser Stelle schließt eine
Hypothese und ist berichtenswert — wie beim Layout-Vergleich.

## Tests, die rot werden müssen

`tests/test_offer_ilp.py`:

1. **Das Dreieck** — der Test, der den ganzen Teil trägt. A–B und B–C stark
   über der Schwelle, A–C stark darunter. Union-Find liefert eine Gruppe aus
   drei Entities, das ILP darf das nicht.
2. **Widerspruchsfreier Fall** — wo kein Dreieck verletzt ist, muss das ILP
   dieselben Gruppen liefern wie `groups_from_edges`. Sonst ist der Vergleich
   in Teil 1 kein Vergleich zweier Dekoder, sondern zweier Systeme.
3. **Der Schwellen-Offset** — ein einzelnes Paar knapp über `threshold` landet
   zusammen, knapp darunter getrennt. Sichert zu, dass der Offset wirkt.
4. **Determinismus** — zweimal derselbe Aufruf, dieselben Gruppen (CBC kann
   bei Gleichstand variieren; nötigenfalls über eine feste Tie-Break-Regel).
5. **Fehlendes PuLP** bricht mit Hinweis ab, statt still zurückzufallen.

**Pflichtprüfung nach CLAUDE.md:** Nach dem Schreiben `MAX_ENTITIES_EXACT` und
den Clipping-Wert je einmal verstellen und nachsehen, ob wirklich etwas bricht.
Beim letzten Mal waren vier von sieben verstellten Konstanten ohne jede Wirkung
auf die Tests.

---

# Teil 2: Efficiency Frontier

## Warum

Das ist die **offene Pflicht** aus dem Proposal, Stufe „Excellent":

> „A comparison of the trained model against the LLM black box, including a
> discussion of the trade-offs (quality, cost, running locally vs. via API)."

`src/magda/blackbox_eval.py` existiert seit heute; `data/eval/blackbox_test.json`
noch nicht. Was fehlt, ist der Lauf und die **Darstellung**. Die Darstellung ist
der neue Teil: Aus einer Tabelle wird eine Abbildung, die den Trade-off zeigt
statt ihn aufzuzählen.

## Was gebaut wird

`src/magda/frontier.py` + `src/magda/cli/frontier.py` → `magda frontier`.

Das Modul **misst nichts selbst**. Es liest vorhandene Reports aus
`data/eval/`, setzt sie zusammen und erzeugt zwei Artefakte:

- `data/eval/frontier.json` — die Datenpunkte
- `reports/frontier.svg` — die Abbildung

Getrennt, weil die Zahl ohne Bild prüfbar bleiben muss.

**Achsen.**

- **X: Sekunden je Seite, logarithmisch.** Ende-zu-Ende, also PDF → Angebote,
  auf beiden Seiten dieselbe Seitenmenge und dieselbe Maschine. Nicht die alte
  170×-Zahl: die vergleicht Labeling gegen Inferenz, nicht Produkt gegen
  Produkt.
- **Y: F1 nach dem `blackbox_eval`-Matching**, also über die gemeinsame
  Feldmenge (`name`, `price`, `original_price`), Referenz `sonnet-5`.
  **Ausdrücklich nicht gegen `gold/`** — drei handannotierte Seiten tragen
  keine Messung, und `gold/` ist seit dem 30.07. nicht mehr Referenz.

**Punkte.**

| Punkt | Anmerkung |
|---|---|
| LLM-Blackbox (Gemini/Sonnet) | Der Vergleichsarm aus dem Proposal |
| GBERT + `offers.cluster_page` | Die Heuristik |
| GBERT + Paarmodell + Union-Find | Der heutige Stand |
| GBERT + Paarmodell + ILP | Aus Teil 1, falls er sich bewährt |

**Flair kommt nicht als gleichrangiger Punkt aufs Diagramm.** Der Arm misst nur
BRAND; sein F1 auf dieselbe Achse zu legen wie Vollschema-Systeme verletzt die
Regel, die sich das Projekt selbst gegeben hat. Entweder weglassen oder als
andersfarbiger, beschrifteter Punkt mit der Einschränkung in der Legende.

**Kostentabelle** — separat neben der Abbildung, nicht darin:

- Hochrechnung auf eine Wochenernte über alle 44 Regionen.
- API-Kosten aus **öffentlicher kommerzieller Preisliste**, deklariert als
  hypothetisch: Die GWDG ist kontingentiert, nicht bepreist. Ein Eurobetrag
  wäre sonst eine Zahl ohne Rechnungsgrundlage.
- Lokale Kosten als Größenordnung (CPU-Sekunden × grober Leistungsaufnahme ×
  Strompreis). **Keine Nachkommastellen**, und ein Satz, warum nicht — sonst
  fällt die Zahl unter dasselbe Urteil wie die ausgeschlossenen CO₂-Zahlen.

## Tests

`tests/test_frontier.py`:

1. Ein Report ohne Zeitangabe wird übersprungen, nicht mit 0 s eingetragen.
2. Punkte mit unterschiedlicher Referenz landen nicht auf derselben Achse
   (Formprüfung wie bei `/api/evaluation`).
3. Der BRAND-only-Punkt trägt eine Markierung im JSON, nicht nur in der Grafik.

---

# Teil 3: Widerspruch als drittes Auswahlkriterium

## Warum

`magda offers-queue` wählt heute abwechselnd nach zwei Kriterien:

- **`luecke`** — kein Grundpreis, also für die Ablation unbeurteilbar
  (praktisch Non-Food)
- **`vorlage`** — Clustergröße, eine Seite steht für elf

Beide sind Eigenschaften der *Seite*. Keines nutzt, dass das System auf
manchen Seiten **nachweislich falsch liegt**: `offers_verify.judge_page`
liefert `contradicted`, wenn ein Preis in einer *anderen* Gruppe der Seite
aufgeht. Das ist ein starkes Signal — nicht „hier ist es schwer", sondern
„hier ist es falsch".

Aufgabe 3 des E2E-Plans baut die Referenz von 51 auf 80–100 Seiten aus. Welche
30–50 Seiten das sind, entscheidet über den Wert des Ausbaus.

## Was gebaut wird

`review.offer_queue` bekommt ein drittes Kriterium `widerspruch`, die Rotation
wird von zwei auf drei Ranglisten erweitert. Ein Eintrag trägt zusätzlich
`contradicted` (die Zahl der widersprüchlichen Preise unter der aktuellen
Systemgruppierung).

## Der Teil, der leicht falsch gebaut wird

Wenn Seiten nach arithmetischem Widerspruch **ausgewählt** und dort dann eine
Referenz erzeugt wird, ist jede spätere `offers-verify`-Zahl auf genau diesen
Seiten verzerrt: Sie wurden hineingeholt, *weil* die Rechnung Alarm schlug.

Die Lösung ist billig und muss von Anfang an drin sein:

- Jede über dieses Kriterium ausgewählte Seite trägt in der Provenance ihrer
  Gruppierungsdatei `selected_by: "contradiction"`.
- `magda offers-verify` weist zwei Zahlen aus: über alle Seiten und über die
  **nicht so ausgewählten**. Berichtet wird die zweite.

Damit bleibt Active Learning erhalten und der Richter unbestechlich. Das ist
dasselbe Muster wie die Ablation in `offers_report` — nur eine Ebene höher: dort
wird ein Merkmal zurückgehalten, hier eine Seitenmenge.

## Tests

`tests/test_offers_queue.py` erweitern:

1. Eine Seite mit `contradicted > 0` erscheint in der Rangliste, auch wenn ihr
   Cluster klein ist und sie prüfbare Preise hat.
2. Die Rotation liefert bei `--limit 30` aus jedem der drei Kriterien Einträge.
3. `offers-verify` trennt die beiden Zahlen und meldet, wie viele Seiten wegen
   der Auswahlherkunft aus der Hauptzahl fallen.

---

# Teil 4: Bildobjekt-Rechtecke als Paarmerkmal (vorgemerkt)

**Nicht in diesem Spec bauen.** Hier festgehalten, damit der Befund nicht
verlorengeht.

## Der Befund

Sonde über zwei Seiten mit `PyMuPDF.get_image_rects()`:

```
bk_1.pdf  S1: 24 Bildobjekte, 24 Rechtecke, Flächenanteile 0.073 … 0.096
bk_10.pdf S1: 16 Bildobjekte, 16 Rechtecke, Flächenanteile 0.034 … 0.100
```

Die Penny-PDFs liefern die **Rechtecke der eingebetteten Produktfotos** direkt
aus dem Vektorlayer — kein Pixel, keine Objektdetektion. Zwei Seiten sind eine
Sonde, kein Befund; der Anteil 1.007 in der ersten Zeile ist ein
Vollseiten-Hintergrundbild und müsste gefiltert werden.

## Warum das interessant ist

Ein Produktfoto ist der **visuelle Anker einer Kachel**. Damit ließen sich zwei
Merkmale bauen, die genau die Information tragen, an der die Farbmerkmale
gescheitert sind (0.438 gegen Basis 0.477) — aber aus einer sauberen Quelle
statt aus verrauschten Pixeln:

- `same_photo` — teilen beide Entities dasselbe nächstgelegene Bildobjekt?
- `photo_between` — kreuzt die Verbindungslinie ein fremdes Bildobjekt?

## Bedingung

„Weitere Paar-Merkmale" steht auf der Ausschlussliste des E2E-Plans, und das
gilt hier. **Erst nach Aufgabe 3** (Referenz von 51 auf 80–100 Seiten), sonst
wiederholt sich der `beide`-Effekt: mehr Merkmale, weniger Leistung, weil ~20
unabhängige Vorlagen sie nicht tragen.

Vorher zu klären, in dieser Reihenfolge:

1. Liefern alle 422 Seiten Bildrechtecke, oder nur manche Katalogjahrgänge?
2. Wie viele Objekte sind Produktfotos, wie viele Hintergrund, Logo, Zierrat?
   (Flächen- und Positionsfilter, entwickelt auf Train/Dev.)
3. Fällt bei Freistellern und Composites überhaupt ein Rechteck je Produkt an,
   oder eines je Composite?

Erst wenn 1–3 beantwortet sind, lohnt der Merkmalsentwurf.

---

# Reihenfolge

1. **Teil 3** zuerst — zwei Stunden, und er ist der einzige mit einem
   Zeitfenster. Nach dem Referenzausbau ist er wirkungslos.
2. **Teil 1** — der größte Hebel auf die Primärzahl, unabhängig von allem
   anderen.
3. **Teil 2** — braucht den Blackbox-Lauf und profitiert davon, Teil 1 als
   vierten Punkt zu haben.
4. **Teil 4** — nach dem Referenzausbau, und erst nach den drei Vorfragen.
