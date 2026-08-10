# Angebots-Clustering: Regressionstests und ehrliche Messung

Stand 06.08.2026. Antwort auf Issue #6, Punkt 1 und 2. Punkt 3 (Schema
`offer` 1:n `variant`) bleibt ausdrücklich außen vor.

## Problem

`feature/db` bringt sieben Heuristiken ins Angebots-Clustering und keinen
einzigen Test. Die Docstrings nennen fünf belegte Fälle; keiner davon ist
festgeschrieben. Wer `_NEARBY_LIMIT` oder die 2-%-Schwelle in `_same_block`
anfasst, macht sie still kaputt, und alle 270 Tests bleiben grün.

Dazu behaupten die Commits Zahlen (77,5 % „Preis beim richtigen Produkt",
90,6 % „Angebote mit Produkt und Preis"), für die kein erzeugendes Skript im
Repo liegt. Beide Regeln aus CLAUDE.md sind damit verletzt.

Die Zahlen haben außerdem zwei inhaltliche Mängel:

1. **In-Sample.** Gemessen wurde über `data/predictions/gbert/`, und das sind
   exakt die 100 KW32-Testseiten. Alle fünf Kalibrierfälle aus den Docstrings
   liegen laut `data/splits/split.json` im Testsplit.
2. **Zirkulär.** „Preis im selben Angebot wie ein Produkt" zählt
   Fragmentierung, nicht Korrektheit: ein Preis am *falschen* Produkt geht als
   Erfolg durch.

## Warum die naheliegende Reparatur nicht funktioniert

Der erste Gedanke war, die Zuordnungen nach ihrem Weg zu trennen —
arithmetisch (Menge × Grundpreis) gegen geometrisch (nächster Anker) — und die
Arithmetik als unabhängiges Urteil über die geometrischen Fälle zu benutzen.

Das geht nicht. `_match_badges` betritt den geometrischen Zweig **nur, wenn
kein einziger Block arithmetisch gepasst hat** (`offers.py:577-592`). Für jede
geometrisch zugeordnete Preisangabe ist die Rechnung also per Konstruktion
bereits gescheitert; sie hinterher zu befragen liefert garantiert „falsch".

## Lösung: Ablation

Zum Messen wird der arithmetische Weg **abgeschaltet**. Die Geometrie ordnet
allein zu, anschließend urteilt die Arithmetik als unbeteiligter Richter:

| Urteil | Bedeutung |
|---|---|
| `confirmed` | Die Rechnung wählt denselben Block wie die Geometrie |
| `contradicted` | Die Rechnung wählt einen anderen Block derselben Seite |
| `unjudgeable` | Kein Grundpreis vorhanden — kein Urteil möglich |

Die Trefferquote ist `confirmed / (confirmed + contradicted)`. Sie misst genau
das schwache Bein des Verfahrens: den geometrischen Rückfall, der alles ohne
Grundpreis trägt — also praktisch das gesamte Non-Food-Sortiment.

Als Nebenprodukt fällt der Ertrag von Bogdans Kernidee an: die Differenz
zwischen „Geometrie allein" und „Geometrie plus Arithmetik" beziffert, was der
arithmetische Abgleich beiträgt.

**Gemessen wird auf `data/labeled/sonnet-5/`, eingeschränkt auf Train + Dev.**
Kein GBERT nötig, keine Testseite berührt.

## Architektur

### Eingriffe in `offers.py`

Zwei optionale Parameter, beide mit Default = heutiges Verhalten:

- `_match_badges(blocks, badges, page, *, arithmetic=True, trace=None)`
- `cluster_page(page, *, arithmetic=True, trace=None)`

`arithmetic=False` überspringt den `grundpreis_candidates`-Zweig. `trace` ist
eine Liste, an die je Preis-Badge ein `BadgeMatch` angehängt wird
(Weg, Preistyp, Wert, Zielblock-Index, Distanz).

Ohne diese Argumente verhält sich das Modul unverändert. Bestehende Aufrufer
(`cli/offers.py`, `write_sqlite`) und die drei vorhandenen Tests bleiben
unberührt.

### Neu: `src/magda/offers_report.py`

Reine Auswertung, keine I/O-Politik:

- `judge_page(page) -> PageVerdict` — führt die Ablation für eine Seite aus und
  urteilt je geometrischer Zuordnung.
- `collect(pages) -> Report` — aggregiert über Seiten, zusätzlich die
  nicht-zirkulären Fehlerzähler.

Nicht-zirkuläre Zähler (unabhängig von der Ablation):

- `offers_total`, `offers_with_product_and_price`, `fragments`
  (Angebot ohne Produkt oder ohne Preis)
- `blocks_without_matching_pairing` — Blöcke mit Menge *und* Grundpreis, bei
  denen keine Paarung den Preis trifft. Das ist der Fall aus CLAUDE.md
  (`1351497_p20`: drei zusammengeworfene Nachbarprodukte) und ein echtes
  Fehlersignal ohne Handannotation.

### Neu: `src/magda/cli/offers_report.py`

Schritt `magda offers-report`. Parst Argumente, lädt Seiten, ruft `collect`,
schreibt JSON nach `data/eval/offers_report_<labels>_<splits>.json` und gibt
eine Tabelle aus. Parameter:

- `--labels-from` (Default: `sonnet-5`)
- `--splits` (Default: `train,dev`; `test` ist zulässig, aber nicht Default)

Registrierung in `cli/__init__.py`, Import erst beim Aufruf.

## Datenfluss

```
data/labeled/<model>/*.json  ──┐
data/words/*.json  ────────────┼──> Seiten (Wörter + BIO)
data/splits/split.json  ───────┘         │
                                         v
                    cluster_page(arithmetic=True)   -> Ist-Zustand, Zähler
                    cluster_page(arithmetic=False)  -> Ablation, Urteile
                                         │
                                         v
                          data/eval/offers_report_*.json
```

## Fehlerbehandlung

- Fehlt `data/splits/split.json`, bricht der Schritt ab und verweist auf
  `magda split` — dieselbe Regel wie in `get_or_create_splits`.
- Seiten ohne Wortliste werden übersprungen und gezählt, nicht stillschweigend
  weggelassen; die Zahl steht im Report.
- Ein leerer Report (0 beurteilbare Zuordnungen) wird als solcher ausgewiesen,
  nicht als 0 % oder 100 %.

## Tests

### Regressionstests für die belegten Fälle

Je ein Test pro Docstring-Fall, gegen die echten Seiten aus `data/words/` und
die Labels aus `data/labeled/sonnet-5/`:

| Fall | Seite | Erwartung |
|---|---|---|
| FREIXENET/HARIBO | `1351497_p1` | Beide Marken landen nicht im selben Angebot |
| Obst-/Süßwarenzeile | `1351497_p1` | Zerfällt in mehrere Angebote |
| Fanta/Coca-Cola | `1351497_p1` | Menge und Grundpreis hängen am richtigen Produkt |
| Burger Patties/Lammspieße | `1351497_p10` | Preis folgt der Rechnung, nicht der Nähe |
| Varianten mit eigener Menge | `1351497_p13` | Getrennte Angebote |
| Lesereihenfolge in der Legende | `1351497_p28` | Legende zerfällt spaltenweise |

Diese Seiten liegen im Testsplit. Das ist hier vertretbar und wird im Modul
vermerkt: die Tests **frieren Verhalten ein**, sie berichten keine Zahl. Es
wird nie eine Konstante nachgezogen, damit einer grün wird — die Messung läuft
auf Train + Dev.

Ein Test, der die dokumentierte Erwartung nicht erfüllt, ist ein Befund und
wird als solcher berichtet, nicht weggedreht.

### Tests für das Messmodul

Gegen synthetische Seiten, weil hier Verhalten *neu* entsteht:

- Ablation ändert die Zuordnung: ein Preis, der geometrisch beim Nachbarn
  landet, aber arithmetisch zum eigenen Block gehört, wird `contradicted`.
- Ohne Grundpreis lautet das Urteil `unjudgeable`, nicht `confirmed`.
- `trace` protokolliert den Weg jeder Zuordnung.
- `arithmetic=True` (Default) liefert exakt das bisherige Ergebnis.
- Block mit Menge und Grundpreis, dessen Preis zu keiner Paarung passt, zählt
  als `blocks_without_matching_pairing`.

## Was diese Arbeit nicht tut

- **Kein Schema-Umbau.** `offer` 1:n `variant` bleibt Issue #6, Punkt 3.
- **Keine Änderung an Bogdans Heuristik.** Keine Konstante wird angefasst. Wenn
  die Messung schwache Stellen zeigt, ist das ein Befund für den PR, keine
  Einladung zum Nachjustieren.
- **Keine Aussage über Non-Food-Korrektheit.** Wo kein Grundpreis existiert,
  bleibt das Urteil `unjudgeable`. Diese Lücke schließt nur eine
  handannotierte Gruppierungsreferenz.
