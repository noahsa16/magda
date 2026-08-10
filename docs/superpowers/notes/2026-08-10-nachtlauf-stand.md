# Nachtlauf 10./11.08.2026 — Stand und Übergabe

Branch: `offers/farbmerkmale`. Ein zweiter Claude arbeitet parallel im Repo —
**kein `git add -A`**, immer explizite Pfade.

## Erledigt

| Paket | Commit | Ergebnis |
|---|---|---|
| Gitterlauf festhalten | `d709202` | Lehrer-Entities, korrigiertes Farbmerkmal |
| Plan B/1 (PFLICHT) | `58a6437` | Blackbox-Arm gebaut, **nicht** auf Test gefahren |
| Plan A/1 | `9cb24cc` | erste Ende-zu-Ende-Zahl des Projekts |
| Plan B/2 Code, B/3 Code | in `9cb24cc` | `subset_by_clusters`, `--train-pages`, `eval --pages` |

## Die drei Reparaturen, ohne die A/1 falsch gewesen wäre

1. **Report-Dateiname trug den Splitnamen, nicht die Entity-Quelle.** Der
   Vorhersagelauf hätte den Lehrerlauf still überschrieben — beide messen
   `dev`. Jetzt `offers_grid_dev.json` gegen `offers_grid_dev_gbert.json`.
2. **`--predictions` galt auch für die Trainingsseite**, für die es keine
   Vorhersagen gibt (0 Seiten). Neu: `--train-labels-from`.
3. **`magda train` schrieb nach `checkpoints/<variante>`**, ohne Rücksicht auf
   `--labels-from`. Jeder Nebenlauf hätte den eingefrorenen KW30/31-Stand
   gelöscht. Neu: `checkpoint_name()`, dazu `--checkpoint` in `eval`/`predict`.

## Die Zahl und ihr Nenner

Gruppen-F1 auf Dev, Referenz `data/offer_groups/claude-sonnet-5`:

| Entities | Basis | +Geometrie | +Farbe | beide |
|---|---|---|---|---|
| Lehrer (sonnet-5) | 0.477 | 0.540 | 0.472 | 0.492 |
| Schüler (gbert) | 0.504 | 0.556 | 0.504 | 0.502 |

**Die zweite Zeile ist nicht besser, sondern auf kleinerem Nenner gemessen:**
1855 von 1996 Referenzpaaren überleben (0.929). Nicht als Verbesserung lesen.

Im blinden Fleck ist `beide` auf **beiden** Entity-Quellen die beste Variante
(Paar-F1 0.782 bzw. 0.740 gegen 0.737 / 0.640 der Basis). Zwei unabhängige
Quellen, dasselbe Vorzeichen — aber die Intervalle reichen bis 1.000, also
kein Befund.

## Offen, in dieser Reihenfolge

1. **Plan A/2 — APP_PRICE-Übernahme.** Neues Modul `src/magda/audit_apply.py`
   plus CLI, schreibt nach `data/labeled/sonnet-5-app/`. **Nie** nach
   `data/labeled/sonnet-5/`. Danach `magda train gbert --labels-from
   sonnet-5-app` (landet dank `checkpoint_name` in `gbert-sonnet-5-app`) und
   `magda eval gbert --checkpoint gbert-sonnet-5-app --split dev`. Erwartet:
   82 geänderte Label, 72 Train / 9 Dev / 0 Test. Code steht fertig im Plan.
2. **Plan B/2 — die vier Trainingsläufe.** `for n in 25 50 100 175`. Je 96 s.
   Auswertung **nicht** jetzt, die gehört in den Schlussbatch.
3. **Plan B/4 — Fehler-Taxonomie** auf Dev, fünf Klassen mit
   Lösbarkeits-Spalte.
4. **Plan A/3 — Gruppierungsreferenz 51 → 80.** Teacher-Subagenten mit
   Seitenbild, Modell **sonnet**, sonst lügt der Ordnername
   `claude-sonnet-5`. Blöcke von zehn, nach jedem Block Bestand prüfen.

## Gesperrt — nicht anfassen

- **Plan B/6, der eine Testbatch.** Setzt Aufgabe 5 voraus (4 h Handarbeit
  am `/audit`-UI). Der Testsplit wird genau einmal angefasst; ihn zu
  verbrennen, während Noah schläft, ist nicht rückholbar.
- **Plan B/7, zweiter Händler.** Braucht einen Download von einer fremden
  Seite — ausdrückliche Erlaubnis nötig.
- **Plan A/4, Woche 4 labeln.** Erst prüfen, wie `data/labeled/sonnet-5/`
  tatsächlich entstanden ist; `sonnet-5` ist kein GWDG-Modell, `magda label
  --model sonnet-5` ist also vermutlich nicht der Weg.

## Dauerregeln

`.venv/bin/` statt `python`. Nie auf `main`. Testsplit einmal, am Ende.
Labelquelle **immer sonnet-5**, nie mistral oder qwen —
`config.default_labeled_model()` liefert `mistral-medium-3.5-128b` und ist an
dieser Stelle eine Falle, deshalb `config.CANONICAL_LABELS`.
