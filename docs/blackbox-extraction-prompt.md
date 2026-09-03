# Der Extraktions-Prompt der Blackbox

`blackbox.PROMPT_VERSION` ist wie `offer_teacher.PROMPT_VERSION` eine Nummer
ohne Text - der Prompt selbst steht nur im Code. Diese Datei hält ihn
nachvollziehbar fest, damit ein späterer Blackbox-Lauf mit einer anderen
Version vergleichbar bleibt.

## Version 1 (02.09.2026)

Ersetzt den Prototyp-Prompt aus `notebooks/pdf_extractor(op).py` (fünf
Felder: name, price, original_price, discount_pct, period). Der neue Prompt
fasst zusammen, worauf `sonnet-5` beim Labeln geachtet hat
(`labeling._PROMPT`) und was ein Angebot laut Gruppierungs-Teacher
zusammenhält (`docs/offer-teacher-prompt.md`) - aber auf Objekt- statt auf
Wort-Span-Ebene, weil die Blackbox fertige Angebote liefert, kein
BIO-Tagging.

Neu gegenüber Version 0 (dem Prototyp-Schema): die Felder `quantity` und
`unit_price`. Ihr Fehlen war der dokumentierte Grund, warum die
arithmetische Gegenprobe (Menge × Grundpreis) für die Blackbox-Spalte
bisher unmöglich war. Die Gegenprobe
selbst ist mit Version 1 noch nicht verdrahtet (`blackbox_eval.
compare_pages` kennt weiterhin nur `COMMON_FIELDS = (name, price,
original_price)`); die Felder werden nur miterfasst und im Report
mitgespeichert.

Der Prompt in `magda.blackbox._EXTRACT_PROMPT`:

