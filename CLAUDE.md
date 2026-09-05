# CLAUDE.md

Semesterprojekt *Information Extraction* (SoSe 2026), Leuphana.
Team: Bogdan Roth, Kjell Lavezzari, Noah Samel.

Wir extrahieren strukturierte Angebotsdaten aus deutschen Supermarkt-Prospekten
(Penny). Ein LLM labelt die Trainingsdaten automatisch, trainiert wird ein
eigenes layout-aware Modell. Grundlage ist `docs/proposal/IE_ProjectProposal_Magda.pdf`.

Ausführliche Erklärung der Pipeline: `EXPLANATION.md` (lokal, nicht im Repo).

## Nicht ohne Rücksprache

Sechs Dinge, die man nicht nebenbei ändert. Sie stehen weiter unten ausführlich
begründet – hier nur, damit niemand erst 100 Zeilen lesen muss, um zu wissen,
wo es weh tut.

- **`ENTITY_TYPES` nur hinten erweitern.** Einfügen in der Mitte macht jeden
  bestehenden Checkpoint ungültig.
- **`data/splits/split.json` ist eingefroren.** Neu würfeln heißt: alle
  bisherigen Zahlen sind nicht mehr vergleichbar.
- **Nichts schreibt nach `data/labeled/`.** Weder API noch Frontend noch die
  Handprüfung. Das ist die Referenz, gegen die gemessen wird. Einzige
  Ausnahme ist `magda audit-apply` nach einer Teamentscheidung – mit eigenem
  Commit, damit die Änderung sichtbar bleibt.
- **`data/labeled/sonnet-5/` wird nicht umbenannt und nicht archiviert.** Der
  Name steht in Checkpoint-Ordnern (`gbert-sonnet-5-app`), in jeder Datei
  unter `data/eval/`, in Commit-Nachrichten und in diesem Dokument. Ein
  Ordner `aktuell/` wäre bequemer und kappte die Belegkette, an der jede
  berichtete Zahl hängt. „Aktuell" ist ein Zeiger, kein Ordnername:
  `config.CANONICAL_LABELS`.
- **Die Wortreihenfolge aus Schritt 02 ist ein Vertrag.** Ändert sie sich, zeigen
  alle Label-Indizes auf andere Wörter – auch die in `gold/`.
- **Kein freies Argument-Textfeld im Frontend.** `jobs.build_command` nimmt nur
  deklarierte Parameter; alles andere wäre praktisch eine Remote-Shell.
- **Auf `main` wird nicht gearbeitet.** Kein Commit, kein Push, kein Merge
  direkt dorthin – siehe Branch-Workflow unter *Konventionen*.

## Struktur

