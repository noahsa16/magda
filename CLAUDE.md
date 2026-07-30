# CLAUDE.md

Semesterprojekt *Information Extraction* (SoSe 2026), Leuphana.
Team: Bogdan Roth, Kjell Lavezzari, Noah Samel.

Wir extrahieren strukturierte Angebotsdaten aus deutschen Supermarkt-Prospekten
(Penny). Ein LLM labelt die Trainingsdaten automatisch, trainiert wird ein
eigenes layout-aware Modell. Grundlage ist `docs/proposal/IE_ProjectProposal_Magda.pdf`.

Ausführliche Erklärung der Pipeline: `EXPLANATION.md` (lokal, nicht im Repo).

## Struktur

```
magda/       Kern-Package – hier liegt die Logik (inkl. api.py, FastAPI fürs Frontend)
scripts/     nummerierte Pipeline-Schritte, dünne CLI-Wrapper um magda/
frontend/    React-SPA (Vite, Tailwind, shadcn) – liest data/ über magda/api.py
catalogs.json Verzeichnis gefundener Blätterkatalog-IDs (versioniert)
tests/       pytest (Labels, Alignment, API)
data/        lokal, gitignored (nur .gitkeep versioniert)
checkpoints/ lokal, gitignored
docs/        Proposal
```

Pipeline: `00_harvest_week` → `02_extract_words` → `06_check_duplicates` →
`03_label_words` → `04_train` → `05_evaluate`, dazu `07_flair_baseline` als
Vergleichsarm. `01_download_flyers` holt einen einzelnen Katalog über seine
URL, `00_harvest_week` eine ganze Woche über alle 44 Regionen. Jeder Schritt
liest vom Vorgänger über die Platte, nichts läuft im Speicher durch.

Die Schritte lassen sich auch aus dem Frontend starten – im Tab *Pipeline*
(`/pipeline`), nicht mehr auf der Übersicht. `magda/runner.py`
startet sie als Subprozess und streamt die Ausgabe an `/api/run`. *Was*
startbar ist und mit welchen Parametern, steht deklarativ in `magda/jobs.py`;
`build_command` validiert und baut argv und ist die einzige Stelle, an der aus
einer Nutzereingabe ein Kommando wird – kein Durchreichen beliebiger
Kommandos. Das Frontend liest den Katalog über `/api/jobs` und baut daraus
seine Formulare: ein neuer Parameter wird nur im Backend gepflegt.

## Kommandos

```bash
.venv/bin/python -m pytest               # Tests – nicht .venv/bin/pytest, das
                                         # bringt den Projektwurzelpfad nicht
                                         # auf sys.path (ModuleNotFoundError)
python scripts/02_extract_words.py       # Schritt ausführen (aus dem Projektroot)
python scripts/04_train.py layoutxlm     # bzw. gbert
python scripts/00_harvest_week.py        # laufende Prospektwoche, alle Regionen
python scripts/00_harvest_week.py --seed 1342881   # ältere Woche über bekannte ID
python scripts/03_label_words.py --model qwen3.6-27b    # anderes Vision-Modell
python scripts/03_label_words.py --only-gold            # Probelauf auf den Gold-Seiten
python scripts/06_check_duplicates.py    # Duplikate berichten (--apply entfernt sie)
python scripts/07_flair_baseline.py --reference gold   # Flair-Vergleichsarm
python scripts/08_compare_labels.py --per-label        # Modelle gegen Gold messen
uvicorn magda.api:app --reload           # Frontend-API (Port 8000)
cd frontend && npm run dev               # Frontend-Dev-Server (proxied /api)
cd frontend && npm test                  # Frontend-Tests (Vitest)
```

Skripte immer aus dem Projektroot starten – sie hängen den Root selbst an
`sys.path`, damit `from magda import ...` ohne Installation funktioniert.

## Konventionen

- Kommentare und Docstrings auf Deutsch, Code-Identifier auf Englisch.
- Docstrings erklären *warum*, nicht *was*. Kein Kommentar, der die Zeile
  darunter wiederholt.
- Neue Pipeline-Logik gehört ins Package, nicht in die Skripte. Skripte machen
  Argumente parsen, Dateien lesen/schreiben, Fortschritt anzeigen – sonst nichts.
- Skripte bleiben idempotent: bereits verarbeitete Seiten überspringen. Ein Lauf
  über mehrere tausend Seiten darf nach einem Abbruch nicht von vorn beginnen.

## Projektwissen, das nicht im Code steht

