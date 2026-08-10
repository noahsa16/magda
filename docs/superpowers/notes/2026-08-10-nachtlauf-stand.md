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