```
src/magda/   Kern-Package – hier liegt die Logik (inkl. api.py, FastAPI fürs Frontend)
  cli/       ein Modul je Pipeline-Schritt, Einstieg über den Befehl `magda`
frontend/    React-SPA (Vite, Tailwind, shadcn) – liest data/ über src/magda/api.py
tests/       pytest (Labels, Alignment, API)
gold/        handannotierte Referenz (versioniert)
data/audit/  Handprüfung einzelner Labels: Kandidaten + menschliche Urteile
data/        versioniert (PDFs, Wörter, Labels, Bilder, Splits)
  labeled/         aktive Span-Labels, ein Ordner je Quelle
  labeled_archive/ abgeschlossene Vergleichsarme, gleicher Aufbau
  offer_groups/    Gruppierungen: welche Entities ein Angebot bilden
  predictions/     Ausgabe von `magda predict`, ein Ordner je Modell
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
magda train layoutxlm               # bzw. gbert, xlmr, lilt
magda eval gbert --split test
magda predict gbert --split test --labels-from sonnet-5   # Wort, Box, Label je Seite
magda predict gbert --all-words     # ganze Ernte, ohne Labels – der Einsatzfall
magda significance --labels-from sonnet-5   # Konfidenzintervall, gepaarter Vergleich
magda significance --labels-from sonnet-5 --compare xlmr lilt   # ein Kettenschritt
magda flair --reference gold        # Flair-Vergleichsarm
magda gold --per-label              # Labeling-Modelle gegen Gold messen
magda agreement qwen3.5-397b-a17b mistral-medium-3.5-128b
magda audit APP_PRICE --labels-from sonnet-5   # Label zur Handprüfung vorsortieren
magda audit-apply APP_PRICE --labels-from sonnet-5 --target sonnet-5-neu  # Urteile übernehmen
magda offers                        # Entities zu Angeboten clustern, als SQLite
magda offers-report                 # Clustering per Ablation messen (Train+Dev)
magda offers-queue                  # welche Seiten die Referenz zuerst braucht
magda offers-gold --labels-from sonnet-5    # Gruppierung gegen gold/offers/ messen
magda offers-gold --groups-from claude-sonnet-5 --reference-from claude-opus-5  # Decke: Teacher gegen Teacher
magda offers-teacher pages --limit 40       # Seiten fürs LLM-Gruppieren
magda offers-teacher task 1342821_p10       # Aufgabe einer Seite (Entities + Bild)
magda offers-verify --reference-from claude-sonnet-5   # Gruppierung nachrechnen
magda offers-model train --labels-from sonnet-5        # Paarmodell lernen (mit Kalibrierung)
magda offers-model eval --labels-from sonnet-5         # gegen Lehrer und Arithmetik messen
magda offers-probe --encoder lilt   # bringt ein Span-Embedding dem Paarmodell etwas?
magda offers-sequence               # fasst eine flache OFFER-Folge das Angebot?
magda blackbox-eval --pages <liste> --dry-run   # LLM-Blackbox gegen die eigene Pipeline
magda blackbox-eval --pages data/eval/test_cluster_pages.txt --reference-groups gold \
    --predictions layoutxlm --grouper pair-model \
    --blackbox-from data/eval/blackbox_test_gemma-4-31b-it_pair-model_ref-teacher.json
                                    # dieselben Blackbox-Antworten gegen die Handannotation, ohne API
magda bundle --labels-from sonnet-5 # Trainingspaket für eine fremde GPU
magda prune-checkpoints             # was checkpoint-N belegt (--apply löscht)
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
- **Keine Zahl ohne das Skript, das sie erzeugt.** Wer eine Messung berichtet –
  im Bericht, im Chat, in einer Commit-Nachricht –, legt den Code dazu ins Repo.
  Sonst kann sie in vier Wochen niemand nachrechnen, und wer sie liest, muss
  glauben statt prüfen. Zweite Hälfte der Regel: dazuschreiben, *woran* gemessen
  wurde. Eine Heuristik an dem Kriterium zu messen, nach dem sie selbst
  zuordnet, ergibt eine hohe Zahl und keine Erkenntnis.
- **Der Testsplit ist zum Messen da, nicht zum Entwickeln.** Heuristiken,
  Schwellwerte und Konstanten werden an Train/Dev entwickelt; Test wird einmal
  am Ende angefasst. Wer eine Regel an Testseiten baut und danach an denselben
  misst, bekommt eine In-Sample-Zahl – auch dann, wenn das *Modell* die Seiten
  nie gesehen hat. Das ist beim Clustering schon passiert.
- **Ein belegter Fall im Docstring gehört als Test ins Repo.** Wer schreibt
  „belegter Fall: FREIXENET/HARIBO auf 1351497_p1", hat die Arbeit schon
  gemacht – die Seite liegt in `data/words/`, die Erwartung steht im Text.
  Ohne Test schützt die Begründung nichts: die nächste Änderung an einer
  Konstante macht den Fall still wieder kaputt, und alle Tests bleiben grün.
- **Ein Test, der nie rot wird, schützt nichts – das prüft man nach.** Beim
  Festschreiben der acht Clustering-Fälle waren vier von sieben verstellten
  Konstanten *ohne jede Wirkung* auf die Tests, darunter beide des
  Legenden-Pfads. Die Pins sahen aus wie Schutz und waren keiner. Wer einen
  Regressionstest schreibt, verstellt danach einmal die Konstante, die er
  schützen soll, und sieht nach, ob wirklich etwas bricht. Zwei Minuten Arbeit,
  und sie unterscheiden einen Test von einer Behauptung. Übrig bleibt bei
  `offers.py` weiterhin die dy-Schwelle in `_same_block`: um das Fünffache
  verstellbar, ohne dass ein Test es merkt.
- **Auf `main` wird nicht gearbeitet: kein Commit, kein Push, kein Merge direkt
  dorthin** – auch nichts Kleines, auch nicht bei grünen Tests. Wer versehentlich
  auf `main` ausgecheckt ist und schon Änderungen im Arbeitsverzeichnis hat,
  nimmt sie mit auf einen Branch (`git switch -c <name>`), statt zu committen
  und hinterher aufzuräumen. Der Weg ist: Feature-Branch → Pull Request nach
  `development` → von dort gesammelt nach `main`. Ein Feature-Branch darf auch
  einfach liegen bleiben, bis jemand draufgeschaut hat; ungemergte Arbeit
  kostet nichts, ein ungeprüfter Merge schon. Der Grund ist nicht Bürokratie:
  `main` trägt die Zahlen, die im Bericht stehen. Wer dort direkt hineinmergt,
  verschiebt die Grundlage einer Messung ohne zweites Augenpaar – und Fehler in
  Heuristiken sehen von innen genau wie Verbesserungen aus, solange niemand
  gegengerechnet hat.

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
  und `magda curve` lesen deshalb den `checkpoint-N`-Ordner mit der höchsten
  Schrittzahl – hilfsweise `<lauf>/trainer_state.json`, wenn keiner mehr liegt
  (`checkpoints.training_state_path`, eine Stelle für beide Leser).
- **Die `checkpoint-N`-Ordner sind 1,2 GB je Stück und nach dem Training
  entbehrlich – bis auf den Verlauf.** `save_total_limit=2` lässt zwei davon
  je Lauf liegen; über sechs Läufe sind das 14,7 GB gegen 417 MB in `best/`.
  `magda prune-checkpoints` berichtet, `--apply` löscht. Zwei Fallen, die
  jeden naiven Aufräumbefehl teuer machen: Eine Kopie des Verlaufs nach
  `best/` **hilft nicht**, weil beide Leser `checkpoint-*` globben und `best/`
  darauf nicht matcht – gesichert wird deshalb nach `<lauf>/trainer_state.json`,
  dorthin, wo das RunPod-Bundle ihn für `gbert` und `layoutxlm` ohnehin schon
  ablegt. Und in `checkpoints/gbert` gehören `checkpoint-60/75` (30.07.) zu
  `best.vor-3wochen-split`, während die Wurzeldatei (02.08.) zum eingefrorenen
  `best/` gehört: ein vorhandener Verlauf wird nie überschrieben. Nebeneffekt
  des Aufräumens ist dort, dass `/api/model` erstmals den Verlauf zeigt, der
  zum ausgelieferten `best/` gehört (0.9186 statt der 0.9419 vom Vorlauf).
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
- **Ein frischer Klon bekommt keine Seitenbilder, und `magda extract` meldet
  dabei Erfolg.** Der Schritt überspringt eine Seite an ihrer vorhandenen
  Wortdatei, *bevor* er das PNG rendert – `data/words/` ist versioniert,
  `data/images/` nicht. Gemessen am 03.09.2026 auf dem vollen Korpus: „0 Seiten
  verarbeitet, 666 schon vorhanden", null Bilder. Der Annotator zeigt danach
  leere Seiten, und README wie `docs/archive/README.md` haben genau diesen
  falschen Befehl empfohlen. Der Weg ist `magda extract --render-missing`; es
  rührt `data/words/` nicht an, weil die Wortreihenfolge der Vertrag ist.
  Naheliegend und falsch wäre, stattdessen `data/words/` zu löschen: das
  entwertet jeden Label-Index in `data/labeled/` und `gold/`.
  Allgemeiner: Eine Ableitung ist nur so gut wie der Schritt, der sie
  herstellt. `data/images` wurde ausgelagert mit der Begründung „deterministisch
  reproduzierbar" – reproduzierbar war sie, der dokumentierte Befehl tat es nur
  nicht.
- **43 Seitenbilder liegen als Ausnahme doch in git** (seit 03.09.2026): die
  Seiten der Handannotation aus `data/annotation_task.json`, also Katalog
  1364390 plus vier Cluster-Vertreter, 89 MB, als Positivliste in
  `.gitignore`. Grund ist der Adressat – wer nur annotiert, soll nicht erst
  1,1 GB aus Drive holen, um 43 von 668 Bildern zu bekommen. Abgelegt sind sie
  **byte-identisch, nicht verkleinert**: `offer_pairs.load_pixels` liest
  dieselben Dateien, verkleinerte ergäben auf einem anderen Rechner andere
  Farbmerkmale. Kein Präzedenzfall für die nächste Erntewoche (~440 MB).
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
- **Die API ist nicht mehr read-only.** Geschrieben wird an sechs aufgezählten
  Stellen: `gold/` (handannotierte Spans), `gold/offers/`
  (Gruppierungsreferenz), `catalogs.json` (Katalog-Verzeichnis), `data/runs/`
  (Lauf-Historie), `data/audit/` (Urteile der Handprüfung – niemals
  `data/labeled/` selbst) und `data/uploads/` (Demo-PDFs samt Ergebnis-JSON
  und Seitenbildern). Bei Letzterem vergibt der Server die ID
  (`secrets.token_hex`, siehe `magda.uploads`), nie der Dateiname des
  Nutzers – sonst wäre ein hochgeladener Dateiname ein potenzieller Pfad
  (`../../etc/passwd.pdf`). Eine Erlaubnisliste, kein freier Schreibzugriff –
  dieselbe enge Beschränkung wie beim Runner.
- **Spans und Gruppen liegen in getrennten Dateien**, obwohl beide von Hand
  entstehen: `gold/<seite>.json` sagt, *was* ein Wort ist,
  `gold/offers/<seite>.json`, *wozu* es gehört. In einer Datei zöge eine
  halbfertige Gruppierung die fertigen Spans derselben Seite in den Status
  `in_progress` – und damit aus
  jeder Messung heraus, die `status: done` verlangt.
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
- **Ein Python-Kind an einer Pipe puffert blockweise, und `bufsize=1` ändert
  daran nichts.** Das Argument steuert nur das Lesen im Elternprozess.
  Belegt am 30.08.2026: `magda offers-grid` lief 7,5 Stunden in eine
  umgeleitete Datei und hinterließ sie **0 Bytes** groß – die fünf
  Fortschrittszeilen füllten den 8-KB-Puffer nie. Im Frontend traf es
  dieselben Schritte, also gerade die langen, bei denen man zusehen will.
  `runner.py` setzt jetzt `PYTHONUNBUFFERED=1`; wer von Hand umleitet,
  nimmt `python -u` oder dieselbe Variable. Ohne das ist ein Lauf ohne
  Ausgabe nicht von einem hängenden zu unterscheiden.
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
  ohne Angabe gilt `config.CANONICAL_LABELS`. Der Modellname wird zum
  Ordnernamen und kommt aus einer Nutzereingabe – deshalb
  `config.model_slug()`, sonst wäre `../../gold` ein gültiger Modellname.
- **Abgeschlossene Arme liegen in `data/labeled_archive/`** (seit 24.08.2026).
  Acht gleich aussehende Ordner beantworteten die Frage „was ist aktuell?"
  nicht mehr, und sie wurde deshalb nach Ordnergröße beantwortet – also
  falsch. Stand jetzt: **aktiv `sonnet-5` (666 Seiten, Stand 25.08.2026)**, archiviert die
  beiden Mistral-Läufe und `qwen3.5-397b-a17b`. Drei abgebrochene Probeläufe
  (2, 3 und 3 Seiten) sind gelöscht; geprüft war vorher, dass keine davon
  eine Seite exklusiv hielt – die Gesamtmenge blieb bei 422.

  Drei Eigenschaften, die daran hängen und leise brechen:

  - **Ein Geschwisterordner, kein Unterordner.** `model_slug()` verbietet
    Pfadtrenner, also wäre `data/labeled/archiv/mistral/` über
    `--labels-from` nicht erreichbar, und `labeled_models()` listete
    „archiv" selbst als Modell.
  - **`labeled_page_ids()` scannt beide Wurzeln.** Es ist die Sicherung von
    `magda dedupe`: fällt das Archiv aus dem Scan, entfernt Schritt 06
    Seiten, in die Labelarbeit geflossen ist, und Schritt 02 stellt sie
    beim nächsten Lauf als `pending` wieder ein.
  - **`labeled_dir()` fällt ins Archiv zurück, aktiv hat Vorrang.**
    Andersherum schriebe ein Labellauf nach `data/labeled/` und gelesen
    würde aus dem Archiv – eine Differenz, die an keiner Zahl auffällt.

  Ebenso mitgewandert ist `review.default_pair()`: aktiv steht nur noch eine
  Modellfamilie, und ohne Zugriff aufs Archiv fände `magda queue` kein Paar
  aus *verschiedenen* Modellen mehr.
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
- **Layout bringt nichts, das Seitenbild bringt etwas – seit 25.08.2026
  getrennt gemessen.** Der Satz darunter („kein Effekt nachweisbar") galt für
  175 Trainingsseiten und einen Vergleich mit *drei* Unterschieden auf einmal:
  GBERT und LayoutXLM haben verschiedene Textencoder, verschiedene
  Positionsinformation und verschiedene Bildinformation. Zwei Zwischenarme
  zerlegen das, alle drei mit demselben Textencoder (XLM-R):

      xlmr  ──+Layout──▶  lilt  ──+Bild──▶  layoutxlm

  Test = KW35, 116 Seiten in **42 Clustern**, 5973 Entities, 494
  Trainingsseiten, Referenz `sonnet-5`. Gepaart über Cluster gebootstrappt,
  Differenz als *später minus früher*:

  | Schritt | Zutat | Differenz | 95-%-KI | p |
  |---|---|---:|---|---:|
  | gbert → xlmr | anderer Encoder | +0.0059 | [−0.0015, +0.0156] | 0.165 |
  | **xlmr → lilt** | **Layout** | **−0.0003** | [−0.0063, +0.0058] | **0.925** |
  | **lilt → layoutxlm** | **Bild** | **+0.0096** | [+0.0033, +0.0182] | **0.019** |
  | gbert → layoutxlm | alle drei | +0.0152 | [+0.0074, +0.0262] | 0.008 |

  Punktschätzer: gbert 0.9084, xlmr 0.9143, lilt 0.9140, layoutxlm 0.9236.
  Der Layout-Schritt ist mit ±0.006 die **präziseste Null des Projekts** –
  keine schwache Wirkung, sondern keine. Der Bildgewinn sitzt fast
  vollständig bei PRODUCT (+0.028) und BRAND (+0.026), also den Labels, für
  die das Proposal Positionsinformation vermutet hatte: die Vermutung stimmt,
  die Annahme „Wortkoordinaten liefern sie" nicht.
  **Vier Vergleiche ohne Korrektur für multiples Testen, und sie sind nicht
  unabhängig** (die Gesamtdifferenz ist die Summe der Schritte). Bei
  Bonferroni hält nur die letzte Zeile. Belastbar ist: LayoutXLM schlägt
  GBERT, und *innerhalb* dieser Differenz ist der Layout-Anteil null.
  Ein Lauf je Arm, keine Seed-Streuung gemessen. Details:
  `reports/woche-06.md`.
- **Der Bildgewinn ist ein Zuordnungs-, kein Erkennungsgewinn** – ablesbar an
  den Matching-Schemata, die `magda eval` ohnehin mitschreibt. Er schrumpft
  mit jeder Lockerung des Schemas: strict +0.0096, exact +0.0079, partial
  +0.0043, type +0.0021. In MUC-Zählungen von GBERT zu LayoutXLM: zehn
  übersehene Entities weniger (313 → 303), aber **69 Zuordnungsfehler weniger**
  (272 → 203). Der Typfehleranteil halbiert sich (0.0046 → 0.0022), der
  Grenzfehleranteil sinkt um ein Fünftel (0.0207 → 0.0161).
  Das erklärt beide Hälften des Befunds: PRODUCT leidet an Grenzfehlern
  (Sortenzusätze – die offene Teamfrage), BRAND an Typfehlern (Marke oder
  Produktname), und beides entscheidet die Stellung auf der Kachel. Und es
  erklärt, warum Wortkoordinaten nichts beitragen: `bbox` sagt, *wo* ein Wort
  steht, nicht *wie es gesetzt ist* – Schriftgröße und Fettung stehen im Bild,
  und selbst 49 grobe Bildkacheln übertragen davon genug.
  **Wer die vier Schemata berichtet, nennt dazu, welches die Primärzahl ist**:
  `strict` (Span und Typ exakt) ist es, alle anderen sind nachsichtiger und
  ergeben höhere Werte für dieselbe Ausgabe – GBERT steht bei `strict` auf
  0.9084 und bei `type` auf 0.9477, ohne dass ein Wort anders vorhergesagt
  wird.
- **Die Nachsicht der lockeren Schemata schenkt fast nur PRODUCT.** Gemessen
  über den KW35-Test (`type` minus `strict`, GBERT): PRODUCT +0.143, BRAND
  +0.055, VALID +0.053, QUANTITY +0.019, UNIT_PRICE +0.008 – und **PRICE,
  OLD_PRICE, DISCOUNT und APP_PRICE exakt ±0.000**. Bei Preisen gibt es keine
  Grenzfehler: `1.99` ist ein Token, richtig oder falsch. Wer also `type`
  berichtet, sagt der Sache nach „wir zählen die Sortenzusatz-Frage weg" –
  genau die offene Teamentscheidung. Deshalb muss das Schema *vor* der Messung
  feststehen; nachträglich das nachsichtigste zu wählen ist dieselbe Bewegung
  wie eine Heuristik an ihrem eigenen Zuordnungskriterium zu messen, nur
  unauffälliger, weil alle vier Zahlen aus demselben Lauf stammen und einzeln
  korrekt sind. Umgekehrt gilt: Ein Teil der 0.143 ist kein Modellfehler,
  sondern die Uneinheitlichkeit von Gold – die Konsequenz ist, die Konvention
  zu entscheiden, nicht das Schema zu wechseln.
- **Berichtet wird F1 über Entities, nie Accuracy über Tokens.** 54,5 % aller
  Wörter tragen `O`; ein Modell, das alles als `O` rät, käme auf über 0.5
  Token-Accuracy, ohne ein einziges Angebot zu finden.
- **APP_PRICE wird vom Seitenbild nicht gelöst – gegenteilig belegt.** Der
  rein visuelle Fall ist genau der, bei dem LayoutXLM *verliert*: 0.882 gegen
  LiLTs 0.906, das ohne Bild arbeitet. Der Grund steht schon in der
  Architektur (49 visuelle Token für die ganze Seite, siehe unten) und ist
  damit gemessen statt vermutet. Der Backbone liefert grobe Seitenstruktur,
  keine lokale Farbe. Weg B (Farbe je Wort als Merkmal) ist dadurch
  gestärkt, nicht erledigt.
- ~~**Zum Layout-Vorteil ist kein Effekt nachweisbar – in keine Richtung.**~~
  *(Überholt am 25.08.2026, siehe oben. Der Befund war nicht falsch, sondern
  unterbestimmt: gemessen an 175 Trainingsseiten und ohne Zwischenarme.)*
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
  (`magda split --strategy week`). **Stand 25.08.2026 über sechs Wochen:
  KW30–KW34 lernen, KW35 testet, 494/56/116 Seiten in 210/25/42
  Duplikat-Clustern, 24900/2584/5973 Entities.** Test-zu-Train Median-Jaccard
  0.297, Max 0.778, keine Seite ≥ 0.9; Dev Median 0.360, keine über 0.7.
  Der Absatz unten beschreibt den vorigen Stand (KW32 als Testwoche) und ist
  als Begründung des Verfahrens weiter gültig – die Zahlen darin sind es
  nicht. Stand 02.08.2026 über drei Wochen:
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
- **Der Testsatz hat 116 Seiten, aber nur 42 unabhängige Einheiten**
  (KW35, seit 25.08.2026; davor 100 Seiten in 43 Clustern – die Zahl der
  unabhängigen Einheiten wächst also *nicht* mit der Seitenzahl).
  Bei Jaccard 0.7 bilden die Seiten 42 Cluster.
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
  Verschachtelung. Ein Span-Label kann nur zusammenfassen, was benachbart ist –
  wie weit das trägt, misst `magda offers-sequence`.
- **Eine flache OFFER-Folge fasst die Beschreibung, den Preis nicht mit.**
  Nachgerechnet über 293 Seiten (`magda offers-sequence --labels-from
  sonnet-5`, 06.08.2026): Von 3066 Angeboten der Heuristik sind **2080 ein
  einziger Lauf – 0.678**. Lässt man die Preis-Badges weg, sind es **2530 von
  2637, also 0.959**. Die Differenz ist die ganze Aussage: Penny setzt den
  Preis in einen gelben Kasten, und der steht im Textlayer weit weg vom
  Produktnamen – auf `1342815_p21` liegt der Preis bei Wort 6, sein Produkt
  bei Wort 166. Ein flacher Span kann beide nicht zusammenfassen, ohne alles
  dazwischen mitzunehmen.
  **Das ersetzt die frühere Zahl 92,7 % (3728 von 4022) nicht, sondern
  ergänzt sie:** die zählte *visuelle Wortgruppen* aus dem Kachelversuch, also
  eine andere Einheit, und hatte kein Skript im Repo. Für die OFFER-Frage
  zählt die Einheit „Angebot", und dort ist 0.678 die Obergrenze, nicht 0.927.
  Einschränkung: gerechnet über die Gruppierung der *Heuristik*, deren Fehler
  also mitgezählt. `--reference` rechnet dieselbe Zahl gegen die
  Handannotation, sobald `gold/offers/` gefüllt ist.
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
- **Das Clustering ließ sich lange nicht ehrlich messen, weil das Messkriterium
  das Zuordnungskriterium war.** „Wie oft landet ein Preis bei einem Produkt"
  zählt Fragmentierung, nicht Korrektheit – ein Preis am *falschen* Produkt
  geht als Erfolg durch. Und der naheliegende Ausweg trägt nicht: die
  Zuordnungen nach arithmetisch und geometrisch zu trennen und die Rechnung
  über die geometrischen Fälle urteilen zu lassen, ergibt garantiert „falsch".
  `_match_badges` betritt den geometrischen Zweig **nur, wenn kein Block
  arithmetisch gepasst hat** – das Urteil steht fest, bevor es gefällt wird.
  Der Ausweg ist eine **Ablation**: `cluster_page(page, arithmetic=False)`
  schaltet die Rechnung zum Messen ab, die Geometrie ordnet allein zu, und
  erst danach wird nachgerechnet. Das ist das allgemeine Muster – halte das
  Merkmal zurück, mit dem du hinterher richten willst.
- **Der geometrische Rückfall trifft in 0,56 bis 0,68 der prüfbaren Fälle**
  (`magda offers-report`, 06.08.2026, Train + Dev, 196 Seiten, `sonnet-5`):
  462 bestätigt, 215 bis 361 widerlegt, 678 bis 532 nicht beurteilbar. Er
  trägt dabei 652 von 1373 Zuordnungen, also knapp die Hälfte. Zwei Zahlen,
  weil eine Frage offen ist: zählt ein Block, der diesen Preistyp schon trägt,
  noch als rechnerische Alternative? Beide Antworten sind vertretbar und
  trennen 146 Fälle; `confirmed` ist unter beiden identisch. Eine Lesart zur
  richtigen zu erklären hieße, eine Genauigkeit zu behaupten, die die Messung
  nicht hergibt – deshalb das Intervall, wie beim Layout-Vergleich.
  Damit ist auch der Ertrag des arithmetischen Abgleichs beziffert: das sind
  genau die Fehler, die er abfängt.
- **Wo kein Grundpreis steht, ist die Zuordnung nicht nur schlechter, sondern
  unprüfbar.** 532 bis 678 der Urteile lauten „nicht beurteilbar", und das
  deckt sich fast mit Non-Food. Dort ist die Geometrie alleinige Instanz *und*
  ohne Kontrolle. Diese Lücke schließt keine Heuristik und kein Schwellwert,
  sondern nur eine handannotierte Gruppierungsreferenz. Der Grund ist
  derselbe wie bei APP_PRICE: wo eine Kachel endet, steht in Rahmen,
  Hintergrundfarbe und gelbem Sticker – **im Bild, nicht in den
  Wortkoordinaten**. Ein fehlendes Merkmal lässt sich nicht kalibrieren.
- **Die Gruppierungsreferenz gruppiert Wortindizes, keine Entity-Spans**
  (`gold/offers/`, seit 06.08.2026). Ein Span gehört immer einem Labelordner;
  eine Referenz darüber wäre nach dem nächsten Labeling-Lauf wertlos und
  könnte die gbert-Vorhersagen gar nicht beurteilen, weil deren Spans anders
  liegen. Über Wortindizes beurteilt dieselbe Annotation die Heuristik, einen
  LLM-Teacher und einen OFFER-Kopf – abgesichert mit `words_hash` wie `gold/`.
  Gemessen wird mit `magda offers-gold`: **Paar-F1** über Entity-Paare (die
  übliche Primärzahl der Line-Item-Literatur) und **Gruppen-F1** über exakt
  getroffene Angebote, also „die Zeile in der Datenbank stimmt". Zwei Regeln,
  die leicht falsch gebaut werden: Die Entity-Grundmenge kommt aus der *Seite*,
  nicht aus der Systemausgabe – sonst verbessert ein System seinen Recall,
  indem es Entities weglässt. Und was der Mensch keinem Angebot zugeordnet hat
  (Kleingedrucktes, Seitenkopf), bewegt keine Zahl, sondern wird als
  `unassignable` ausgewiesen.
- **Annotiert wird aus dem Seitenbild, nicht durch Korrigieren der Heuristik.**
  Eine vorbefüllte Gruppierung wäre bequem und wiederholte genau den Fehler,
  gegen den `magda offers-report` gebaut wurde: Wer die Ausgabe des Verfahrens
  korrigiert, ankert daran und misst hinterher teilweise sich selbst. Ein Klick
  im Annotator nimmt dafür die ganze Entity statt eines Wortes – wortweise wäre
  die Referenz genauso ausdrucksstark, aber ein Angebot hat schnell zwölf
  Wörter.
- **`magda offers-queue` wählt die 30 bis 50 Seiten**, abwechselnd nach dem
  gemessenen blinden Fleck (kein Grundpreis, also kein Urteil der Ablation
  möglich) und nach der Clustergröße. Nur nach dem blinden Fleck sortiert
  entstünde eine reine Non-Food-Referenz; nur nach der Größe deckte die
  Handarbeit genau das ab, was die Rechnung ohnehin prüft. Stand 06.08.2026
  decken die ersten 40 Vorschläge 125 der 196 Train/Dev-Seiten ab, hälftig aus
  beiden Ranglisten. Train und Dev, nie Test.
- **Die Handannotation findet nicht statt – ein Vision-Modell gruppiert**
  (Teamentscheidung, 06.08.2026). 30 bis 50 Seiten von Hand sprengen den
  Projektrahmen. Das Ergebnis liegt deshalb in `data/offer_groups/<quelle>/`
  und **nicht** in `gold/offers/`, mit `provenance: {"kind": "llm", …}` in
  jeder Datei. Der getrennte Pfad ist der eigentliche Punkt: `magda
  offers-gold --reference-from claude-sonnet-5` misst damit
  **Übereinstimmung, nicht Richtigkeit** – dieselbe Einschränkung wie bei
  `magda agreement`, und die Ausgabe sagt es dazu. Was den Vergleich trotzdem
  tragfähig macht, sind die verschiedenen Informationsquellen: die Heuristik
  kennt nur Wortkoordinaten, das Modell sieht den gelben Preiskasten. Wo
  beide sich einig sind, ist das ein Argument; wo nicht, zeigt es auf eine
  Seite zum Nachsehen. `gold/offers/` bleibt als Format bestehen und ist
  weiter der Default – wer später doch Stichproben von Hand macht, misst
  ohne Codeänderung dagegen.
- **`magda offers-verify` ist die einzige unabhängige Kontrolle über eine
  maschinelle Referenz.** Menge × Grundpreis beweist sich selbst, und ein
  Modell, das nach dem Seitenbild gruppiert, hat dabei nie gerechnet. Genau
  deshalb braucht dieser Weg **keine Ablation**, anders als `magda
  offers-report`: dort ordnet `_match_badges` teilweise selbst arithmetisch
  zu, das Urteil stünde vor der Frage fest. Vier Urteile statt drei, und die
  Trennung ist wesentlich: `unresolved` (Grundpreis da, Rechnung geht
  nirgends auf) getrennt von `contradicted` (Rechnung zeigt auf eine andere
  Gruppe). Ein Preis, der zu keiner Gruppe passt, belegt nichts gegen die
  Zuordnung – die Ursache ist meist eine Mehrfachpackung (`2 x 350 g`, deren
  Multiplikator `_quantity_in_unit` ignoriert) oder ein fehlendes Label. Wer
  ihn als widerlegt zählte, schriebe Labelfehler dem Gruppieren zu.
  Zusammen mit `accuracy` gehört immer `coverage` berichtet: eine Genauigkeit
  von 0.9 über ein Fünftel der Preise ist eine Aussage über ein Fünftel.
- **Der Teacher antwortet in Entity-Nummern, gespeichert werden Wortindizes.**
  Entities sind die Einheit, in der auch der Annotator klickt – ein Angebot
  hat schnell zwölf Wörter, und wortweise zu antworten vervielfacht die
  Ausgabe ohne Gewinn an Ausdruckskraft. Wortindizes sind die Einheit, die
  den nächsten Labeling-Lauf überlebt. `offer_teacher.expand_entity_groups`
  lehnt unbekannte und doppelt vergebene Nummern ab, statt sie zu
  überspringen: eine halbe Antwort als ganze zu speichern macht die Referenz
  um genau den Betrag falsch, den niemand sieht.
- **Erste Messung gegen die LLM-Gruppierung** (06.08.2026, 33 Train/Dev-Seiten,
  1634 Entities, `claude-sonnet-5` als Subagent mit Seitenbild). Alle drei
  Zahlen über dieselbe Seitenmenge, sonst wären sie nicht vergleichbar –
  dafür gibt es `magda offers-report --pages-from`:

  | | Trefferquote | beurteilte Preise |
  |---|---|---|
  | Heuristik, Geometrie allein (Ablation) | 0.463 – 0.620 | 100 – 134 |
  | LLM, sieht das Seitenbild | **0.925** | 159 |

  Richter ist beide Male die Rechnung Menge × Grundpreis, und sie ist an
  beiden Zuordnungen unbeteiligt: die Heuristik läuft unter Ablation, das
  LLM hat nie gerechnet. **`offers_verify` zählt dabei nach der strengeren
  Regel** – jede andere Gruppe gilt als Gegenbeleg, ohne Rücksicht darauf,
  ob sie diesen Preistyp schon trägt. Das entspricht dem strengen Ende der
  Heuristik-Spanne (0.463), das LLM wird also nicht bessergestellt.
  Übereinstimmung insgesamt: **Paar-F1 0.723, Gruppen-F1 0.331.** Die Lücke
  zwischen beiden ist die Aussage – Teile eines Angebots trifft die Heuristik
  oft, das vollständige Angebot nur bei knapp jedem dritten. Gruppen-F1 ist
  die Zahl, die „die Zeile in der Datenbank stimmt" entspricht.
  **Einschränkung, die immer mitgehört:** Abdeckung 0.429. Über die Hälfte
  der Preise trägt keinen Grundpreis, dort schweigt die Rechnung – und das
  deckt sich mit Non-Food, also mit genau dem Bereich, für den die
  Gruppierung gebraucht wird. Die 0.925 gelten für die prüfbare Hälfte.
- **Die Heuristik fragmentiert messbar: 417 Angebote gegen 296.** Über
  dieselben 33 Seiten bildet `cluster_page` 41 % mehr „Angebote" als das LLM,
  davon 147 Fragmente ohne Produkt-und-Preis. Das erklärt auch, warum das LLM
  *mehr* beurteilbare Fälle hat (159 gegen 100–134): wo ein Preis als
  Bruchstück liegen bleibt, entsteht keine Rechnung, die man prüfen könnte.
  Ein Verfahren, das seltener zuordnet, sieht in einer Genauigkeitszahl
  besser aus, als es ist – deshalb gehört die Zahl der Zuordnungen daneben.
- **Belegter Fall für den blinden Fleck: `1347387_p31`.** Non-Food-Legende,
  kein Grundpreis, also für `magda offers-report` grundsätzlich unbeurteilbar.
  Im Seitenbild steht „④ Pflanztopf-Set – je Set 8.99" und „⑤
  Fensterdoppelrollo – je Stück 9.99"; die Heuristik ordnet beide vertauscht
  zu, das LLM richtig. Die Fehlerform ist kein Zufall, sondern ein **Versatz
  über eine ganze Legendenspalte**: jeder Preis greift zum nächstgelegenen
  Namen, und wenn der Abstand einmal kippt, kippt die Kette mit. Ein anderer
  Schwellwert repariert das nicht, er verschiebt nur die Stelle. Kein
  Regressionstest, weil hier ein Fehler festgeschrieben würde, keine
  Zusicherung – der Fall gehört in die Fehleranalyse, nicht in die Pins.
- **Ein gelerntes Paarmodell schlägt die Heuristik deutlich** (Stand
  29.08.2026: Gruppen-F1 0.778 gegen 0.524 auf 56 Dev-Seiten; die Tabelle
  unten ist der historische Erstbefund vom 06.08. über 21 Seiten und
  erklärt, warum die Zahl damals „knapp" hieß).
  `magda offers-model` klassifiziert jedes Entity-Paar
  („gehören die zusammen?"), verschmilzt die Kanten oberhalb einer Schwelle
  zu Zusammenhangskomponenten und ist damit die zweite Standardlösung aus
  DocILE. Gelernt aus `data/offer_groups/claude-sonnet-5/` (damals 51 Seiten:
  30 Train, 21 Dev; **seit dem 25.08.2026 sind alle 666 Seiten gruppiert,
  davon 494 Train**), 4097 Parameter. Eine GPU lohnt hier weiterhin nicht –
  der Grund für RunPod war LayoutXLMs RAM-Bedarf, nicht Rechenzeit.
  **Die oft zitierten „16,8 s Training auf CPU" gelten so nicht mehr**: Das
  war ein Lauf ohne Kalibrierung über 54 Seiten. Mit den heutigen Defaults
  (5 Folds, 25 Schwellen, ILP-Dekoder) sind es über 494 Seiten rund 21
  Minuten bei `MAX_COMPONENT = 40` und **gemessen 76 bei 120** (29.08.2026,
  MacBook Air M2, ein Kern) – die vorher geschätzten 45 waren zu
  optimistisch. Die Zeit steckt
  fast vollständig im ILP, nicht im Netz mit seinen 4097 Parametern – wer
  die alte Zahl als Aufwandsschätzung benutzt, verrechnet sich um zwei
  Größenordnungen. Stand 06.08.2026 auf Dev, Schwelle 0.94:

  | | Paar-F1 | Gruppen-F1 | Angebote |
  |---|---|---|---|
  | Paarmodell | **0.742** | **0.477** | 138 |
  | Heuristik | 0.683 | 0.436 | 185 |
  | Lehrer (Referenz) | – | – | 122 |

  Das Modell ist in beiden Zahlen vorn *und* fragmentiert weniger. Die
  arithmetische Gegenprobe stützt das: 0.864 gegen 0.802 der Heuristik –
  und die Rechnung ist beim Modell wirklich unbeteiligt, während
  `cluster_page` teilweise selbst arithmetisch zuordnet.
  **Drei Einschränkungen, die mitgehören:** 21 Dev-Seiten in 14 Clustern
  sind dünn, ein Konfidenzintervall gibt es noch nicht. Der Lehrer ist ein
  LLM, also misst „Übereinstimmung", nicht Richtigkeit. Und die Abdeckung
  der Gegenprobe liegt bei 0.589 – die Non-Food-Hälfte bleibt ungeprüft.
- **Der Dekoder wiegt schwerer als jedes bisher gefundene Merkmal.**
  `groups_from_edges` verschmilzt A-B und B-C zu einer Gruppe, auch wenn
  A-C weit unter der Schwelle liegt – das steht seit jeher im eigenen
  Docstring. `magda offers-grid --decoder union,ilp --cross-validate`
  (11.08.2026, 75 Seiten in 68 Clustern, out-of-fold, geschachtelte
  Schwellenwahl) beziffert es erstmals: Gruppen-F1 **0.553 gegen 0.453**,
  gepaarte Differenz **+0.100 [+0.067, +0.133] bei p = 0.000**; im blinden
  Fleck +0.115. Zum Vergleich: `+Geometrie`, der beste Merkmalsblock, lag
  bei +0.044 (p = 0.018).
  **Die Wirkungskette ist die eigentliche Aussage:** Der Gewinn kommt nicht
  daher, dass das ILP bei gleicher Schwelle besser dekodiert, sondern dass
  es eine niedrigere *erlaubt* – die Kalibrierung wählte out-of-fold 0.868
  statt 0.956, ohne Vorgabe. Union-Find muss so hoch drehen, weil eine
  einzige durchgerutschte Kante eine Legendenspalte verschmilzt; das ILP
  kappt stattdessen die schwächste Kante des Widerspruchs.
  **Drei Dinge gehören zu jeder Nennung:** Im CV-Lauf *fällt* Paar-F1
  (0.569 gegen 0.715), weil die tiefere Schwelle 19060 statt 13531 Paare
  vorhersagt – auf Dev steigt es dagegen (0.880 gegen 0.782), und
  belastbar ist die CV-Zahl. Die Komponentenkappung (`MAX_COMPONENT`)
  griff bei 1611 von 37367 Komponenten; dort *ist* das ILP Union-Find, der
  Effekt also eher unter- als überschätzt. Und beide Dekoder wurden auf
  `group_f1` kalibriert – **wer Paar-F1 zur Primärzahl macht, dreht den
  Teilbefund um.** Das ist die schon offene Teamentscheidung.
  Die arithmetische Gegenprobe stützt das Ergebnis (0.883 gegen 0.845 bei
  *identischer* Abdeckung 0.589, widerlegte Preise 12 statt 16). Sie ist
  hier unbefangen, weil die Rechnung bewusst kein Constraint des ILP ist –
  und die gleiche Abdeckung entkräftet den Einwand, gröbere Gruppen
  schmeichelten der Prüfung.
  **`MAX_COMPONENT` steht seit dem 29.08.2026 auf 120 statt 40** – die
  Zahlen dieses Absatzes stammen aus dem gekappten Lauf und sind damit
  nicht mehr reproduzierbar, ohne die Konstante zurückzustellen.
- **Die Komponentenkappung des ILP kann eine Metrik allein entscheiden –
  belegt am 29.08.2026.** Nach dem Neutraining des Paarmodells auf 494
  statt 54 Referenzseiten wählte die Kalibrierung out-of-fold die Schwelle
  **0.82** statt 0.88. Tiefere Schwelle heißt größere Komponenten, und bei
  `MAX_COMPONENT = 40` kappte der Dev-Lauf dadurch **5 von 297
  Komponenten**, die größte mit 111 Entities. Das Ergebnis sah so aus:

  | | Paar-F1 | Gruppen-F1 | Angebote |
  |---|---:|---:|---:|
  | Paarmodell (Cap 40) | **0.398** | 0.659 | 413 |
  | Heuristik | 0.817 | 0.524 | 510 |
  | Lehrer (Referenz) | – | – | 422 |

  (56 Dev-Seiten, arithmetische Gegenprobe 0.908 gegen 0.833 der Heuristik
  bei Abdeckung 0.548 / 0.529. Die Zeile „Paarmodell" ist mit dem
  Neutraining bei Cap 120 hinfällig – sie steht hier als Beleg des Befunds,
  nicht als Leistungsangabe.)

  **Die Gegenprobe ist gelaufen, und sie fällt deutlicher aus als erwartet.**
  Dasselbe Netz, dieselben 35 Merkmale, nur `MAX_COMPONENT = 120` und eine
  neu kalibrierte Schwelle (0.68 statt 0.82), Dev vom 29.08.2026:

  | | Paar-F1 | Gruppen-F1 | Angebote |
  |---|---:|---:|---:|
  | Paarmodell, Cap 120 | **0.929** | **0.778** | 429 |
  | Paarmodell, Cap 40 | 0.398 | 0.659 | 413 |
  | Heuristik | 0.817 | 0.524 | 510 |
  | Lehrer (Referenz) | – | – | 422 |

  Über alle 245 Dev-Komponenten wurde **keine einzige gekappt**. Paar-F1
  steigt um 53 Punkte, Gruppen-F1 um 12 – ohne dass eine Zeile am Modell
  geändert wurde. Die arithmetische Gegenprobe steigt mit: 0.912 gegen
  0.833 der Heuristik bei Abdeckung 0.548 / 0.529, widerlegte Preise 23
  statt 42. Und das Verfahren bildet 429 Angebote gegen 422 in der
  Referenz, fragmentiert also praktisch nicht mehr, während die Heuristik
  bei 510 liegt.

  **Damit ist die Notbremse als Fehlerquelle beziffert, nicht nur benannt.**
  Eine Konstante, die niemand als Modellparameter gelesen hätte, war über
  ein Jahr Projektarbeit hinweg der größte einzelne Hebel auf die
  Gruppierungsqualität – größer als jeder Merkmalsblock (+0.044) und größer
  als der Dekoderwechsel selbst (+0.100).

  **Die 0.398 sind kein Modellzusammenbruch, sondern fünf Seiten.** Paare
  wachsen quadratisch mit der Gruppengröße: die 5 Blobs erzeugten **20903
  der 26279 vorhergesagten Paare (80 %)**, bei 7351 Paaren in der Referenz.
  Ohne diese Seiten stünde Paar-F1 bei 0.919 – das ist eine Diagnose, **keine
  berichtbare Zahl**: nachträglich die Seiten zu entfernen, an denen ein
  Verfahren scheitert, ist dieselbe Bewegung, gegen die `offers_report` die
  Ablation braucht. Es sind auch eher zwei Vorlagen als fünf Fälle,
  `1342821_p20`, `1342905_p20` und `1342920_p20` liegen untereinander bei
  Jaccard 0.906 bis 0.934.
  **Der Fehler war nicht das Modell, sondern die Erlaubnis.** Ohne Kappung
  löst dieselbe 111er-Komponente in 6 bis 28 s und zerfällt in 15 Gruppen
  mit höchstens 11 Entities. Über eine Stichprobe von 12 Train-Seiten und
  das ganze Kalibrierungsraster kostet Cap 120 gegenüber 40 den Faktor 2.7
  und kappt kein einziges Mal.
  **Zwei Lehren, die über diesen Fall hinausgehen:** Erstens ist eine
  Notbremse gegen Rechenzeit keine neutrale Optimierung – sie greift
  bevorzugt dort, wo das Verfahren gebraucht wird, und *verbessert* dabei
  scheinbar die Laufzeit. Zweitens war der Befund nur sichtbar, weil
  `offer_ilp.LAST_RUN` mitzählt; im Report von `magda offers-model` stand
  der Zähler bis zum 29.08.2026 nicht, obwohl der eigene Docstring ihn „in
  jedem Report" verlangt. Er steht jetzt drin, in der Kalibrierung wie in
  der Auswertung. Ein Zähler, den kein Report ausgibt, ist keiner.
- **Checkpoint und Dekoder passen wieder zusammen** (Neutraining am
  29.08.2026, 76 Minuten). `checkpoints/offer_pairs/model.pt` trägt jetzt
  die Schwelle **0.68**, out-of-fold über 494 Seiten mit
  `MAX_COMPONENT = 120` gewählt. Der Zwischenstand mit Schwelle 0.82 aus
  der Cap-40-Kalibrierung liegt als `model.cap40.pt` – nicht als Reserve,
  sondern weil die Kappungszahlen dieses Tages daran hängen.
  Die Vorgängerstände der Testwoche KW32 sind
  `checkpoints/offer_pairs/*.kw32-split.pt`; `checkpoints/` ist gitignored,
  und an den 11.08-Zahlen hängen berichtete Ergebnisse.
  **Die Regel dahinter gilt weiter:** eine Schwelle ist für ihren Dekoder
  gewählt. Wer `MAX_COMPONENT` anfasst, hat den Checkpoint entwertet, auch
  wenn nichts abstürzt und die Zahl korrekt gerechnet bleibt.
- **Der Endvergleich gegen die LLM-Blackbox ist gebaut und bewusst nicht
  gefahren.** `magda blackbox-eval` (Commit 58a6437) stellt drei Zeilen
  gegenüber – Blackbox gegen Referenz, eigene Pipeline gegen Referenz,
  Blackbox gegen eigene Pipeline – und matcht beide Seiten durch *dieselbe*
  Funktion über die gemeinsame Feldmenge (`name`, `price`,
  `original_price`). **Der Testlauf ist nicht wiederholbar**, deshalb fallen
  die Entscheidungen vorher. Stand 29.08.2026 sind drei getroffen
  (Entscheidung Noah) und das Design noch nicht ausgearbeitet:
  - *Kein neutraler Richter.* Berichtet werden Übereinstimmung und Zeit,
    keine handannotierte Angebotsreferenz. Qualität und Fehlerzahl kommen
    über den arithmetischen Richter und die strukturellen Defekte
    (Fragmente ohne Produkt-und-Preis) hinein.
  - *Beste lokale Konfiguration tritt an*: LayoutXLM plus Paarmodell. Heute
    ist der Arm fest auf `--predictions gbert` und `offers.cluster_page`
    verdrahtet, also auf den schwächeren Labeler *und* die Heuristik.
  - *Baseline ist `sonnet-5` als Subagent*, nicht ein GWDG-Modell. Bewusst
    in Kauf genommen: die Sekunden je Seite sind damit nicht mit den 44,8 s
    des API-Labelings vergleichbar.

  Drei technische Lücken stehen dem noch im Weg: `data/eval/test_cluster_pages.txt`
  existiert nicht (je eine Seite pro Test-Cluster, 42 Stück); das
  Blackbox-Schema kennt weder `quantity` noch `unit_price` und ist damit
  arithmetisch unprüfbar; und der Subagent-Aufruf folgt besser dem Muster
  von `magda offers-teacher` (pages / task / save) als einem API-Client –
  `blackbox.py` spricht nur den OpenAI-kompatiblen GWDG-Endpunkt an, und
  die `sonnet-5`-Labels tragen `source: "annotation"`, sind also nie über
  eine API entstanden.
- **Die Decke ist gemessen, nicht geschätzt: Gruppen-F1 0.916** (29.08.2026).
  Zwei unabhängige LLM-Annotatoren auf denselben 26 Dev-Seiten – je eine
  pro Duplikat-Cluster – stimmen zu **Paar-F1 0.970 und Gruppen-F1 0.916**
  überein. Gemessen mit `magda offers-gold --groups-from claude-sonnet-5
  --reference-from claude-opus-5`. Zur Einordnung auf derselben
  Seitenmenge: die Heuristik erreicht gegen den Zweit-Teacher 0.851 / 0.566.

  | | Paar-F1 | Gruppen-F1 |
  |---|---:|---:|
  | Teacher gegen Teacher (Decke) | 0.970 | **0.916** |
  | Paarmodell (56 Dev-Seiten) | 0.929 | 0.778 |
  | Heuristik | 0.851 | 0.566 |

  **Das widerlegt die naheliegende Rechnung.** Aus 5,97 Entities je Gruppe
  und exakter Mengengleichheit folgt scheinbar eine Decke von 0.95^6 ≈ 0.74
  – tatsächlich sind es 0.916, weil die Fehler zweier Annotatoren **nicht
  unabhängig** sind: Beide sehen dasselbe Bild, und die meisten Kacheln sind
  eindeutig. Wer die Decke über eine Fehlerpotenz schätzt, unterschätzt sie
  systematisch. **Über 0.778 liegen also rund 14 Punkte Luft**, nicht 0 bis
  8 – die Arbeit an der Gruppierung lohnt weiter.
  **Einschränkungen:** 26 Seiten ohne Konfidenzintervall; die Decke ist auf
  26, das Modell auf 56 Seiten gemessen (die Heuristik steht dort bei 0.566
  gegen 0.524, die 26 sind also eher etwas leichter). Der Zweit-Annotator
  hatte ein anderes Modell *und* einen anderen Prompt – beides senkt die
  Übereinstimmung eher, die 0.916 ist damit konservativ. Er durfte die
  erste Gruppierung nicht ansehen; ohne diese Sperre misst man das Ankern.
- **`magda offers-gold --groups-from` misst zwei gespeicherte Gruppierungen
  gegeneinander**, statt die Heuristik zu beurteilen. Gemessen wird nur, wo
  *beide* Seiten gruppiert haben – eine dem System fehlende Seite als leere
  Ausgabe zu werten hieße „alles falsch" statt „nicht gemessen", derselbe
  Fehler, den `load_reference` für die Referenz schon vermeidet.
  `test_offers_gold_groups_from.py` hält das fest, und der Test wurde durch
  Ausbau der Filterzeile auf Wirksamkeit geprüft.
- **`offer_teacher.PROMPT_VERSION` ist eine Nummer ohne Text.** Der Prompt,
  mit dem `data/offer_groups/claude-sonnet-5/` entstand, ist nirgends
  gespeichert – die Referenz ist damit nicht reproduzierbar. Ab Version 2
  steht er in `docs/offer-teacher-prompt.md`. Zweite Lücke derselben Art:
  die Konstante ist nicht pro Lauf setzbar, deshalb tragen auch die
  `claude-opus-5`-Dateien `prompt_version: 1`, obwohl sie mit dem neuen
  Prompt entstanden. Wer die Versionen auseinanderhalten will, geht über
  `provenance.model`, nicht über `prompt_version`.
- **Typ-Constraints im ILP sind von den Daten widerlegt – nicht probieren.**
  Der naheliegende nächste Schritt nach dem Dekoder-Befund wäre „höchstens
  ein PRODUCT je Gruppe" als hartes Constraint. Ausgezählt über die
  Referenz (`data/offer_groups/claude-sonnet-5/`, 5491 Gruppen):
  **982 davon (17,9 %) enthalten zwei oder mehr PRODUCT-Entities**, 952
  (17,3 %) mehrere PRICE/APP_PRICE. Das Constraint wäre auf jeder fünften
  bis sechsten Gruppe falsch und zementierte den Plättungsfehler – dieselbe
  Begründung, die `offer_ilp.py` für PRICE schon führt, gilt für PRODUCT mit
  fast identischer Quote. Als weiche Strafe wäre es redundant: genau diese
  Information geben die Typ-One-Hots dem MLP bereits. Nachzählen:

  ```python
  import json, glob
  from collections import Counter
  from magda import config, offers
  multi = total = 0
  for path in sorted(glob.glob("data/offer_groups/claude-sonnet-5/*.json")):
      ref = json.loads(open(path).read())
      page = json.loads((config.labeled_dir("sonnet-5") / f"{ref['page_id']}.json").read_text())
      page["page_id"] = ref["page_id"]
      ents = offers.entities_from_page(page)
      by_word = {w: k for k, e in enumerate(ents) for w in range(e.start, e.end)}
      for group in ref["groups"]:
          keys = {by_word[w] for w in group if w in by_word}
          if not keys:
              continue
          total += 1
          multi += Counter(ents[k].type for k in keys).get("PRODUCT", 0) >= 2
  print(multi, total, multi / total)
  ```
- **Die mittlere Referenzgruppe hat 5,97 Entities, und Gruppen-F1 verlangt
  sie alle.** Das ist die Einordnung, die zu jeder Nennung gehört: Bei einer
  Entity-Trefferquote von 0.95 liegt exakte Gruppengleichheit rechnerisch
  bei 0.95^6 ≈ 0.74. Wer Gruppen-F1 0.66 als „zwei Drittel richtig" liest,
  hat die Metrik nicht verstanden – sie ist alles-oder-nichts über sechs
  Zuordnungen. Deshalb steht Paar-F1 immer daneben.
- **Literatureinordnung für die Gruppierung** (Recherche 29.08.2026, gegen
  die Papers geprüft). Zwei Zahlenräume, die man nicht verwechseln darf:
  *Relation Extraction auf FUNSD* – LiLT[InfoXLM] **0.6276**, LayoutXLM
  0.5483; XFUND über acht Sprachen 0.6781 / 0.6432 (arXiv:2202.13669,
  Table 6). Das ist Key-Value-Linking, also eine *einfachere* Relation als
  unsere Angebote, gegen eine *handannotierte* Referenz. Der Sprung auf
  0.8945 kam erst mit GeoLayoutLM und wird dort ausdrücklich dem
  relationsspezifischen Pretraining zugeschrieben (arXiv:2304.10759) – eine
  Zutat, die in einem Semester nicht nachgebaut wird.
  *Line Item Recognition auf DocILE* – Baselines F1 **0.594–0.721**
  (LayoutLMv3 0.721), und im ICDAR-2023-Wettbewerb blieb alles unter 0.80
  (arXiv:2302.05658; CEUR Vol-3497 paper-049).
  **Beim Vergleich die Metrik mitlesen:** DocILE-LIR ist micro-F1 über
  *Felder* unter maximalem Line-Item-Matching, zählt teilrichtige Zeilen
  also anteilig. Das ist deutlich nachsichtiger als unser `group_f1` mit
  exakter Mengengleichheit und liegt näher an unserem Paar-F1. Wer 0.778
  strikt neben 0.72 nachsichtig stellt, vergleicht zwei Protokolle – die
  Schema-Falle aus dem NER-Teil, nur in die andere Richtung.
- **Ein blanker Relationskopf auf LiLT ist deshalb nicht der nächste
  Schritt.** Die Architektur, die dabei entstünde, ist genau die mit 0.6276
  auf FUNSD. Was dem Paarmodell fehlt, ist trotzdem real: in den 35
  Merkmalen (`offer_pairs.py`) steckt **keine einzige lexikalische
  Information** – der belegte Legendenfall `1347387_p31` („④ Pflanztopf-Set
  … je Set 8.99") hängt an einem Textmarker, den kein Merkmal sieht. Der
  billige Weg dorthin sind eingefrorene LiLT-Span-Embeddings aus
  `checkpoints/lilt/best` als zusätzlicher Merkmalsblock: einmal je Seite
  vorrechnen und cachen, dann lernt nur der Kopf, der Messaufbau mit
  5 Folds bleibt unverändert und alles bleibt lokal. End-to-end hieße
  **fünf Fold-Finetunings je Gitterzelle** – die GPU bräuchte man dann für
  die *Messung*, nicht fürs Training. Erst messen, dann mieten.
  **Die Reihenfolge steht, die Erwartung ist gestiegen:** Diese Einordnung
  entstand, als die Decke auf 0.70–0.75 geschätzt wurde – ein Encoder hätte
  danach um wenige Punkte gekämpft. Mit der gemessenen Decke von 0.916 sind
  es rund 14, und der Fehlermodus, auf den ein Textencoder zielt, ist
  belegt. Verworfen ist damit nur der *direkte* Sprung zu end-to-end, nicht
  der Weg.
- **Der billige Weg dorthin ist gemessen und trägt nicht** (`magda
  offers-probe`, 29.08.2026, 30 Train-Cluster, Sonden-Test über 10
  Vorlagen, 43872 Paare). Eingefrorene, mittelgepoolte Span-Embeddings
  kosten Punkte, statt welche zu bringen – bei **beiden** Encodern und in
  jeder Kombination:

  | Merkmale | AUC (lilt) | Paar-F1 | AUC (gbert) | Paar-F1 |
  |---|---:|---:|---:|---:|
  | geometrie (35) | **0.965** | 0.779 | **0.965** | 0.779 |
  | +lexik (43) | 0.956 | **0.801** | 0.956 | **0.801** |
  | Embedding allein (1536) | 0.852 | 0.503 | 0.813 | 0.469 |
  | geometrie + Embedding | 0.962 | 0.773 | 0.959 | 0.746 |
  | alles | 0.961 | 0.764 | 0.958 | 0.741 |

  Dass **GBERT schlechter abschneidet als LiLT** widerlegt die naheliegende
  Erklärung „LiLT ist layout-aware, also redundant zur Geometrie" – der
  reine Textencoder ist noch schwächer. Eine Erklärung, die dazu passt und
  **ungeprüft** ist: Beide Encoder sind auf Token-Klassifikation
  feingetunt, ihr letzter Hidden State zeigt also Richtung Labelidentität –
  und der Entity-Typ steckt als One-Hot längst im Merkmalsvektor.
  **Was damit widerlegt ist und was nicht:** widerlegt ist der *billige*
  Weg – einmal vorrechnen, cachen, als Block anhängen. Nicht widerlegt ist
  end-to-end, wo die Repräsentation sich der Relationsaufgabe anpassen
  könnte; das ist die Architektur mit 0.6276 auf FUNSD und kostet fünf
  Fold-Finetunings je Gitterzelle. Der Spike stärkt also gerade das
  Argument, dass die Abkürzung das Finetuning nicht ersetzt.
  **Grenzen der Sonde:** kein Dekoder, gemessen wird Paar-F1 statt
  Gruppen-F1; 20 Trainings- und 10 Holdout-Vorlagen; eine Poolingvariante
  (Mittelwert) und eine Paarbildung (`[|Δ|, ⊙]`). Sie taugt für den
  Vergleich zweier Merkmalsmengen, nicht als Ersatz für `magda
  offers-grid`.
- **Der Rechner ist größer, als CLAUDE.md an einer Stelle behauptet.** Der
  Satz „auf einem 8-GB-Mac füllt LayoutXLM den Swap" begründet den
  RunPod-Weg; Noahs Maschine ist ein MacBook Air M2 mit **16 GB**, und
  `torch.backends.mps.is_available()` ist `True` (torch 2.13.0). `magda
  train` wählt kein Device und überlässt das dem HF-Trainer, der MPS von
  selbst nimmt. Entweder gilt der Satz für einen anderen Rechner im Team
  oder er ist veraltet – vor der nächsten GPU-Miete nachprüfen, statt ihn
  weiterzureichen.
- **Der ILP-Dekoder lief unter Rosetta, und das hat einen Messlauf
  gekostet.** Der Gitterlauf vom 29.08. wurde nach **14 h 55 ohne
  Ergebnis** abgebrochen. Ursache war nicht die Komponentengröße, sondern
  der Solver: PuLPs mitgeliefertes CBC ist ein **x86_64-Binary** und läuft
  auf dem M2 unter Rosetta, und `PULP_CBC_CMD` startet **je
  Schnittebenen-Runde einen neuen Prozess**, schreibt das Modell als MPS
  und liest es wieder ein – bei der beobachteten Instanz 1,9 MB pro Runde.
  Was wie „eine harte Instanz" aussah, waren vier *Runden* derselben
  93er-Komponente zu je 1,5 bis 2 Stunden.
  Gemessen an genau dieser Instanz (93 Entities, 4278 binäre Variablen,
  6772 nachgereichte Dreiecke): **HiGHS 96 s, CBC nach 900 s noch nicht
  fertig**, Zielwert beide Male 990.238714. Faktor also mindestens 9,4.
  `offer_ilp._solver()` nimmt jetzt HiGHS und fällt ohne highspy auf CBC
  zurück – gleiches Ergebnis, längerer Lauf. Der Wechsel ist methodisch
  folgenlos, das hält `test_beide_solver_finden_dasselbe_optimum` fest.
- **Komponenten dieser Größe sind der Normalfall, nicht der Ausreißer.**
  Ausgezählt über 40 Trainingsseiten, ohne Solver (die Komponentenbildung
  hängt nur an den Kantengewichten):

  | Schwelle | größte | >40 Entities | >80 |
  |---|---:|---:|---:|
  | 0.52 | 119 | 18 | 2 |
  | 0.68 (Arbeitsschwelle) | 118 | 12 | 1 |
  | 0.92 | 46 | 1 | 0 |

  Der Gitterlauf löst so etwas je Variante, Fold und Schwelle dutzendfach.
  **Das hängt direkt an `MAX_COMPONENT` 40 → 120:** Der Sprung hat
  Gruppen-F1 um 12 Punkte gehoben und zugleich genau diese 90- bis
  118er-Brocken ans ILP gegeben statt an Union-Find – dreifache Knotenzahl,
  neunfache Variablenzahl. Im Trainingslauf fiel das nicht auf, weil der
  einmal dekodiert statt über das ganze Raster. Die Konsequenz ist nicht,
  die Kappung zurückzudrehen, sondern das ILP für 120 Knoten tauglich zu
  halten.
- **Die Gruppierungsläufe sind single-threaded, und deshalb hilft RunPod
  dort nicht.** Gemessen am 29.08.2026: `magda offers-grid` und `magda
  offers-model train` belegen zusammen einen Kern von acht. Eine GPU ist
  gegenstandslos – die Zeit steckt im LP-Solver, nicht im Netz mit seinen
  4097 Parametern –, und mehr Kerne bringen ohne Parallelisierung nichts.
  *Korrektur vom 29.08.2026, später am Tag:* Hier stand „ohne
  CBC-Kindprozesse". Das ist falsch – PuLP ruft das CBC-Binary als eigenen
  Prozess auf (`pulp/solverdir/cbc/osx/i64/cbc`), und der trägt die Last,
  während der Python-Prozess bei 0 % wartet. Wer nur den Elternprozess
  misst, hält den Lauf für hängend. An der Schlussfolgerung ändert das
  nichts: ein Kern, ein Solver, keine Parallelität. Der Hebel wäre, die unabhängigen
  Varianten als eigene Prozesse zu starten (aus 7 Stunden werden ~100
  Minuten). **Was dem entgegensteht, ist kein technisches, sondern ein
  methodisches Problem:** `offer_grid.paired_bootstrap` braucht die
  seitenweisen Zählungen aller Varianten im selben Prozess, und getrennte
  Einzelintervalle sind genau die Aussage, die das Projekt nicht machen
  will. Lösbar, indem `per_page` mit in den Report geschrieben wird –
  der Bootstrap selbst kostet keine Rechenzeit.
- **Die Rechnung Menge × Grundpreis ist bewusst kein Merkmal des
  Paarmodells.** Sie ist das einzige Signal, das sich selbst beweist, und
  damit der einzige unbestechliche Richter. Als Eingabe gefüttert bewertete
  sie sich hinterher selbst – derselbe Zirkelschluss, gegen den
  `offers_report` die Ablation braucht. Das allgemeine Muster: halte das
  Merkmal zurück, mit dem du hinterher richten willst. Ein Test in
  `test_offer_pairs.py` hält das fest, indem er die Merkmalsnamen prüft.
- **Die Schwelle wird out-of-fold kalibriert, nicht geraten – und 0.5 ist
  grob falsch.** `pos_weight` gleicht die Schieflage aus (4553 positive
  gegen 46359 negative Paare) und schiebt dabei alle Wahrscheinlichkeiten
  nach oben: bei 0.5 entstanden 83 Gruppen statt 268, bei 0.94 dann 253.
  Kalibriert wird über 5 Folds auf Train, und die Folds gehen über ganze
  Duplikat-Cluster – sonst bewertet ein Fold-Modell eine Vorlage, die es in
  einer anderen Regionalfassung im Training hatte.
  **Die beiden Kriterien wählen verschiedene Schwellen**, und das war lange
  die interessantere Hälfte des Befunds: Paar-F1 war bei 0.98 maximal (0.740
  out-of-fold), aber Gruppen-F1 brach dort auf 0.175 bei 463 Angeboten ein.
  Paar-F1 belohnt Vorsicht, weil kleine Gruppen wenige Paare zu verlieren
  haben. Default ist deshalb `--objective group_f1` – die Zahl, die „die
  Zeile in der Datenbank stimmt" entspricht. **Offenlegung:** Diese Wahl
  fiel, nachdem beide Schwellen auf Dev gemessen waren; die Dev-Zahl ist
  dadurch leicht optimistisch. Der Testsplit ist unangetastet.
  **Mit `MAX_COMPONENT = 120` ist der Gegensatz weitgehend verschwunden**
  (Kalibrierung vom 29.08.2026, 494 Seiten, out-of-fold):

  | Schwelle | 0.52 | 0.60 | 0.68 | 0.76 | 0.84 | 0.92 | 0.96 |
  |---|---:|---:|---:|---:|---:|---:|---:|
  | Paar-F1 | 0.872 | 0.884 | 0.897 | 0.903 | 0.900 | 0.875 | 0.833 |
  | Gruppen-F1 | 0.678 | 0.684 | **0.689** | 0.677 | 0.645 | 0.563 | 0.433 |

  Beide Kriterien sind jetzt über eine breite Spanne gleichzeitig hoch, und
  Gruppen-F1 bildet zwischen 0.52 und 0.76 ein Plateau statt einer Spitze –
  die Schwellenwahl ist damit robust geworden, wo sie vorher 17 Punkte
  entschied. Das gekappte Bild (Paar-F1-Optimum bei 0.96 mit Gruppen-F1
  0.429 gegen Gruppen-Optimum bei 0.82 mit Paar-F1 0.518) war kein
  Eigenschaft der Metriken, sondern ein Artefakt der Notbremse.
- **Die Kette kostet fast nichts – gemessen am 29.08.2026 über 56 Dev-Seiten,
  beide Entity-Quellen gegen dieselbe Referenz.** `magda offers-model eval
  --predictions <modell>` berichtet die Kette jetzt in einem Stück
  (Entity-F1 → überlebende Referenzpaare → Paar-F1 → Gruppen-F1), weil
  jede Stufe den Nenner der nächsten verkleinert:

  | Entity-Quelle | Entity-F1 | Referenzpaare | Paar-F1 | Gruppen-F1 | Angebote |
  |---|---:|---:|---:|---:|---:|
  | sonnet-5 (Lehrer) | – | 7351 (1.000) | 0.929 | 0.778 | 429 |
  | layoutxlm | **0.932** | 7128 (0.970) | **0.932** | **0.782** | 427 |
  | gbert | 0.927 | 7026 (0.956) | 0.926 | 0.781 | 426 |

  **Der Befund ist die Flachheit der Spalte Gruppen-F1**: 0.778 auf
  Lehrer-Entities, 0.782 und 0.781 auf Schüler-Entities. Fehler der ersten
  Stufe pflanzen sich also *nicht* in die Qualität der zweiten fort – sie
  nehmen nur Aufgabe weg (3,0 % bzw. 4,4 % der Referenzpaare). Damit hat
  die „beste lokale Konfiguration" aus der Blackbox-Entscheidung erstmals
  eine Zahl: **LayoutXLM + Paarmodell = 0.932 / 0.782 auf Dev.**
  Zwei Nebenbefunde: LayoutXLMs Vorsprung bei den Entities (0.932 gegen
  0.927, überlebende Paare 0.970 gegen 0.956) passt zum gemessenen
  Bildgewinn und trägt bis in die Gruppierung durch. Und **die Heuristik
  verträgt Schüler-Entities schlecht** – ihr Gruppen-F1 fällt von 0.524 auf
  0.478 (layoutxlm) bzw. 0.457 (gbert), während das Paarmodell stabil
  bleibt. Die arithmetische Gegenprobe stützt die Reihenfolge: 0.912
  (Lehrer), 0.898 (layoutxlm), 0.878 (gbert) bei Abdeckung um 0.54.
  **Einschränkungen:** Dev stammt aus den Trainingswochen, die
  Entity-Qualität ist dort in-distribution-optimistisch; kein
  Konfidenzintervall; Richter ist ein LLM-Lehrer, gemessen wird
  Übereinstimmung. Und `data/eval/offers_model_dev_ilp.json` hieß bis
  heute unabhängig von der Entity-Quelle gleich – ein Lauf auf
  Vorhersagen überschrieb den auf Lehrer-Entities. Jetzt trägt der Name
  ein `_pred-<modell>`.
- **Die Kette ist erstmals ende-zu-ende gemessen – und die Zahl steigt, weil
  das Problem schrumpft.** *(Erstbefund vom 10.08.2026, überholt durch den
  Absatz darüber: 21 Dev-Seiten, alter Split, 51 Referenzseiten. Die
  Warnung vor dem Nenner gilt unverändert und ist der Grund, warum die
  Kette heute mitberichtet wird.)* Bis zum 10.08.2026 war das unmöglich:
  `data/predictions/gbert` hatte 101 Seiten (alle Test),
  `data/offer_groups/claude-sonnet-5` 51 (alle Train/Dev), **Schnittmenge
  null**. Nach `magda predict gbert --split dev` treffen sich beide auf 21
  Seiten. Gemessen mit `magda offers-grid --predictions gbert
  --train-labels-from sonnet-5` (das Paarmodell lernt an Lehrer-Entities,
  weil nur die gruppiert sind, und arbeitet auf denen des Schülers – der
  Einsatzfall):

  | Entities | Basis | +Geometrie | +Farbe | beide |
  |---|---|---|---|---|
  | Lehrer (sonnet-5) | 0.477 | 0.540 | 0.472 | 0.492 |
  | Schüler (gbert) | 0.504 | 0.556 | 0.504 | 0.502 |

  **Die zweite Zeile ist nicht besser, sie ist auf einem kleineren Nenner
  gemessen.** GBERT findet 717 statt 730 Entities (0.982), aber nur **1855
  der 1996 Referenzpaare** überleben (0.929) – 7,1 % der Gruppierungsaufgabe
  verschwinden, und zwar die Paare, deren Entity der Schüler nicht gefunden
  hat. Die Regel aus `offers-gold` („die Entity-Grundmenge kommt aus der
  Seite, nicht aus der Systemausgabe") greift hier nicht, weil die *Seite*
  in diesem Lauf die Vorhersagedatei ist. Wer die +0.027 als Verbesserung
  liest, hat den Nenner nicht angesehen.
  **Was die Zahl trägt:** Die Gruppierung bricht mit Schüler-Entities nicht
  zusammen. Die Zahl der Referenzgruppen bleibt bei 122, das Verfahren
  bildet 136 statt 138 Angebote, und Stufe 1 → Stufe 2 kostet auf Dev
  weniger als das Konfidenzintervall breit ist. Mehr sagt sie nicht –
  **Dev stammt aus den Trainingswochen, die Entity-Qualität ist dort
  in-distribution-optimistisch, die Zahl ist eine Obergrenze.**
- **Im blinden Fleck liegt die Farbe vorn – auf beiden Entity-Quellen.**
  Über alle Paare ist zwischen den Varianten nichts zu unterscheiden. Im
  Bereich ohne Grundpreis, für den die Farbmerkmale gebaut wurden, ist
  `beide` (39 Merkmale) dagegen zweimal die beste Variante: Paar-F1 0.782
  gegen 0.737 der Basis auf Lehrer-Entities, 0.740 gegen 0.640 auf
  Vorhersagen, bei jeweils den wenigsten gebildeten Angeboten (48 bzw. 43).
  **Das ist kein Befund, und drei Gegenrechnungen machen es noch schwächer**
  (Review vom 11.08.2026): Die beiden Quellen sind *nicht* unabhängig – GBERT
  ist auf sonnet-5 trainiert, 98 % der Entities und 93 % der Referenzpaare
  sind dieselben. Die beiden Zeilen messen *nicht dieselbe Aufgabe* – die
  Einteilung blind/prüfbar hängt an den Entity-Typen der jeweiligen Quelle,
  und die blinden Referenzpaare fallen von 606 auf 444 (−27 %), während die
  prüfbaren steigen. Und die Paar-Precision ist im blinden Fleck in **allen
  acht Zellen exakt 1.000**: die Unterschiede sind reiner Recall, „Farbe
  findet die richtige Kachel" und „Farbe macht das Verschmelzen mutiger"
  sind damit nicht unterscheidbar. Dazu Intervalle bis 1.000, weil viele der
  14 Dev-Cluster dort gar keine Paare haben. Die Konsequenz bleibt: größere
  Referenz, nicht der nächste Merkmalsblock.
  **Nebenbefund für alle künftigen Blind-Auswertungen:**
  `test_blind_haengt_an_der_referenz_nicht_an_der_vorhersage` prüft die
  falsche Invarianz – es variiert nur die Gruppierung, nie die Typquelle.
  Die Eigenschaft, die sein Name behauptet, schützt es nicht.
- **Der Label-Default zeigte auf ein Modell, mit dem hier gar nicht gelabelt
  wird.** `config.default_labeled_model()` gab `CHAT_AI_VISION_MODEL` den
  Vorrang und lieferte damit `mistral-medium-3.5-128b`. Jeder Befehl ohne
  `--labels-from` maß also gegen Mistral-Labels, und man sah es nur, wenn man
  die Kopfzeile las. Beziffert am 11.08.2026: über *dieselbe* Gruppierung
  fand `magda offers-verify` mit Mistral-Labels **399** Preise (Genauigkeit
  0.927, Abdeckung 0.446), mit sonnet-5 dagegen **494** (0.936, 0.478). Ein
  Viertel mehr Preise bei gleicher Rechnung – die Zahl beantwortete leise
  eine andere Frage. Über die Ordnergröße allein wäre es auch nicht
  gutgegangen: `sonnet-5`, `sonnet-5-app` und der Mistral-Ordner hatten alle
  296 Seiten, dann entscheidet die Sortierreihenfolge. Vorrang hat jetzt
  `config.CANONICAL_LABELS`. (Seit dem 24.08.2026 gibt es die beiden anderen
  Ordner nicht mehr – `sonnet-5-app` ist in `sonnet-5` aufgegangen, Mistral
  liegt im Archiv. Der Befund bleibt trotzdem stehen: er begründet, warum
  der Default nicht an der Ordnergröße hängen darf.) **Ältere Zahlen aus Befehlen ohne
  `--labels-from` stehen unter diesem Vorbehalt** – wer eine davon
  weiterverwendet, rechnet sie besser nach.
- **„Mehr Referenz" war die halb falsche Antwort auf die breiten
  Intervalle.** Gemessen wurde auf **Dev**, und Dev hat 21 Seiten in 14
  Duplikat-Clustern – *alle* davon längst gruppiert. Die Breite eines
  Bootstrap-Intervalls hängt an der Zahl der Auswertungs-Cluster; keine
  weitere *Trainings*seite ändert daran etwas. Das naheliegende Ziel „Dev auf
  25–30 Seiten ausbauen" war nicht schwer, sondern **unmöglich**.
  Der Ausweg ist kein Datenproblem, sondern der Messaufbau: `magda
  offers-grid --cross-validate` wertet jede Referenzseite einmal aus, mit
  einem Modell, das sie nicht gesehen hat. Aus 14 Clustern werden 68. Die
  Schwelle wird dabei **geschachtelt** gewählt – `calibrate` auf den inneren
  Folds, Auswertung nur auf dem äußeren. Einmal auf allem gewählt wäre sie
  bequemer und genau der Zirkelschluss, gegen den `offers_report` die
  Ablation braucht: eine Schwelle ist ein Freiheitsgrad wie jeder andere.
  Die Referenz ist trotzdem gewachsen (51 → 75 Seiten, Train 30 → 54) – das
  hilft dem *Training* des Paarmodells, nur eben nicht dem Intervall.
- **Zwei überlappende Einzelintervalle heißen nicht „kein Unterschied".**
  Beide Varianten sehen dieselben Seiten; ist eine Seite schwer, ist sie es
  für beide. Wer sie einzeln resampelt, zählt diese gemeinsame Streuung
  zweimal und verdeckt genau den Effekt, den er messen will.
  `offer_grid.paired_bootstrap` bootstrappt deshalb die **Differenz** –
  dieselbe Konstruktion wie `magda significance`, nur über Duplikat-Cluster.
  Kostet keine Rechenzeit: die seitenweisen Zählungen aller Varianten liegen
  im selben Lauf ohnehin vor.
- **Die Kontextmerkmale wirken, die Farbmerkmale nicht** (11.08.2026, 75
  Seiten in 68 Clustern, out-of-fold, gepaart gegen die Basis, Gruppen-F1):

  | Variante | Bereich | Differenz | Intervall | p |
  |---|---|---:|---|---:|
  | +Geometrie | alle Paare | **+0.044** | [+0.009, +0.082] | **0.018** |
  | +Geometrie | prüfbar | +0.052 | [+0.002, +0.099] | 0.042 |
  | +Farbe | alle Paare | −0.008 | [−0.036, +0.023] | 0.596 |
  | +Farbe | blinder Fleck | −0.007 | [−0.043, +0.032] | 0.684 |
  | beide | blinder Fleck | **−0.051** | [−0.103, −0.001] | 0.042 |

  „+Geometrie schlägt Basis" ist damit zum ersten Mal ein Befund. Die
  **Farbmerkmale sind einer in die andere Richtung**: sie bringen nichts und
  verschlechtern das Ergebnis auf der Geometrie obendrauf im blinden Fleck –
  also genau dort, wofür sie gebaut wurden. Der frühere Dev-Eindruck (`beide`
  im blinden Fleck vorn) **dreht sich um**, sobald über 68 statt 14 Cluster
  und gepaart gerechnet wird.
  **Einschränkungen:** neun Vergleiche ohne Korrektur für multiples Testen,
  und die drei Bereiche sind nicht unabhängig (alle Paare = blind + prüfbar).
  Belastbar ist die stärkste Zahl (p = 0.018); die beiden bei p = 0.042 sind
  Hinweise. Richter bleibt ein LLM-Lehrer, gemessen wird Übereinstimmung.
  Ob die Farbmerkmale bleiben oder fallen, ist eine Teamentscheidung – nicht
  vertretbar wäre nur, sie mitzuführen und dabei die alte Dev-Zahl zu zitieren.
  **Überholt am 30.08.2026** – siehe den nächsten Punkt. Der Lauf dort misst
  über 494 statt 54 Trainingsseiten, mit `MAX_COMPONENT = 120` statt 40 und
  auf Dev statt out-of-fold. Drei Änderungen auf einmal, die Zahlen sind
  deshalb nicht direkt vergleichbar; die Farbmerkmale drehen darin ihr
  Vorzeichen.
- **Der Lexikblock ist der größte Merkmalsgewinn des Projekts – und er sitzt
  ganz im blinden Fleck** (30.08.2026, 7 Varianten in einem Prozess, 6 h 19
  Rechenzeit, Training auf 494 Seiten, Messung auf 56 Dev-Seiten in 25
  Duplikat-Clustern, ILP, Schwelle je Variante out-of-fold auf `group_f1`
  kalibriert; `data/eval/offers_grid_dev_ilp.json`):

  | Variante | Merkmale | Paar-F1 | Gruppen-F1 | Angebote | Differenz gegen `basis` | p |
  |---|---:|---:|---:|---:|---|---:|
  | basis | 30 | 0.918 | 0.702 | 453 | – | – |
  | geometrie | 35 | 0.929 | 0.778 | 429 | +0.076 [+0.028, +0.142] | 0.000 |
  | farbe | 34 | 0.933 | 0.745 | 450 | +0.044 [+0.013, +0.075] | 0.008 |
  | beide | 39 | 0.935 | 0.798 | 430 | +0.096 [+0.036, +0.167] | 0.000 |
  | anker | 38 | 0.943 | 0.783 | 423 | +0.082 [+0.016, +0.148] | 0.010 |
  | **lexik** | 43 | 0.941 | **0.821** | 431 | **+0.119 [+0.058, +0.184]** | 0.000 |
  | anker+lexik | 46 | 0.929 | 0.778 | 424 | +0.076 [+0.033, +0.128] | 0.000 |

  **Der ganze Effekt liegt dort, wo die Rechnung schweigt.** Im blinden Fleck
  hebt `lexik` Gruppen-F1 von 0.478 auf **0.709** (+0.232 [+0.136, +0.375],
  p = 0.000); im prüfbaren Bereich ist **kein einziger** der sechs
  Vergleiche signifikant (p 0.056 bis 0.574). Das ist kein Widerspruch,
  sondern die Bestätigung der Arbeitsteilung: wo ein Grundpreis steht,
  reicht die Geometrie schon.
  **Drei Nebenbefunde:** Der Anker bringt auf der Geometrie nichts (0.783
  gegen 0.778) und **schadet auf dem Lexikblock obendrauf** (`anker+lexik`
  0.778 gegen `lexik` 0.821) – beide Blöcke lesen „Aktion", der Anker ist
  darin schon enthalten. Die Farbmerkmale drehen ihr Vorzeichen gegen den
  11.08.-Lauf (+0.044 statt −0.008), was aber durch drei gleichzeitige
  Änderungen konfundiert ist und unter Bonferroni nicht hält. Und **keine
  einzige Komponente wurde gekappt** (`capped: 0` in allen sieben
  Varianten) – die 120 halten.
  **Einschränkungen:** 18 Vergleiche ohne Korrektur für multiples Testen,
  und die drei Bereiche sind nicht unabhängig (alle Paare = blind +
  prüfbar). Bei Bonferroni (0.05/18) fallen `farbe` (0.008 / 0.012) und
  `anker` gesamt (0.010) heraus; belastbar sind `geometrie`, `beide`,
  `lexik` und `anker+lexik`. **Differenzen zwischen zwei Varianten haben
  kein Intervall** – der gepaarte Bootstrap läuft nur gegen `basis`, weil
  `per_page` nicht im Report steht. 25 Cluster, ein Lauf, keine
  Seed-Streuung; Dev stammt aus den Trainingswochen, ist also
  in-distribution-optimistisch. Richter bleibt ein LLM-Lehrer, gemessen
  wird Übereinstimmung. Gegen die gemessene Decke (0.916) bleiben von
  0.821 noch **9,5 Punkte**.
- **Bis zum 29.08.2026 las kein einziges Merkmal des Paarmodells den Text.**
  Die 35 Merkmale in `offer_pairs.py` kennen Lage, Typ, Farbe und
  Nachbarschaft – kein Wort. Dabei trägt der Textlayer die Struktur der
  Kachel offen, und zwar in Wörtern, die als `O` durchs Labeling fallen:
  ausgezählt über die 494 Trainingsseiten tragen von 7411 Preisen **2033
  eine Mengenaktion** („je", „statt", „nur") und **2029 eine Einheit**
  („Stück", „Set") in den drei Wörtern davor, **1117 ein „Aktion"** in den
  zwei davor; dazu 1733 Treffer auf Wörtern des Kleingedruckten und 772
  „oder". Der neue Block `lexical` (acht binäre Merkmale) macht daraus
  Eingabe: vier `_before`-Merkmale binden, zwei `_between`-Merkmale
  trennen. Messbar als Varianten `lexik` und `anker+lexik` in `magda
  offers-grid`. **Gemessen am 30.08.2026: der größte Merkmalsgewinn des
  Projekts** (+0.119 Gruppen-F1, siehe oben).
- **Die Legendennummer steht im Textlayer und ist trotzdem kein Merkmal
  geworden.** Auf `1347387_p31` liegen die Ziffern 1–5 als eigene
  Textläufe am Seitenanfang und -ende, ihre Boxen sitzen aber an den
  Kacheln – in Lesereihenfolge unerreichbar weit weg, über die Box genau
  am Angebot. In zwei Größen: eine schmale Legendenspalte am linken Rand
  (Höhe 8,4) und Badges auf den Produktfotos (Höhe 13,3). Über den
  Mittelpunktsabstand zugeordnet entscheidet ein Gleichstand:
  „Pflanztopf-Set" liegt 29,6 von seiner „4" entfernt, sein Preis „8.99"
  liegt 29,0 von der „5" des Nachbarangebots – das Merkmal bekäme genau
  den belegten Fall falsch, für den es gebaut war. Deshalb entfernt statt
  mitgeführt. Wer es wieder aufnimmt, braucht eine **gerichtete**
  Zuordnung (die Nummer steht *vor* ihrem Eintrag), nicht den Abstand.
- **Clusterweise ziehen heißt nicht automatisch fair ziehen.**
  `dataset.subset_by_clusters` sortierte zuerst nach absteigender
  Clustergröße – naheliegend und genau falschherum: die Duplikate landen
  dann zuerst im Budget. Auf den 175 Trainingsseiten (93 Cluster) ergab die
  Grenze 25 damit **23 Seiten aus drei Vorlagen**, also genau das, was
  clusterweises Ziehen verhindern soll. Nach `page_id` sortiert sind es
  9/16/50/93 Cluster statt 3/9/25/93. Zu jedem Kurvenpunkt gehört die
  **Clusterzahl** – „p25" allein ist eine Seitenzahl ohne das, woran
  gemessen wurde.
- **`checkpoints/*.kw32-split` sind die eingefrorenen Stände der Testwoche
  KW32** (umbenannt am 25.08.2026, als KW35 Testwoche wurde). Ein Checkpoint
  ohne den Split, gegen den er gemessen wurde, ist eine Zahl ohne Fußnote –
  und `checkpoint_name()` kennt den Split nicht als Dimension, hätte sie also
  beim kanonischen Retrain überschrieben. Dasselbe gilt für
  `data/predictions/*.kw32-split/`.
- **`data/eval/` und `data/predictions/` sind Archive, keine Abbilder des
  aktuellen Splits.** Beide Leser mussten das lernen, und beide Fehler waren
  unsichtbar: `magda significance` nahm die Schnittmenge zweier
  Vorhersageordner und verglich dadurch über 216 statt 116 Seiten, 100 davon
  inzwischen Trainingsdaten (`shared_test_pages` schränkt jetzt auf den
  Testsplit ein und meldet die Verworfenen). Die Evaluationsseite fand drei
  Reports mit `variant: "gbert"` – einen Testlauf und zwei Dev-Läufe eines
  früheren Splits – und ließ die Dateisortierung entscheiden, welcher die
  Spalte füllt (`reportsOfOneSplit`). Wer einen neuen Leser über diese Ordner
  baut, filtert zuerst.
- **Ein Report kann `variant` und `report` tragen und trotzdem nicht
  vergleichbar sein.** `flair_llm_test.json` kommt durch die Formprüfung von
  `/api/evaluation`, misst aber nur BRAND (micro-F1 0.281 über 24 Instanzen).
  Neben den vier Armen gelesen wäre das ein katastrophal schlechtes Modell
  statt einer anderen Frage. Marker ist `restricted_to`; die Seite nennt
  solche Arme, stellt sie aber nicht in die Tabelle.
- **Das RunPod-Image bringt kein torchvision mehr mit** (geprüft 25.08.2026,
  `pytorch:1.0.3-cu1281-torch291`). detectron2 übersetzt und importiert sich
  trotzdem – erst `detectron2.layers` zieht torchvision, und das passiert im
  Trainer. Der Ausfall kommt also nach dem Aufsetzen und mitten in der
  Mietzeit. Beim Nachinstallieren die torch-Version pinnen: ein blankes
  `pip install torchvision` zog torch von 2.9.1 auf 2.11.0 und brach die ABI,
  gegen die detectron2 übersetzt war – wieder ohne Fehler beim Import.
  `bundle.py` installiert es jetzt vorab und prüft mit
  `import detectron2.modeling`.
- **`checkpoints/gbert` war der eingefrorene KW30/31-Stand, und bis zum
  10.08.2026 hätte ihn jeder Nebenlauf überschrieben.** `magda train`
  schrieb nach `CHECKPOINTS_DIR / variant`, ohne Rücksicht auf
  `--labels-from`. Ein APP_PRICE-Nachtraining hätte damit genau das Modell
  gelöscht, gegen das es verglichen werden soll, und jeder Punkt einer
  Lernkurve den vorigen. Jetzt vergibt `cli/train.checkpoint_name()` eigene
  Ordner (`gbert-sonnet-5-app`, `gbert-p50`); `magda eval` und `magda
  predict` erreichen sie über `--checkpoint`. Anker für „der kanonische
  Lauf" ist `config.CANONICAL_LABELS` (= `sonnet-5`), **nicht**
  `default_labeled_model()` – das folgt `CHAT_AI_VISION_MODEL` und liefert
  `mistral-medium-3.5-128b`, also ein Modell, mit dem hier gar nicht
  gelabelt wird. Sonst hätte der Inhalt einer `.env` Namensgewalt über
  Checkpoints, an denen berichtete Zahlen hängen.
- **`test_hilfe_laedt_keine_schweren_module` hat torch aus `sys.modules`
  genommen und nicht zurückgestellt.** Ein zweiter echter Import registriert
  dieselben C-Extensions erneut und stirbt an „Only a single TORCH_LIBRARY
  can be used to register the namespace triton". Aufgefallen ist es erst,
  als mit `test_offer_model.py` der erste Test *nach* `test_cli.py` torch
  benutzte – elf Fehlschläge, die einzeln alle grün waren. Wer Module aus
  `sys.modules` nimmt, stellt sie im `finally` zurück.
- **Der Legenden-Pfad kostet ~115 Zeilen und greift auf einer Seitenvorlage.**
  `_segment_legend` zerlegt in `data/labeled/sonnet-5/` 3 von 162 Seiten, in
  `data/predictions/gbert/` 6 von 66 – und dort ausschließlich auf `_p30`,
  also einer Vorlage in mehreren Regionalfassungen. Kein Grund, ihn zu
  entfernen; er löst eine Layout-Klasse, die weder Nähe noch Arithmetik
  können. Aber wer ihn anfasst, sollte wissen, wie schmal die Basis ist.
  Dazu: `_reading_order_groups` nennt `1351497_p28` als belegten Fall, doch
  dort liefert `_segment_legend` `None` – der Code läuft auf dieser Seite gar
  nicht, weder mit sonnet-5-Labels noch mit den gbert-Vorhersagen. Der
  Regressionstest sitzt deshalb auf `1351518_p30`.
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
  **Die Übernahme ist am 24.08.2026 erfolgt** (Entscheidung Noah), mit
  `magda audit-apply APP_PRICE --labels-from sonnet-5 --target …` und einem
  eigenen Commit. 81 Spans von PRICE nach APP_PRICE, 292 Urteile bestätigt,
  eines ohne Zielabel (`1342881_p31:165`, die Aufzählungsziffer – das alte
  Label bleibt stehen, ein Ersatz wäre geraten). Danach je Split: **train
  187, dev 20, test 98** – der Test ändert sich um keinen einzigen Span,
  also bleiben alle berichteten Testzahlen gültig.

  **Nachgerechnet auf Dev, und erstmals als echter Vergleich** (24.08.2026,
  beide Checkpoints gegen *dieselbe* korrigierte Referenz, n = 20 in beiden
  Zellen – die frühere Tabelle maß jeden Arm gegen seine eigene Referenz und
  verglich damit zwei verschiedene Fragen):

  | Checkpoint | micro-F1 | APP_PRICE | P | R |
  |---|---:|---:|---:|---:|
  | `gbert` (auf der alten Referenz gelernt) | 0.914 | 0.645 | 0.909 | 0.500 |
  | `gbert-sonnet-5-app` (auf der korrigierten) | 0.927 | 0.947 | 1.000 | 0.900 |

  Die Differenz ist fast reiner **Recall**: 0.500 gegen 0.900. Das Modell mit
  den 72 zusätzlichen Trainingsbeispielen findet die App-Preise, das alte
  übersieht die Hälfte. Damit ist auch beziffert, was `checkpoints/gbert`
  jetzt ist – ein Checkpoint, der zu seiner Referenz nicht mehr passt. Ein
  Retraining ist fällig, bleibt aber eine bewusste Weiche (siehe
  Branch-Workflow); die 0.914 ist keine Aussage über die Referenz, sondern
  über einen veralteten Checkpoint.

  **Einschränkung:** 21 Dev-Seiten in 14 Clustern, kein Konfidenzintervall,
  und `gbert-sonnet-5-app` ist auf 296 Seiten trainiert, kennt KW33 also
  nicht – wie `gbert` auch, deshalb sind die beiden untereinander
  vergleichbar. Der Ordnername des Checkpoints verweist auf `sonnet-5-app`,
  den es seit heute nicht mehr gibt; der Inhalt ist unverändert.

  **Und KW33 brauchte die Korrektur nicht.** `label_audit.collect` über alle
  422 Seiten findet dort 134 bereits gelabelte APP_PRICE und **null** PRICE
  auf App-Grund – genau den Fehlermodus, der in KW30–32 81-mal auftrat. Die
  sechs übrigen Kandidaten sind OLD_PRICE, und dafür hat die Handprüfung
  67 von 67 bestätigt. Zwischen den Wochen entsteht also keine
  Konventionslücke; das war die Bedingung, unter der die Übernahme
  überhaupt vertretbar war.

  Weg B (dem Modell die Farbe als Merkmal geben) ist davon unberührt und
  bleibt offen.
- **Sortenangaben und Gebinde-Komposita** (`50-ml-Fläschchen`, `0,33-l-Dose`,
  `1-l-Sonderedition`): unverändert offen, und mit 106 von 135 PRODUCT-Fehlern
  jetzt beziffert. Prüfen per Auszählung je Wortlaut über den Korpus, nicht
  seitenweise.
- **Sliding Window auch im Training?** In der Inferenz ist es drin und bringt
  +1,7 Punkte gegen die volle Referenz. Im Training wäre es Augmentierung, kein
  Messfehler – also eine Abwägung, keine Korrektur. Bisher bewusst nicht getan,
  damit Trainingssignal und Checkpoint-Auswahl unverändert bleiben.
- ~~**LiLT als dritter Arm?**~~ **Entschieden am 25.08.2026 (Noah): ja, und
  dazu `xlmr` als vierter Arm.** Ohne den vierten wäre die Kette lückenhaft
  geblieben – LiLT gegen GBERT hätte weiterhin zwei Unterschiede auf einmal
  gemessen. Ergebnis oben unter „Layout bringt nichts, das Seitenbild bringt
  etwas". Die Abweichung vom Proposal ist bewusst und gehört in den Bericht.
- **Weitere Label – aufgekommen, weil das Zusammensetzen der Angebote hakt**
  (Frage von Bogdan und Kjell, 03.08.2026). Die Messung dazu steht oben; sie
  sagt vor allem, was ein neues Label **nicht** leistet: das Clustern löst es
  nicht, dafür bräuchte es die OFFER-Sequenz. Von den vier Kandidaten unten
  wirkt nur `LEGAL` überhaupt aufs Gruppieren, und auch nur durch Ausschluss.
  `PROMO`, `DEPOSIT` und `ORIGIN` sitzen alle schon direkt neben dem Wort, zu
  dem sie gehören (Pfand am Preis, `je` am Preis, Herkunft am Produkt) – ihr
  räumliches Zuordnungsproblem existiert gar nicht. Sie verbessern die
  Vollständigkeit eines bereits korrekt gruppierten Angebots, lösen aber nicht,
  warum das Gruppieren heute hakt. Unabhängig davon lohnen sich vier
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
- **OFFER als zweite Tag-Folge?** Ist ein zusätzlicher Modellkopf, kein
  weiteres Label, und weicht vom Proposal ab → Teamentscheidung. Der
  Machbarkeitstest ist inzwischen gelaufen und fällt **zweigeteilt** aus
  (siehe oben): Eine flache Folge fasst die *Beschreibung* zu 0.959, das
  vollständige Angebot samt Preis nur zu 0.678. Wer den Preis mit
  hineinnehmen will, braucht paarweise Relationsklassifikation – oder behält
  den bestehenden zweistufigen Weg, in dem `_match_badges` den Preis
  nachträglich zuordnet. Letzteres ist naheliegender, als es klingt: Die
  Architektur von `offers.py` trennt heute schon aus genau diesem Grund
  Beschreibungsblöcke von Preis-Badges.

  **Einordnung (Literaturrecherche 06.08.2026).** Das Problem heißt in der
  Fachliteratur *Line Item Recognition* und ist der Kern des DocILE-Benchmarks
  (ICDAR 2023, arXiv:2302.05658): Felder zu Tupeln je Objektinstanz gruppieren.
  Ein Angebot ist ein Line Item mit Kachel- statt Tabellengeometrie. DocILE
  kennt dafür zwei Standardlösungen, und eine davon ist **genau die
  OFFER-Tag-Folge** – sie ist also kein Sonderweg. Die zweite ist paarweise
  Relationsklassifikation im FUNSD-Stil (LiLT arXiv:2202.13669, GeoLayoutLM
  arXiv:2304.10759, SPADE arXiv:2005.00642). Wichtig für die Aufwandsfrage:
  **FUNSD trainiert mit 149 Dokumenten** – die Sorge, 196 Seiten seien zu
  wenig, ist literaturseitig unbegründet.

  **Vorgeschlagene Reihenfolge, falls das Team zustimmt:**
  1. *Gruppierungsreferenz von Hand*, 30–50 Seiten aus Train/Dev, clusterweise
     gezogen (`magda queue`-Logik), Non-Food überrepräsentiert. Der einzige
     Schritt ohne Alternative – ohne ihn ist keine Variante messbar, auch die
     jetzige Heuristik nicht. Format: `offer_id` je Gold-Span, mit
     `words_hash` abgesichert wie in `gold/`.
  2. *Vision-LLM als Gruppierungs-Teacher*: der Labeling-Prompt gibt Spans
     künftig gruppiert aus, gemessen gegen die Referenz wie `magda gold` fürs
     Labeling. Das ist zugleich der geforderte Machbarkeitstest vor der
     GPU-Miete. Als **Teacher** richtig, als Deployment falsch – 44,8 s gegen
     0,264 s je Seite ist die Projektfrage selbst.
  3. *OFFER-Kopf auf GBERT.* Paarweise Relationsklassifikation nur als Ausbau,
     falls die Referenz zeigt, dass die 7,3 % nicht zusammenhängenden Gruppen
     den Feldwert spürbar deckeln.
     **Schritt 3 ist teilweise erledigt, aber anders als geplant:** gebaut ist
     die paarweise Klassifikation (`magda offers-model`), und zwar
     *eigenständig* auf Merkmalen statt als Kopf auf GBERTs Embeddings. Sie
     schlägt die Heuristik auf Dev (Gruppen-F1 0.477 gegen 0.436). Was das
     Modell nicht bekommt, ist die Bildinformation – und genau dort sitzt der
     gemessene blinde Fleck. Der naheliegende nächste Schritt ist deshalb
     nicht ein größeres Netz, sondern **Farbmerkmale je Paar**: Hintergrund
     an beiden Wortpositionen und der Farbwechsel dazwischen, analog zu
     `label_audit.APP_BACKGROUND`, das bei der App-Preis-Prüfung 97,6 %
     traf. Vier Zahlen statt eines visuellen Backbones – und LayoutXLM hat
     gezeigt, dass ein Backbone über die ganze Seite hier nichts bringt.
  4. *Arithmetik und positionsweise Variantenpaarung bleiben als harte
     Nachprüfung* über jeder gelernten Gruppierung. Sie sind das einzige
     Signal im System, das sich selbst beweist.

  Als Metriken sind üblich: Paar-F1 über Entity-Paare („gleiches Angebot")
  als Primärzahl, dazu Feld-F1 unter Gruppen-Matching im DocILE-Protokoll –
  das ist die Zahl, die „Zeile in der Datenbank stimmt" entspricht. Test
  einmal am Ende, je eine Seite pro der 43 unabhängigen Cluster.
- **`Aktion` als möglicher Anker für den Angebots-Beginn – kostet kein
  Relabeling.** Ausgezählt über `data/labeled/sonnet-5/` (Erstbefund
  03.08.2026 über 296 Seiten mit 755/656, nachgerechnet am 24.08.2026 über
  alle 422): das Wort steht **1142-mal als `O` auf 316 Seiten**, und in **968
  der 1142 Fälle (84,8 %)** folgt direkt ein `B-PRICE`. Anders als
  `PROMO`/`DEPOSIT`/`ORIGIN` trägt es vermutlich keine verlorene Information –
  es markiert nur, dass gleich ein neuer Preisblock beginnt. Damit kein
  Kandidat für `ENTITY_TYPES`, aber ein möglicher textueller Signalgeber
  für `offers.py`, robuster als Boxabstand und ohne LLM-Zeit zu kosten, weil
  die Information schon in den bestehenden O-Tags steckt. Ungeprüft: ob das
  über die 43 Test-Cluster hinweg tatsächlich zuverlässiger trennt als die
  18,5-%-Distanzheuristik. Nachzählen ohne eigenes Kommando:

  ```python
  import json
  from magda import config
  total = vor_preis = 0
  for path in sorted(config.labeled_dir("sonnet-5").glob("*.json")):
      payload = json.loads(path.read_text())
      words, tags = payload["words"], payload["tags"]
      for i, (word, tag) in enumerate(zip(words, tags)):
          if word["text"].strip().rstrip(":").lower() == "aktion" and tag == "O":
              total += 1
              vor_preis += i + 1 < len(tags) and tags[i + 1] == "B-PRICE"
  print(total, vor_preis)
  ```
- **Gerichtete Relationen statt „gehören zusammen"?** Vorschlag von außen
  (29.08.2026), noch nicht gebaut. Heute lernt das Paarmodell eine
  *symmetrische* Frage: gehören i und j zum selben Angebot? Gerichtet
  gestellt – PRODUCT → PRICE, QUANTITY → PRICE, BRAND → PRODUCT – ist die
  Aufgabe womöglich leichter, weil BRAND und VALID nicht direkt aufeinander
  zeigen müssen, sondern beide auf dieselbe Mitte. Der Haken sitzt in der
  Ableitung: um eine gerichtete Zielgröße aus `data/offer_groups/` zu
  gewinnen, braucht jede Referenzgruppe einen Kopf – und **982 von 5491
  Gruppen (17,9 %) haben zwei oder mehr PRODUCT**. Der Kopf ist damit selbst
  eine Modellierungsentscheidung, kein Datum. Als *hartes* Constraint im ILP
  ist dieselbe Zahl schon der Widerlegungsgrund (siehe oben); als weiche
  gerichtete Relation ist die Frage offen. Entscheidung steht aus.
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
