# Nachtlauf 11./12.08.2026 — KW33 labeln und alles gruppieren

Ziel (Teamansage Noah): die sonnet-5-Labels auf **alle** Seiten ausbreiten,
Entities *und* Angebotsgruppen, danach neu trainieren.

## Ausgangslage

| Woche | extrahiert | Span-Labels | Gruppen-Labels |
|---|---:|---:|---:|
| KW30 | 89 | 89 | 38 |
| KW31 | 107 | 107 | 37 |
| KW32 | 100 | 100 | **0** |
| KW33 | 126 | **0** | **0** |
| | 422 | 296 | 75 |

Die beiden Nullen sind die ganze Arbeit: 126 Span-Labels und 347
Gruppierungen.

## Was heute gebaut wurde

**`magda label-teacher pages|task|save`** (Commit `cb8b7c7`). Es gab keinen
Weg, mit sonnet-5 zu labeln: `magda label` erreicht nur die GWDG-Modelle,
und die Referenzlabels tragen `source: "annotation"` — sie stammen von
einem Agenten mit Bildzugriff. KW33 war schlicht nicht labelbar, ohne die
Labelquelle zu wechseln.

Der Inhalt des Moduls ist der Guard-Pfad. `finish_spans` kettet
`trim_spans` und *danach* `apply_app_price_rule`, dieselbe Reihenfolge wie
`magda label --repair`. Eine Woche mit anderen Konventionen wäre kein
zusätzlicher Datensatz, sondern ein zweiter.

**`magda offers-teacher view`** (Commit `2b0288e`). Gruppierungen als
Seitenbild mit farbigen Wortboxen. Bei 347 maschinell erzeugten
Gruppierungen ist die einzige Alternative, der Zahl am Ende zu glauben.

**`magda offers-grid --curve`** (Commit `a9c1eff`). Lernkurve des
Paarmodells, out-of-fold. Beschneidet clusterweise nur die innere Menge
je Fold; die äußere bleibt ganz, sonst wären die Punkte auf verschieden
großen Nennern gemessen.

**`magda offers-model train --features`**. Der ausgelieferte Checkpoint
trug 30 Merkmale (Basis) und war für Union-Find kalibriert — zweimal die
gemessen unterlegene Variante, und der Befehl konnte die bessere gar nicht
bauen. Neue Defaults: `geometrie` (+0.044, p = 0.018) und `ilp` (+0.100,
p = 0.000).

## Belegt: der Agenten-Pfad ist konventionsgleich

Drei Seiten aus KW30/31 neu gelabelt, `magda agreement sonnet-5
sonnet-5-recheck`: **95.2 %** Wortübereinstimmung (1.000 / 0.994 / 0.887).
Zwischen Mistral und sonnet-5 sind es 82.2 %.

Die Abweichung sitzt auf zwei Labels, die beide in CLAUDE.md offen sind:
APP_PRICE 11.1 %, QUANTITY 80.4 %. BRAND, OLD_PRICE, DISCOUNT und VALID
sind zu 100 % einig.

Beim Nachsehen auf `1342812_p38` zerfällt sie in zwei Klassen, und **keine
ist inhaltlicher Dissens**:

1. *Dieselbe Entscheidung, andere Textstelle.* `9.99` steht an Index 65 und
   85, `1.59` an 179 und 187. Beide Läufe halten den Preis für einen
   App-Preis und zeigen auf verschiedene Vorkommen desselben Zahlenwerts.
   seqeval zählt Positionen — ein Teil der berichteten APP_PRICE-Schwäche
   ist Positionswahl, nicht Klassifikation.
2. *Die bestehende Referenz hat Lücken.* Der Recheck labelt `Einzelpreis je
   400 g 0.89,`, `Abtropfgewicht = 280 g (1 kg = 3.18)` und
   `12 x 280 g (1 kg = 2.65)`; im Bestand sind alle drei durchgehend `O`.

## Taktung: das Session-Limit ist der Engpass

