# Woche 8 — Erste Testmessung der Gruppierungskette

Stand: 02.–03.09.2026

## Kurzfassung

Drei offene Punkte aus Woche 7 sind erledigt: der Lexikblock ist jetzt der
produktive Checkpoint, die Gruppierungskette (LayoutXLM-Entities plus
Paarmodell) ist zum ersten Mal auf dem vollen, eingefrorenen Testsplit
gemessen, und der Endvergleich gegen die LLM-Blackbox ist gelaufen — gegen
drei GWDG-Vision-Modelle (Qwen 3.6, Mistral medium 3.5, Gemma 4) statt
gegen `claude-sonnet-5` als Subagent, aus Budgetgründen. Die eigene
Pipeline (F1 0.839) liegt vor allen drei Blackbox-Modellen (F1 0.474 bis
0.554), aber der Abstand ist kleiner als die rohen Zahlen zeigen — ein
gemeinsamer Messfehler in Referenz und eigener Spalte drückt beide
Blackbox-Zeilen künstlich. Details unten.

| | Paar-F1 | Gruppen-F1 | Angebote |
|---|---:|---:|---:|
| **Paarmodell (Lexikblock, LayoutXLM-Entities)** | **0.932** | **0.778** | 978 |
| Heuristik | 0.781 | 0.439 | 1133 |
| Lehrer (Referenz) | – | – | 939 |

*(116 Testseiten, KW35, Referenz `data/offer_groups/claude-sonnet-5/`,
Schwelle 0.68 out-of-fold über 494 Trainingsseiten kalibriert, ILP-Dekoder.)*

Der Wert deckt sich fast exakt mit dem Dev-Ergebnis vom 30.08. (0.932/0.778,
siehe [`woche-07.md`](woche-07.md)) — kein Hinweis auf eine Schwelle, die an
Dev überangepasst wäre. Zweiter Fund der Woche: die für den späteren
Blackbox-Vergleich vorbereitete Seitenliste war seit dem Wochen-Split vom
25.08. stillschweigend falsch.

## Der Checkpoint

`checkpoints/offer_pairs/model.pt` trug bis heute den Merkmalsblock
`geometrie` (35 Merkmale) — der Lexikblock (+0.119 Gruppen-F1, siehe Woche 7)
existierte nur im Gitter-Report, nicht als lauffähiges Modell. Nachtrainiert:

```
magda offers-model train --features lexik --splits train \
    --out checkpoints/offer_pairs/model.pt
```

494 Seiten, 781902 Paare, 5 Folds, ILP-Dekoder, 44,5 Minuten auf einem Kern
(MacBook Air M2). Out-of-fold-Kalibrierung wählt Schwelle 0.68 (Kriterium
`group_f1`), Paar-F1 0.914, Gruppen-F1 0.729 über die Trainingsseiten selbst
— die Zahl, die zählt, ist die Testmessung unten, nicht diese.

Der vorige Checkpoint (`geometrie`) liegt jetzt als
`checkpoints/offer_pairs/model.geometrie.pt` daneben, damit ein Vergleich
gegen den alten Stand nicht verloren ist. `checkpoints/` ist gitignored;
beide Dateien liegen nur lokal.

## Die Testmessung

Vorbereitung: LayoutXLM-Vorhersagen für den vollen Testsplit lagen nicht
vor — `data/predictions/layoutxlm/` enthielt einen veralteten Mix aus einem
Dev-Lauf (56 Seiten, Index-Metadaten vom 29.08.) und Resten eines noch
älteren Laufs. Neu erzeugt:

```
magda predict layoutxlm --split test --labels-from sonnet-5
```

116 Seiten, 25351 Wörter, 5865 Entities, rund 12 Sekunden Inferenz plus
Modell-Ladezeit. Danach:

```
magda offers-model eval --predictions layoutxlm --labels-from sonnet-5 \
    --splits test
```

**Kette Stufe 1 → Stufe 2** (wie viel der Gruppierungsaufgabe stehen bleibt,
nachdem der Labeler seine eigenen Entities liefert statt der Lehrer-Labels):

- Entity-F1 (strict): 0.924 — 5467 von 5973 Referenz-Entities getroffen
- Überlebende Referenzpaare: 0.902 — 16905 von 18739

