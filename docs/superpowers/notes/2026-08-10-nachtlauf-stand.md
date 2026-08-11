# Nachtlauf 10./11.08.2026 — Stand und Übergabe

Branch: `offers/farbmerkmale`. Ein zweiter Claude arbeitet parallel im Repo —
**kein `git add -A`**, immer explizite Pfade.

## Erledigt

| Paket | Commit | Ergebnis |
|---|---|---|
| Gitterlauf festhalten | `d709202` | Lehrer-Entities, korrigiertes Farbmerkmal |
| Plan B/1 (PFLICHT) | `58a6437` | Blackbox-Arm gebaut, **nicht** auf Test gefahren |
| Plan A/1 | `9cb24cc` | erste Ende-zu-Ende-Zahl des Projekts |
| Plan A/2 | `f7e81d2` | 81 Spans PRICE → APP_PRICE in `sonnet-5-app` |
| Plan B/4 | `05d31d8` | Fehler-Taxonomie auf Dev, mit Lösbarkeitsspalte |
| Plan B/3 (Code + Liste) | `da555b3` | `eval --pages`, 126 Frischwochen-Seiten |

Tests: 489 grün (vorher 420).

## Die drei Reparaturen, ohne die Plan A/1 falsch gewesen wäre

1. **Report-Dateiname trug den Splitnamen, nicht die Entity-Quelle.** Der
   Vorhersagelauf hätte den Lehrerlauf still überschrieben — beide messen
   `dev`. Jetzt `offers_grid_dev.json` gegen `offers_grid_dev_gbert.json`.
2. **`--predictions` galt auch für die Trainingsseite**, für die es keine
   Vorhersagen gibt (0 Seiten). Neu: `--train-labels-from`.
3. **`magda train` schrieb nach `checkpoints/<variante>`**, ohne Rücksicht auf
   `--labels-from`. Jeder Nebenlauf hätte den eingefrorenen KW30/31-Stand
   gelöscht. Neu: `checkpoint_name()`, dazu `--checkpoint` in `eval`/`predict`.
   Anker ist `config.CANONICAL_LABELS` (= `sonnet-5`), **nicht**
   `default_labeled_model()` — das folgt `CHAT_AI_VISION_MODEL` und liefert
   `mistral-medium-3.5-128b`.

## Ergebnisse

**Ende-zu-Ende (Gruppen-F1 auf Dev, Referenz `claude-sonnet-5`):**

| Entities | Basis | +Geometrie | +Farbe | beide |
|---|---|---|---|---|
| Lehrer (sonnet-5) | 0.477 | 0.540 | 0.472 | 0.492 |
| Schüler (gbert) | 0.504 | 0.556 | 0.504 | 0.502 |

Die zweite Zeile ist **nicht besser**, sondern auf kleinerem Nenner gemessen:
1855 von 1996 Referenzpaaren überleben (0.929).

Im blinden Fleck ist `beide` auf **beiden** Entity-Quellen die beste Variante
(Paar-F1 0.782 bzw. 0.740 gegen 0.737 / 0.640 der Basis) — aber die
Intervalle reichen bis 1.000. Kein Befund, ein Fingerzeig.

