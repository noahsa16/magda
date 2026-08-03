# CLAUDE.md

Semesterprojekt *Information Extraction* (SoSe 2026), Leuphana.
Team: Bogdan Roth, Kjell Lavezzari, Noah Samel.

Wir extrahieren strukturierte Angebotsdaten aus deutschen Supermarkt-Prospekten
(Penny). Ein LLM labelt die Trainingsdaten automatisch, trainiert wird ein
eigenes layout-aware Modell. Grundlage ist `docs/proposal/IE_ProjectProposal_Magda.pdf`.

Ausführliche Erklärung der Pipeline: `EXPLANATION.md` (lokal, nicht im Repo).

## Struktur

```
src/magda/   Kern-Package – hier liegt die Logik (inkl. api.py, FastAPI fürs Frontend)
  cli/       ein Modul je Pipeline-Schritt, Einstieg über den Befehl `magda`
frontend/    React-SPA (Vite, Tailwind, shadcn) – liest data/ über src/magda/api.py
tests/       pytest (Labels, Alignment, API)
gold/        handannotierte Referenz (versioniert)
data/audit/  Handprüfung einzelner Labels: Kandidaten + menschliche Urteile
data/        versioniert (PDFs, Wörter, Labels, Bilder, Splits)
checkpoints/ lokal, gitignored
docs/        Proposal, RunPod-Anleitung, Ursprungs-Prototyp
reports/     Wochenberichte
```

`catalogs.json` und `catalog_meta.json` liegen in der Wurzel und sind
versioniert: gefundene Katalog-IDs und ihre Region lassen sich nicht
reproduzieren, nur wiederfinden.

Pipeline: `magda harvest` → `magda extract` → `magda dedupe` →
`magda label` → `magda train` → `magda eval`, dazu `magda flair` als
Vergleichsarm. `magda download` holt einen einzelnen Katalog über seine
URL, `magda harvest` eine ganze Woche über alle 44 Regionen. Jeder Schritt
liest vom Vorgänger über die Platte, nichts läuft im Speicher durch.

Die Schritte lassen sich auch aus dem Frontend starten – im Tab *Pipeline*
(`/pipeline`), nicht mehr auf der Übersicht. `src/magda/runner.py`
startet sie als Subprozess und streamt die Ausgabe an `/api/run`. *Was*
startbar ist und mit welchen Parametern, steht deklarativ in `src/magda/jobs.py`;
`build_command` validiert und baut argv und ist die einzige Stelle, an der aus
einer Nutzereingabe ein Kommando wird – kein Durchreichen beliebiger
Kommandos. Das Frontend liest den Katalog über `/api/jobs` und baut daraus
seine Formulare: ein neuer Parameter wird nur im Backend gepflegt.

## Kommandos

```bash
.venv/bin/pip install -e '.[dev]'   # einmalig – legt auch den Befehl `magda` an
.venv/bin/python -m pytest          # Tests
magda --help                        # alle Schritte in Pipeline-Reihenfolge
magda harvest                       # laufende Prospektwoche, alle Regionen
magda harvest --seed 1342881        # ältere Woche über bekannte ID
magda extract
magda dedupe                        # Duplikate berichten (--apply entfernt sie)
magda label --model qwen3.6-27b     # anderes Vision-Modell
magda label --only-gold             # Probelauf auf den Gold-Seiten
magda label --model X --repair      # Span-Guard nachträglich anwenden
magda split --strategy week         # Aufteilung neu festlegen (--force überschreibt)
magda train layoutxlm               # bzw. gbert
magda eval gbert --split test
magda predict gbert --split test --labels-from sonnet-5   # Wort, Box, Label je Seite
magda predict gbert --all-words     # ganze Ernte, ohne Labels – der Einsatzfall
magda significance --labels-from sonnet-5   # Konfidenzintervall, gepaarter Vergleich
magda flair --reference gold        # Flair-Vergleichsarm
magda gold --per-label              # Labeling-Modelle gegen Gold messen
magda agreement qwen3.5-397b-a17b mistral-medium-3.5-128b
magda audit APP_PRICE --labels-from sonnet-5   # Label zur Handprüfung vorsortieren
magda bundle --labels-from sonnet-5 # Trainingspaket für eine fremde GPU
magda serve --frontend              # API (8000) und Oberfläche (5173)
magda serve                         # nur die API
cd frontend && npm test             # Frontend-Tests (Vitest)
```

Immer aus dem Projektroot starten: die Schritte lesen und schreiben relativ zu
`config.PROJECT_ROOT`. Ohne die editierbare Installation gibt es weder den
Befehl `magda` noch den Import – alles bricht mit `ModuleNotFoundError` ab.

Die Schritte liegen als je ein Modul unter `src/magda/cli/`, registriert in
`cli/__init__.py`. Importiert wird erst beim Aufruf: `train` zieht torch und
transformers herein, und `magda --help` soll nicht zehn Sekunden brauchen, um
eine Liste auszugeben.

## Konventionen

- **Kommentare und Docstrings auf Deutsch, jeder Code-Identifier auf Englisch.**
  Das gilt für Klassen, Funktionen, Parameter, JSON-Feldnamen *und lokale
  Variablen* – `target`, nicht `ziel`; `previous`, nicht `vorheriges`.
- **Der umgebende Code ist hier kein Vorbild.** Im Altbestand stehen deutsche
  Identifier (`Befehl`, `wochen`, `zaehler`, `sicherung`, `fehler`); sie sind
  Altlast, kein Stil, an den man sich anpasst. Neuer Code wird englisch
  benannt, auch wenn direkt daneben deutscher steht. Bestehende Namen werden
  nicht nebenbei umbenannt – das gehört in einen eigenen Commit, sonst
  versteckt sich eine Umbenennung in einer inhaltlichen Änderung.
  Einzige Ausnahme: Testfunktionsnamen (`test_dev_kommt_nicht_aus_der_testwoche`)
  bleiben deutsch – sie sind Sätze über das Verhalten, keine Bezeichner.
