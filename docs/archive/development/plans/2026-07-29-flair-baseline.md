# Flair-Baseline-Arm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein fertiges deutsches NER-Modell (`flair/ner-german-large`) als vierten Vergleichsarm neben GBERT, LayoutXLM und der LLM-Blackbox auf BRAND messen.

**Architecture:** Flair bekommt die Wortliste aus Schritt 02 vorsegmentiert (eine Seite = eine `Sentence`), sodass jede Vorhersage auf genau einem Wortindex sitzt — kein Alignment, und dieselbe Eingabe wie GBERT. Verglichen wird ausschließlich auf BRAND (`ORG` → `BRAND`), beide Seiten werden dafür auf dieses eine Label reduziert. Der Gold-Ladepfad und der Wort-Level-Report entstehen als Paket-Logik, weil `06_compare_labels.py` beide ebenfalls braucht.

**Tech Stack:** Python, flair (optionale Abhängigkeit), seqeval, pytest.

## Global Constraints

- Kommentare und Docstrings auf Deutsch, Code-Identifier auf Englisch.
- Docstrings erklären *warum*, nicht *was*.
- Neue Pipeline-Logik gehört ins Package (`magda/`), Skripte parsen nur Argumente, lesen/schreiben Dateien und zeigen Fortschritt.
- `ENTITY_TYPES` wird nicht angefasst — die Label-IDs hängen an der Reihenfolge.
- `flair` steht in `requirements-flair.txt`, nie in `requirements.txt`.
- Tests müssen **ohne installiertes flair** laufen: `import flair` nur lazy innerhalb der Vorhersagefunktion.
- Keine Änderung an `magda/runner.py` und am Frontend.
- Skriptnummer `06` bleibt für `06_compare_labels.py` reserviert.
- `python -m pytest` aus dem Projektroot muss nach jeder Task grün sein.

---

### Task 1: Gold-Ladepfad als Paket-Logik (`magda/gold.py`)

**Files:**
- Create: `magda/gold.py`
- Modify: `magda/api.py` (Zeilen um 301-308: `_words_hash` entfernen, aus `magda.gold` importieren; Aufrufstellen ~336-352, 362, 397)
- Test: `tests/test_gold.py`

**Interfaces:**
- Consumes: `magda.config.GOLD_DIR`, `magda.config.WORDS_DIR`, `magda.labels.spans_to_bio`
- Produces:
  - `words_hash(words: list[dict]) -> str`
  - `class GoldPages(NamedTuple): pages: list[dict]; stale: list[str]; in_progress: list[str]`
  - `load_gold_pages() -> GoldPages` — `pages` in derselben Form wie `dataset.load_labeled_pages()`: `{"page_id", "width", "height", "words", "tags"}`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gold.py
"""Tests für den Gold-Ladepfad (handannotierte Referenz unter gold/)."""

import json

import pytest

from magda import config, gold


@pytest.fixture
def gold_dirs(tmp_path, monkeypatch):
    """Verlegt gold/ und data/words/ in ein tmp-Verzeichnis."""
    words_dir = tmp_path / "words"
    gold_dir = tmp_path / "gold"
    words_dir.mkdir()
    gold_dir.mkdir()
    monkeypatch.setattr(config, "WORDS_DIR", words_dir)
    monkeypatch.setattr(config, "GOLD_DIR", gold_dir)
    monkeypatch.setattr(gold, "WORDS_DIR", words_dir)
    monkeypatch.setattr(gold, "GOLD_DIR", gold_dir)
    return words_dir, gold_dir


def _write_page(words_dir, gold_dir, page_id, texts, spans, status="done", hash_override=None):
    words = [{"text": t, "bbox": [0, 0, 1, 1]} for t in texts]
    with open(words_dir / f"{page_id}.json", "w") as f:
        json.dump({"page_id": page_id, "width": 100, "height": 200, "words": words}, f)
    with open(gold_dir / f"{page_id}.json", "w") as f:
        json.dump(
            {
                "page_id": page_id,
                "words_hash": hash_override or gold.words_hash(words),
                "status": status,
                "annotator": "",
                "spans": spans,
            },
            f,
        )