**APP_PRICE-Übernahme:** 81 Spans, Training 115 → 187 (+63 %), Dev 11 → 20,
Test unverändert 98. Ein Urteil (`1342881_p31:165`, „Aktion «1.99» 1 2 3")
hat kein Zielabel und bleibt bewusst stehen.

**Fehler-Taxonomie (Dev, 77 Fehler auf Span-Ebene):** Grenzfehler 0.325
(21 von 25 bei PRODUCT), echte Falsch-Negative 0.390 (20 bei QUANTITY),
Typverwechslungen 0.065, Lehrerlücken 0.000.

## Offen, in dieser Reihenfolge

1. **Plan B/2 — die vier Trainingsläufe.** Code und Tests stehen.
   `for n in 25 50 100 175; do .venv/bin/magda train gbert --labels-from
   sonnet-5 --train-pages $n; done`. Landen in `checkpoints/gbert-p<N>`.
   Auswertung **nicht** jetzt — die gehört in den Schlussbatch.
2. **Plan A/2 Rest** — `magda eval gbert --checkpoint gbert-sonnet-5-app
   --split dev --labels-from sonnet-5-app`, gegen den Dev-Lauf auf
   `sonnet-5` halten. Nur 9 Dev-Spans ändern sich: Bewegung auf
   Rauschniveau erwarten und als solche berichten.
3. **Plan A/3 — Gruppierungsreferenz 51 → 80.** Teacher-Subagenten mit
   Seitenbild, Modell **sonnet**, sonst lügt der Ordnername
   `claude-sonnet-5`. Blöcke von zehn, nach jedem Block Bestand prüfen.
   Heute Nacht bewusst nicht angefangen: 30–50 Subagenten hätten das
   Kontingent verbrannt, das für die Fortsetzung um 2:00 gebraucht wird.

## Gesperrt — nicht anfassen

- **Plan B/6, der eine Testbatch.** Setzt Aufgabe 5 voraus (4 h Handarbeit
  am `/audit`-UI). Der Testsplit wird genau einmal angefasst; ihn zu
  verbrennen, während Noah schläft, ist nicht rückholbar.
- **Plan B/7, zweiter Händler.** Braucht einen Download von einer fremden
  Seite — ausdrückliche Erlaubnis nötig.
- **Plan A/4, Woche 4 labeln — geprüft und blockiert.** `magda label`
  spricht nur die GWDG-API an; deren bildfähige Modelle heißen mistral,
  qwen und gemma. `sonnet-5` ist keins davon, `data/labeled/sonnet-5/` ist
  also nicht über diesen Befehl entstanden. Da die Labelquelle gesetzt ist
  (immer sonnet, nie mistral oder qwen), braucht Woche 4 den
  Subagenten-Weg — 126 Seiten, eine Entscheidung über Kontingent.
  **Folge:** die Drift-Kurve (Plan B/3) hat ihren Code und ihre Seitenliste,
  aber noch keine Zahl.

## Dauerregeln

`.venv/bin/` statt `python`. Nie auf `main`. Testsplit einmal, am Ende.
Labelquelle **immer sonnet-5**, nie mistral oder qwen.

---

## Nachtrag 11.08.2026 — was das Review geändert hat

Fable hat gegengelesen. Drei Fehler behoben (Commit `e088019`), keiner hätte
einen Test rot gemacht:

1. **`subset_by_clusters` sortierte nach Clustergröße** und packte die
   Duplikate zuerst ins Budget: Grenze 25 → 23 Seiten aus **drei** Vorlagen.
   Jetzt nach `page_id`: 9/16/50/93 Cluster. Der bereits gelaufene
   Kurvenpunkt `gbert-p25` wurde verworfen und neu gestartet.
2. **`magda train gbert` ohne `--labels-from` hätte `checkpoints/gbert`
   überschrieben** — mit Mistral-Labels, weil `build_datasets` über
   `default_labeled_model()` auflöst. Aufgelöst wird jetzt vor der
   Namensvergabe.
3. **`blackbox-eval --dry-run` gab eine Quote aus**, und das Docstring-Beispiel
   zeigte die Testseitenliste. Der Probelauf schweigt jetzt.

Dazu: die Paarung in `error_taxonomy` nimmt jetzt die stärkste Überlappung
statt der ersten. Auf Dev ändert das nichts an den Zahlen.

### Drei Dinge, die Noah entscheiden muss

- **Blackbox-Referenz vor dem Schlussbatch.** Heute sind es
  `cluster_page`-Angebote aus den Lehrer-Labels, also dieselbe Heuristik wie
  auf der eigenen Seite — der Vergleich wäre strukturell zugunsten der
  eigenen Pipeline verzerrt. Alternative: `data/offer_groups/`. Der Testlauf
  ist nicht wiederholbar.
- **Kontingent für die Gruppierungsreferenz 51 → 80.** Der Schritt mit dem
  höchsten Ertrag.
- **Woche 4 labeln oder nicht.** 126 Seiten über den Subagenten-Weg, weil
  `magda label` nur GWDG-Modelle kennt und die Labelquelle sonnet ist.

### Noch offen aus dem Review, nicht behoben

- `test_blind_haengt_an_der_referenz_nicht_an_der_vorhersage` prüft die
  falsche Invarianz (variiert nur die Gruppierung, nie die Typquelle).
- `blackbox_eval.match_deals` paart gierig in Systemreihenfolge statt
  optimal; kann Treffer verschenken, Richtung unklar.
- `error_taxonomy.teacher_gap_reason` nennt jede ein- bis zweistellige
  Ziffer ±2 Wörter eine Fußnote — eher locker als konservativ.

---

## Nachtrag 2 — Lernkurve gelaufen (11.08.2026, 23:57)

Vier Punkte durch, mit der korrigierten Sortierung (`magda curve`):

| Punkt | Seiten | Cluster | bestes Dev-F1 |
|---|---:|---:|---:|
| p25 | 25 | 9 | 0.8348 |
| p50 | 50 | 16 | 0.8908 |
| p100 | 100 | 50 | **0.9247** |
| p175 | 175 | 93 | 0.9206 |

**Die Kurve sättigt zwischen 100 und 175 Seiten.** Die letzten 43
unabhängigen Vorlagen bringen nichts mehr — weitere LLM-Zeit für Stufe 1
kauft kaum noch etwas. Deckt sich mit der Fehleranalyse: die Grenze ist die
Konsistenz der Referenz, nicht ihre Menge.

Dev-Zahl ist optimistisch (bestes `eval_f1` über zehn Epochen = das
Auswahlkriterium selbst). Form vergleichbar, Niveau nicht. Belastbar erst im
Schlussbatch.

**Plan A/2 ist ebenfalls fertig:** micro-F1 0.926 (`sonnet-5`) gegen 0.927
(`sonnet-5-app`) auf Dev — Rauschen, wie erwartet bei neun geänderten
Dev-Spans. Der saubere Vergleich wartet im Test, wo die Übernahme null Spans
ändert und beide Arme dieselbe Messlatte haben.

**Hinweis zur Platte:** `checkpoints/` liegt jetzt bei **20 GB** (vier
Kurvenpunkte plus der APP_PRICE-Arm, je ~3,3 GB). Gitignored, aber es lohnt
sich, nach dem Schlussbatch aufzuräumen — gebraucht wird dann nur noch
`best/` je Lauf.

### Damit ist offen

- **Plan A/3** — Gruppierungsreferenz 51 → 80 (Kontingent-Entscheidung)
- **Plan A/4** — Woche 4 labeln, blockiert am Labelweg
- **Plan B/5, B/6** — Handprüfung, dann der eine Testbatch
- **Plan B/7** — zweiter Händler, braucht Erlaubnis zum Download

---

## Nachtrag 3 — Fortsetzung ab 02:03 (Plan A/3)

### Gruppierungsreferenz von 51 auf 71 Seiten

Zwanzig neue Seiten, von sonnet-Subagenten aus dem Seitenbild gruppiert,
ausgewählt über `magda offers-queue` (abwechselnd blinder Fleck und
Clustergröße). Train wächst von 30 auf 50, Dev war schon vollständig.

Eine Antwortdatei kam abgeschnitten zurück (`1347471_p44`) — `save` hat sie
korrekt abgelehnt statt halb zu übernehmen, danach repariert. Der Prompt
verlangt seither ausdrücklich gültiges JSON und ≤400 Zeichen `notes`.

### Zwei Funde, die wichtiger sind als die zwanzig Seiten

**1. Der Label-Default zeigte auf mistral.** `config.default_labeled_model()`
gab `CHAT_AI_VISION_MODEL` den Vorrang, also `mistral-medium-3.5-128b` — ein
Modell, mit dem hier gar nicht gelabelt wird. Was das kostet, ist beziffert:
über *dieselbe* Gruppierung fand `magda offers-verify` mit Mistral-Labels
**399** Preise (Genauigkeit 0.927, Abdeckung 0.446), mit sonnet-5 dagegen
**494** (0.936, 0.478). Ein Viertel mehr Preise, dieselbe Rechnung — die Zahl
beantwortete leise eine andere Frage, ohne dass irgendwo „mistral" stand.
Über die Ordnergröße allein wäre es auch nicht gutgegangen: `sonnet-5`,
`sonnet-5-app` und der Mistral-Ordner haben alle 296 Seiten. Vorrang hat
jetzt `CANONICAL_LABELS`.

**2. „Mehr Referenz" war die halb falsche Antwort auf die breiten
Intervalle.** Gemessen wird auf **Dev**, und Dev hat 21 Seiten in 14
Duplikat-Clustern — *alle* davon längst gruppiert. Die Breite eines
Bootstrap-Intervalls hängt an der Zahl der Auswertungs-Cluster, und keine
weitere Trainingsseite ändert daran etwas. Das Planziel „Dev auf 25–30 Seiten
ausbauen" war nicht schwer, sondern **unmöglich**.

Der Ausweg ist kein Datenproblem, sondern der Messaufbau: `magda offers-grid
--cross-validate` wertet jede Referenzseite einmal aus, mit einem Modell, das
sie nicht gesehen hat. Aus 14 Clustern werden **62**. Die Schwelle wird dabei
geschachtelt gewählt (`calibrate` auf den inneren Folds, Auswertung nur auf
dem äußeren) — einmal auf allem gewählt wäre sie genau der Zirkelschluss,
gegen den `offers_report` die Ablation braucht.

### Das Ergebnis der Fortsetzung

75 Seiten in 68 Clustern, out-of-fold, gepaarte Differenz gegen die Basis:

| Variante | Bereich | Differenz | Intervall | p |
|---|---|---:|---|---:|
| +Geometrie | alle Paare | **+0.044** | [+0.009, +0.082] | **0.018** |
| +Geometrie | prüfbar | +0.052 | [+0.002, +0.099] | 0.042 |
| +Farbe | alle Paare | −0.008 | [−0.036, +0.023] | 0.596 |
| beide | blinder Fleck | **−0.051** | [−0.103, −0.001] | 0.042 |

**+Geometrie wirkt, Farbe nicht** — und auf der Geometrie obendrauf
verschlechtert die Farbe das Ergebnis im blinden Fleck, also genau dort,
wofür sie gebaut wurde. Der Dev-Eindruck dreht sich um.

Einschränkung: neun Vergleiche ohne Korrektur für multiples Testen, drei
Bereiche nicht unabhängig. Belastbar ist p = 0.018; die beiden bei p = 0.042
sind Hinweise.

**Offene Teamentscheidung:** Farbmerkmale entfernen oder als sauber
gemessenen Negativbefund stehen lassen. Nicht vertretbar wäre nur, sie
mitzuführen und die alte Dev-Zahl zu zitieren.

### Was jetzt noch offen ist

- **Plan B/5** — Handprüfung der Schülerabweichungen auf Test (4 h am
  `/audit`-UI). Vorbedingung für den Schlussbatch.
- **Plan B/6** — der eine Testbatch. Wartet auf B/5.
- **Plan B/7** — zweiter Händler, braucht Erlaubnis zum Download.
- **Plan A/4** — Woche 4 labeln, 126 Seiten über den Subagenten-Weg.
- **Blackbox-Referenz** vor dem Schlussbatch klären (siehe Nachtrag 1).
- 5 Seiten bleiben in der `offers-queue` — die Referenz kann weiter wachsen,
  hilft aber nur dem Training, nicht dem Intervall.

---

## Nachtrag 4 — ILP-Dekoder (11.08.2026) — **fertig gemessen**

Nach `docs/superpowers/specs/2026-08-10-ilp-frontier-und-auswahl-design.md`,
Teil 1. Neu: `src/magda/offer_ilp.py`, `tests/test_offer_ilp.py`, dazu der
`decoder`-Parameter in `offer_model.py`, `offer_grid.py` und den beiden CLIs.
523 Tests grün.

### Das Ergebnis

`magda offers-grid --labels-from sonnet-5 --variants geometrie
--cross-validate --decoder union,ilp`, 75 Seiten in 68 Clustern,
out-of-fold, geschachtelte Schwellenwahl:

| | Schwelle | Paar-F1 | **Gruppen-F1** | Angebote | exakt | Sekunden |
|---|---:|---:|---:|---:|---:|---:|
| Union-Find | 0.956 | 0.715 | 0.453 | 620 | 270/573 | 765 |
| ILP | 0.868 | 0.569 | **0.553** | 588 | **321**/573 | 2055 |

Gepaarte Differenz im Gruppen-F1, dieselben Seiten:

| Bereich | Differenz | Intervall | p |
|---|---:|---|---:|
| alle Paare | **+0.100** | [+0.067, +0.133] | **0.000** |
| blinder Fleck | **+0.115** | [+0.065, +0.168] | **0.000** |
| prüfbar | +0.085 | [+0.034, +0.130] | 0.004 |

Zum Vergleich: Der Merkmalsgewinn `+Geometrie` lag bei +0.044 (p = 0.018).
Der Dekoder wirkt also stärker als der beste bisher gefundene
Merkmalsblock — und am stärksten im **blinden Fleck**, also dort, wo die
Arithmetik schweigt und bisher nichts geholfen hat.

### Die Wirkungskette — wichtiger als die Zahl

Der Gewinn kommt **nicht** daraus, dass das ILP bei gleicher Schwelle
besser dekodiert. Er kommt daraus, dass es eine **niedrigere Schwelle
erlaubt**: 0.868 statt 0.956, out-of-fold gewählt, ohne dass jemand es
vorgegeben hätte. Genau die Vorhersage aus dem Spec. Union-Find muss so
hoch kalibrieren, weil eine einzige durchgerutschte Kante eine ganze
Legendenspalte verschmilzt; das ILP kappt stattdessen die schwächste
Kante des Widerspruchs.

### Was dagegen spricht — gehört mitberichtet

**Paar-F1 fällt von 0.715 auf 0.569.** Das ist kein Nebengeräusch: Das ILP
sagt 19060 Paare vorher (Referenz: 9508), Union-Find 13531. Die niedrigere
Schwelle erkauft die exakten Gruppen mit deutlich mehr falschen Paaren.
Welche der beiden Zahlen das Projekt trägt, ist die schon offene
Teamentscheidung — `group_f1` ist Default, weil es „die Zeile in der
Datenbank stimmt" entspricht, und beide Dekoder wurden danach kalibriert.
Wer Paar-F1 zur Primärzahl macht, dreht diesen Teilbefund um.

**Und genau dieser Punkt widerspricht sich zwischen den beiden Messungen —
siehe die Gegenprobe unten.** Auf Dev *steigt* Paar-F1 (0.880 gegen 0.782).
Belastbarer ist die CV-Zahl (68 Cluster gegen 14); der Dev-Wert ist ohne
Intervall und aus 14 Clustern. Wer den Paar-F1-Effekt berichtet, muss
sagen, aus welcher der beiden Messungen er stammt.

**Die Kappung greift messbar:** 1611 von 37367 Komponenten (4,3 %) wurden
durchgereicht statt optimiert, die größte hatte 118 Entities. Dort *ist*
das ILP Union-Find. Der Effekt ist also eher unterschätzt als
übertrieben — aber die Zahl gehört neben jede Angabe.

**Laufzeit 2055 s gegen 765 s**, Faktor 2,7. Für die Inferenz belanglos
(die teuren Fälle entstehen nur im unteren Kalibrierungsraster), für
Gitterläufe spürbar.

**Und die übliche Einschränkung bleibt:** Gemessen wird Übereinstimmung
mit einem LLM-Lehrer, nicht Richtigkeit.

### Die arithmetische Gegenprobe — die einzige unbeteiligte Instanz

Alles oben misst Übereinstimmung mit dem Lehrer. `magda offers-model eval`
auf Dev, beide Dekoder frisch trainiert und kalibriert (getrennte
Checkpoints `model_union.pt` / `model_ilp.pt`, damit keiner den anderen
überschreibt):

| | Schwelle | Paar-F1 | Gruppen-F1 | Angebote | Rechnung | Abdeckung |
|---|---:|---:|---:|---:|---:|---:|
| Union-Find | 0.94 | 0.782 | 0.494 | 145 | 0.845 | 0.589 |
| ILP | 0.86 | **0.880** | **0.711** | 151 | **0.883** | 0.589 |
| Heuristik | – | 0.683 | 0.436 | 185 | 0.802 | 0.577 |
| Lehrer | – | – | – | 122 | – | – |

Widerlegte Preise fallen von 16 auf 12, „ohne Treffer" von 2 auf 0.

**Der naheliegende Einwand greift hier nicht.** Die Rechnung bestätigt
einen Preis, wenn er zu einer Menge-mal-Grundpreis-Kombination *in seiner
eigenen Gruppe* passt — gröbere Gruppen tragen mehr Kombinationen, also
schmeichelt Verschmelzen der Prüfung (im Grenzfall bestätigt eine
seitengroße Gruppe jeden prüfbaren Preis). Ein Anstieg wäre deshalb für
sich genommen schwach. Hier aber ist die **Abdeckung identisch (0.589)**
und die Angebotszahl fast gleich (151 gegen 145) — das ILP gewinnt nicht
durch gröbere Gruppen, sondern bei gleicher Körnung.

**Diese Messung steht auf 21 Dev-Seiten in 14 Clustern und hat kein
Intervall.** Sie ist die unabhängige Gegenprobe, nicht die Hauptzahl.

### Ende zu Ende: die ganze Kette, ohne Leck

`magda offers-grid --predictions gbert --train-labels-from sonnet-5
--splits dev --variants geometrie --decoder union,ilp`

**Warum hier keine Kreuzvalidierung möglich ist:** GBERT hat die 54
Train-Seiten der Referenz im Training gesehen; seine Vorhersagen dort
wären auswendig gelernt. Deshalb existieren für Train gar keine
Vorhersagen, und der saubere Aufbau ist: Paarmodell auf 54 Train-Seiten
mit Lehrer-Entities lernen, auf 21 Dev-Seiten mit **GBERT-Entities**
messen. Keine Seite auf beiden Seiten, keine Stufe sieht ihre eigenen
Messdaten. Preis: 14 Cluster statt 68.

| | Paar-F1 | Gruppen-F1 | Angebote | exakt |
|---|---:|---:|---:|---:|
| Union-Find | 0.824 | 0.599 | 152 | 82/122 |
| ILP | **0.878** | **0.729** | 147 | **98**/122 |

Gepaart: **+0.130 [+0.070, +0.159], p = 0.000** gesamt; prüfbar +0.128
(p = 0.026); **im blinden Fleck +0.114, aber p = 0.231** — dort trägt die
Stichprobe die Aussage nicht, anders als im CV-Lauf.

**Die eigentliche Nachricht steckt im Vergleich mit den Lehrer-Entities
auf denselben Seiten: 98 exakte Gruppen gegen 97.** Die Wortfehler von
GBERT (F1 0.894) kosten die Gruppierung praktisch nichts. Plausibel, weil
die Fehler-Taxonomie 0.325 der Fehler als *Grenzfehler* ausweist,
überwiegend an Sortenzusätzen bei PRODUCT — die verschieben eine
Span-Grenze, zerstören aber kein Angebot.

### Wer deckelt? Nicht das Paarmodell — `magda offers-model diagnose`

Die Frage „ist das Paarmodell der Deckel?" ist beantwortet, und die Antwort
ist **nein**:

| Entities / Dekoder | AUC | erreicht | Obergrenze | mit perfekten Kanten |
|---|---:|---:|---:|---:|
| Lehrer / ILP | 0.981 | 0.711 | 0.738 (Schwelle 0.74) | 1.000 |
| Lehrer / Union | 0.981 | 0.494 | 0.538 (Schwelle 0.90) | 1.000 |
| gbert / ILP | **0.984** | 0.701 | 0.745 | 1.000 |

**AUC 0.98** heißt: In 98 von 100 Vergleichen bewertet das Paarmodell ein
zusammengehöriges Paar höher als ein nicht zusammengehöriges. Die Kanten
sind exzellent, und mit *perfekten* Kanten liefert der Dekoder 1.000 — er
verschenkt also von sich aus nichts.

**Auch die Schwellenwahl ist es nicht.** Der Abstand zwischen erreicht und
Obergrenze beträgt 0.027 (ILP) bzw. 0.044 (Union) — und die Obergrenze ist
post-hoc gewählt, also nicht einmal erreichbar. Bemerkenswert: Union-Find
kommt selbst mit der *besten* Schwelle nur auf 0.538 und bleibt damit
deutlich unter dem ILP bei seiner kalibrierten. Der Vorteil des ILP ist
also nicht Kalibrierungsglück.

**Interessant nebenbei:** Auf gbert-Entities ist die AUC sogar *höher*
(0.984 gegen 0.981) — ein weiterer Beleg, dass Stufe 2 die Gruppierung
nicht beschädigt.

### Die Fehler sind gebündelt, nicht verteilt

Nachgerechnet über den E2E-Lauf: Bei 15,2 Paaren je Referenzgruppe und
Paar-Recall 0.797 wären bei *unabhängigen* Fehlern nur **0.032** der
Gruppen komplett richtig. Tatsächlich sind es **0.803**.

Der Unterschied um den Faktor 25 ist die eigentliche Aussage: Das System
macht nicht überall kleine Fehler, sondern **wenige Gruppen gründlich
falsch**. Das deckt sich mit dem Legendenversatz auf `1347387_p31`, wo
eine ganze Spalte kippt, sobald ein Abstand kippt.

Für die Priorisierung heißt das: Der nächste Hebel ist weder ein größeres
Modell noch ein anderer Dekoder, sondern **herauszufinden, welche Gruppen
kaputtgehen und warum**. Eine Fehleranalyse auf Gruppenebene, analog zur
Fehler-Taxonomie für die Labels.

### Und die Antwort darauf: es sind die Variantenblöcke

Ausgezählt über dieselben Dev-Seiten. Ein Block gilt als Variantenblock,
wenn seine Referenzgruppe mehr als einen PRICE oder mehr als eine
QUANTITY trägt:

| | Gruppen | getroffen | Recall |
|---|---:|---:|---:|
| alle | 122 | 96 | 0.787 |
| **ohne Variantenblöcke** | 103 | 91 | **0.883** |
| **Variantenblöcke allein** | **19** | **5** | **0.263** |

**19 Gruppen (16 %) verursachen 14 der 26 Fehler (54 %).** Unter den
verfehlten Gruppen sind 54 % Variantenblöcke, unter den getroffenen 5 % —
Faktor 11.

Belegte Fälle, alle von `1342812_p27` und alle Non-Food:

    Motivations-trinkflasche* | 4.99 | 4.99 | 5.99 | 7.99
    Kochgeschirr* | 9.99 | 14.99 | 17.99 | Kasserolle, | 14.99 | Topf, | 24.99
    1.49 | Grill-und-Abtropf-Schale*, | 1.49 | 2er-Set Steakmesser* | 3.99 | ...

**Damit lösen sich drei Muster in eines auf.** „Non-Food ist
überrepräsentiert", „verfehlte Gruppen sind größer" und „85 % zerfallen"
sind nicht drei Befunde, sondern derselbe: Variantenblöcke stehen fast nur
in Non-Food, sie sind naturgemäß groß, und ein flaches Gruppenlabel kann
sie nicht abbilden — also zerfallen sie.

**Das ist kein Modellfehler, sondern eine falsch gestellte Aufgabe.**
Genau die Lücke aus Issue #6: `offer` 1:n `variant(quantity, price,
old_price, unit_price)`. Auf allen anderen Angeboten liegt das System bei
Recall 0.883.

Wichtig für die Erwartung: Das 1:n-Schema hebt keine Zahl von selbst. Es
verlangt, dass **Referenz und Metrik die Hierarchie mitmachen** — die
heutige LLM-Referenz gruppiert flach. Wer nur das Datenbankschema ändert,
ändert die Aufgabe, nicht die Leistung. Die Zuordnung *innerhalb* eines
Blocks ist dagegen schon gelöst und gemessen: Größenvarianten paaren sich
positionsweise (26 von 43 Blöcken, 0 in anderer Reihenfolge).

**Vorbehalt zum Nenner, und er ist derselbe wie einst bei `magda eval`:**
Entities, die GBERT nicht findet, fehlen nicht als Falsch-Negative,
sondern **im Nenner**. Gemessen: 656 von 675 Referenz-Entities überleben
(97,2 %), 15 der 122 Referenzgruppen werden dadurch kleiner, die mittlere
Gruppengröße sinkt von 5,53 auf 5,38. Kleinere Gruppen sind leichter
exakt zu treffen — die absolute E2E-Zahl ist also **leicht nach oben
verzerrt**. Der gepaarte ILP-Union-Vergleich ist davon unberührt, beide
sehen dieselben Entities.

**Teil 3 dieses Specs (Widerspruch als drittes Auswahlkriterium) ist
gestrichen**, nicht vergessen: Die Referenz ist schon auf 75, in der Queue
stehen 5 Seiten, und die breiten Intervalle waren ohnehin ein Cluster- und
kein Datenproblem. Wieder relevant, falls Woche 4 den Auswahlpool füllt.
Begründung im Spec-Nachtrag.

**Teil 2 (Efficiency Frontier) ist noch frei** — `src/magda/frontier.py`
existiert nicht.

**Und er braucht mehr Vorarbeit als gedacht: Kein Report in `data/eval/`
enthält eine Zeitangabe.** Geprüft über `gbert_test`, `layoutxlm_test`,
`flair_llm_test`, `gbert_dev` und `offers_grid_dev_cv` — kein Feld für
Sekunden, Latenz oder Dauer. Die Zahlen 0,264 s je Seite und 44,8 s beim
LLM stehen in `CLAUDE.md`, aber ohne erzeugendes Skript; nach der eigenen
Projektregel („Keine Zahl ohne das Skript") sind sie damit nicht
nachrechenbar.

Der Frontier ist deshalb kein reiner Darstellungsschritt, sondern zwei
Aufgaben: **erst eine Zeitmessung je Konfiguration** (eigenes Skript,
gleiche Seitenmenge, gleiche Maschine — sonst vergleicht die X-Achse
Äpfel mit Birnen), **dann die Abbildung**. Die Zeitmessung ist unabhängig
von der offenen Blackbox-Referenzfrage und kann sofort gebaut werden; die
Abbildung kann ohne den Blackbox-Punkt erscheinen und ihn nachtragen.

---

## Nachtrag 5 (11.08.2026): die Variantenblöcke, out-of-fold nachgerechnet

Die Zahl aus Nachtrag 4 (19 Blöcke, Recall 0.263 gegen 0.883) hatte zwei
Mängel, die zusammen ihre Größenordnung erklären: sie war **auf Dev
gemessen** und stammte von einem **Checkpoint, der diese Seiten im
Training hatte**. Gebaut ist jetzt `magda offers-model variants`, damit
sie überhaupt ein Skript hat — bisher stand sie nur in dieser Notiz,
erzeugt von einem Wegwerf-Skript.

Out-of-fold über Train+Dev, 75 Seiten, 573 Referenzgruppen, davon **95
Variantenblöcke** (Merkmale: Basis, 30):

| Dekoder | alle | ohne Variantenblöcke | Variantenblöcke | Faktor |
|---|---:|---:|---:|---:|
| Union-Find | 239/573 = 0.417 | 0.425 | 0.379 | 1.12 |
| ILP | 301/573 = 0.525 | **0.546** | **0.421** | **1.30** |
| *Dev, Checkpoint (alt)* | *0.656* | *0.738* | *0.211* | *3.4* |

**Der Effekt ist real, aber ein Drittel so groß wie berichtet.** Dasselbe
Muster wie bei den Farbmerkmalen: ein Dev-Eindruck über 19 Einheiten
hält der Kreuzvalidierung über 95 nicht stand. Wer die 0.263 weiter
zitiert, zitiert eine In-sample-Zahl.

### Welche Kante ausfällt — und die Kontrolle, die es entscheidet

Mittlere Kantenwahrscheinlichkeit auf *zusammengehörigen* Paaren, ILP,
out-of-fold:

| Typpaar | in Variantenblöcken | sonst | Differenz |
|---|---:|---:|---:|
| **PRICE\|PRICE** | **0.639** (n=172) | – | *nur hier möglich* |
| **QUANTITY\|QUANTITY** | **0.868** (n=123) | – | *nur hier möglich* |
| PRODUCT\|PRODUCT | 0.814 | 0.962 | −0.149 |
| PRICE\|PRODUCT | 0.782 | 0.882 | −0.100 |
| QUANTITY\|UNIT_PRICE | 0.894 | 0.985 | −0.090 |
| BRAND\|PRODUCT | 0.959 | 0.991 | −0.031 |

**`QUANTITY|QUANTITY` ist die Kontrolle, und sie trägt den ganzen
Befund.** Beide Kantenarten gibt es *nur* in Variantenblöcken, beide
verbinden gleichartige Entities derselben großen Gruppe. Wäre die Ursache
die Gruppengröße (8.74 Entities gegen 5.03), müssten beide gleich leiden.
Tatsächlich liegt die Mengenkante bei 0.868 und die Preiskante bei 0.639.

Das Modell findet also **mehrere Größenangaben eines Blocks zusammen,
mehrere Preise nicht**. Die Erklärung steht seit Woche 1 im Projektwissen:
Penny setzt Mengen untereinander in den Fließtext und Preise in getrennte
gelbe Kästen. Für zwei Preise sagt die Geometrie „getrennt", und global
hat sie damit fast immer recht — zwei Preise sind fast immer zwei
Angebote.

Der allgemeine Größeneffekt existiert daneben, ist aber klein: alle
übrigen Kanten verlieren in Variantenblöcken nur 0.01 bis 0.15.

### Was das für die Richtung heißt

**Ein Dekoderwechsel scheidet aus.** Das ILP hebt den Variantenblock-Recall
zwar von 0.379 auf 0.421, aber es hebt alles andere im selben Zug
(0.425 → 0.546). Es schließt die Lücke nicht, es verschiebt beide Zahlen.

**Die ursprüngliche Hypothese hat sich bestätigt, aber erst beim ILP.**
Im Union-Lauf sah `PRICE|PRICE` unauffällig aus — die Schwelle 0.94
schneidet so hoch ab, dass alle Kanten gleichmäßig durchfallen und die
Rangfolge verschwindet. Erst bei der tieferen ILP-Schwelle (0.80–0.88)
trennt sich, welche Kante das Modell wirklich schwach bewertet. **Für
künftige Kantendiagnosen: die mittlere Wahrscheinlichkeit lesen, nicht
den Recall.** Der Recall ist eine Aussage über die Schwelle.

**Offener Vorbehalt:** gemessen mit den Basis-Merkmalen (30), weil der
Default-Checkpoint `('types', 'geometry_base')` trägt. Die Kontextmerkmale
(`products_between`, `closer_rivals`, `distance_ratio`) sind genau die,
die auf einen gemeinsamen Anker zielen könnten, und sie sind der einzige
Block mit belegtem Effekt (+0.044, p = 0.018). Der Lauf mit `--features
geometrie` steht aus; ohne ihn ist nicht entschieden, ob die Lücke ein
fehlendes Merkmal ist oder ein schon vorhandenes, das nur nicht im
Checkpoint steckt.

### Der Vorbehalt ist aufgelöst: +Geometrie wirkt an Variantenblöcken vorbei

Derselbe Lauf mit `--features geometrie` (35 Merkmale), ILP, out-of-fold
über dieselben 573 Gruppen:

| Merkmale | alle | ohne Variantenblöcke | Variantenblöcke |
|---|---:|---:|---:|
| Basis (30) | 0.525 | 0.546 | **40/95 = 0.421** |
| +Geometrie (35) | 0.574 | **0.605** | **40/95 = 0.421** |
| Differenz | +0.049 | **+0.059** | **±0.000** |

**Der einzige Merkmalsblock mit belegtem Effekt (+0.044, p = 0.018) hebt
alles außer den Variantenblöcken.** Dort unverändert 40 von 95 — *gleiche
Anzahl; ob es dieselben Gruppen sind, ist ungeprüft.* Der Report hielt
bisher nur Summen fest, verglichen wurden also zwei Zählungen, nicht zwei
Mengen. Die Aussage hängt nicht daran: die Preiskante bewegt sich um
+0.001 (0.639 → 0.639), während `QUANTITY|QUANTITY` +0.016 gewinnt.

Das ist kein Zufall, sondern die Bauart der Merkmale: `products_between`,
`closer_rivals` und `distance_ratio` sind **Trennmerkmale** — sie
beantworten „steht etwas dazwischen" und „gibt es einen näheren
Kandidaten". Ein Variantenblock braucht das Gegenteil: eine Verbindung
*trotz* Distanz und *trotz* näherer Konkurrenz.

**Die Lücke wächst dadurch**, von Faktor 1.30 auf **1.44**. Je besser das
Modell im Normalfall wird, desto deutlicher fallen Variantenblöcke
heraus. Sie sind mit 95 von 573 Gruppen (16,6 %) der größte
zusammenhängende Fehlerblock, den die Fehleranalyse bisher gefunden hat.

**Konsequenz für die Merkmalsfrage:** Ein Merkmal für Variantenblöcke ist
damit erstmals begründet, statt nur naheliegend. Der Vorschlag aus der
Struktur des Befundes — nicht aus dem Bauchgefühl — ist die
**Stern-Eigenschaft**: zeigen beide Entities auf denselben nächsten
Produktanker? Das ist genau die Form „n Preise, ein Name", enthält weder
Text noch die Rechnung, und es ist die Gegenrichtung zu den vorhandenen
Trennmerkmalen.

### Protokoll für den Ankerlauf, festgelegt vor dem Lauf

Vergleich `anker` (38 Merkmale) gegen `geometrie` (35), ILP, gepaarter
Bootstrap über die 68 Duplikat-Cluster, out-of-fold mit geschachtelter
Schwellenwahl, Primärzahl Gruppen-F1.

**Akzeptanzkriterium, damit es hinterher nicht beliebig ist: die
Variantenblock-Treffer müssen steigen *und* die Gesamtzahl darf nicht
fallen.** Nur eines von beiden reicht nicht — ein Merkmal, das
Variantenblöcke rettet und dafür anderswo verschmilzt, hat nichts
gewonnen.

**Erwartung, ebenfalls vorher:** Selbst bei vollem Erfolg sind es
95/573 × (0.605 − 0.421) ≈ **+0.03** insgesamt, also dieselbe
Größenordnung wie +Geometrie (+0.044). Wer mehr erwartet, hat den Anteil
der Variantenblöcke nicht angesehen.

**Zwei Vorbehalte, die mitgehören:** Das ist ungefähr der zehnte Vergleich
ohne Korrektur für multiples Testen. Und die Grenze des Merkmals steht
fest, bevor die Zahl da ist — Blöcke mit mehreren Produktnamen löst es
nicht.

### Ergebnis: das Ankermerkmal fällt durch

Out-of-fold über 75 Seiten in 68 Clustern, ILP, gepaart gegen `geometrie`:

| Variante | Merkmale | Paar-F1 | Gruppen-F1 | Angebote |
|---|---:|---:|---:|---:|
| geometrie | 35 | **0.569** | **0.553** | 588 |
| anker | 38 | 0.448 | 0.532 | 529 |

Gepaarte Differenz Gruppen-F1: **−0.021 [−0.060, +0.021], p = 0.318**;
im blinden Fleck −0.026, im prüfbaren Bereich −0.014.

**Das vorab festgeschriebene Kriterium verlangte: Variantenblock-Treffer
steigen *und* die Gesamtzahl fällt nicht.** Die Gesamtzahl fällt. Damit
ist das Kriterium verfehlt, und die Variantenblock-Zahl braucht gar nicht
mehr erhoben zu werden — sie könnte den zweiten Teil nicht heilen.

**Was das Merkmal tatsächlich tut, ist ablesbar:** Die kalibrierten
Schwellen sinken (0.76–0.86 gegen 0.86–0.88), es entstehen weniger
Angebote (529 gegen 588), und Paar-F1 bricht deutlich stärker ein als
Gruppen-F1. Es macht das Verschmelzen also mutiger — wie beabsichtigt —,
aber es verschmilzt das Falsche. Ein gemeinsamer nächster Anker ist
offenbar auch dann gegeben, wenn zwei Entities *nicht* zusammengehören;
auf einer Penny-Seite steht fast immer irgendein Produktname in der Nähe.

### Damit ist Merkmals-Engineering am Paarmodell ausgereizt

Vier Blöcke gemessen, out-of-fold und gepaart:

| Block | Differenz zur Basis bzw. zu +Geometrie | p |
|---|---:|---:|
| +Geometrie | **+0.044** | **0.018** |
| +Farbe | −0.008 | 0.596 |
| Farbe auf Geometrie, blinder Fleck | −0.051 | 0.042 |
| +Anker | −0.021 | 0.318 |

**Genau einer von vier hat gewirkt.** Drei zielten auf den blinden Fleck
bzw. die Variantenblöcke und haben ihn nicht getroffen. Das ist kein
Zufall mehr, sondern ein Befund über die Aufgabe: Was der Gruppierung
fehlt, ist keine weitere Zahl je Paar.

Der Code des Ankerblocks bleibt als optionaler Block stehen (nicht im
Default, `ANCHOR_BLOCKS`), damit der Negativbefund reproduzierbar ist und
niemand ihn ein zweites Mal baut — dieselbe Begründung wie bei
`blackbox.py`.