- Docstrings erklären *warum*, nicht *was*. Kein Kommentar, der die Zeile
  darunter wiederholt.
- Neue Pipeline-Logik gehört ins Package, nicht in die Skripte. Skripte machen
  Argumente parsen, Dateien lesen/schreiben, Fortschritt anzeigen – sonst nichts.
- Skripte bleiben idempotent: bereits verarbeitete Seiten überspringen. Ein Lauf
  über mehrere tausend Seiten darf nach einem Abbruch nicht von vorn beginnen.
- **Nichts wird direkt nach `main` gemergt – auch nichts Kleines, auch nicht
  bei grünen Tests.** Der Weg ist: Feature-Branch → Pull Request nach
  `development` → von dort gesammelt nach `main`. Ein Feature-Branch darf auch
  einfach liegen bleiben, bis jemand draufgeschaut hat; ungemergte Arbeit
  kostet nichts, ein ungeprüfter Merge schon. Der Grund ist nicht Bürokratie:
  `main` trägt die Zahlen, die im Bericht stehen. Wer dort direkt hineinmergt,
  verschiebt die Grundlage einer Messung ohne zweites Augenpaar – und Fehler in
  Heuristiken sehen von innen genau wie Verbesserungen aus, solange niemand
  gegengerechnet hat. Direkt auf `main` committen oder pushen entsprechend
  auch nicht.

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
- **`src/magda/blackbox.py` ist kein toter Code**, sondern der alte Prototyp. Er
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
- **`data/` ist seit dem 02.08.2026 mitversioniert – absichtlich.** Die
  Alternative war, dass jede Person im Team Ernte, Extraktion und Labeling
  selbst durchläuft; das kostet LLM-Kontingent für ein Ergebnis, das
  identisch sein soll. Wer daran etwas ändern will, fragt vorher im Team.
  Eine Nebenwirkung war, dass `magda bundle` auf 1054 MB anschwoll, weil
  `git ls-files` plötzlich die Original-PDFs mitlieferte – deshalb filtert
  `bundle._tracked_files()` `data/` heraus und legt die für die GPU nötigen
  Teile gezielt dazu. Das Filtern betrifft nur das Transportpaket, nicht das
  Repo.
- **`gold/` ist versioniert, `data/` inzwischen auch.** Handannotierte Referenzlabels
  sind nicht reproduzierbar – ein verlorenes `data/labeled/` kostet API-Zeit,
  ein verlorenes `gold/` kostet Arbeitstage. Gespeichert werden Spans, nicht
  BIO-Tags: git-diffbar, und `labels.spans_to_bio()` erzeugt die Tags daraus.
- **Der `words_hash` in Gold-Dateien** ist die Absicherung des
  Wortreihenfolge-Vertrags. Ändert sich Schritt 02, zeigen die Span-Indizes
  auf andere Wörter, ohne dass etwas kaputtgeht. Die API lehnt dann mit 409 ab.
- **Die API ist nicht mehr read-only.** Geschrieben wird an vier aufgezählten
  Stellen: `gold/` (handannotierte Referenz), `catalogs.json`
  (Katalog-Verzeichnis), `data/runs/` (Lauf-Historie) und `data/audit/`
  (Urteile der Handprüfung – niemals `data/labeled/` selbst). Eine Erlaubnisliste,
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
  beantwortbar. `magda train --labels-from` wählt aus, worauf trainiert wird;
  ohne Angabe gilt `CHAT_AI_VISION_MODEL`, sonst der größte Ordner. Der
  Modellname wird zum Ordnernamen und kommt aus einer Nutzereingabe – deshalb
  `config.model_slug()`, sonst wäre `../../gold` ein gültiger Modellname.
- **Der Prompt in `labeling.py` widersprach dem eigenen Goldstandard.** Er
  erklärte `"je 200 g"` zum QUANTITY-Span, während Gold nur `"200 g"` markiert,
  und sein Beispiel zeigte den Grundpreis nicht als eigene Angabe. QUANTITY und
  UNIT_PRICE lagen deshalb bei F1 **0.000** – nicht ungenau, sondern
  systematisch falsch. Nach der Überarbeitung 0.752 statt 0.306. Wer den Prompt
  anfasst, misst danach mit `magda gold`, sonst ist es Bauchgefühl.
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
- **Was mechanisch entscheidbar ist, gehört in Code statt in den Prompt.**
  `labeling.trim_spans()` erzwingt drei Grenzen, die der Prompt jahrelang nur
  hätte erbitten können: kein Span enthält „oder", die Grundpreis-Klammer
  beendet jeden Nicht-UNIT_PRICE-Span, und ein numerisches Label ohne Ziffer
  fällt weg. Gemessen über 196 Seiten: 179 und 322 Verstöße vorher, null
  danach; Werbewörter von 2,4 auf 0,06 je Seite. Eine Prompt-Regel senkt die
  Fehlerrate, ein Guard setzt sie auf null.
- **`data/eval/` enthält nicht nur Evaluationsreports.** Dort liegen auch
  `labels_vs_gold.json` und `agreement_*.json`. `/api/evaluation` prüft
  deshalb die *Form* (`variant` + `report`), nicht den Dateinamen – vorher
  reichte es alles durch und die Evaluationsseite starb an
  `Object.entries(undefined)`. Aus demselben Grund hat der Bootstrap-Vergleich
  einen **eigenen Endpunkt `/api/significance`**: `significance_*.json` gehört
  keiner der beiden Varianten, hat weder `variant` noch `report` und fällt
  durch dieselbe Formprüfung. Für die Seite ist er trotzdem die wichtigste
  Datei im Ordner – die Differenz ohne Intervall ist genau die Behauptung, die
  wir nicht aufstellen wollen.
- **Übereinstimmung ist keine Richtigkeit.** `src/magda/agreement.py` misst, wo
  sich zwei Labeling-Modelle widersprechen – über alle 196 Seiten statt über
  die drei annotierten. Nützlich ist vor allem die Rangfolge: die uneinigsten
  Seiten bringen pro Annotationsstunde am meisten. Aber zwei Modelle können
  sich einig und gemeinsam irren; die Zahl ist eine Obergrenze für Vertrauen,
  kein Ersatz für `gold/`.
