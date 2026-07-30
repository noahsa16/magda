# Fehleranalyse der LLM-Labels und Überarbeitung des Prompts

Stand: 30.07.2026. Grundlage sind die drei handannotierten Gold-Seiten
(`1342881_p1` bis `p3`, 108 Entities über 410 Wörter) und die 196 vom LLM
gelabelten Seiten unter `data/labeled/`.

Gemessen wird mit `scripts/08_compare_labels.py`, Entity-Level-F1 über seqeval.

## Kurzfazit

Der Prompt aus Schritt 03 hat dem Modell an zwei Stellen das **Gegenteil des
Goldstandards** beigebracht. Er erklärte `"je 200 g"` zum QUANTITY-Span,
während Gold nur `"200 g"` markiert, und sein einziges Beispiel zeigte den
Grundpreis nicht als eigenständige Angabe. Ergebnis: QUANTITY und UNIT_PRICE
lagen bei **F1 0.000** – nicht ungenau, sondern systematisch falsch.

Nach der Überarbeitung liegt dasselbe Modell bei **F1 0.752** statt 0.306.

| Fassung | micro-F1 | Precision | Recall |
|---|---|---|---|
| Prompt v1 (Ausgangslage) | 0.306 | 0.265 | 0.361 |
| Prompt v2 (Regeln 1–8) | 0.638 | 0.603 | 0.676 |
| Prompt v3 (Preisregel geschärft) | **0.752** | 0.745 | 0.759 |

## Ergebnis je Label-Typ

| Label | F1 v1 | F1 v3 | Support |
|---|---|---|---|
| PRICE | 0.850 | **0.895** | 18 |
| QUANTITY | 0.000 | **0.875** | 18 |
| UNIT_PRICE | 0.000 | **0.824** | 18 |
| BRAND | 0.182 | **0.824** | 15 |
| OLD_PRICE | 0.813 | 0.750 | 14 |
| DISCOUNT | 0.353 | 0.750 | 3 |
| PRODUCT | 0.074 | **0.368** | 21 |
| VALID | 1.000 | 1.000 | 1 |

VALID und DISCOUNT haben 1 bzw. 3 Instanzen – diese Zahlen sind Rauschen und
dürfen nicht einzeln berichtet werden.

## Die gefundenen Fehlerklassen

Alle Beispiele stammen aus dem Span-Vergleich gegen Gold, nicht aus Schätzung.

**1. Grundpreis landete in QUANTITY (18 von 18 Spans verfehlt).**
`(1 kg = 11.98)` wurde als QUANTITY gelabelt oder mit der Mengenangabe zu
einem Span verschmolzen: `QUANTITY="g (1 kg = 11.98)"`. Einmal wanderte er in
den Preis: `PRICE="0.88 (1 l = 0.70)"`.

**2. QUANTITY zog Füllwörter mit (18 von 18 verfehlt).**
Gold `"500 g"`, Modell `"je 500 g"`. Der alte Prompt hat das ausdrücklich so
verlangt – der Fehler saß im Prompt, nicht im Modell.

**3. BRAND verschluckte den Produktnamen (12 Spans verfehlt).**
`BRAND="MÜHLENHOF Frische Hähnchen- Brustfilets"` statt BRAND `"MÜHLENHOF"`
plus PRODUCT. Ebenso `"LENOR Waschmittel*"`, `"JACOBS Krönung*"`,
`"MARATHON Isotonischer"`.

**4. PRODUCT nahm die Umgebung mit (19 Spans verfehlt).**
`"oder Weichkäse"`, `"Versch. Sorten, je 200 g"`, `"Natur, je 150 g"`,
`"Haltungsform 2, je 1.000 g %"`.

**5. Werbewörter innerhalb von Preis-Spans.**
`OLD_PRICE="UVP 10.49"` statt `"10.49"` – dreimal auf einer Seite. `"Aktion"`
bekam dreimal PRICE. Beide Wörter standen bereits auf der Ausschlussliste des
Prompts, aber in einem Abschnitt, den das Modell beim Preislabeln nicht
heranzog. Erst als sie **in der Preisregel selbst** standen, verschwanden sie.
Das ist die übertragbare Lehre: eine Regel wirkt dort, wo die Entscheidung
fällt, nicht dort, wo sie thematisch hingehört.

**6. PRICE und OLD_PRICE vertauscht.**
Auf `1342881_p2` waren alle acht Preise vertauscht, auf `p3` keiner. Die Regel
„der niedrigere Wert ist PRICE" allein genügte nicht; erst der ausdrückliche
Rechenhinweis mit drei durchgerechneten Beispielen brachte PRICE von 0.615 auf
0.895 und OLD_PRICE von 0.429 auf 0.750.

