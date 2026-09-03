# Woche 8 — Erste Testmessung der Gruppierungskette

Stand: 02.–03.09.2026

## Kurzfassung

Drei offene Punkte aus Woche 7 sind erledigt: der Lexikblock ist jetzt der
produktive Checkpoint, die Gruppierungskette (LayoutXLM-Entities plus
Paarmodell) ist zum ersten Mal auf dem vollen, eingefrorenen Testsplit
gemessen, und der Endvergleich gegen die LLM-Blackbox ist gelaufen — gegen
drei GWDG-Vision-Modelle (Qwen 3.6, Mistral medium 3.5, Gemma 4) statt
gegen `claude-sonnet-5` als Subagent, aus Budgetgründen. Die eigene
Pipeline (LayoutXLM + Paarmodell, F1 0.811 gegen die Teacher-Gruppierung)
liegt vor allen drei Blackbox-Modellen (F1 0.592 bis 0.695). Ein erster
Durchlauf hatte 0.839 gegen 0.474–0.554 ergeben; die Differenz zwischen
beiden Tabellen ist vollständig ein Messaufbau-Effekt und unten als
2×2-Aufschlüsselung belegt. **Wichtigste Einschränkung, die für den ganzen
Blackbox-Vergleich gilt: die Referenz ist selbst LLM-erzeugt
(`claude-sonnet-5`, Entities *und* Gruppierung), gemessen wird also
Übereinstimmung, nicht Richtigkeit. Der Vorschlag am Ende dieses Berichts
ist, den Testkatalog 1364390 einmal von Hand zu annotieren – ohne das ist
keine der Zahlen hier eine Genauigkeit.** Details unten.

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
Neu gezogen am 02.09.2026: `dataset.duplicate_clusters()` über
`split.json["test"]`, ein Vertreter je Cluster, 42 statt 43 Zeilen — 38
davon aus Katalog 1364390. Der Blackbox-Vergleich unten läuft über diese
Datei.

## Der Blackbox-Vergleich ist gelaufen — gegen drei Modelle

**Vorab die Einschränkung, die für die ganze Tabelle unten gilt und nicht
verloren gehen darf: "Referenz" ist in beiden Stufen von `claude-sonnet-5`
erzeugt — die Entitäten (`data/labeled/sonnet-5/`, Schritt 03) und die
Gruppierung zu Angeboten (`data/offer_groups/claude-sonnet-5/`,
Vision-Modell statt Handannotation, Teamentscheidung vom 06.08.2026).**
Jede Zahl in diesem Abschnitt — eigene Pipeline *und* alle drei
Blackbox-Modelle — misst also **Übereinstimmung mit `claude-sonnet-5`,
nicht Richtigkeit gegen eine von Menschen geprüfte Referenz**. Dieselbe
Einschränkung wie bei `magda agreement` und `magda offers-gold`, hier nur
besonders folgenreich: Ein Modell, das denselben Fehler macht wie
`claude-sonnet-5`, wird dafür belohnt; ein Modell, das es *richtiger* macht
als die Referenz, wird dafür bestraft (belegter Fall an anderer Stelle im
Projekt: die APP_PRICE-Messung vom 02.08.2026 — `magda eval` fand F1 0.234
bei Precision 1.000 und null echten Falsch-Negativen, weil das Modell jeden
App-Preis fand, ihn aber teils "PRICE" statt "APP_PRICE" nannte, wie die
Referenz selbst uneinheitlich gelabelt hatte). Was daraus folgt, steht im
Abschnitt *Handannotation des Testkatalogs* unten.

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

### Ergebnis

Lauf über die 42 Testcluster-Vertreter (38 davon aus Katalog 1364390),
`--predictions layoutxlm --grouper pair-model --reference-groups teacher`,
jedes Modell einzeln:

```
magda blackbox-eval --pages data/eval/test_cluster_pages.txt \
    --predictions layoutxlm --grouper pair-model \
    --reference-groups teacher --model <modell>
```

| | Treffer | System | Referenz | Präzision | Recall | **F1** | Fehler | s/Seite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| eigene Pipeline gegen Referenz | 219 | 253 | 287 | 0.866 | 0.763 | **0.811** | – | ~0,3¹ |
| Gemma 4 (31B) gegen Referenz | 195 | 274 | 287 | 0.712 | 0.679 | **0.695** | 5/42 | 73.8² |
| Qwen 3.6 (35B) gegen Referenz | 205 | 329 | 287 | 0.623 | 0.714 | **0.666** | 0/42 | 8.0 |
| Mistral medium 3.5 gegen Referenz | 189 | 352 | 287 | 0.537 | 0.659 | **0.592** | 3/42 | 31.4² |

¹ LayoutXLM-Inferenz (~0,1 s/Seite) plus Paarmodell mit ILP-Dekoder
(0,2 s/Seite über die 42 Seiten). ² Inklusive Retry-Overhead auf den
gescheiterten Seiten; die reine Inferenzzeit liegt darunter. Fehlerhafte
Seiten fließen mit 0 Angeboten in `system` ein.