**Unabhängige Gegenprobe** (Menge × Grundpreis, kein Merkmal des Modells):
Genauigkeit 0.864 bei Abdeckung 0.560 (bestätigt 567, widerlegt 89, ohne
Treffer 77, unbeurteilbar 439 — überwiegend Non-Food ohne Grundpreis). Die
Heuristik liegt bei 0.831 Genauigkeit auf praktisch gleicher Abdeckung
(0.546), ist dabei aber milder zu lesen: `cluster_page` ordnet teils selbst
arithmetisch zu, der Richter ist dort nicht unbeteiligt.

Report: `data/eval/offers_model_test_ilp_pred-layoutxlm.json`.

**Einschränkungen, die mitgehören:** Ein Lauf, keine Seed-Streuung, kein
Konfidenzintervall über die Testcluster — dafür fehlt `per_page` im
Report des Trainingslaufs (offener Punkt seit Woche 7). Der Lehrer ist ein
LLM; gemessen wird Übereinstimmung, nicht Richtigkeit. Der Testsplit ist
damit einmal angefasst — weitere Änderungen an Merkmalen oder Schwelle
brauchen wieder Dev.

## Fund: `data/eval/test_cluster_pages.txt` war stale

Die Datei wurde am 10.08.2026 angelegt (Commit 58a6437) für den damaligen
Blackbox-Vergleichsarm — 43 Zeilen, gedacht als eine Seite je
Duplikat-Cluster des Testsplits. Der Wochen-Split wurde am 25.08.2026 neu
gezogen (KW35 testet statt KW32, andere Kataloge); die Datei wurde dabei
nicht nachgezogen. Überschneidung mit dem aktuellen Testsplit: **0 von 43**.

Für die heutige Messung war das folgenlos, aus einem zweiten, unabhängigen
Grund: Seit dem 25.08.2026 sind alle 666 gelabelten Seiten unter
`data/offer_groups/claude-sonnet-5/` gruppiert — auch der komplette aktuelle
Testsplit. Der ursprünglich geplante Schritt (`magda offers-teacher` über
die 43 Zeilen laufen lassen, um Lehrer-Gruppierungen für den Test zu
gewinnen) war damit gegenstandslos; gemessen wurde direkt über alle 116
Testseiten statt über eine 43er-Auswahl.

Betroffen bleibt `magda blackbox-eval --pages
data/eval/test_cluster_pages.txt`: Wer diesen Vergleich fährt, ohne die
Datei vorher neu zu ziehen, misst auf Seiten, die nicht mehr Test sind.
Neu ziehen heißt: `dataset.duplicate_clusters()` über `split.json["test"]`,
ein Vertreter je Cluster (aktuell 42 statt 43 Cluster). Nicht ohne
Rücksprache repariert, weil das Design des Blackbox-Vergleichs laut
Woche 7 bewusst vertagt ist.

## Der Blackbox-Vergleich ist gelaufen — gegen drei Modelle

Noch am selben Tag entschieden (Budgetgründe: ein Claude-Subagent als
Blackbox hätte Sitzungskontingent statt GWDG-Kontingent gekostet) und
ausgeführt: `magda blackbox-eval` gegen drei GWDG-Vision-Modelle statt
gegen `claude-sonnet-5` als Subagent wie am 29.08. geplant. Nebeneffekt:
Referenz (`claude-sonnet-5`) und Blackbox laufen dadurch nicht mehr in
derselben Modellfamilie — weniger Zirkelschluss als ursprünglich
vorgesehen.

Der alte Extraktions-Prompt (`name`/`price`/`original_price`/`discount_pct`/
`period`, aus dem Vorgängerprojekt) kannte weder `quantity` noch
`unit_price` — genau die Lücke, die die arithmetische Gegenprobe für diesen
Arm bisher verhinderte. Neu geschrieben, an `labeling._PROMPT` und den
Gruppierungs-Teacher angelehnt, Version 1 in
`docs/blackbox-extraction-prompt.md`. Die Gegenprobe selbst ist damit
vorbereitet, aber nicht verdrahtet — offen, siehe unten.

**Zwei Fehler sind beim ersten Durchlauf aufgefallen und behoben, bevor die
hier berichteten Zahlen entstanden:**