Erster Versuch mit **10 parallelen Agenten**: alle zehn nach Minuten am
Session-Limit gescheitert, 2 von 50 Seiten durchgekommen. Eine Seite kostet
den Subagenten rund 100k Token, das Seitenbild dominiert.

Das Limit ist ein **Durchsatz pro Zeitfenster, kein Vorrat**. Drei Agenten,
die durchlaufen, schaffen über acht Stunden mehr als zehn, die sofort
abstürzen und dann 45 Minuten warten. Chargengröße 4 statt 5, damit ein
Abbruch weniger Arbeit kostet.

## Was läuft

- **Span-Labeling KW33**: 122 offen, 31 Chargen zu 4 Seiten, 3 Agenten
  gleichzeitig. Fortschritt: `magda label-teacher pages`.
- **Lernkurve Paarmodell**: `--curve 10,20,35,0`, out-of-fold über 75
  Seiten in 68 Clustern, ILP. Ein Punkt ≈ 34 min. Log im Scratchpad.

## Nachtrag: Gruppieren läuft parallel mit (auf Nachfrage Noah)

Ein Agent erledigt für eine KW33-Seite **beide** Stufen — labeln, dann
gruppieren. Das Seitenbild (~100k Token) ist der teure Teil und nach dem
Labeln schon im Kontext; die Gruppierung kostet fast nichts extra. Für die
221 Altseiten (haben schon Spans) laufen reine Gruppierungschargen.

`offers-queue --splits test` freigeschaltet: der Testsplit hatte null
Gruppierungen, damit ist die zweite Stufe auf Test überhaupt erst messbar.
Acht Vorschläge decken 41 der 100 Testseiten. `--reference-from` zählt den
Teacher-Bestand als erledigt (sonst kommen dieselben Seiten wieder).

Reihenfolge der Gruppierung: **Testseiten zuerst** (schalten die erste
ehrliche Test-Messung frei), dann Train/Dev-Rest, dann KW33 im Verbund mit
dem Labeln.

## Zwischenstand ~00:30

- **Test-Gruppierung vollständig:** jeder Duplikat-Cluster des Testsplits
  hat eine Referenz (42/100 Seiten, restliche 58 sind Duplikate innerhalb
  abgedeckter Cluster). Die zweite Stufe ist damit **erstmals auf Test
  messbar** — vorher null Testgruppen.
- **Lernkurve fertig und committet** (`ace7b75`): Gruppen-F1 sättigt bei 60
  Trainingsseiten nicht, +0.101 gegen 10 Seiten (p=0.000), im blinden Fleck
  +0.142. Mehr Gruppierungsreferenz hilft — der Nachtlauf ist belegt sinnvoll.
- **KW33-Labels:** ~71 offen, kombinierte Chargen (labeln+gruppieren je
  Seite) laufen weiter.
- **Zwei Vergabelisten** im Scratchpad (`vergeben.json` für Labels,
  `group_vergeben.json` für Gruppierungen) verhindern Doppelvergabe an
  gleichzeitig laufende Agenten. Leere Seiten (nur VALID, keine Entities)
  sind dort dauerhaft vermerkt, sonst schlägt die Queue sie ewig vor.

## Zwangspause 00:22–04:00 (Session-Limit)

Drei kombinierte Chargen (Y/AA/AB) gleichzeitig rissen das Limit erneut —
Reset 4 Uhr. Lehre bestätigt: auch drei token-schwere kombinierte Chargen
(~150k je Stück) sind zu viel gleichzeitig. **Nach dem Reset höchstens zwei
kombinierte parallel, oder eine kombinierte plus zwei leichte
Gruppierungschargen.**

Stand bei der Pause: Labels 354/422 (68 KW33 offen), Gruppierungen 142,
Testsplit vollständig. Alles committet, Vergabelisten zurückgesetzt
(`vergeben.json` leer, `group_vergeben.json` nur die zwei leeren Seiten
1351497_p9, _p24). Ein Hintergrund-Timer (`sleep` bis ~04:05) reaktiviert
den Lauf; bei erneutem Limit kurz weiterschlafen und wieder versuchen.