Reports: `data/eval/blackbox_test_<modell>_pair-model_ref-teacher.json`.
Die Blackbox-Antworten je Seite sind darin gespeichert (`blackbox_deals`);
jede Zahl dieses Abschnitts lässt sich daraus ohne API-Aufruf nachrechnen.

**Reihenfolge unter den drei Blackbox-Modellen:** Gemma vor Qwen vor
Mistral, alle drei hinter der eigenen Pipeline. Mistral erzeugt mit
Abstand die meisten Angebote (352 gegen 287 Referenz) und hat dadurch die
schwächste Präzision; Gemma bleibt am nächsten an der Referenzmenge, hat
aber die meisten JSON-Syntaxfehler (5 Seiten auch nach drei Versuchen
kaputt — ein Zuverlässigkeitsproblem, unabhängig von der
Extraktionsqualität). Qwen ist mit 8 s je Seite und null Fehlern das
einzige Modell, das betrieblich unauffällig lief.

### Warum die erste Tabelle nicht trägt: 2×2-Aufschlüsselung

Der erste Durchlauf (03.09. vormittags, Reports
`data/eval/blackbox_test_<modell>.json`) lief mit zwei anderen
Einstellungen: "eigene Pipeline" gruppierte mit der Heuristik
`offers.cluster_page` statt mit dem Paarmodell, und "Referenz" waren
ebenfalls `cluster_page`-Angebote, nur auf den Lehrer-Labels statt auf den
LayoutXLM-Vorhersagen. Ergebnis damals: eigene Pipeline 0.839, Gemma
0.554, Qwen 0.541, Mistral 0.474.

Beide Einstellungen wurden für den zweiten Lauf gewechselt, und die
Wirkung ist getrennt nachgerechnet — offline aus den gespeicherten
Antworten, Skript im Repo (`scripts/blackbox_decompose.py`):

| eigene Pipeline gegen Referenz | Heuristik-Referenz | Teacher-Referenz |
|---|---:|---:|
| Heuristik als Grouper | **0.839** (264/265) | 0.708 (264/287) |
| Paarmodell als Grouper | 0.695 (253/265) | **0.811** (253/287) |

*(F1, dahinter Angebote System/Referenz.)* Die 0.839 waren die Heuristik
im Vergleich mit sich selbst: dieselbe Funktion bildete beide Seiten, nur
aus leicht verschiedenen Entities. Nur den Grouper zu wechseln hätte das
Paarmodell auf 0.695 fallen lassen, also *schlechter* als die Heuristik
aussehen lassen — obwohl es auf dem vollen Testsplit Gruppen-F1 0.778
gegen 0.439 erreicht (Testmessung oben). Gegen die tatsächliche
Teacher-Gruppierung dreht sich das Bild: Paarmodell 0.811, Heuristik 0.708.
Das ist genau die Warnung aus dem Docstring von `blackbox_eval.py`, und
sie galt auch für jede Blackbox-Zeile, weil die Heuristik-Referenz 22
Angebote weniger enthielt als der Teacher (265 gegen 287) — darunter
Fälle wie "Storck Nimm2" und "Axe" auf `1364390_p21`, die alle drei
Blackboxen fanden und die als Fehler zählten.

| Blackbox gegen Referenz | Heuristik-Ref, Lauf 1 | Heuristik-Ref, Lauf 2 | Teacher-Ref, Lauf 1 | Teacher-Ref, Lauf 2 |
|---|---:|---:|---:|---:|
| Qwen 3.6 | 0.541 | 0.532 | 0.673 | 0.666 |
| Mistral medium 3.5 | 0.474 | 0.483 | 0.592 | 0.592 |
| Gemma 4 | 0.554 | 0.553 | 0.692 | 0.695 |

Zwei Dinge lassen sich daran ablesen. Der Referenzwechsel hebt alle drei
Blackboxen um 12 bis 14 Punkte, gleichmäßig. Und der zweite API-Lauf hat
gegenüber dem ersten praktisch nichts geändert (±0.01) — die Antworten
sind bei `temperature=0.2` stabil, und **der zweite Lauf war unnötig**:
für den Referenzwechsel hätten die gespeicherten Antworten gereicht. Das
gehört hierher, weil es Kontingent gekostet hat und weil der Wechsel der
Referenz nicht vorher abgestimmt war; die Aufschlüsselung ist der
Nachweis, dass er nötig war.

**Was die Tabelle trotzdem nicht sagt:** Vereinzelt falsch gelesene
Preise (Sagrotan No Touch: 2.59 statt 2.49 bei Qwen) verfehlen bei
`price_tolerance=0.0` einen sonst korrekten Treffer vollständig. Duplikate
(identischer Name und Preis auf derselben Seite) liegen bei Qwen 1,5 %,
Mistral 2,7 %, Gemma 0 % — ein Generierungsfehler, keine Referenzlücke.
Und 42 Seiten in 42 Clustern, kein Bootstrap: die Abstände zwischen den
drei Blackboxen (0.592 bis 0.695) sind ohne Intervall, der Abstand zur
eigenen Pipeline (0.811) ist der einzige, der auch bei grober Unsicherheit
stehen bleibt.

