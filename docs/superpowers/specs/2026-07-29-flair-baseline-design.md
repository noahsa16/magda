# Flair-Baseline-Arm — Design

**Stand: 29.07.2026**

## Zweck

Ein fertiges deutsches NER-Modell (`flair/ner-german-large`, Akbik et al. 2018)
als vierter Vergleichsarm neben GBERT, LayoutXLM und der LLM-Blackbox. Es
beantwortet die Frage, die die anderen drei Arme offenlassen: **Wie viel bringt
die Domänenanpassung überhaupt — was bekäme man ohne jedes Training geschenkt?**

Das Ergebnis wird schlecht ausfallen, und das ist der Zweck. Ohne diesen Arm ist
„unsere Anpassung war nötig" eine Behauptung; mit ihm ist sie eine Zahl.

Nebennutzen: Flair *ist* die Arbeit, die das Proposal als Komplexitätsreferenz
für den Kurs nennt. Sie wird damit nicht nur zitiert, sondern gemessen.

## Was der Arm kann — und was nicht

`flair/ner-german-large` ist auf CoNLL-03 German trainiert und kennt vier
Klassen: `PER`, `LOC`, `ORG`, `MISC`. Kein `MONEY`, kein `DATE`, kein
`QUANTITY` — die deutschen spaCy-Modelle ebenso wenig.

Von den acht Projekt-Labels ist damit genau eines erreichbar: **BRAND über
`ORG`**. Das ist keine Einschränkung des Vorgehens, sondern das interessante
Label: PRODUCT und BRAND sind die Stelle, an der sich das Projekt entscheidet,
und BRAND ist die einzige der beiden, für die es überhaupt eine fertige
Entsprechung gibt.

`MISC` → PRODUCT wird **nicht** gemappt. CoNLL-MISC ist ein Sammelbecken
(Nationalitäten, Ereignisse, Werktitel) und trifft Produktnamen nur zufällig;
die Zahl wäre nicht interpretierbar.

Das Tagset wird zur Laufzeit gegen das geladene Modell geprüft, nicht geglaubt
— dieselbe Regel wie beim GWDG-Modellkatalog.

## Bewertungsvertrag: eingeschränkte Referenz

Verglichen wird ausschließlich auf BRAND. Dafür werden **beide** Seiten
reduziert:

- Referenz: alle Tags außer `B-BRAND`/`I-BRAND` werden zu `"O"`.
- Vorhersage: alles außer dem aus `ORG` gemappten BRAND wird zu `"O"`.

Damit ist die Zahl direkt gegen die BRAND-Zeile aus `05_evaluate.py`
vergleichbar. Der Bericht muss ausdrücklich nennen, dass die übrigen sieben
Labels ausgeschlossen wurden und warum — sonst liest sich ein hohes Mikro-F1
als Gesamtleistung.

## Eingabe: Ansatz A (vorsegmentiert)

Flair bekommt die Wortliste aus Schritt 02 als fertige Token; sein eigener
Tokenizer bleibt aus. Eine Seite ist eine `Sentence`.

Zwei Gründe:

1. **Kein Alignment.** Jede Vorhersage sitzt auf genau einem Wortindex. Ein
   Rückmapping über Zeichen-Offsets müsste auflösen, dass Flairs Tokenizer
   `(1 kg = 24.95)` anders zerlegt als unsere Wortliste — und jede
   Auflösungsregel verschiebt still das Ergebnis.
2. **Faire Ablation.** Flair sieht exakt dieselbe Eingabe wie GBERT. Gleicher
   Input, anderes Modell. Bei abweichender Tokenisierung wären die beiden
   Zahlen nicht mehr direkt vergleichbar.

Verworfen: zeilenweise `Sentence`s aus den Bounding-Boxen. Das gäbe dem
*text-only* Arm Layout-Information durch die Hintertür — an genau dem Arm, der
den Wert von Layout-Information beziffern soll. Wird im Bericht als bewusst
nicht genutzte Verbesserung erwähnt.

## Komponenten

### `magda/gold.py` (neu)

Gold-Laden als Paket-Logik. Bisher liegt der einzige Gold-Lesepfad in
`api.py` — also in der HTTP-Schicht, wo ihn kein Skript erreicht.

- `words_hash(words)` — **verschoben** aus `api.py._words_hash`, unverändert.
  `api.py` importiert ihn künftig von hier. Der Hash ist Domänenlogik, kein
  HTTP-Detail, und der neue Ladepfad braucht dieselbe Prüfung.
- `load_gold_pages()` → Seiten in derselben Form, die `load_labeled_pages()`
  liefert (`page_id`, `width`, `height`, `words`, `tags`), erzeugt durch Join
  von `gold/*.json` mit `data/words/*.json` und `labels.spans_to_bio()`.

  Zwei Filter, beide mit Begründung:
  - **Nur `status == "done"`.** Eine halb annotierte Seite erzeugt
    Falsch-Negative und würde jeden Arm gleichmäßig schlechter aussehen
    lassen — ein stiller Messfehler.
  - **Stale Seiten werden übersprungen**, mit Warnung auf stderr. Bei
    abweichendem `words_hash` zeigen die Span-Indizes auf andere Wörter; die
    Seite still mitzunehmen ist der Fehler, gegen den der Hash existiert.