def test_laedt_fertige_seite_mit_bio_tags(gold_dirs):
    words_dir, gold_dir = gold_dirs
    _write_page(words_dir, gold_dir, "p1", ["Landliebe", "Vollmilch", "1.29"],
                [{"start": 0, "end": 1, "label": "BRAND"},
                 {"start": 1, "end": 2, "label": "PRODUCT"}])

    result = gold.load_gold_pages()

    assert [p["page_id"] for p in result.pages] == ["p1"]
    assert result.pages[0]["tags"] == ["B-BRAND", "B-PRODUCT", "O"]
    assert result.pages[0]["width"] == 100
    assert len(result.pages[0]["words"]) == 3


def test_ueberspringt_unfertige_seiten(gold_dirs):
    words_dir, gold_dir = gold_dirs
    _write_page(words_dir, gold_dir, "p1", ["Landliebe"],
                [{"start": 0, "end": 1, "label": "BRAND"}], status="in_progress")

    result = gold.load_gold_pages()

    assert result.pages == []
    assert result.in_progress == ["p1"]


def test_ueberspringt_stale_seiten(gold_dirs):
    words_dir, gold_dir = gold_dirs
    _write_page(words_dir, gold_dir, "p1", ["Landliebe"],
                [{"start": 0, "end": 1, "label": "BRAND"}], hash_override="veraltet")

    result = gold.load_gold_pages()

    assert result.pages == []
    assert result.stale == ["p1"]


def test_ueberspringt_gold_ohne_wortdatei(gold_dirs):
    words_dir, gold_dir = gold_dirs
    _write_page(words_dir, gold_dir, "p1", ["Landliebe"],
                [{"start": 0, "end": 1, "label": "BRAND"}])
    (words_dir / "p1.json").unlink()

    result = gold.load_gold_pages()

    assert result.pages == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_gold.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'magda.gold'`

- [ ] **Step 3: Write the implementation**

```python
# magda/gold.py
"""Zugriff auf die handannotierte Referenz unter gold/.

Der einzige Gold-Lesepfad lag bisher in api.py, also in der HTTP-Schicht, wo
ihn kein Skript erreicht. Der Vergleich gegen Gold ist aber Kernlogik: er
beantwortet die Frage, wofür das Gold-Set überhaupt existiert.
"""

import hashlib
import json
from typing import NamedTuple

from magda.config import GOLD_DIR, WORDS_DIR
from magda.labels import spans_to_bio