**Ergebnis:** die eigene Pipeline liegt mit ihrer besten Konfiguration
(LayoutXLM + Paarmodell mit Lexikblock) vor allen drei Blackbox-Modellen,
0.811 gegen 0.592–0.695, bei 0,3 s gegen 8 bis 74 s je Seite und ohne
Ausfälle (Blackbox: 0 bis 5 von 42 Seiten). Die Aussage gilt unter der
Einschränkung oben: Richter ist ein LLM, das dieselbe Prospektvorlage
gesehen hat wie die Blackboxen.

## Handannotation des Testkatalogs

Alle Zahlen dieses Berichts messen Nähe zu `claude-sonnet-5`. Ob die
eigene Pipeline *richtiger* ist als Gemma oder nur *ähnlicher zu Sonnet*,
lässt sich aus ihnen nicht ablesen — und die Blackboxen sind gerade dort
im Nachteil, wo sie von Sonnet abweichen, egal in welche Richtung. Die
einzige Abhilfe ist eine handannotierte Referenz auf dem Testsplit, für
Entities und Gruppierung.

**Vorschlag: Katalog 1364390 komplett.** Er stellt 39 der 116 Testseiten
und **38 der 42 Cluster-Vertreter**, über die der Blackbox-Vergleich läuft.
Ein Prospekt von Hand deckt damit fast den ganzen Vergleich ab; die
übrigen vier Vertreter (`1364393` ×2, `1364411`, `1364420`) sind
Regionalvarianten, die sich bei Bedarf nachziehen lassen. Von den 39
Seiten liegt heute keine in `gold/`.

Die Werkzeuge existieren: `/annotate` im Frontend schreibt Spans nach
`gold/<seite>.json`, `/group` schreibt Gruppen nach `gold/offers/`, beide
mit `words_hash` gegen den Wortreihenfolge-Vertrag abgesichert. Gemessen
wird danach ohne Codeänderung mit `magda gold` (Labels) und `magda
offers-gold` (Gruppierung, Default-Referenz ist `gold/offers/`). Für den
Blackbox-Vergleich fehlt ein `--reference-groups gold` in
`blackbox_eval.py` — eine kleine Ergänzung, die erst lohnt, wenn die
Referenz da ist.

Zwei Regeln aus CLAUDE.md gelten dabei: annotiert wird aus dem Seitenbild,
nicht durch Korrigieren der Sonnet-Ausgabe (sonst misst man das Ankern
mit), und die Person sollte nicht dieselbe sein, die Pipeline und
Vergleich gebaut hat — also Kjell oder Bogdan. Aufwand nach den drei
Gold-Seiten von Noah geschätzt: 15 bis 25 Minuten je Seite für Spans und
Gruppen zusammen, also ein bis zwei Arbeitstage für den Katalog. Das ist
die Teamentscheidung vom 06.08. („30–50 Seiten von Hand sprengen den
Rahmen") noch einmal aufgemacht, diesmal mit dem Argument, dass ohne sie
der Endvergleich keine Genauigkeit berichten kann.

## Offen

- **Handannotation von Katalog 1364390** (Vorschlag oben) — Entities und
  Gruppierung, durch Kjell oder Bogdan. Danach `--reference-groups gold`
  in `blackbox_eval.py` ergänzen und den Vergleich ohne API-Aufruf aus
  den gespeicherten Antworten nachrechnen.
- **Konfidenzintervall für die Testmessung.** `per_page` fehlt weiterhin im
  Report (offener Punkt aus Woche 7) — ohne die seitenweisen Zählungen ist
  0.778 eine Punktschätzung, kein Intervall. Dasselbe gilt für die drei
  Blackbox-F1-Werte — 42 Seiten in 42 Clustern, kein Bootstrap gerechnet.
- **Die arithmetische Gegenprobe für die Blackbox-Spalte** ist mit
  `quantity`/`unit_price` im Schema vorbereitet, aber nicht verdrahtet -
  `blackbox_eval.compare_pages` kennt weiterhin nur `name`/`price`/
  `original_price`.
- **Gemmas JSON-Zuverlässigkeit** (5 von 42 Seiten auch nach drei Versuchen
  syntaktisch kaputt, alle in Katalog 1364390/1364393) ist nicht weiter
  untersucht — offen, ob ein anderes Response-Format (z. B.
  `response_format: json_object`, falls die GWDG-Bereitstellung das
  unterstützt) das behebt.
- **Über den Anker entscheiden** (ersetzt durch den Lexikblock, schadet in
  Kombination) — unverändert offen aus Woche 7.