1. `gemma-4-31b-it` antwortete bei Text-vor-Bild mit "du hast mir noch kein
   Bild geschickt" — das Modell verarbeitete das Bild schlicht nicht, mit
   und ohne `enable_thinking`-Schalter reproduzierbar. Behoben durch
   Bild-vor-Text in der Nachricht; Mistral und Qwen verarbeiten beide
   Reihenfolgen gleich, die Änderung ist für sie folgenlos.
2. `max_tokens=4096` war für Seiten mit vielen kleinen Angeboten (v. a.
   Non-Food/Deko) zu knapp — 7 von 42 Seiten brachen bei Mistral
   mittendrin ab. Auf 8192 angehoben; zusätzlich wiederholt
   `extract_deals_from_page_with_retry` jetzt auch abgeschnittene/kaputte
   JSON-Antworten (nicht nur Netzwerkfehler wie beim Labeling), weil bei
   `temperature=0.2` derselbe Aufruf beim zweiten Versuch reproduzierbar
   vollständiges JSON lieferte — das Abschneiden ist eine gelegentliche
   Wiederholungsschleife, kein stabiler Fehler.

Dazu eine dritte, betriebliche Lehre: **die drei Modelle nicht parallel
laufen lassen.** Ein erster Versuch mit allen drei gleichzeitig löste bei
Mistral und Gemma reihenweise HTTP-429-Fehler aus (gemeinsames
GWDG-Kontingent) — 13 bzw. 20 von 42 Seiten verworfen. Verworfen und
sequenziell wiederholt.

Lauf über die (neu gezogenen) 42 Testcluster-Vertreter, `--predictions
layoutxlm`, jedes Modell einzeln, alle Zahlen aus den JSON-Reports
nachgerechnet, nicht aus der Konsolenausgabe übernommen:

| | Treffer | System | Referenz | Präzision | Recall | **F1** | Fehler | s/Seite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| eigene Pipeline gegen Referenz | 222 | 264 | 265 | 0.841 | 0.838 | **0.839** | – | ~0,1¹ |
| Qwen 3.6 (35B) gegen Referenz | 162 | 334 | 265 | 0.485 | 0.611 | **0.541** | 0/42 | 6.8 |
| Gemma 4 (31B) gegen Referenz | 154 | 291 | 265 | 0.529 | 0.581 | **0.554** | 3/42 | 37.3² |
| Mistral medium 3.5 gegen Referenz | 151 | 372 | 265 | 0.406 | 0.570 | **0.474** | 2/42 | 33.7² |

¹ LayoutXLM-Inferenz (~0,1 s/Seite, siehe Testmessung oben) plus
Gruppierung (0,002–0,003 s); die im Report stehende „eigene Pipeline"-Zeit
zählt nur Letzteres und ist ohne diesen Zusatz nicht fair vergleichbar.
² Inklusive Retry-Overhead auf den paar gescheiterten Seiten — die reine
Inferenzzeit liegt darunter.

Reports: `data/eval/blackbox_test_qwen3.6-35b-a3b.json`,
`data/eval/blackbox_test_mistral-medium-3.5-128b.json`,
`data/eval/blackbox_test_gemma-4-31b-it.json`. Fehlerhafte Seiten fließen
mit 0 Angeboten in `system` ein (Recall-Verlust, kein Absturz des Laufs).

**Reihenfolge unter den drei Blackbox-Modellen:** Gemma vor Qwen vor
Mistral — aber knapp (0.554/0.541/0.474), und alle drei liegen deutlich
hinter der eigenen Pipeline (0.839). Mistral erzeugt mit Abstand die
meisten Angebote (372 gegen 265 Referenz) und hat dadurch die schwächste
Präzision; Gemma bleibt am nächsten an der Referenzmenge (291) und liefert
keine einzige exakte Duplikat-Angebotszeile, dafür die meisten
JSON-Syntaxfehler (3, alle nach drei Versuchen noch kaputt — ein
Zuverlässigkeitsproblem, unabhängig von der Extraktionsqualität).

**Der Vergleich ist insgesamt optimistischer zu lesen, als die Zahlen
nahelegen — Stichprobe auf `1364390_p21` gezogen, Befund gilt für alle drei
Modelle gleichermaßen:**