def words_hash(words: list[dict]) -> str:
    """Fingerabdruck der Wortliste, gegen stille Index-Verschiebung.

    Nur die Texte in ihrer Reihenfolge - Koordinaten bleiben außen vor, damit
    eine um einen Punkt verschobene Box die Annotation nicht entwertet.
    """
    payload = json.dumps([w["text"] for w in words], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GoldPages(NamedTuple):
    """Geladene Seiten plus die Gründe, warum andere fehlen.

    Die Ausschlüsse gehören ins Ergebnis, nicht auf stderr: Wer eine Zahl über
    12 statt 40 Seiten berichtet, muss das im Report sehen können.
    """

    pages: list[dict]
    stale: list[str]
    in_progress: list[str]


def load_gold_pages() -> GoldPages:
    """Lädt fertig annotierte Gold-Seiten in der Form von load_labeled_pages().

    Zwei Ausschlüsse, beide notwendig:

    Halb annotierte Seiten (`in_progress`) erzeugen Falsch-Negative und ziehen
    jeden Vergleichsarm gleichmäßig nach unten - ein Messfehler, den niemand
    an der Zahl erkennt.

    Bei abweichendem `words_hash` zeigen die Span-Indizes auf andere Wörter.
    Genau dagegen existiert der Hash; die Seite still mitzunehmen wäre der
    Fehler, den er verhindern soll.
    """
    pages, stale, in_progress = [], [], []

    for gold_file in sorted(GOLD_DIR.glob("*.json")):
        page_id = gold_file.stem
        with open(gold_file) as f:
            annotation = json.load(f)

        words_file = WORDS_DIR / f"{page_id}.json"
        if not words_file.exists():
            continue
        with open(words_file) as f:
            page = json.load(f)

        if annotation.get("status") != "done":
            in_progress.append(page_id)
            continue
        if annotation.get("words_hash") != words_hash(page["words"]):
            stale.append(page_id)
            continue

        pages.append({
            "page_id": page_id,
            "width": page["width"],
            "height": page["height"],
            "words": page["words"],
            "tags": spans_to_bio(len(page["words"]), annotation.get("spans", [])),
        })

    return GoldPages(pages=pages, stale=stale, in_progress=in_progress)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_gold.py -v`
Expected: PASS (4 Tests)

- [ ] **Step 5: `_words_hash` aus `api.py` entfernen**

In `magda/api.py` die Funktion `_words_hash` (samt Docstring) löschen und stattdessen importieren. Bei den bestehenden Importen ergänzen:

```python
from magda.gold import words_hash
```

Alle vier Aufrufstellen von `_words_hash(` auf `words_hash(` umstellen. Danach prüfen, ob `import hashlib` in `api.py` noch gebraucht wird — falls nicht, entfernen.

- [ ] **Step 6: Gesamte Testsuite laufen lassen**

Run: `python -m pytest`
Expected: PASS — insbesondere `tests/test_api.py` unverändert grün.

- [ ] **Step 7: Commit**

```bash
git add magda/gold.py magda/api.py tests/test_gold.py
git commit -m "Hole den Gold-Ladepfad aus der HTTP-Schicht ins Package"
```

---

### Task 2: Wort-Level-Report (`magda/evaluation.py`)

**Files:**
- Modify: `magda/evaluation.py` (`full_report` und `report_dict` auf die neuen Funktionen zurückführen)
- Test: `tests/test_evaluation.py` (erweitern)

**Interfaces:**
- Consumes: nichts Neues
- Produces:
  - `word_level_report(true_tags: list[list[str]], pred_tags: list[list[str]]) -> str`
  - `word_level_report_dict(true_tags: list[list[str]], pred_tags: list[list[str]]) -> dict`

- [ ] **Step 1: Write the failing test**

An `tests/test_evaluation.py` anhängen:

```python
from magda.evaluation import word_level_report_dict


def test_word_level_report_dict_auf_wort_tags():
    true_tags = [["B-BRAND", "I-BRAND", "O"], ["B-BRAND", "O"]]
    pred_tags = [["B-BRAND", "I-BRAND", "O"], ["O", "O"]]

    report = word_level_report_dict(true_tags, pred_tags)

    assert report["BRAND"]["support"] == 2
    assert report["BRAND"]["recall"] == 0.5
    assert report["BRAND"]["precision"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_evaluation.py -v`
Expected: FAIL mit `ImportError: cannot import name 'word_level_report_dict'`

- [ ] **Step 3: Write the implementation**

In `magda/evaluation.py` die beiden neuen Funktionen ergänzen und die bestehenden darauf zurückführen:

```python
def word_level_report(true_tags: list[list[str]], pred_tags: list[list[str]]) -> str:
    """Report über zwei Wort-Tag-Listen statt über Subword-Arrays.

    Modelle ohne HF-Trainer (der Flair-Arm, später der Gold-gegen-LLM-Vergleich)
    liefern Tags pro Wort. Die Metrik ist dieselbe - nur die Eingabe kommt nicht
    aus einem maskierten Tensor.
    """
    return classification_report(true_tags, pred_tags, digits=3)


def word_level_report_dict(true_tags: list[list[str]], pred_tags: list[list[str]]) -> dict:
    """Wie word_level_report, aber als Dict für den JSON-Export.

    seqeval gibt "support" als numpy.int64 zurück, worüber json.dump stolpert.
    """
    report = classification_report(true_tags, pred_tags, digits=3, output_dict=True)
    return {
        entity: {metric: value.item() if hasattr(value, "item") else value
                 for metric, value in scores.items()}
        for entity, scores in report.items()
    }


def full_report(predictions: np.ndarray, label_ids: np.ndarray) -> str:
    """Ausführlicher Report pro Entity-Typ, für die Fehleranalyse in Phase 3."""
    return word_level_report(*_decode(predictions, label_ids))


def report_dict(predictions: np.ndarray, label_ids: np.ndarray) -> dict:
    """Wie full_report, aber als Dict – für den JSON-Export ans Frontend."""
    return word_level_report_dict(*_decode(predictions, label_ids))
```

Die alten Rümpfe von `full_report` und `report_dict` werden dabei ersetzt, nicht ergänzt.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_evaluation.py -v`
Expected: PASS — auch `test_report_dict_liefert_metriken_pro_entity` muss unverändert grün bleiben (Regression gegen die Rückführung).

- [ ] **Step 5: Commit**

```bash
git add magda/evaluation.py tests/test_evaluation.py
git commit -m "Oeffne den Entity-Report fuer Wort-Tag-Listen"
```

---

### Task 3: Mapping und Einschränkung (`magda/flair_baseline.py`, reine Logik)

**Files:**
- Create: `magda/flair_baseline.py`
- Test: `tests/test_flair_baseline.py`

**Interfaces:**
- Consumes: `magda.labels.spans_to_bio`
- Produces:
  - `FLAIR_MODEL: str = "flair/ner-german-large"`
  - `TAG_MAPPING: dict[str, str] = {"ORG": "BRAND"}`
  - `REPORTED_LABELS: frozenset[str] = frozenset({"BRAND"})`
  - `restrict_to(tags: list[str], keep: frozenset[str]) -> list[str]`
  - `spans_to_project_tags(num_words: int, flair_spans: list[tuple[int, int, str]]) -> list[str]` — `flair_spans` ist `(start_wortindex, end_wortindex_exklusiv, flair_label)`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_flair_baseline.py
"""Tests für den Flair-Vergleichsarm.

Laufen ohne installiertes flair - die Modellanbindung ist bewusst von der
Mapping-Logik getrennt, damit die Testsuite nicht an einer optionalen
Abhängigkeit hängt.
"""

from magda.flair_baseline import (
    REPORTED_LABELS,
    restrict_to,
    spans_to_project_tags,
)


def test_restrict_to_behaelt_nur_das_gewuenschte_label():
    tags = ["B-BRAND", "I-BRAND", "B-PRICE", "O", "B-PRODUCT"]

    assert restrict_to(tags, REPORTED_LABELS) == ["B-BRAND", "I-BRAND", "O", "O", "O"]


def test_restrict_to_laesst_reines_O_unberuehrt():
    assert restrict_to(["O", "O"], REPORTED_LABELS) == ["O", "O"]


def test_spans_to_project_tags_mappt_org_auf_brand():
    # 4 Wörter, ORG über Wort 1-2 (end exklusiv).
    tags = spans_to_project_tags(4, [(1, 3, "ORG")])

    assert tags == ["O", "B-BRAND", "I-BRAND", "O"]


def test_spans_to_project_tags_verwirft_nicht_gemappte_label():
    # PER, LOC und MISC haben im Projekt-Schema keine Entsprechung.
    tags = spans_to_project_tags(3, [(0, 1, "PER"), (1, 2, "LOC"), (2, 3, "MISC")])

    assert tags == ["O", "O", "O"]


def test_spans_to_project_tags_ohne_spans():
    assert spans_to_project_tags(3, []) == ["O", "O", "O"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_flair_baseline.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'magda.flair_baseline'`

- [ ] **Step 3: Write the implementation**

```python
# magda/flair_baseline.py
"""Vergleichsarm: fertiges deutsches NER-Modell ohne jede Anpassung.

Beziffert, was man geschenkt bekommt - und damit, was die Domänenanpassung
wert ist. Ohne diesen Arm ist "unsere Anpassung war nötig" eine Behauptung.

flair/ner-german-large ist auf CoNLL-03 German trainiert und kennt PER, LOC,
ORG und MISC. Von den acht Projekt-Labels ist damit genau eines erreichbar:
BRAND über ORG. MISC bleibt bewusst ungemappt - es sammelt Nationalitäten,
Ereignisse und Werktitel und trifft Produktnamen nur zufällig, die Zahl wäre
nicht interpretierbar.

Der Import von flair passiert absichtlich erst in predict_pages(): die
Mapping-Logik muss ohne die optionale Abhängigkeit testbar bleiben.
"""

from magda.labels import spans_to_bio

FLAIR_MODEL = "flair/ner-german-large"

TAG_MAPPING = {"ORG": "BRAND"}
REPORTED_LABELS = frozenset(TAG_MAPPING.values())


def restrict_to(tags: list[str], keep: frozenset[str]) -> list[str]:
    """Setzt alle Entity-Typen außer den genannten auf "O".

    Wird auf beide Seiten angewandt: Ein Modell, das PRICE gar nicht vorhersagen
    kann, darf dafür weder bestraft noch belohnt werden. Ohne die Einschränkung
    der Referenz zählte jeder Preis als Falsch-Negativ.
    """
    return [tag if tag != "O" and tag[2:] in keep else "O" for tag in tags]


def spans_to_project_tags(num_words: int, flair_spans: list[tuple[int, int, str]]) -> list[str]:
    """Übersetzt Flair-Spans in BIO-Tags des Projekt-Schemas.

    flair_spans sind (start, end, label) mit Wortindizes, end exklusiv. Nicht
    gemappte Flair-Label fallen hier raus. Die BIO-Erzeugung übernimmt
    spans_to_bio() - inklusive Grenzprüfung und Überlappungsregel.
    """
    spans = [
        {"start": start, "end": end, "label": TAG_MAPPING[label]}
        for start, end, label in flair_spans
        if label in TAG_MAPPING
    ]
    return spans_to_bio(num_words, spans)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_flair_baseline.py -v`
Expected: PASS (5 Tests)

- [ ] **Step 5: Commit**

```bash
git add magda/flair_baseline.py tests/test_flair_baseline.py
git commit -m "Mappe Flair-Entities auf das Projekt-Schema"
```

---

### Task 4: Modellanbindung (`magda/flair_baseline.py`, Vorhersage)

**Files:**
- Modify: `magda/flair_baseline.py`
- Test: `tests/test_flair_baseline.py` (erweitern)

**Interfaces:**
- Consumes: `restrict_to`, `spans_to_project_tags`, `TAG_MAPPING`, `FLAIR_MODEL` aus Task 3
- Produces:
  - `check_tagset(labels: set[str]) -> None` — wirft `RuntimeError`, wenn ein gemapptes Flair-Label fehlt
  - `load_tagger(model_name: str = FLAIR_MODEL)` — lädt das Modell, prüft das Tagset
  - `predict_pages(pages: list[dict], tagger) -> list[list[str]]` — ein Tag pro Wort, bereits im Projekt-Schema und auf `REPORTED_LABELS` eingeschränkt

- [ ] **Step 1: Write the failing tests**

An `tests/test_flair_baseline.py` anhängen:

```python
import pytest

from magda.flair_baseline import check_tagset, predict_pages


def test_check_tagset_akzeptiert_conll_labels():
    check_tagset({"PER", "LOC", "ORG", "MISC"})  # wirft nicht


def test_check_tagset_wirft_ohne_org():
    with pytest.raises(RuntimeError, match="ORG"):
        check_tagset({"PER", "LOC", "MISC"})


class _FakeToken:
    def __init__(self, idx):
        self.idx = idx


class _FakeLabel:
    def __init__(self, value):
        self.value = value


class _FakeSpan:
    def __init__(self, start_idx, end_idx, value):
        # flair zählt Token ab 1, end inklusiv.
        self.tokens = [_FakeToken(i) for i in range(start_idx, end_idx + 1)]
        self._value = value

    def get_label(self, _name):
        return _FakeLabel(self._value)


class _FakeTagger:
    """Steht für den SequenceTagger, ohne flair zu installieren."""

    def __init__(self, spans_per_call):
        self.spans_per_call = list(spans_per_call)
        self.seen = []

    def predict(self, sentence):
        sentence._spans = self.spans_per_call.pop(0)
        self.seen.append(sentence)


def test_predict_pages_setzt_tags_auf_die_richtigen_wortindizes(monkeypatch):
    import magda.flair_baseline as fb

    class _FakeSentence:
        def __init__(self, tokens):
            self.tokens_in = tokens
            self._spans = []

        def get_spans(self, _name):
            return self._spans

    monkeypatch.setattr(fb, "_make_sentence", lambda words: _FakeSentence(words))

    page = {"words": [{"text": t} for t in ["Angebot", "Landliebe", "Vollmilch", "1.29"]]}
    # ORG über Token 2-3 (flair, 1-basiert, end inklusiv) = Wortindex 1-2.
    tagger = _FakeTagger([[_FakeSpan(2, 3, "ORG")]])

    tags = predict_pages([page], tagger)

    assert tags == [["O", "B-BRAND", "I-BRAND", "O"]]


def test_predict_pages_verwirft_nicht_gemappte_label(monkeypatch):
    import magda.flair_baseline as fb

    class _FakeSentence:
        def __init__(self, tokens):
            self._spans = []

        def get_spans(self, _name):
            return self._spans

    monkeypatch.setattr(fb, "_make_sentence", lambda words: _FakeSentence(words))

    page = {"words": [{"text": t} for t in ["Berlin", "Aldi"]]}
    tagger = _FakeTagger([[_FakeSpan(1, 1, "LOC")]])

    assert predict_pages([page], tagger) == [["O", "O"]]


def test_predict_pages_bei_leerer_seite(monkeypatch):
    import magda.flair_baseline as fb

    monkeypatch.setattr(fb, "_make_sentence", lambda words: None)

    assert predict_pages([{"words": []}], _FakeTagger([])) == [[]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_flair_baseline.py -v`
Expected: FAIL mit `ImportError: cannot import name 'check_tagset'`

- [ ] **Step 3: Write the implementation**

An `magda/flair_baseline.py` anhängen:

```python
def check_tagset(labels: set[str]) -> None:
    """Prüft am geladenen Modell, ob die gemappten Label überhaupt existieren.

    Modellkataloge ändern sich, und ein umbenanntes Label fällt sonst nicht auf:
    Das Mapping liefe leer durch, der Report stünde auf 0.000, und niemand
    wüsste, ob das Modell schlecht ist oder das Mapping tot.
    """
    missing = set(TAG_MAPPING) - labels
    if missing:
        raise RuntimeError(
            f"Modell kennt {sorted(missing)} nicht (gefunden: {sorted(labels)}). "
            "Das Mapping wäre leer und der Report 0.000 ohne erkennbaren Grund."
        )


def _tagger_labels(tagger) -> set[str]:
    """Entity-Typen des Modells, unabhängig vom Tagging-Schema.

    flair legt im label_dictionary je nach Modell "S-ORG"/"B-ORG" oder schlicht
    "ORG" ab, ältere Fassungen zudem als bytes.
    """
    labels = set()
    for item in tagger.label_dictionary.get_items():
        if isinstance(item, bytes):
            item = item.decode("utf-8")
        labels.add(item.split("-", 1)[1] if "-" in item else item)
    return labels


def _make_sentence(words: list[str]):
    """Eine Seite als vorsegmentierte flair-Sentence.

    Die Wortliste aus Schritt 02 wird als fertige Token übergeben, flairs
    eigener Tokenizer bleibt aus. Damit sitzt jede Vorhersage auf genau einem
    Wortindex - kein Rückmapping über Zeichen-Offsets, das (1 kg = 24.95)
    anders zerlegen würde als unsere Wortliste. Nebeneffekt und eigentlicher
    Grund: Flair sieht exakt dieselbe Eingabe wie GBERT, sonst wären die
    beiden Zahlen nicht vergleichbar.
    """
    from flair.data import Sentence

    return Sentence(words)


def load_tagger(model_name: str = FLAIR_MODEL):
    """Lädt das Modell und prüft sein Tagset, statt es zu glauben."""
    try:
        from flair.models import SequenceTagger
    except ImportError as exc:
        raise RuntimeError(
            "flair ist nicht installiert: pip install -r requirements-flair.txt"
        ) from exc

    tagger = SequenceTagger.load(model_name)
    check_tagset(_tagger_labels(tagger))
    return tagger


def predict_pages(pages: list[dict], tagger) -> list[list[str]]:
    """Taggt Seiten und gibt ein Projekt-BIO-Tag je Wort zurück."""
    all_tags = []
    for page in pages:
        words = [w["text"] for w in page["words"]]
        if not words:
            all_tags.append([])
            continue

        sentence = _make_sentence(words)
        tagger.predict(sentence)

        spans = []
        for span in sentence.get_spans("ner"):
            # flair zählt Token ab 1 und meint end inklusiv.
            start = span.tokens[0].idx - 1
            end = span.tokens[-1].idx
            spans.append((start, end, span.get_label("ner").value))

        all_tags.append(restrict_to(spans_to_project_tags(len(words), spans), REPORTED_LABELS))
    return all_tags
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_flair_baseline.py -v`
Expected: PASS (10 Tests)

- [ ] **Step 5: Commit**

```bash
git add magda/flair_baseline.py tests/test_flair_baseline.py
git commit -m "Binde den Flair-Tagger an die Wortliste aus Schritt 02"
```

---

### Task 5: CLI-Skript (`scripts/07_flair_baseline.py`)

**Files:**
- Create: `scripts/07_flair_baseline.py`
- Modify: `requirements.txt` (Kommentar-Verweis auf `requirements-flair.txt`)
- Modify: `CLAUDE.md` (Kommandos und Projektwissen)

**Interfaces:**
- Consumes: `magda.gold.load_gold_pages`, `magda.dataset.load_labeled_pages/get_or_create_splits/select_split`, `magda.evaluation.word_level_report/word_level_report_dict`, `magda.flair_baseline.*`
- Produces: `data/eval/flair_{reference}_{split}.json`

- [ ] **Step 1: Skript schreiben**

```python
# scripts/07_flair_baseline.py
"""Vergleichsarm: fertiges deutsches NER-Modell ohne jede Anpassung.

Aufruf:
    python scripts/07_flair_baseline.py --reference gold
    python scripts/07_flair_baseline.py --reference llm --split test

Beantwortet, was man ohne Training geschenkt bekommt - und beziffert damit,
was die Domänenanpassung wert ist. Verglichen wird nur auf BRAND: das Modell
kennt PER/LOC/ORG/MISC, und nur ORG hat im Projekt-Schema eine Entsprechung.

Braucht flair, das bewusst nicht in requirements.txt steht:
    pip install -r requirements-flair.txt
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from magda.config import EVAL_DIR
from magda.dataset import get_or_create_splits, load_labeled_pages, select_split
from magda.evaluation import word_level_report, word_level_report_dict
from magda.flair_baseline import (
    FLAIR_MODEL,
    REPORTED_LABELS,
    TAG_MAPPING,
    load_tagger,
    predict_pages,
    restrict_to,
)
from magda.gold import load_gold_pages


def _gold_pages(split: str) -> tuple[list[dict], dict]:
    result = load_gold_pages()
    if result.stale:
        print(f"Übersprungen (words_hash veraltet): {', '.join(result.stale)}")
    if result.in_progress:
        print(f"Übersprungen (noch nicht fertig): {', '.join(result.in_progress)}")
    if not result.pages:
        sys.exit(
            "Keine fertig annotierte Gold-Seite gefunden. Im Annotator mit 'f' als "
            "fertig markieren – oder für einen Rauchtest --reference llm nehmen."
        )

    pages = result.pages
    if split != "all":
        splits = get_or_create_splits(load_labeled_pages())
        pages = select_split(pages, splits, split)
        if not pages:
            sys.exit(
                f"Keine Gold-Seite liegt im '{split}'-Split. Mit --split all über "
                "alle fertigen Gold-Seiten evaluieren (bei Flair unbedenklich, weil "
                "nichts trainiert wurde – aber nicht mit den trainierten Armen "
                "vergleichbar)."
            )
    return pages, {"stale": result.stale, "in_progress": result.in_progress}


def _llm_pages(split: str) -> tuple[list[dict], dict]:
    print(
        "Achtung: --reference llm misst, wie gut Flair Mistral imitiert, nicht wie "
        "gut es Angebote extrahiert. Als Rauchtest brauchbar, nicht berichtsfähig."
    )
    pages = load_labeled_pages()
    if split != "all":
        pages = select_split(pages, get_or_create_splits(pages), split)
    return pages, {"stale": [], "in_progress": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default="gold", choices=["gold", "llm"])
    parser.add_argument("--split", default="test", choices=["dev", "test", "all"])
    parser.add_argument("--model", default=FLAIR_MODEL)
    args = parser.parse_args()

    pages, skipped = _gold_pages(args.split) if args.reference == "gold" else _llm_pages(args.split)
    print(f"Evaluiere '{args.model}' auf {len(pages)} Seiten "
          f"(Referenz: {args.reference}, Split: {args.split}).")

    print("Lade Modell – beim ersten Mal wird es heruntergeladen (~1.5 GB).")
    tagger = load_tagger(args.model)

    predictions = predict_pages(pages, tagger)
    # Beide Seiten einschränken: Labels, die das Modell nicht vorhersagen kann,
    # dürfen weder als Falsch-Negativ noch als Treffer zählen.
    references = [restrict_to(page["tags"], REPORTED_LABELS) for page in pages]

    print(word_level_report(references, predictions))

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_file = EVAL_DIR / f"flair_{args.reference}_{args.split}.json"
    with open(out_file, "w") as f:
        json.dump(
            {
                "variant": "flair",
                "model": args.model,
                "reference": args.reference,
                "split": args.split,
                "num_pages": len(pages),
                "mapping": TAG_MAPPING,
                "restricted_to": sorted(REPORTED_LABELS),
                "skipped": skipped,
                "created": datetime.now().isoformat(timespec="seconds"),
                "report": word_level_report_dict(references, predictions),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Report gespeichert: {out_file}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Skript ohne Modell prüfen (Fehlerpfade)**

Run: `python scripts/07_flair_baseline.py --reference gold`
Expected: Abbruch mit dem Hinweis auf fehlende fertige Gold-Seiten (das Gold-Set enthält aktuell nur `in_progress`). Kein Traceback.

Run: `python scripts/07_flair_baseline.py --help`
Expected: Hilfetext, kein Import-Fehler.

- [ ] **Step 3: Rauchtest mit Modell**

Run: `python scripts/07_flair_baseline.py --reference llm --split test`
Expected: Lädt das Modell, gibt einen seqeval-Report mit einer BRAND-Zeile aus, schreibt `data/eval/flair_llm_test.json`.

Falls flair nicht installiert ist: Abbruch mit dem Hinweis auf `requirements-flair.txt` — dann diesen Schritt überspringen und im Commit vermerken, dass der Rauchtest aussteht.

- [ ] **Step 4: `requirements.txt` ergänzen**

Nach dem Block „Modelltraining & Evaluation" einfügen:

```
# Vergleichsarm mit fertigem deutschen NER-Modell (scripts/07_flair_baseline.py):
# separat installieren, siehe requirements-flair.txt
```

- [ ] **Step 5: `CLAUDE.md` ergänzen**

Unter „Kommandos" ergänzen:

```bash
python scripts/07_flair_baseline.py --reference gold   # Flair-Vergleichsarm
```

Unter „Projektwissen, das nicht im Code steht" ergänzen:

```markdown
- **Der Flair-Arm misst nur BRAND.** `flair/ner-german-large` kennt
  PER/LOC/ORG/MISC; von unseren acht Labels hat nur BRAND eine Entsprechung
  (`ORG`). Deshalb werden Referenz *und* Vorhersage auf BRAND eingeschränkt –
  ohne das zählte jeder Preis in der Referenz als Falsch-Negativ. Jede
  berichtete Zahl aus diesem Arm muss die Einschränkung mitnennen.
- **Flair bekommt die Wortliste vorsegmentiert.** Nicht aus Bequemlichkeit:
  So sitzt jede Vorhersage auf genau einem Wortindex, und Flair sieht exakt
  dieselbe Eingabe wie GBERT. Eine eigene Tokenisierung würde `(1 kg = 24.95)`
  anders zerlegen und die beiden Zahlen unvergleichbar machen.
- **`flair` steht nicht in `requirements.txt`.** Es zieht gensim und weitere
  Pakete nach, die sich mit der NumPy/Transformers-Pinnung beißen können. Das
  Trainings-Env wird nicht für einen Arm riskiert, den man zweimal startet.
```

- [ ] **Step 6: Gesamte Testsuite**

Run: `python -m pytest`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/07_flair_baseline.py requirements.txt requirements-flair.txt CLAUDE.md
git commit -m "Fuege den Flair-Vergleichsarm als Skript hinzu"
```

---

## Self-Review

**Spec-Abdeckung:**

| Spec-Abschnitt | Task |
|---|---|
| `magda/gold.py`, `words_hash` verschieben | Task 1 |
| `word_level_report(_dict)` | Task 2 |
| `TAG_MAPPING`, `restrict_to`, Mapping | Task 3 |
| Tagset-Prüfung, `predict_pages`, Ansatz A | Task 4 |
| CLI, `--reference`/`--split`/`--model`, JSON-Report | Task 5 |
| `requirements-flair.txt` | vorab angelegt, Verweis in Task 5 |
| Fehlerbehandlungs-Tabelle | Task 1 (stale/in_progress), Task 4 (flair fehlt, Tagset), Task 5 (kein Gold, leerer Split) |
| Kein Eingriff in Runner/Frontend | keine Task fasst sie an |

Offen laut Spec und bewusst nicht im Plan: `06_compare_labels.py`, die Berichtsentscheidung `--split test` vs. `all`.

**Überlange Seiten:** Task 4 verlässt sich auf flairs Standardverhalten (`allow_long_sentences`). Wird im Rauchtest (Task 5, Step 3) an einer echten Seite mit 216 Wörtern geprüft; kürzt flair doch, fällt es dort als abgeschnittener Tag-Vektor auf, weil `predict_pages` sonst weniger Tags als Wörter zurückgäbe. Ein Längenabgleich gehört daher in Task 5, Step 3: Die Anzahl Tags je Seite muss der Anzahl Wörter entsprechen.

**Typkonsistenz:** `restrict_to(tags, keep)`, `spans_to_project_tags(num_words, flair_spans)`, `predict_pages(pages, tagger)`, `load_tagger(model_name)`, `check_tagset(labels)`, `load_gold_pages() -> GoldPages`, `word_level_report(true, pred)` — in Tasks 1-5 durchgängig gleich benannt und verwendet.