- **Sortenangaben gehören ins PRODUCT** (Teamentscheidung, 30.07.2026):
  `"Löslicher Kaffee Classic,"`, nicht `"Löslicher Kaffee"`. Gold ist an
  dieser Stelle noch uneinheitlich – auf `1342881_p1` fehlen die Sorten
  (`"Käsescheiben"` statt `"Käsescheiben Natur,"`). Das drückt die messbare
  Obergrenze und gehört im Annotator geradegezogen.
- **Gebindeangaben als zusammengesetztes Wort sind ungeklärt.** Gemessen über
  alle Gold-Seiten: `50-ml-Fläschchen` ist 4× QUANTITY, `0,33-l-Dose` 6× gar
  nicht, `1-l-Sonderedition` war 8× ohne und 3× QUANTITY. Die drei Fälle sind
  strukturell gleich (Menge, Einheit, Gebindeart in einem Token) und werden
  verschieden behandelt. `1-l-Sonderedition` ist auf die Mehrheit angeglichen,
  damit Gold in sich stimmt – die Regel dahinter steht aus und ist eine
  Teamentscheidung. Prüfen lässt sie sich mit einer Auszählung je Wortlaut,
  nicht seitenweise: seitenweise sieht man Einzelfälle, über den Korpus den
  Widerspruch.
- **`magda queue` sagt, welche Gold-Seite als Nächstes drankommt.** Eine Seite
  je Duplikat-Cluster (Jaccard 0.7), Testseiten zuerst, darin die uneinigsten.
  Ohne die Clusterung annotiert man 30 Seiten und misst 11-mal dieselbe
  Vorlage. Als Uneinigkeitsmass taugt nur ein Paar aus *verschiedenen*
  Modellen – `mistral-…` gegen `mistral-…-promptv1` misst die
  Prompt-Überarbeitung, nicht die Schwierigkeit der Seite (`review.default_pair`).
- **Das Projekt-Env ist `.venv`, nicht die Anaconda-Basis.** `which python`
  zeigt auf Anaconda; dort fehlt `seqeval`, und Tests brechen beim Import ab.
  Immer `.venv/bin/python` benutzen.
- **LayoutXLM braucht das Seitenbild, nicht nur Wörter und Boxen.** Es ist eine
  LayoutLMv2-Architektur; der visuelle Backbone ist Teil des
  Vorwärtsdurchlaufs. Fehlt `image`, stirbt der Lauf an einem nichtssagenden
  `'NoneType' object has no attribute 'tensor'` tief im Backbone. Ein
  Forward-Pass mit Batch-Größe 1 findet so etwas in 40 Sekunden – vor dem
  Mieten einer GPU, nicht danach.
- **Der Split wird über alle extrahierten Seiten gezogen, nicht über die
  gelabelten.** Sonst hängt eine dauerhaft eingefrorene Aufteilung am
  Zufall des Labeling-Fortschritts: wer bei 141 von 196 Seiten trainiert,
  friert einen Split ohne die restlichen 55 ein, und die landen später
  sämtlich im Training.
- **Zum Layout-Vorteil ist kein Effekt nachweisbar – in keine Richtung.**
  Über drei Wochen (02.08.2026, Test = KW32, 100 Seiten, 5107 Entitäten):
  GBERT 0.891, LayoutXLM 0.878. Die Differenz von +0.013 hat ein
  95-%-Intervall von [−0.008, +0.043] bei p = 0.435 – sie überdeckt die Null.
  „GBERT ist besser" ist damit **nicht** belegt; belegt ist nur, dass der
  Aufwand für den visuellen Backbone sich nicht auszahlt. Frühere Zahlen
  (0.908 gegen 0.895, davor 0.929 gegen 0.930) sahen nach einem klaren
  Ergebnis aus, weil das Intervall fehlte. Wer den Vergleich berichtet, nennt
  das Intervall mit – sonst behauptet er mehr, als 43 Cluster hergeben.
  Auffällig bleibt die *Streuung*: LayoutXLMs Intervall ist mit [0.812, 0.928]
  deutlich breiter als GBERTs [0.852, 0.927]. Das layout-aware Modell ist über
  die Vorlagen hinweg instabiler, und das verschluckt der Punktschätzer.
  BRAND, das Label, für das LayoutXLM angetreten ist, erreicht auch ohne jede
  Positionsinformation 0.938 – in Woche 1 waren es 0.10. Der Unterschied lag
  nie am Layout, sondern an den Labels.
- **Die Modelle sind an der Konsistenzgrenze ihres Lehrers angekommen.**
  Fehleranalyse über die 100 Testseiten (02.08.2026): APP_PRICE hat F1 0.234
  bei Precision 1.000 – und **null reine Falsch-Negative**. Das Modell findet
  jeden App-Preis, nennt ihn nur PRICE (74×) oder OLD_PRICE (24×). Ursache ist
  die Referenz: Penny setzt App-Preise mal mit dem Text „mit PENNY App", mal
  nur mit der Fußnote „2" hinter der Zahl, und das Muster `<preis> 2` ist in
  den sonnet-5-Labels **1× als APP_PRICE und 60× als O** vergeben. Dasselbe
  von der anderen Seite bei PRICE (Precision 0.766): von rund 263
  Falsch-Positiven sind 74 Referenz-APP_PRICEs und mindestens 60 die
  ungelabelten Badge-Preise – die Metrik bestraft dort Vorhersagen, die
  richtiger sind als die Referenz. Bei PRODUCT (0.835) sind 106 von 135
  Fehlern Grenzfehler an Sortenzusätzen, also die offene Teamfrage.
  **Konsequenz für die Priorisierung:** mehr Daten und größere Modelle bringen
  hier nichts, konsistentere Labels schon. Was mechanisch entscheidbar ist,
  gehört als Regel in den Code – wie bei `labeling.trim_spans()`.