- Alle drei Blackboxen erzeugen systematisch mehr Angebote als die
  Referenz und drücken damit ihre eigene Präzision. Ein Teil davon sind
  aber keine Halluzinationen: Auf der Stichprobenseite fand die Blackbox
  "Storck Nimm2 Soft/Sommer Hit" und "Axe Deo/Body wash" — beide Marken
  sind in `data/labeled/sonnet-5/1364390_p21.json` korrekt als
  `B-BRAND`/`B-PRODUCT` gelabelt, tauchen aber **weder in der Referenz
  noch in der eigenen Pipeline** als Angebot auf. Grund: beide Spalten
  bauen ihre Angebote über `offers.cluster_page` - dieselbe Heuristik, die
  hier den Preis nicht zum Produkt gruppiert. Das ist exakt die
  Einschränkung, vor der `blackbox_eval.py`s eigener Docstring warnt ("die
  Zeile 'eigene gegen Referenz' vergleicht die Heuristik weitgehend mit
  sich selbst") - hier wird sichtbar, dass sie auch jede Blackbox-Zeile
  trifft, weil dieselbe Heuristik die Referenz *und* die eigene Spalte
  bildet.
- Vereinzelt falsch gelesene Preise (z. B. Sagrotan No Touch: 2.59 statt
  2.49 bei Qwen) verfehlen bei `price_tolerance=0.0` einen sonst korrekten
  Treffer vollständig.
- Echte Qualitätsprobleme gibt es trotzdem, modellabhängig unterschiedlich
  stark: Duplikat-Angebote (identischer Name und Preis auf derselben
  Seite) bei Qwen 1,5 % (5/334), Mistral 2,7 % (10/372), Gemma 0 % — ein
  Generierungsfehler, keine Referenzlücke.
- Die Zeitangabe ist nicht direkt vergleichbar, siehe Fußnote ¹ oben: die
  faire Zahl ist eher **Faktor ~70 (Qwen) bis ~370 (Mistral/Gemma inkl.
  Retries)**, nicht der Faktor 3500+, den die rohen Sekundenwerte allein
  suggerieren.

**Ergebnis:** die eigene Pipeline liegt vor allen drei Blackbox-Modellen,
über die ganze getestete Bandbreite (Qwen, Gemma, Mistral) konsistent.
Aber der Abstand ist kleiner, als die rohen F1-Werte zeigen - ein
spürbarer Teil davon ist Messartefakt (gemeinsamer Flaschenhals
`cluster_page`, strikte Preisgleichheit, eine Handvoll Duplikate), kein
reiner Qualitätsunterschied. Für den Kostenvergleich bleibt die Aussage
robust: 0,1 s gegen mehrere Sekunden je Seite bei niedrigerer Trefferquote
UND geringerer Zuverlässigkeit (0 bis 3 von 42 Seiten scheitern ganz).

## Offen

- **Konfidenzintervall für die Testmessung.** `per_page` fehlt weiterhin im
  Report (offener Punkt aus Woche 7) — ohne die seitenweisen Zählungen ist
  0.778 eine Punktschätzung, kein Intervall. Dasselbe gilt für die drei
  Blackbox-F1-Werte oben — 42 Seiten in 42 Clustern, kein Bootstrap
  gerechnet.
- **Die arithmetische Gegenprobe für die Blackbox-Spalte** ist mit
  `quantity`/`unit_price` im Schema vorbereitet, aber nicht verdrahtet -
  `blackbox_eval.compare_pages` kennt weiterhin nur `name`/`price`/
  `original_price`.
- **`offers.cluster_page` als gemeinsamer Flaschenhals** von "Referenz" und
  "eigene Pipeline" im Blackbox-Vergleich. Der Docstring von
  `blackbox_eval.py` nennt `data/offer_groups/claude-sonnet-5/` (die
  tatsächliche Teacher-Gruppierung statt der Heuristik) als Alternative -
  das wäre ein zweiter Testlauf und damit eine bewusste Abweichung vom
  „Testsplit einmal anfassen"-Grundsatz. Nicht ohne Rücksprache wiederholt.
- **Gemmas JSON-Zuverlässigkeit** (3 von 42 Seiten auch nach drei Versuchen
  syntaktisch kaputt) ist nicht weiter untersucht — offen, ob ein anderes
  Response-Format (z. B. `response_format: json_object`, falls die GWDG-
  Bereitstellung das unterstützt) das behebt.
- **Über den Anker entscheiden** (ersetzt durch den Lexikblock, schadet in
  Kombination) — unverändert offen aus Woche 7.