> Du siehst eine Seite aus einem deutschen Supermarkt-Prospekt (Penny).
> Extrahiere alle beworbenen Angebote als JSON-Array. Jedes Element hat
> genau diese Felder:
>
>   "brand"         Markenname, oder null wenn keine erkennbar ist
>   "product"       Produktname inkl. Sortenangabe, ohne Menge und Preis
>   "quantity"      Füllmenge als Text, z. B. "500 g", "6 x 1,5 l", oder null
>   "price"         Aktionspreis, den man ohne Bedingung zahlt (Zahl)
>   "old_price"     durchgestrichener/höherer Vergleichspreis, oder null
>   "app_price"     Preis, den nur PENNY-App-Nutzer zahlen, oder null
>   "discount_pct"  Rabatt als negative Zahl, z. B. -33, oder null
>   "unit_price"    Grundpreis wie gedruckt, z. B. "(1 kg = 11.98)", oder null
>   "valid"         Gültigkeitszeitraum der Seite, z. B. "Mo, 9.3. bis Sa, 14.3.", oder ""
>
> Domänenwissen, das beim Zuordnen häufig zu Fehlern führt:
>
> - **price vs. old_price**: die kleinere Zahl ist immer price, die größere
>   old_price - unabhängig davon, welche zuerst steht oder größer gedruckt
>   ist. Steht nur eine Zahl da, ist sie price.
> - **app_price** ist ein dritter, eigener Fall, erkennbar an "mit PENNY App",
>   "Nur mit der App" oder einem blauen App-Symbol/-Kasten. Der Preis ohne
>   App bleibt price, auch wenn er höher ist als der App-Preis - die
>   Ziffernregel oben gilt nur zwischen price und old_price.
> - **product** enthält die Sortenangabe ("Löslicher Kaffee Classic"), aber
>   NICHT Handelsklasse, Haltungsform oder Herkunftsland ("Kl. I",
>   "Haltungsform 2", "Deutschland") und NICHT die Menge oder den Grundpreis.
> - **quantity** ist nur Zahl und Einheit. Wörter wie "je", "ca.", "zzgl.",
>   "Pfand" gehören nicht hinein.
> - **unit_price** steht immer in runden Klammern der Form "(1 kg = 11.98)"
>   oder "(1 l = 0.70)" - gib den Text wie gedruckt zurück, keine eigene
>   Umrechnung.
> - Ignoriere Seitenkopf, Kleingedrucktes ("Abgabe nur in haushaltsüblichen
>   Mengen"), Öffnungszeiten und die Druckkennung am rechten Seitenrand
>   (Form "25_02-09-10") - das sind keine Angebote.
>
> Was zu EINEM Angebot zusammengehört (maßgeblich ist die Bildkachel, nicht
> die Textnähe - Preise stehen bei Penny oft in einem gelben Kasten, der
> räumlich näher am Nachbarangebot liegt als am eigenen Produkt):
>
> - **Größen- oder Sortenvarianten mit je eigenem Preis** (z. B. "20 cm 9.99 /
>   24 cm 14.99") sind dasselbe Angebot mit demselben Produktnamen - gib pro
>   Preis ein eigenes JSON-Objekt aus, jeweils mit identischem "brand" und
>   "product".
> - **Varianten mit gemeinsamem Preis** ("je 205 g oder 190 g, 0.69") sind ein
>   einziges JSON-Objekt; wähle eine der Mengenangaben oder trenne sie mit
>   " | ".
> - **Legendenlayouts**: nummerierte Produkte ("④ Pflanztopf-Set") mit einer
>   Preisliste an anderer Stelle der Seite. Dort entscheidet die Nummer,
>   nicht die Nähe im Bild.
> - Ein Angebot ohne erkennbaren Produktnamen (nur Foto + Preis) bekommt
>   "product": null - erfinde keinen Namen.
>
> Antworte ausschließlich mit dem JSON-Array, keine Markdown-Fences, keine
> Erklärung, kein Vorspann.

## Modellwahl

Läuft standardmäßig gegen `config.CHAT_AI_VISION_MODEL`
(`mistral-medium-3.5-128b`), per `--model` überschreibbar. Der
Vergleichslauf vom 02.–03.09.2026 (siehe `reports/woche-08.md`) deckt drei
GWDG-Vision-Modelle ab (Team-Entscheidung 02.09.2026, Budgetgründe statt
`claude-sonnet-5` als Subagent, dazu weniger Zirkelschluss: Referenz und
Blackbox laufen so nicht in derselben Modellfamilie):

| Modell | F1 gegen Referenz | Fehler | s/Seite |
|---|---:|---:|---:|
| `gemma-4-31b-it` | 0.554 | 3/42 | 37.3 |
| `qwen3.6-35b-a3b` | 0.541 | 0/42 | 6.8 |
| `mistral-medium-3.5-128b` | 0.474 | 2/42 | 33.7 |

Qwen-Modelle denken vor der Antwort und verbrauchen dabei `max_tokens`
(dieselbe Falle wie beim Labeling, siehe `labeling.py`); `blackbox.
extract_deals_from_page` schaltet das serverseitig ab
(`chat_template_kwargs.enable_thinking=False`) und fällt bei Modellen, die
den Schalter ablehnen (Mistral: HTTP 400), automatisch zurück.

**Zwei modellspezifische Fallen, gefunden beim ersten Durchlauf:**

- `gemma-4-31b-it` sieht das Bild nicht, wenn der Text vor dem Bild in der
  Nachricht steht ("du hast mir noch kein Bild geschickt", reproduzierbar
  mit und ohne `enable_thinking`). Der Prompt-Aufbau in `extract_deals_
  from_page` schickt das Bild deshalb zuerst, den Text danach - für
  Mistral und Qwen folgenlos.
- `max_tokens=4096` reichte bei Seiten mit vielen kleinen Angeboten nicht
  (Mistral: 7 von 42 Seiten abgeschnitten). Auf 8192 angehoben, dazu
  wiederholt `extract_deals_from_page_with_retry` jetzt auch bei
  abgeschnittener/kaputter JSON-Antwort (nicht nur bei Netzwerkfehlern) -
  bei `temperature=0.2` ist das Abschneiden eine gelegentliche
  Wiederholungsschleife, kein stabiler Fehler; ein zweiter Versuch liefert
  reproduzierbar vollständiges JSON.

**Drittens, betrieblich statt inhaltlich:** die drei Modelle nicht
parallel laufen lassen. Gleichzeitig ausgeführt teilen sie sich
offenbar ein GWDG-Kontingent - ein Testlauf mit allen dreien im selben
Moment löste bei Mistral und Gemma reihenweise HTTP-429-Fehler aus (13
bzw. 20 von 42 Seiten). Sequenziell gefahren treten praktisch keine
Rate-Limits mehr auf.

## Offen

Die arithmetische Gegenprobe (Menge × Grundpreis) für die Blackbox-Spalte
ist mit den neuen Feldern vorbereitet, aber nicht gebaut -
`blackbox_eval.compare_pages` matcht weiterhin nur über `name`/`price`/
`original_price`. Wer sie ergänzt, sollte `unit_price` als String parsen
(Format wie im Prompt: `"(1 kg = 11.98)"`) statt als eigenes Feld neu zu
verhandeln.