- **Kein echtes OCR.** Die Penny-PDFs haben einen Textlayer, PyMuPDF liefert
  Wörter und Koordinaten direkt. Das Proposal spricht von OCR, weil das der
  allgemeine Fall ist – ein Tesseract-Fallback wird erst nötig, wenn Händler
  mit reinen Bild-PDFs dazukommen.
- **Die Wortreihenfolge aus Schritt 02 ist ein Vertrag.** Alle Labels sind
  Indizes in diese Liste. Ändert sich die Extraktion, sind bestehende Labels in
  `data/labeled/` wertlos und müssen neu erzeugt werden.
- **Das LLM liefert Spans, keine Tag-Listen.** Bei „gib exakt N Labels für N
  Wörter" verzählen sich Modelle. Ungültige Spans werden in
  `labels.spans_to_bio()` einzeln verworfen, statt die Seite abzubrechen.
- **`-100` beim Subword-Alignment** ist der `ignore_index` von PyTorchs
  CrossEntropyLoss. Wer dort versehentlich `0` (= `"O"`) setzt, trainiert das
  Modell auf Wortfortsetzungen und merkt es erst an schlechten Metriken.
- **`ENTITY_TYPES` nur hinten erweitern.** Die Label-IDs werden aus der
  Reihenfolge abgeleitet; Einfügen in der Mitte macht alte Checkpoints ungültig.
- **`data/splits/split.json` ist eingefroren.** Einmal gewürfelt, dann fest,
  damit alle im Team auf denselben Testseiten evaluieren. Neu würfeln = löschen.
- **`magda/blackbox.py` ist kein toter Code**, sondern der alte Prototyp. Er
  bleibt als Vergleichssystem für die Requirements-Stufe „Excellent".
- **Der Trainingsverlauf steht nicht in `checkpoints/{variant}/best`.**
  `trainer.save_model()` schreibt dort kein `trainer_state.json`; `/api/model`
  liest deshalb den `checkpoint-N`-Ordner mit der höchsten Schrittzahl.
- **Penny gibt je Woche 44 Regionalausgaben heraus, und sie sind fast gleich.**
  Über alle 44 liegen ~2000 Seiten, davon exakt verschieden nur ~170, und bei
  Jaccard 0.95 bleiben ~130. Die Unterschiede sind echt, aber winzig: eine
  Herkunftsangabe („NRW" statt „Deutschland"), ein ausgetauschter Artikel.
  Ungefiltert bläht das den Datensatz auf, kostet LLM-Zeit und lässt dieselbe
  Seite in Train- *und* Testsplit landen.
- **Am rechten Seitenrand steht eine Druckkennung** der Form `25_02-09-10` —
  Seite 25, gedruckt für die Regionen 02, 09 und 10. Sie steht im Textlayer,
  gehört aber nicht zum Prospekt: ohne sie zu entfernen gilt jede geteilte
  Seite als vielfach verschieden. Als Herkunftsangabe ist sie dafür die
  genaueste, die eine einzelne Seite hergibt (`dedupe.print_marker`).
- **`data/excluded.json` ist der Wirkmechanismus der Entdopplung, nicht das
  Löschen.** Schritt 02 baut `data/words` aus `data/raw` jederzeit neu auf;
  wer nur Dateien entfernt, hat sie beim nächsten Lauf zurück und zahlt sie
  beim übernächsten mit LLM-Zeit. Die Datei bildet ausgeschlossene `page_id`
  auf die Seite ab, die sie vertritt — geschrieben von `06 --apply` *und* von
  Schritt 02 für exakt gleiche Wortlisten. Deshalb gilt
  `raw = words + excluded + pending`, und `pending > 0` ist echte offene
  Arbeit. Ohne diese Buchführung sieht die Übersicht aus, als hätte die
  Pipeline ein Drittel der Seiten liegen lassen (327 geladen, 196 extrahiert).
- **`catalog_meta.json` hält fest, zu welcher Region ein Katalog gehört.**
  Penny's Markt-API kennt nur die laufende Woche; ungespeichert ist die
  Zuordnung nach sieben Tagen weg und ein Katalog nur noch eine sechsstellige
  Nummer. Für vergangene Wochen wird sie über den Gitterabstand übertragen und
  als `confirmed: false` ausgewiesen — vermutet, nicht belegt.
- **`gold/` ist versioniert, `data/` nicht.** Handannotierte Referenzlabels
  sind nicht reproduzierbar – ein verlorenes `data/labeled/` kostet API-Zeit,
  ein verlorenes `gold/` kostet Arbeitstage. Gespeichert werden Spans, nicht
  BIO-Tags: git-diffbar, und `labels.spans_to_bio()` erzeugt die Tags daraus.