- **Ein fehlendes `data/words` machte den Signifikanztest zur Punktschätzung.**
  `significance.test_clusters` fiel bei fehlenden Wortlisten auf einen
  Sammel-Cluster zurück. Auf dem Trainings-Pod – wo das Bundle `data/words`
  nicht mitliefert – hieß das: alle 100 Testseiten in *einem* Cluster,
  Konfidenzintervall der Breite null, p = 0.0. Also die Optik eines
  hochsignifikanten Befunds an genau der Stelle, die Unsicherheit ausweisen
  soll. Bricht jetzt ab, statt zu schätzen. Der Schritt gehört dorthin, wo
  `data/words` vollständig ist, nicht auf die GPU.
- **Stand 03.08.2026 nach dem Repair-Lauf** (Referenz: sonnet-5 mit
  Fußnotenregel, 5080 Entities statt vorher 5107 – die KW32-Labels waren nie
  durch `trim_spans` gelaufen, deshalb sind die Zahlen mit dem Vorlauf **nicht**
  direkt vergleichbar):
  GBERT **0.8938** [0.8484, 0.9306], LayoutXLM **0.8952** [0.8418, 0.9366],
  Differenz −0.0014 [−0.0164, +0.0108] bei **p = 0.843**. Das Vorzeichen hat
  gegenüber dem Vorlauf gewechselt (vorher GBERT +0.0132, p = 0.435) – genau
  das Verhalten eines Effekts, der die Null überdeckt. Der Layout-Negativbefund
  ist damit bestätigt, nicht widerlegt.
- **LayoutXLM sieht das Seitenbild und löst den visuellen Fall trotzdem nicht.**
  Bei APP_PRICE erreicht es 0.554 gegen GBERTs 0.660 – schlechter, obwohl nur
  es den blauen Kasten sehen könnte. Der Grund steht in der Architektur:
  `image_feature_pool_shape` ist `[7, 7, 256]`, also **49 visuelle Token für
  die ganze Seite**. Eine Gitterzelle deckt 142 × 251 px des Originals ab; der
  App-Kasten (~230 × 80 px) fällt mit Produktfoto und Nachbarpreis in dieselbe
  Zelle. Dazu hängen die 49 Token als *globale* Sequenz an – es gibt keine
  Verknüpfung „dieses Wort steht auf blauem Grund". **Größere Eingabebilder
  ändern daran nichts**, weil der Processor ohnehin auf 224 × 224 skaliert
  (`bundle.py` nimmt ihm das nur vorweg, mit demselben Filter). Wer den
  Layout-Arm verteidigen will, braucht eine Architektur mit lokaler
  Wort-Bild-Verknüpfung, nicht mehr Pixel.
