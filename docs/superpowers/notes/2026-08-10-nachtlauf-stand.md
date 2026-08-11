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