- **Der `words_hash` in Gold-Dateien** ist die Absicherung des
  Wortreihenfolge-Vertrags. Ändert sich Schritt 02, zeigen die Span-Indizes
  auf andere Wörter, ohne dass etwas kaputtgeht. Die API lehnt dann mit 409 ab.
- **Die API ist nicht mehr read-only.** Geschrieben wird an drei aufgezählten
  Stellen: `gold/` (handannotierte Referenz), `catalogs.json`
  (Katalog-Verzeichnis) und `data/runs/` (Lauf-Historie). Eine Erlaubnisliste,
  kein freier Schreibzugriff – dieselbe enge Beschränkung wie beim Runner.
- **Der Runner-Vertrag lautet „nur deklarierte Parameter", nicht „nur
  Varianten".** `jobs.build_command` lehnt unbekannte Jobs, unbekannte
  Parameternamen, nicht konvertierbare Werte und Werte außerhalb von `choices`
  ab. Werte werden typkonvertiert und als eigene argv-Elemente übergeben, es
  gibt keine Shell. Ein freies Argument-Textfeld im Frontend wäre effektiv eine
  Remote-Shell und ist deshalb ausdrücklich nicht vorgesehen.
- **Defaults aus `jobs.py` landen nicht im argv.** Sie dienen nur dem Frontend
  zum Vorbelegen des Feldes; den echten Default kennt argparse im Skript. Zwei
  Quellen für denselben Wert driften auseinander.
- **Positionale Werte dürfen nicht mit `-` beginnen.** argparse liest `--help`
  als Option, nicht als URL – der Lauf täte dann etwas anderes als eingegeben.
- **`runner.status()` hängt nicht an `poll()`.** Der Prozess ist eher fertig als
  der Pump-Thread, der den letzten Ausgabeblock schreibt. Über `poll()` meldete
  der Lauf kurz „beendet, Exit-Code unbekannt", und das Frontend zeigte einen
  Abbruch, den es nie gab. Maßgeblich ist der eingetragene Exit-Code. Tests, die
  einen Lauf starten, müssen auf den Pump-Thread warten, bevor sie `RUNS_DIR`
  zurückdrehen – sonst landet der Testlauf im echten `data/runs/`.
- **`data/runs/` ist die einzige Spur eines Laufs nach dem Backend-Neustart.**
  Der Ringpuffer in `runner.py` hält nur 400 Zeilen für die Live-Ansicht. Wer
  einen Fehlschlag untersucht, liest den Log auf der Platte. Aufgeräumt wird
  bei 100 Läufen.
- **`getcatalog.do` läuft früher ab als die PDFs.** Geprüft am 29.07.2026: für
  Katalog 1342881 liefert die Metadatenseite 404, während `bk_1.pdf` weiter mit
  200 antwortet. `scraping.fetch_catalog_meta` fängt den 404 ab und nutzt den
  Fallback `"1"`; bei 5xx wird weiterhin geworfen. Vorher lief das in
  `raise_for_status()` – ein erneuter Download des eigenen Katalogs wäre
  gecrasht.
- **Katalog-IDs lassen sich nicht erraten.** 14 Proben rund um eine gültige ID
  ergaben 0 Treffer; der ID-Raum ist dünn besetzt. Deshalb `catalogs.json`:
  gefundene IDs werden geteilt, nicht wiedergefunden. Versioniert aus demselben
  Grund wie `gold/`.
- **`probe_catalog` ruft die übergebene URL nie ab.** Aus der Eingabe wird per
  Regex nur `catalogId=(\d+)` gelesen; die Ziffern landen in zwei fest
  verdrahteten Basis-URLs. Wer daraus ein direktes `session.get(url)` macht,
  baut einen Proxy in fremde Netze – `test_probe_ruft_niemals_die_uebergebene_url_ab`
  hält das fest.
- **Speichervorgänge im Annotator sind pro Seite serialisiert**, und zwar im
  Frontend (`use-annotation.ts`). Zwei gleichzeitige PUTs derselben Gold-Seite
  erreichen den Server in beliebiger Reihenfolge; `os.replace` macht den
  letzten zum Gewinner, der ältere Stand überschreibt also still den neueren.
  Ein Lock in `put_gold` hilft dagegen nicht – der Schreibvorgang ist ohnehin
  atomar, ihm fehlt nur die Reihenfolge, und die kennt allein der Client.
  Nicht abgedeckt: zwei Tabs oder zwei Personen auf derselben Seite. Dafür
  bräuchte es optimistisches Locking, nicht Serialisierung.