- **`magda eval` misst in drei Protokollen, und nur eines davon ist ehrlich.**
  Das alte Protokoll wertete nur die Tensorpositionen aus, die ins 512er-Fenster
  passten. Entities dahinter fehlten damit nicht als Falsch-Negative, sondern
  **im Nenner**: gemessen 0.890 über 4921 Entitäten statt 0.891 über 5107. Die
  Zahl war also nicht falsch berechnet, sie beantwortete eine andere Frage
  („F1 auf den ersten 512 Subwords"). Primärmetrik ist `windowed`, weil sie das
  misst, was `magda predict` ausliefert. `no-windows` (0.874) zeigt gegen
  dieselbe volle Referenz, was ein Deployment ohne Fenster kostet – die
  Differenz von 1,7 Punkten ist der Wert der Fenster, nicht die 0.001 gegen
  `truncated`. Wer nur zwei Zahlen vergleicht, muss den Support danebenstellen.
- **Sliding Window steckt in der Inferenz, nicht im Training** (`windows.py`,
  Stride 128). Bewusst so: Training und Checkpoint-Auswahl bleiben unverändert,
  damit die Vergleichbarkeit erhalten bleibt, während der ausgelieferte Output
  vollständig ist – 0 statt 1476 Wörtern ohne Vorhersage auf der Testwoche.
  Fenstergrenzen liegen auf Subwords, nicht auf Wörtern: das erste Wort eines
  Folgefensters kann mit einem Fortsetzungs-Subword beginnen, das im Training
  mit `-100` maskiert war. `merge_windows` überspringt es, solange ein anderes
  Fenster das Wort ganz sieht.
- **`get_or_create_splits` würfelt nichts mehr.** Fehlte `split.json`, entstand
  dort kommentarlos ein 80/10/10-Seiten-Split – genau der, dessen Leck gemessen
  und verworfen wurde. Auf einer frischen GPU-Instanz oder bei einem
  Teammitglied ohne die Datei wäre das unbemerkt passiert, und die Zahlen sehen
  dabei *besser* aus. Jetzt bricht die Funktion ab und verweist auf
  `magda split`.
- **Der Seiten-Split leckt: 12 von 19 Testseiten hatten einen Trainingszwilling
  mit Jaccard ≥ 0.7**, Median 0.851. Die Entdopplung greift erst ab 0.95,
  Seiten bei 0.949 überleben sie und landen dann auf verschiedenen Seiten des
  Splits. Gemessener Effekt: F1 0.944 auf Seiten mit nahem Zwilling gegen
  0.886 ohne. Behoben durch den **Wochen-Split**
  (`magda split --strategy week`). Stand 02.08.2026 über drei Wochen:
  KW30+KW31 lernen, KW32 testet, **175/21/100 Seiten**. Median-Ähnlichkeit von
  Test zu Train 0.285, keine der 100 Testseiten hat einen Zwilling ≥ 0.9. Ein
  Split über *Kataloge* hätte das nicht behoben – `1347375_p30` und
  `1347396_p34` sind verschiedene Kataloge mit Jaccard 0.939, zwei
  Regionalausgaben derselben Woche.
- **Dev wird clusterweise gezogen, nicht seitenweise.** Zufällig je Seite lag
  Dev bei Median-Ähnlichkeit 0.721 zum Training, vier von 19 Seiten über 0.9 –
  kein Test-Leck, aber die Checkpoint-Auswahl bewertete damit teils
  Auswendiggelerntes und griff zum falschen Modell. Über ganze Duplikat-Cluster
  gezogen (Jaccard 0.7): Median 0.315, keine Dev-Seite mehr über 0.7.
- **Was von Test zu Train an Ähnlichkeit übrig bleibt, ist kein Leck.** Zwei
  von 100 Testseiten liegen über 0.7 (Max 0.824), und beide sind Rückseiten mit
  dem rechtlichen Kleingedruckten: 46 Wörter, davon 42 wortgleich zur Vorwoche,
  verschieden sind Produkt, Preis und Datum. Solche Wiederholung tritt im
  Einsatz garantiert auf – sie zu entfernen machte den Testsatz unrealistisch
  schwer. Der schädliche Leak war ein anderer: dieselbe Seite in 44
  Regionalfassungen, künstlich vervielfacht.
- **Der Testsatz hat 100 Seiten, aber nur 43 unabhängige Einheiten.**
  Bei Jaccard 0.7 bilden die 100 Seiten 43 Cluster, der größte umfasst 11.
  Jede Unsicherheitsrechnung muss über *Cluster* resampeln
  (`magda significance`), nicht über Seiten – sonst gelten elf Kopien einer
  Vorlage als elf Beobachtungen und das Intervall wird zu eng. Praktische
  Folge: ein Teacher-Fehler auf einer Seite im großen Cluster zählt 11-fach.
- **Die Woche steht nirgends in den Daten, nur im Abstand der Katalog-IDs.**
  Innerhalb einer Woche liegen sie höchstens 24 auseinander, zwischen zwei
  Wochen 4446. `dataset.WEEK_GAP = 200` schneidet großzügig dazwischen. Feste
  ID-Bereiche wären beim nächsten Erntelauf veraltet.
- **Der Wochen-Split misst Generalisierung über die Zeit – und deckt damit
  Verteilungsverschiebungen auf.** APP_PRICE wächst über die drei Wochen von
  2 auf 57 auf 98 Spans: Penny rollt den App-Preis gerade aus. Trainiert wird
  auf 57 Beispielen, gemessen gegen 98. Mit zwei Wochen (Training nur KW30,
  2 Spans) lag das Label bei F1 0.000, mit drei Wochen bei 0.234 – bei
  Precision 1.000 und Recall 0.133. Ein Zufallssplit hätte die Spans verteilt
  und eine passable Zahl geliefert; der Befund „unsere Pipeline hinkt
  Sortimentsänderungen eine Woche hinterher" wäre unsichtbar geblieben. Dev
  enthält nur 2 APP_PRICE-Spans – die Checkpoint-Auswahl kann dieses Label
  praktisch nicht bewerten.
- **Dev ist mit 21 Seiten in 14 Clustern dünn.** Für die Wahl unter zehn
  Epochen-Checkpoints reicht es knapp; für Hyperparametersuche oder
  Architekturentscheidungen nicht. Dazu kommt eine bauartbedingte Schieflage:
  Dev stammt aus den Trainingswochen, misst also In-Distribution-Fit, während
  Test die Zeitverschiebung misst. Mit drei Wochen nicht besser lösbar – aber
  im Bericht zu nennen, samt Entity-Zahl von Dev, damit das Auswahlrauschen
  einzuordnen ist.
- **`data/labeled/sonnet-5/` ist die Referenz** (Teamentscheidung, 30.07.2026).
  Nicht `gold/`: drei handannotierte Seiten tragen keine Messung, und die
  Alternative – 30 Seiten von Hand durchsehen – kostet Tage für eine Zahl, die
  die Projektfrage nicht beantwortet. Trainiert und getestet wird gegen
  dieselbe Quelle, und das ist beim überwachten Lernen der Normalfall, kein
  Mangel. Was 0.908 heißt, steht im nächsten Punkt.
- **Die Projektfrage ist Kosten, nicht Perfektion.** GBERT und LayoutXLM sind
  die günstige Alternative zum LLM: 109 Mio. Parameter, 437 MB, läuft lokal
  auf CPU ohne Netz, API-Key und Kontingent. Gemessen: **0,264 s je Seite**
  gegen **44,8 s** beim LLM-Labeling (155 Seiten, 6 parallele Anfragen, ohne
  die 2,4 h Kontingentsperre gerechnet). Für eine Wochenernte über alle 44
  Regionen sind das **8,8 Minuten gegen 24,9 Stunden**. F1 0.908 ist damit
  nicht „90 % richtig", sondern „90 % dessen, was das große Modell liefert,
  zum 170sten Teil der Zeit". Das ist die Aussage, die der Bericht trägt.
- **`gold/` bleibt liegen, ist aber nicht mehr Referenz.** Die drei Seiten von
  Noah und die 193 vorannotierten bleiben versioniert – sie kosten nichts und
  eine spätere Stichprobe kann darauf aufsetzen. `magda gold` läuft weiter,
  seine Zahl ist aber eine Randnotiz über drei Seiten, keine Bewertung.
- **`torch.cuda.is_available()` ist keine Prüfung.** Zwei RunPod-Instanzen
  meldeten die GPU als verfügbar und brachen bei der ersten Allokation ab
  („CUDA-capable device(s) is/are busy or unavailable"); `nvidia-smi` zeigte
  0 MiB belegt, keine Prozesse, 100 % Auslastung – ein Nachbarcontainer hielt
  die Karte. Das Bootstrap in `bundle.py` fasst sie deshalb wirklich an
  (`torch.zeros(8, device="cuda")`). Sonst schlägt der Fehler erst nach der
  zehnminütigen detectron2-Übersetzung mitten im Trainer auf. Zweiter Pod auf
  demselben Host scheitert identisch – bei diesem Fehler die Hardware wechseln.
- **Anweisung für die Handannotation und Prompt in `labeling.py` sind
  auseinandergelaufen.** Qwen labelt `je`, `ca.`, Abmessungen als QUANTITY und
  `Kl. I`/`Haltungsform` als PRODUCT – alles Dinge, die nur in der
  Annotationsanweisung ausgeschlossen sind. 82.2 % Wortübereinstimmung
  zwischen den Armen, und die Abweichung hat fast nur diese eine Ursache.
- **Training gehört auf eine fremde GPU, wegen RAM statt Rechenzeit.** GBERT
  braucht 96 Sekunden, LayoutXLM 254; auf einem 8-GB-Mac füllt LayoutXLM den
  Swap und die Maschine steht (Load 67 bei 100 MB freiem RAM).
  `magda bundle` packt Code (per `git ls-files`, also inklusive
  nicht gepushter Commits), Labels, Split und auf 224 px verkleinerte Bilder in
  17 MB. Ohne `split.json` bricht der Export ab – sonst würfelt die fremde
  Maschine klaglos einen eigenen und die Zahlen sind unvergleichbar.
  Anleitung: `docs/runpod.md`.
- **Angebote lassen sich nicht über Boxabstände gruppieren – gemessen, nicht
  vermutet.** Über alle 296 Seiten geometrisch gekachelt und die
  Distanzschwelle durchgefahren (0,8× bis 13× Medianworthöhe): der Anteil
  sauberer Kacheln (genau 1 PRODUCT, 1 PRICE) erreicht bei 4× sein Maximum von
  **18,5 %** und bildet dort ein Plateau, keine Spitze. Der Grund steht im
  Layout: Penny setzt den Preis in einen gelben Kasten, der weiter vom
  zugehörigen Produktnamen entfernt liegt als vom Nachbarangebot. Wer an
  Schwellwerten dreht, arbeitet gegen die Seitengestaltung. Dazu 4,7 % Blöcke
  der Form „ein Produktname, mehrere Varianten mit je eigenem Preis"
  (`Pfanne: 20 cm 9.99 / 24 cm 14.99 / 28 cm 17.99`) – die sind auch bei
  perfekter Kachelung nicht durch Nähe auflösbar.
- **Gruppieren ist eine Relation, Labeln eine Klassifikation.** BIO-Tags können
  ausdrücken „dieses Wort ist ein Preis", aber nicht „dieser Preis gehört zu
  jenem Produkt". `ENTITY_TYPES` zu erweitern bringt der Frage deshalb
  grundsätzlich nichts – das Vokabular enthält die Relation nicht. Wer das
  Clustern lösen will, braucht eine **zweite, parallele Tag-Folge**
  (`B-OFFER`/`I-OFFER`) über die ganze Kachel, nicht einen weiteren
  Entity-Typ: `OFFER` läge über PRODUCT und PRICE, und flaches BIO kann keine
  Verschachtelung. Machbar ist es – **92,7 % der visuellen Wortgruppen sind
  genau ein zusammenhängender Lauf** in der Wortliste (3728 von 4022, der Rest
  zerfällt fast immer in genau zwei). Ein Span-Label kann nur zusammenfassen,
  was benachbart ist; diese Zahl ist die Vorbedingung.
- **Menge × Grundpreis prüft sich selbst – Boxabstände nicht.** `0,205 kg ×
  3,37 €/kg = 0,69 €` stimmt oder stimmt nicht; das ist Arithmetik und braucht
  keine Handannotation. Deshalb ordnet `offers.py` Preise bevorzugt darüber zu
  statt über Nähe. Nützlicher ist die Umkehrung: geht die Rechnung in einem
  Block *nicht* auf, ist der Block verdächtig. Auf `1351497_p20` steht
  `900 g | 750 ml | 313,5 g` bei Preis 4.49, aber nur 0,75 × 5,99 trifft ihn –
  keine Varianten, sondern drei zusammengeworfene Nachbarprodukte. Das findet
  Clustering-Fehler ohne Gold. Grenze: es gibt Grundpreise nur bei Lebensmitteln,
  Non-Food trägt allein die Lesereihenfolge.
- **Größenvarianten paaren sich positionsweise** – gemessen über die 1283
  Angebote aus `magda offers --predictions gbert`: von 43 Blöcken mit mehreren
  Mengen *und* mehreren Grundpreisen gehen 26 positionsweise auf (i-te Menge zur
  i-ten Grundpreisangabe), **0 nur in einer anderen Reihenfolge**, 11 in keiner,
  6 haben ungleich viele. Wenn die Rechnung überhaupt aufgeht, geht sie in
  Lesereihenfolge auf – die Zuordnung Größe→Preis braucht also weder ein neues
  Label noch Geometrie. Die 11 Fehlschläge sind meist falsch geclusterte
  Nachbarprodukte oder Mehrfachpackungen (`2 x 350 g`, deren Multiplikator die
  Mengenerkennung noch ignoriert).
- **Das Angebots-Schema plättet Varianten.** `offers` hat eine Zeile je Angebot
  und joint mehrere Mengen als `"205 g | 190 g"` in ein Textfeld. Bei einem
  gemeinsamen Preis („je 205 g oder 190 g, 0.69") trägt das noch; bei drei
  Größen mit drei Preisen nicht, weil `_match_badges` jedem Block höchstens ein
  PRICE gibt und die übrigen als Fragment liegen bleiben. Von 1283 Datensätzen
  haben 777 Produkt *und* Preis, 506 sind Bruchstücke. Nötig ist `offer` 1:n
  `variant(quantity, price, old_price, unit_price)` – ohne das kann auch eine
  bessere Heuristik ihr Ergebnis nicht ablegen. Anmerkungen dazu in Issue #6.
- **54,5 % aller Wörter sind `O`** (32102 von 58956 in `sonnet-5`), und die
  Masse ist nicht Füllwerk. Ausgezählt über alle 296 Seiten: Mengenaktionen
  (`je`, `2für`, `3er-Set`) 3411 Treffer auf 287 Seiten – `je` allein ist mit
  2666 das häufigste ungelabelte Wort überhaupt; Pfand (`zzgl. 0.25 Pfand`)
  777 auf 91 Seiten; Kleingedrucktes 511 auf 130; Herkunft und Güteklasse
  (`Deutschland`, `Kl. I`, `Haltungsform`) 215 auf 84. **`UVP` ist geprüft und
  kein Kandidat**: der Preis dahinter trägt bereits in 833 von 855 Fällen
  `OLD_PRICE`, dort geht nichts verloren.

## Offene Entscheidungen (nicht eigenmächtig festlegen)

- **APP_PRICE: die Kennzeichnung ist Grafik, kein Text.** *Der Befund vom
  03.08.2026 räumt die alte Fassung dieses Punktes ab.* Penny zeichnet den
  App-Preis auf zwei Arten aus: mit dem Text „mit PENNY App" daneben, oder mit
  einem türkisblauen Kasten samt Logo und der Zeile „Nur mit App". **Der Kasten
  steht nicht im Textlayer.** Auf `1347375_p5` liefert PyMuPDF an der Stelle
  `Aktion 1.99 1.69 1 Kernarm` – das Wort „App" kommt auf der ganzen Seite
  nicht vor, obwohl `1.69` dort ein App-Preis ist. Acht Seiten sind so.

  Gemessen über alle 296 Seiten: bei **73 von 224** APP_PRICE-Spans (33 %)
  steht „App" nicht im Fenster ±8 Wörter. Für diese Fälle ist das Label aus
  dem Text **prinzipiell nicht ableitbar** – weder von GBERT noch von einer
  Prompt- oder Code-Regel. Das Labeling-Modell kann es, weil es das Seitenbild
  sieht. Das ist eine strukturelle Obergrenze, keine Datenmenge-Frage.

  Die Farbe an der Wortposition trennt dagegen sauber. Verifiziert am Kasten
  auf `1347375_p5`: **rgb(0, 124, 132)** gegen das Preisgelb **rgb(255, 212, 0)**
  direkt daneben. Ein grober Test „Blaukanal über Rotkanal" reicht *nicht* – er
  fängt die hellblauen Kacheln (196, 227, 248), und die stehen ausgerechnet
  neben „ohne PENNY App". Deshalb Abstand zum verifizierten Ton
  (`label_audit.APP_BACKGROUND`, Toleranz 60).

  **Was die Fußnotenregel wirklich getan hat** (Lauf vom 02.08.2026): Sie hat
  67 Spans von PRICE auf APP_PRICE umgewidmet, **alle in Train und Dev, keinen
  einzigen im Test**. Der Grund ist banal: In KW32 steht die Fußnote meist
  *vor* dem Preis (`-37% 1 0.99`), die Regel sucht sie dahinter. Die
  Verbesserung von F1 0.234 auf 0.660 kommt also allein aus den zusätzlichen
  Trainingsbeispielen (57 → 115), nicht aus einer veränderten Testreferenz –
  sauberer als befürchtet. Die Precision fiel dabei von 1.000 auf 0.630: das
  Modell überproduziert jetzt, und darunter sind Fehlgriffe der Regel auf
  Aufzählungsziffern (`Aktion 1.99 1 2 3`, `2 Jahre Garantie`, `3 Paar`).

  **Der Lehrer ist an dieser Stelle inkonsistent.** Preise mit Ziffer daneben
  auf einer App-Seite labelt sonnet-5 zu 35,5 % als O, 33,0 % als PRICE und
  29,0 % als APP_PRICE. Das ist nahezu Zufall – aber kein Modellfehler,
  sondern die Folge davon, dass die Ziffer allein nichts trägt und der Kasten
  im Text fehlt.

  **Offen bleibt die Entscheidung, was daraus folgt.** Zwei Wege, die
  verschiedene Fragen beantworten und einander nicht ersetzen:

  *A – Referenz bereinigen.* Farbe schlägt vor, ein Mensch entscheidet, die
  Urteile werden übernommen. Macht die Zahlen **ehrlicher, nicht besser**: Wenn
  jeder Kasten APP_PRICE wird, verlangt man von GBERT eine Vorhersage über ein
  Merkmal, das in seiner Eingabe nicht vorkommt – die Metrik fällt. Genau
  deshalb ist der heutige Wert 0.660 teilweise Zufallstreffer auf Textmustern.

  *B – dem Modell das Merkmal geben.* Dieselbe Farbmessung als zusätzliche
  Eingabe je Wort. Löst das Problem tatsächlich, weicht aber vom Proposal ab,
  wo LayoutXLM den Layout-Anteil beisteuern soll.

  Ohne A lässt sich nicht messen, was B gebracht hat. Vorbereitet ist A:
  `magda audit APP_PRICE --labels-from sonnet-5` sortiert vor, durchgesehen
  wird unter `/audit`. **Kein Schritt schreibt dabei nach `data/labeled/`** –
  ein Klick in der Oberfläche darf die Referenz nicht stillschweigend ändern,
  gegen die anschließend gemessen wird.
- **Die Handprüfung von APP_PRICE ist durch** (03.08.2026, Noah): 374 von 374
  Kandidaten in 267 Vorlagen beurteilt, Urteile in `data/audit/APP_PRICE.json`.
  Drei Befunde, und sie sind alle drei nützlich.
  **Sonnets Präzision ist praktisch perfekt: 223 von 224 bestätigt.** Der eine
  Fehlgriff ist `Aktion «1.99» 1 2 3` – eine Aufzählungsziffer, die die
  Fußnotenregel für eine Fußnote hielt, also genau der vermutete Fehlermodus,
  aber einmal unter 224. Die berichtete Precision von 0.630 ist eine
  Eigenschaft des *Modells*, nicht der Referenz: GBERT überproduziert.
  **Sonnets Recall ist es nicht: 81 App-Preise fehlen, rund ein Viertel**
  (223 von 304). Alle in derselben Situation – im Kasten, ohne Text daneben.
  **Die Prioritätsheuristik hat gehalten.** 67 von 67 OLD_PRICE auf App-Grund
  bleiben OLD_PRICE (der durchgestrichene Preis im Kasten), und die Farbe
  trifft in der Gruppe „fehlt vermutlich" zu 97,6 % (81/83). Die zwei
  Ausreißer stehen beide neben „ohne PENNY App", also der Verneinung – genau
  der Fall, wegen dem `is_bluish` durch den Abstand zu `APP_BACKGROUND`
  ersetzt wurde.
  **Wo eine Übernahme landen würde: 72 in Train, 9 in Dev, null im Test.**
  Der Testsatz enthält keinen Preis auf App-Grund, der nicht schon APP_PRICE
  heißt. Damit gilt dasselbe wie für die Fußnotenregel – die Messlatte bleibt
  liegen, nur das Training wächst, bei APP_PRICE um 62 % (115 → 186).
  Einschränkung: Die Prüfung findet nur, was *farblich* auffällt. Ein im Test
  fehlender, nur per Text ausgezeichneter App-Preis wäre ihr entgangen; eine
  Gegenprobe über die Textumgebung ergab keinen solchen Fall, ist aber
  schwächer als die Farbprüfung.
  **Die Übernahme selbst ist weiter nicht gebaut und bleibt Teamentscheidung.**
- **Sortenangaben und Gebinde-Komposita** (`50-ml-Fläschchen`, `0,33-l-Dose`,
  `1-l-Sonderedition`): unverändert offen, und mit 106 von 135 PRODUCT-Fehlern
  jetzt beziffert. Prüfen per Auszählung je Wortlaut über den Korpus, nicht
  seitenweise.
- **Sliding Window auch im Training?** In der Inferenz ist es drin und bringt
  +1,7 Punkte gegen die volle Referenz. Im Training wäre es Augmentierung, kein
  Messfehler – also eine Abwägung, keine Korrektur. Bisher bewusst nicht getan,
  damit Trainingssignal und Checkpoint-Auswahl unverändert bleiben.
- **LiLT als dritter Arm?** LayoutXLM verliert konsistent, aber nicht
  nachweisbar (Intervall überdeckt die Null). LiLT hat keinen visuellen
  Backbone und ist bei 175 Trainingsseiten gutmütiger; ein Lauf würde den
  Layout-Negativbefund gegen den Einwand „falsche Layout-Architektur"
  absichern. Weicht vom Proposal ab → Teamentscheidung.
- **Weitere Label – aufgekommen, weil das Zusammensetzen der Angebote hakt**
  (Frage von Bogdan und Kjell, 03.08.2026). Die Messung dazu steht oben; sie
  sagt vor allem, was ein neues Label **nicht** leistet: das Clustern löst es
  nicht, dafür bräuchte es die OFFER-Sequenz. Unabhängig davon lohnen sich vier
  Kandidaten, nach Nutzen sortiert:
  - `PROMO` (`je`, `2für`, `3er-Set`) – 287 von 296 Seiten. Nicht nur Masse,
    sondern semantisch nötig: `2für 1.99` gegen `je 1.99` ändert, was der Preis
    bedeutet. Ohne das ist der Preis selbst in einem korrekt gebildeten Cluster
    mehrdeutig.
  - `DEPOSIT` (`zzgl. 0.25 Pfand`) – 91 Seiten. Echtes Feld, geht heute
    verloren; ohne es stimmt der Endpreis nicht. Steht immer am Preis.
  - `LEGAL` (Kleingedrucktes) – 130 Seiten. Wirkt durch **Ausschluss**:
    „Abgabe nur in haushaltsüblichen Mengen" steht räumlich zwischen den
    Angeboten und gehört zu keinem, zieht also jede Nachbarschaftsheuristik
    schief.
  - `ORIGIN` (`Deutschland`, `Kl. I`, `Haltungsform 3`) – 84 Seiten. Echtes
    Feld, in der Annotationsanweisung bisher ausdrücklich aus PRODUCT
    ausgeschlossen. Hilft beim Gruppieren nicht.

  Der Preis dafür ist jedes Mal derselbe: `ENTITY_TYPES` hinten anhängen, den
  **kompletten Korpus neu labeln** (~3,5 h LLM-Zeit für 296 Seiten), Prompt
  überarbeiten, mit `magda gold` nachmessen; alte Checkpoints passen nicht
  mehr, weil der Klassifikationskopf wächst. Deshalb nicht alle vier auf
  einmal – naheliegend wäre `PROMO` und `DEPOSIT` in einem Durchgang.
  Entscheidung steht aus.
- **OFFER als zweite Tag-Folge?** Der einzige Weg, der das Gruppieren wirklich
  löst (92,7 % Machbarkeit, siehe oben). Ist aber ein zusätzlicher Modellkopf,
  kein weiteres Label, und weicht vom Proposal ab → Teamentscheidung. Vor einer
  GPU-Miete gehört ein Machbarkeitstest auf den Gold-Seiten davor.
- Label-Set ist ein Entwurf und wird nach Sichtung der ersten gelabelten Seiten
  finalisiert.

### Beantwortet (nicht erneut aufmachen)

- ~~Split über Kataloge statt Seiten?~~ Hätte nicht gereicht: `1347375_p30`
  und `1347396_p34` sind verschiedene Kataloge mit Jaccard 0.939. Gelöst durch
  den Wochen-Split.
- ~~detectron2 als Risiko, Plan B LayoutLMv3?~~ detectron2 baut auf dem
  RunPod-PyTorch-Image ohne Eingriff durch (02.08.2026).
- ~~Sliding Window nur, wenn messbar Entities verlorengehen.~~ Gemessen: 186
  von 5107 Entitäten (3,6 %) lagen hinter dem Abschnitt, 1476 von 20952 Wörtern
  (7,0 %) hatten keine Vorhersage. Umgesetzt für die Inferenz.

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
`mistral-medium-3.5-128b` (Begründung im Kommentar in `src/magda/config.py`).
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