## Danach, in dieser Reihenfolge

1. **Alle Seiten gruppieren** (347). Werkzeug steht, Kontrolle mit
   `offers-teacher view`. Alle statt einer Auswahl, damit jede
   Split-Entscheidung offenbleibt.
2. **Split-Entscheidung** — steht unter *Nicht ohne Rücksprache*. Mit vier
   Wochen wäre KW30–32 Training und KW33 Test: Zeitrichtung intakt,
   Training von 196 auf 296 Seiten. Preis: alle bisherigen Zahlen sind
   nicht mehr direkt vergleichbar. Braucht Bogdan und Kjell.
3. **Neu trainieren und messen.** Erstmals möglich: die Gruppierung auf dem
   Testsplit messen. Bisher hat Test null Gruppen-Labels — *jede*
   Gruppierungszahl des Projekts ist eine Dev-Zahl.

## Aufräumen, das noch aussteht

`data/offer_groups/kw33-pipeline/` ist die Ausgabe des Paarmodells vom
Lauf mit dem falsch kalibrierten Checkpoint. In einer Auflistung sieht sie
aus wie eine Referenz. Löschen, sobald mit dem neuen Checkpoint neu
gruppiert ist.

## Fortsetzung 12.08.2026 vormittags

Session-Limit weg, Labeling wieder aufgenommen. Taktung: 3 Agenten je
Welle, 3 Seiten pro Agent, beide Stufen kombiniert. Nach jeder Welle
committet der Koordinator mit **expliziten Dateipfaden** (nicht
verzeichnisweit) - `zsh` macht kein Word-Splitting bei unquoted `$FILES`,
und der Blackbox-Parallelprozess schreibt in denselben Baum.

**Zwei Befunde beim Wiederaufnehmen, beide von Noah ausgelöst:**

1. **15 von 144 Gruppierungen waren aus Mistral-Entities gebaut**, nicht
   aus sonnet. `offers-teacher task` nimmt `args.labels_from or
   config.default_labeled_model()`, und `default_labeled_model()` liefert
   den *größten* Labelordner. Als der frühe Nachtlauf lief, war der
   Mistral-Ordner (296) größer als der sonnet-Ordner - der Default kippte
   mit der Größe. Inzwischen hat sonnet 354 und gewinnt, aber die 15 frühen
   Seiten (alle KW30-32, denn Mistral hat kein KW33) tragen Mistrals
   Entity-Grenzen. **Aufräumarbeit: diese 15 aus sonnet-5 neu gruppieren.**
   Der Aufruf muss künftig `--labels-from sonnet-5` global tragen (steht
   jetzt im Agenten-Prompt). Gemessen: App-Preis-Wörter von sonnet-5 landen
   zu 113/116 in einer Gruppe.

2. **Die Website zeigte die Gruppierungen nicht.** `/api/offer-gold` las nur
   `gold/offers/` (eine Datei), während die 142+ sonnet-Gruppierungen in
   `data/offer_groups/claude-sonnet-5/` liegen. Behoben mit einer
   Overlay-Sicht (Commit `f40988f`): Hand-Annotation vor sonnet-Default, neues
   Feld `source`. Bewusst **nicht** `offers_gold.reference_dir()` global
   umgebogen - die Funktion speist auch `magda offers-gold`, und die Messung
   gegen den Teacher wäre Selbstbezug. Zwei Tests, tamper-gegengeprüft.

Noah hat außerdem bekräftigt, was CLAUDE.md schon sagt: **sonnet-5 IST der
Goldstandard** (nicht `gold/`), Mistral wird nicht benutzt. Im Gedächtnis
verankert.

**Zwei offene Teamentscheidungen, die nicht eigenmächtig fallen:**
- sonnet-5-app (81 handgeprüfte Audit-App-Preise, Weg A) in die Referenz
  übernehmen? Sonst erben die Gruppierungen sonnet-5s App-Preis-Lücken.
- Split: wird KW33 die Testwoche? Blockiert das Retraining, gehört zu
  Bogdan und Kjell.