- **Der Flair-Arm misst nur BRAND.** `flair/ner-german-large` kennt
  PER/LOC/ORG/MISC; von unseren acht Labels hat nur BRAND eine Entsprechung
  (`ORG`). Deshalb werden Referenz *und* Vorhersage auf BRAND eingeschränkt –
  ohne das zählte jeder Preis in der Referenz als Falsch-Negativ. Jede
  berichtete Zahl aus diesem Arm muss die Einschränkung mitnennen.
- **Flair bekommt die Wortliste vorsegmentiert.** Nicht aus Bequemlichkeit:
  So sitzt jede Vorhersage auf genau einem Wortindex, und Flair sieht exakt
  dieselbe Eingabe wie GBERT. Eine eigene Tokenisierung würde `(1 kg = 24.95)`
  anders zerlegen und die beiden Zahlen unvergleichbar machen.
- **Flair kürzt lange Seiten nicht, GBERT schon.** Flairs
  `TransformerWordEmbeddings` schiebt ein Fenster über Sequenzen über 512
  Subwords; `dataset.py` schneidet mit `truncation=True` ab. Auf Seite
  `1342881_p22` (602 Subwords) sieht Flair die ganze Seite, GBERT zwei Drittel.
  Beim Berichten des Vergleichs mitnennen – und es ist das erste Argument in
  der offenen Sliding-Window-Frage.
- **`flair` steht nicht in `requirements.txt`.** Es bringt zwei Dutzend Pakete
  mit, die für Pipeline und Training keine Rolle spielen. Wer nur trainiert,
  soll sie nicht installieren müssen.
- **Labels liegen je Modell getrennt: `data/labeled/<modell>/<seite>.json`.**
  Flach gespeichert überschreibt der zweite Labeling-Lauf den ersten, und die
  Frage „labelt Qwen näher am Goldstandard als Mistral?" ist danach nicht mehr
  beantwortbar. `04_train --labels-from` wählt aus, worauf trainiert wird;
  ohne Angabe gilt `CHAT_AI_VISION_MODEL`, sonst der größte Ordner. Der
  Modellname wird zum Ordnernamen und kommt aus einer Nutzereingabe – deshalb
  `config.model_slug()`, sonst wäre `../../gold` ein gültiger Modellname.
- **Der Prompt in `labeling.py` widersprach dem eigenen Goldstandard.** Er
  erklärte `"je 200 g"` zum QUANTITY-Span, während Gold nur `"200 g"` markiert,
  und sein Beispiel zeigte den Grundpreis nicht als eigene Angabe. QUANTITY und
  UNIT_PRICE lagen deshalb bei F1 **0.000** – nicht ungenau, sondern
  systematisch falsch. Nach der Überarbeitung 0.752 statt 0.306. Wer den Prompt
  anfasst, misst danach mit `08_compare_labels.py`, sonst ist es Bauchgefühl.
- **Eine Prompt-Regel wirkt dort, wo die Entscheidung fällt.** „UVP" und
  „Aktion" standen längst auf der Ausschlussliste; das Modell labelte sie
  trotzdem als OLD_PRICE bzw. PRICE. Erst als sie *in der Preisregel selbst*
  standen, verschwanden sie. Ein thematisch sauber einsortierter Hinweis wird
  beim Labeln des Preises nicht herangezogen.
- **`labeling.trim_spans()` gehört nicht in `labels.spans_to_bio()`.** Der
  Guard erzwingt, dass „oder" zwei Angebote trennt und die Grundpreis-Klammer
  jeden Nicht-UNIT_PRICE-Span beendet. Durch `spans_to_bio()` laufen aber auch
  die handannotierten Gold-Spans, und die dürfen nicht stillschweigend
  umgeschrieben werden. Was ein Mensch annotiert hat, gilt.
- **Die Qwen-Modelle denken vor der Antwort, und das kostet `max_tokens`.**
  qwen3.5-397b lieferte auf allen drei Gold-Seiten 0 Zeichen bei
  `finish_reason=length`. Abhilfe ist `extra_body={"chat_template_kwargs":
  {"enable_thinking": False}}` – Mistral lehnt das mit HTTP 400 ab, deshalb
  probiert `labeling.py` es aus und merkt sich die Absage.
- **Bildfähigkeit prüft man mit genug `max_tokens`, sonst misst man Unsinn.**
  Mit `max_tokens=20` antworteten fünf Modelle mit leerem Text – das Budget
  ging fürs Reasoning drauf. Und `openai-gpt-oss-120b` nimmt Bilder ohne
  HTTP-Fehler an, antwortet aber „Ich kann das Bild nicht sehen". Wer nur auf
  400 prüft, labelt damit einen halben Korpus blind. Die geprüfte Liste steht
  in `config.VISION_MODELS`.