### `magda/evaluation.py` (erweitert)

Der bestehende Report arbeitet auf Subword-Arrays des HF-Trainers
(`predictions`, `label_ids` mit `-100`). Flair liefert Wort-Tags. Neu:

- `word_level_report(true_tags, pred_tags) -> str`
- `word_level_report_dict(true_tags, pred_tags) -> dict`

  beide auf `list[list[str]]`.

`full_report()` und `report_dict()` werden darauf zurückgeführt — `_decode()`
erzeugt bereits genau diese Struktur. Kein Duplikat, und `06_compare_labels.py`
(Gold gegen Mistral) bekommt denselben Baustein geschenkt: auch dort werden
zwei Wort-Tag-Listen verglichen.

### `magda/flair_baseline.py` (neu)

- `TAG_MAPPING = {"ORG": "BRAND"}`
- `restrict_to(tags, keep)` — alles außer `keep` auf `"O"`; für beide Seiten.
- `map_flair_tags(...)` — Flair-Spans → Projekt-BIO über die Wortindizes.
- `predict_pages(pages, model_name)` — lädt das Modell, prüft das Tagset,
  taggt seitenweise.

`import flair` passiert **lazy** in `predict_pages`. Die reinen Funktionen
(Mapping, Einschränkung) bleiben ohne installiertes Flair testbar — sonst
hinge die halbe Testsuite an einer optionalen Abhängigkeit.

### `scripts/07_flair_baseline.py` (neu)

```
python scripts/07_flair_baseline.py --reference gold
python scripts/07_flair_baseline.py --reference llm --split test
```

- `--reference gold|llm` (Default `gold`). `llm` liest `data/labeled/` und ist
  als Rauchtest gedacht, solange das Gold-Set noch wächst — die Zahl misst dann
  „wie gut imitiert Flair Mistral" und ist nicht berichtsfähig. Das Skript sagt
  das beim Start.
- `--split test|dev|all` (Default `test`). `all` ist bei Flair unbedenklich, weil
  nichts trainiert wurde — aber nicht mit den Zahlen der trainierten Arme
  vergleichbar. Auch das schreibt das Skript hin.
- `--model` (Default `flair/ner-german-large`).
- Schreibt `data/eval/flair_{reference}_{split}.json` im Format von
  `05_evaluate.py`, ergänzt um `model`, `mapping` und `restricted_to`.

Die 06 bleibt für `06_compare_labels.py` frei.

### `requirements-flair.txt` (neu)

`flair` zieht `gensim` und weitere Pakete nach, die sich mit der NumPy- und
Transformers-Pinnung beißen können. Das Trainings-Env läuft — es wird nicht für
einen Arm riskiert, den man zweimal startet. Separate Datei, Hinweis in
`requirements.txt` als Kommentar.

## Nicht im Scope

- Keine Änderung an `runner.py` und am Frontend. Der Runner-Vertrag („kennt nur
  die fünf Skripte") bleibt unangetastet; der Arm ist ein Berichts-Baustein,
  kein bedienbarer Pipeline-Schritt.
- Kein `06_compare_labels.py`. Der geteilte Baustein entsteht hier, das Skript
  selbst ist eine eigene Aufgabe.

## Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| `flair` nicht installiert | Klarer Abbruch mit Verweis auf `requirements-flair.txt` |
| Kein Gold mit `status == "done"` | Abbruch mit Hinweis auf `--reference llm` |
| Gold-Seite stale | Überspringen, Warnung, Anzahl im Report vermerken |
| Modell-Tagset ohne `ORG` | Abbruch — das Mapping wäre still leer, das Ergebnis 0.000 ohne erkennbaren Grund |
| Seite > 512 Subwords | Flairs `TransformerWordEmbeddings` schiebt standardmäßig ein Fenster über lange Sequenzen (`allow_long_sentences`), kürzt also nicht. Wird beim Bauen am geladenen Modell geprüft; trifft es nicht zu, zählt das Skript betroffene Seiten und weist sie im Report aus, statt still Entities zu verlieren |

## Tests

Ohne installiertes Flair lauffähig (`tests/test_flair_baseline.py`):

- `restrict_to` setzt Fremdlabels auf `"O"` und lässt BRAND stehen
- `map_flair_tags` erzeugt `B-`/`I-`-Folgen an den richtigen Wortindizes
- Ein Flair-Label ohne Mapping (`PER`, `LOC`) landet nicht im Ergebnis

`tests/test_gold.py`:

- `load_gold_pages` überspringt `in_progress`
- `load_gold_pages` überspringt stale Seiten
- Tags entsprechen `spans_to_bio` über die Wortliste

`tests/test_evaluation.py` (erweitert):

- `word_level_report_dict` auf zwei Wort-Tag-Listen
- `report_dict` liefert unverändert dieselben Werte wie vorher (Regression
  gegen die Rückführung)

## Offen, bewusst nicht entschieden

- **Ob der Arm am Ende auf `--reference gold --split all` oder `--split test`
  berichtet wird.** Hängt daran, wie das Team den Split über Gold legt (siehe
  `reports/woche-02.md`). Das Skript kann beides; die Entscheidung fällt beim
  Schreiben des Berichts.