## Was der Prompt jetzt anders macht

Aufbau übernommen aus dem Extractor des Vorgängerprojekts
(`notebooks/pdf_extractor(op).py`): benannte Erkennungsmerkmale statt vager
Anweisungen, kontrastive Richtig/Falsch-Paare, ausdrückliche Negativliste.

1. Grundpreis ist immer ein eigener Span, inklusive Klammern
2. QUANTITY ist nur Zahl und Einheit
3. BRAND endet beim ersten nicht durchgehend großgeschriebenen Wort
4. Preis-Span ist genau ein Wort; die kleinere Zahl ist PRICE
5. Ausdrückliche Liste dessen, was nie ein Label bekommt
6. Angebote ohne Produkttext: nur den Preis labeln, nichts erfinden
7. Am Zeilenumbruch getrennte Wörter gehören in einen Span
8. Gültigkeitszeitraum zuerst suchen

Regel 6 geht auf einen Hinweis aus dem Team zurück: manche Angebote bestehen
nur aus Produktfoto und Preis. Da wir ausschließlich auf Wörter der Liste
zeigen dürfen, ist die einzig richtige Antwort dort, den Produktnamen
wegzulassen – nicht, ein benachbartes Wort dafür zu missbrauchen.

## Belege aus dem Korpus

Zwei Auszählungen über alle 196 Seiten, die in den Prompt eingeflossen sind:

**Marken stehen in Versalien.** 419 verschiedene Versalien-Tokens; die
häufigsten echten Marken sind MÜHLENHOF (20 Seiten), COCA-COLA (15), FERRERO
(14), KNORR (13). Häufige Versalien-Tokens, die *keine* Marken sind: UVP (107
Seiten), PENNY (117, fast immer „PENNY App"), ENTSPRICHT (24), KAUFEN (19),
TOP (19). Sie stehen jetzt namentlich auf der Ausschlussliste.

**Zeilenumbrüche zerlegen Wörter.** 384 Wörter enden auf `-`, 53 enthalten ein
Soft-Hyphen (U+00AD). Betroffen sind 149 von 196 Seiten – gut drei Viertel.
Beispiele: `SCHÖFFER-` + `HOFER`, `Schlemmer-` + `sauce*`, `Orangen-` +
`Nektar`. Genau diese Wörter tragen Marken- und Produktnamen.

## Was offen bleibt

**PRODUCT liegt bei 0.368** und ist der verbleibende Schwachpunkt. Die
Gold-Konvention ist „Produktname inklusive Sortenangabe bis zum Komma vor der
Mengenangabe". Eine gezielte Regel dafür steht aus; sie wurde bewusst nicht in
denselben Lauf gepackt, weil sonst Prompt-Änderung und Modellvergleich
gleichzeitig variiert hätten.

**Drei Gold-Seiten sind eine schmale Basis.** Der Sprung von 0.306 auf 0.752
ist zu groß, um Zufall zu sein, aber die Werte einzelner Label-Typen sind es
nicht. Mehr Gold-Seiten sind der wirksamste nächste Schritt.

**Die Gold-Annotation ist an zwei Stellen uneinheitlich.** Auf `p3` gehört
`"3 Versch. Sorten,"` zum PRODUCT-Span, wenige Zeilen weiter steht
`"Versch. Sorten, je"` ohne Label. Und ein Grundpreis (`(1 kg = 9.95)`) blieb
unmarkiert. Beides drückt die erreichbare Obergrenze und sollte beim nächsten
Durchgang durch den Annotator geradegezogen werden.

**Zur Label-Definition, Teamentscheidung:** Gold markiert `COCA-COLA2,`,
`FANTA2,` und `SPRITE` als drei PRODUCT-Spans, nicht als BRAND. Das ist
vertretbar – es sind Produktvarianten einer Angebotsgruppe –, widerspricht
aber der Regel „Marke in Versalien am Angebotsanfang". Vor dem großen
Labeling-Lauf festlegen.

## Methodischer Hinweis

Eine erste Fassung dieser Analyse stammte von einem Subagenten und berichtete
für die Gold-Referenz **100 % F1 bei null Fehlern**. Das war falsch; die
Nachrechnung ergab 0.306. Der Befund widersprach dem Ergebnisprofil aus
`reports/woche-01.md` so deutlich, dass er auffiel. Zahlen aus Subagenten
gehören nachgerechnet, bevor sie in einen Bericht wandern – besonders die
angenehmen.