- **Sortenangaben gehören ins PRODUCT** (Teamentscheidung, 30.07.2026):
  `"Löslicher Kaffee Classic,"`, nicht `"Löslicher Kaffee"`. Gold ist an
  dieser Stelle noch uneinheitlich – auf `1342881_p1` fehlen die Sorten
  (`"Käsescheiben"` statt `"Käsescheiben Natur,"`). Das drückt die messbare
  Obergrenze und gehört im Annotator geradegezogen.
- **Das Projekt-Env ist `.venv`, nicht die Anaconda-Basis.** `which python`
  zeigt auf Anaconda; dort fehlt `seqeval`, und Tests brechen beim Import ab.
  Immer `.venv/bin/python` benutzen.

## Offene Entscheidungen (nicht eigenmächtig festlegen)

- Split über Kataloge statt Seiten? Angebote wiederholen sich zwischen Wochen,
  das leakt möglicherweise vom Train- in den Test-Split.
- LayoutXLM braucht detectron2 (visueller Backbone von LayoutLMv2). Falls die
  Installation scheitert: Plan B wäre LayoutLMv3 – weicht aber vom Proposal ab
  und muss im Team besprochen werden.
- Seiten mit >512 Subwords werden aktuell abgeschnitten. Sliding Window nur,
  wenn messbar Entities verlorengehen.
- Label-Set ist ein Entwurf und wird nach Sichtung der ersten gelabelten Seiten
  finalisiert.

## Zugangsdaten

API-Key für die GWDG Academic Cloud kommt aus einer lokalen `.env`
(`.env.example` als Vorlage). Keys gehören nie in den Code oder ins Repo.

Die API ist OpenAI-kompatibel (`openai`-Client mit geänderter `base_url`).
Doku: https://docs.hpc.gwdg.de/services/saia/index.html
Modellübersicht: https://docs.hpc.gwdg.de/services/chat-ai/models/index.html

Der Modellkatalog der GWDG ändert sich – Modellnamen nicht raten, sondern
gegen `GET /v1/models` prüfen. Nicht jedes Modell dort versteht Bilder, und
das Labeling in Schritt 03 braucht zwingend Bild-Input.

Getestet am 23.07.2026: von 16 Modellen nehmen nur `mistral-medium-3.5-128b`,
`gemma-4-31b-it` und `qwen3-omni-30b-a3b-instruct` Bilder an. Default ist
`mistral-medium-3.5-128b` (Begründung im Kommentar in `magda/config.py`).
Modelle starten kalt und brauchen beim ersten Request teils Minuten.

## Erster kompletter Durchlauf (23.07.2026)

Die Pipeline ist einmal end-to-end gelaufen: Katalog 1342881 (Penny, Woche
20.–25.7.), 40 Seiten, 7216 Wörter, 4796 davon getaggt (66 %). GBERT
trainiert, Test-F1 0.333. Details in `reports/woche-01.md`.

Was daraus für die weitere Arbeit wichtig ist:

- **Modellwahl an echten Seiten prüfen, nicht an Beispielen.** Auf einer
  synthetischen Seite mit 23 Wörtern sah `gemma-4-31b-it` am besten aus; auf
  echten Seiten mit 150–400 Wörtern schaffte es 1 von 3 und lief einmal in
  eine Endlosschleife. Entscheidend ist, ob ein Modell 50–80 Spans am Stück
  ohne Formatbruch durchhält.
- **`temperature=0` ist beim Labeling gefährlich.** Greedy Decoding kann in
  Wiederholungsschleifen laufen, bis das Token-Limit greift. Deshalb 0.2.
- **LLM-Antworten enthalten Prosa**, trotz gegenteiliger Anweisung im Prompt –
  einmal sogar auf Koreanisch. `labeling._extract_json_array()` schneidet das
  Array per Klammerzählung heraus.
- **Der Textlayer der Penny-PDFs enthält Steuerdaten** des Web-Viewers
  (`json://…gif;0.000;…`). Werden in `ocr._is_artifact()` gefiltert.
- **Ergebnisprofil:** Preise, Streichpreise und Rabatte erreichen F1 0.59–0.78,
  Produkte und Marken nur 0.08–0.10. Plausible Erklärung: Preise erkennt man am
  Textmuster, Marke vs. Produktname erst an der Position auf der Seite. Genau
  das ist die Hypothese, die LayoutXLM prüfen soll.
- **Nicht überinterpretieren:** 32 Trainingsseiten, 4 Testseiten. VALID hat 4
  Instanzen im Testsplit – die 0.000 dort sind Rauschen, kein Befund.
