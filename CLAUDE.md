# CLAUDE.md

Semesterprojekt *Information Extraction* (SoSe 2026), Leuphana.
Team: Bogdan Roth, Kjell Lavezzari, Noah Samel.

Wir extrahieren strukturierte Angebotsdaten aus deutschen Supermarkt-Prospekten
(Penny). Ein LLM labelt die Trainingsdaten automatisch, trainiert wird ein
eigenes layout-aware Modell. Grundlage ist `docs/proposal/IE_ProjectProposal_Magda.pdf`.

Ausführliche Erklärung der Pipeline: `EXPLANATION.md` (lokal, nicht im Repo).

## Struktur

```
magda/       Kern-Package – hier liegt die Logik
scripts/     nummerierte Pipeline-Schritte, dünne CLI-Wrapper um magda/
tests/       pytest (Labels, Alignment)
data/        lokal, gitignored (nur .gitkeep versioniert)
checkpoints/ lokal, gitignored
docs/        Proposal
```

Pipeline: `01_download_flyers` → `02_extract_words` → `03_label_words` →
`04_train` → `05_evaluate`. Jeder Schritt liest vom Vorgänger über die Platte,
nichts läuft im Speicher durch.

## Kommandos

```bash
pytest                                   # Tests
python scripts/02_extract_words.py       # Schritt ausführen (aus dem Projektroot)
python scripts/04_train.py layoutxlm     # bzw. gbert
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

Getestet am 23.07.2026: von 16 Modellen nehmen nur `gemma-4-31b-it`,
`mistral-medium-3.5-128b` und `qwen3-omni-30b-a3b-instruct` Bilder an.
Default ist `gemma-4-31b-it` (Begründung im Kommentar in `magda/config.py`).
Modelle starten kalt und brauchen beim ersten Request teils Minuten –
Timeouts im Labeling-Skript großzügig lassen.
