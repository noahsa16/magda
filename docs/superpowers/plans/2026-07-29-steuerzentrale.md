# Steuerzentrale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pipeline-Ausführung und -Konfiguration bekommen einen eigenen Frontend-Tab mit typisierten Parametern, Lauf-Historie auf Platte und einem Katalog-Verzeichnis; die Übersicht wird zur reinen Lagebesprechung.

**Architecture:** Ein deklarativer Job-Katalog (`magda/jobs.py`) beschreibt jeden Pipeline-Schritt samt Parametern; `build_command` validiert und baut argv und ist die einzige Stelle, an der aus Nutzereingaben ein Kommando wird. `magda/runner.py` kümmert sich nur noch um den Prozess und schreibt jeden Lauf über `magda/runs.py` nach `data/runs/`. Das Frontend liest den Job-Katalog über `GET /api/jobs` und baut daraus seine Formulare — neue Parameter erscheinen ohne Frontend-Änderung.

**Tech Stack:** Python 3.12, FastAPI, pytest · React 19, TypeScript, Vite, TanStack Query, Tailwind, shadcn/ui, Vitest + Testing Library

## Global Constraints

- **Python immer `.venv/bin/python`, nie `python`.** `which python` zeigt auf Anaconda; dort fehlt `seqeval` und Tests brechen beim Import ab. Tests: `.venv/bin/pytest`.
- **Kommentare und Docstrings auf Deutsch, Code-Identifier auf Englisch.** Docstrings erklären *warum*, nicht *was*.
- **Neue Pipeline-Logik gehört ins Package `magda/`, nicht in die Skripte.**
- **Pfade werden als `config.X`-Attribute zur Laufzeit gelesen, nie importiert** (`from magda import config` + `config.RUNS_DIR`). Nur so biegen die Tests sie auf ein Temp-Verzeichnis um. Gilt für `api.py`, `runs.py`, `catalogs.py`, `jobs.py`.
- **Kein Durchreichen beliebiger Kommandos.** Nur deklarierte Jobs, nur deklarierte Parameter, nur deklarierte Typen. Kein `shell=True`, kein freies Argument-Textfeld.
- **Skripte bleiben idempotent.** Ein Abbruch darf keinen Lauf von vorn beginnen lassen.
- **`ENTITY_TYPES` nur hinten erweitern** — dieser Plan fasst die Liste nicht an.
- Frontend-Tests: `cd frontend && npm test`. Backend-Tests: `.venv/bin/pytest`.

## Dateistruktur

| Datei | Verantwortung |
|---|---|
| `magda/jobs.py` (neu) | Was startbar ist und womit. `build_command` validiert und baut argv. |
| `magda/runs.py` (neu) | Lauf-Historie auf Platte: Metadaten-JSON plus Log je Lauf, listen, lesen, aufräumen. |
| `magda/runner.py` (geändert) | Nur noch Prozess-Lebenszyklus. Delegiert an `jobs` und `runs`. |
| `magda/catalogs.py` (neu) | Katalog-Verzeichnis `catalogs.json`: laden, anlegen, entfernen. |
| `magda/scraping.py` (geändert) | 404-Fallback repariert, `fetch_catalog_meta` und `probe_catalog` neu. |
| `magda/gold.py` (geändert) | `count_by_status()` für die vierte Kennzahlkarte. |
| `magda/config.py` (geändert) | `RUNS_DIR`, `CATALOGS_FILE`. |
| `magda/api.py` (geändert) | Neue Endpunkte; `POST /api/run` nimmt `args` statt `variant`. |
| `frontend/src/features/control/` (neu) | Steuerzentrale: Seite, Formular, Historie, Katalogverwaltung, Konsole, Run-Hook. |
| `frontend/src/features/overview/` (umgebaut) | Diagramm statt Runner, Label-Verteilung, volle Breite. |

---

### Task 1: Job-Katalog mit typisierten Parametern

**Files:**
- Create: `magda/jobs.py`
- Create: `tests/test_jobs.py`

**Interfaces:**
- Consumes: `magda.config.PROJECT_ROOT`
- Produces:
  - `Param(name, kind, label, default=None, choices=(), required=False, help="")` mit Property `key -> str`
  - `Job(script, title, what, params)`
  - `JOBS: dict[str, Job]`
  - `build_command(job: str, values: dict) -> list[str]` — wirft `ValueError`
  - `describe() -> list[dict]` — JSON-fähiger Katalog für die API

- [ ] **Step 1: Write the failing test**

`tests/test_jobs.py`:

```python
"""Der Job-Katalog ist die Sicherheitsgrenze zwischen Frontend und Subprozess."""

import sys

import pytest

from magda import jobs


def test_build_command_setzt_positional_und_option():
    cmd = jobs.build_command("01_download_flyers", {"url": "https://x/?catalogId=1", "max_pages": 5})

    assert cmd[0] == sys.executable
    assert cmd[1] == "-u"
    assert cmd[2].endswith("scripts/01_download_flyers.py")
    assert cmd[3:] == ["https://x/?catalogId=1", "--max-pages", "5"]


def test_build_command_laesst_optionale_parameter_weg():
    cmd = jobs.build_command("01_download_flyers", {"url": "https://x/?catalogId=1"})

    assert "--max-pages" not in cmd


def test_build_command_kennt_alle_pipeline_schritte():
    assert set(jobs.JOBS) == {
        "01_download_flyers", "02_extract_words", "03_label_words",
        "04_train", "05_evaluate", "07_flair_baseline",
    }


def test_build_command_lehnt_unbekannten_job_ab():
    with pytest.raises(ValueError, match="Unbekannter Schritt"):
        jobs.build_command("rm -rf /", {})


def test_build_command_lehnt_unbekannten_parameter_ab():
    with pytest.raises(ValueError, match="Unbekannter Parameter"):
        jobs.build_command("02_extract_words", {"outfile": "/etc/passwd"})


def test_build_command_lehnt_wert_ausserhalb_choices_ab():
    with pytest.raises(ValueError, match="bash"):
        jobs.build_command("04_train", {"variant": "bash"})


def test_build_command_lehnt_falschen_typ_ab():
    with pytest.raises(ValueError, match="Zahl"):
        jobs.build_command("01_download_flyers", {"url": "https://x", "max_pages": "viele"})


def test_build_command_verlangt_pflichtparameter():
    with pytest.raises(ValueError, match="URL"):
        jobs.build_command("01_download_flyers", {})


def test_build_command_lehnt_positional_mit_bindestrich_ab():
    """argparse liest "--help" als Option, nicht als URL – der Lauf täte etwas
    anderes als der Nutzer meint."""
    with pytest.raises(ValueError, match="Bindestrich"):
        jobs.build_command("01_download_flyers", {"url": "--help"})


def test_leerer_wert_zaehlt_wie_nicht_gesetzt():
    """Ein leeres Formularfeld ist keine Eingabe – sonst landet "" im argv."""
    cmd = jobs.build_command("01_download_flyers", {"url": "https://x", "max_pages": ""})

    assert "--max-pages" not in cmd


def test_describe_liefert_json_faehigen_katalog():
    entry = next(j for j in jobs.describe() if j["job"] == "04_train")

    assert entry["title"]
    variant = next(p for p in entry["params"] if p["key"] == "variant")
    assert variant["choices"] == ["gbert", "layoutxlm"]
    assert variant["required"] is True
    epochs = next(p for p in entry["params"] if p["key"] == "epochs")
    assert epochs["default"] == 10
    assert epochs["kind"] == "int"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'magda.jobs'`

- [ ] **Step 3: Write the implementation**

`magda/jobs.py`:

```python
"""Was sich aus dem Frontend starten lässt – und mit welchen Parametern.

Der Runner kümmert sich um Prozesse, dieses Modul um Erlaubnis. `build_command`
ist die einzige Stelle, an der aus einer Nutzereingabe ein Kommando wird, und
damit die Sicherheitsgrenze: unbekannte Jobs, unbekannte Parameternamen, nicht
konvertierbare Werte und Werte außerhalb von `choices` kommen nicht durch.
Werte werden typkonvertiert und als eigene argv-Elemente übergeben, nie zu
einem String zusammengeklebt – es gibt keine Shell, die etwas interpretieren
könnte.

Pfade als config.X zur Laufzeit, damit Tests sie umbiegen können.
"""

import sys
from dataclasses import dataclass, field

from magda import config


@dataclass(frozen=True)
class Param:
    name: str
    kind: str
    label: str
    default: object | None = None
    choices: tuple[str, ...] = ()
    required: bool = False
    help: str = ""

    @property
    def key(self) -> str:
        """Name in JSON und Formular: "--max-pages" -> "max_pages"."""
        return self.name.lstrip("-").replace("-", "_")

    @property
    def positional(self) -> bool:
        return not self.name.startswith("-")


@dataclass(frozen=True)
class Job:
    script: str
    title: str
    what: str
    params: tuple[Param, ...] = field(default_factory=tuple)


VARIANTS = ("gbert", "layoutxlm")

JOBS: dict[str, Job] = {
    "01_download_flyers": Job(
        script="01_download_flyers",
        title="Prospekte laden",
        what="Holt einen Penny-Katalog und legt jede Seite einzeln als PDF in data/raw ab.",
        params=(
            Param("url", "str", "Katalog-URL", required=True,
                  help="Blätterkatalog-Adresse mit catalogId"),
            Param("--max-pages", "int", "Seiten höchstens", default=40),
        ),
    ),
    "02_extract_words": Job(
        script="02_extract_words",
        title="Wörter extrahieren",
        what="PyMuPDF liest Text und Koordinaten aus dem PDF-Textlayer und rendert je ein PNG.",
    ),
    "03_label_words": Job(
        script="03_label_words",
        title="LLM-Labeling",
        what="Ein Vision-Modell markiert Spans auf dem Seitenbild, daraus werden BIO-Tags.",
    ),
    "04_train": Job(
        script="04_train",
        title="Training",
        what="Token-Klassifikation auf den gelabelten Seiten – einmal mit, einmal ohne Layout.",
        params=(
            Param("variant", "choice", "Variante", choices=VARIANTS, required=True),
            Param("--epochs", "int", "Epochen", default=10),
            Param("--batch-size", "int", "Batch-Größe", default=8),
            Param("--lr", "float", "Lernrate", default=5e-5),
        ),
    ),
    "05_evaluate": Job(
        script="05_evaluate",
        title="Evaluation",
        what="Entity-Level-F1 auf dem eingefrorenen Test-Split, als Report nach data/eval.",
        params=(
            Param("variant", "choice", "Variante", choices=VARIANTS, required=True),
            Param("--split", "choice", "Split", choices=("dev", "test"), default="test"),
        ),
    ),
    "07_flair_baseline": Job(
        script="07_flair_baseline",
        title="Flair-Vergleichsarm",
        what="Fertiges deutsches NER-Modell ohne Anpassung. Misst nur BRAND – "
             "flair/ner-german-large kennt PER/LOC/ORG/MISC, nur ORG hat eine Entsprechung.",
        params=(
            Param("--reference", "choice", "Referenz", choices=("gold", "llm"), default="gold"),
            Param("--split", "choice", "Split", choices=("dev", "test", "all"), default="test"),
            Param("--model", "str", "Modell", default="flair/ner-german-large"),
        ),
    ),
}


def _coerce(param: Param, raw: object) -> object:
    if param.kind == "choice":
        text = str(raw)
        if text not in param.choices:
            raise ValueError(
                f"{param.label}: {text!r} ist nicht erlaubt "
                f"({' oder '.join(param.choices)})."
            )
        return text
    if param.kind in ("int", "float"):
        caster = int if param.kind == "int" else float
        try:
            return caster(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(f"{param.label}: {raw!r} ist keine Zahl.") from None
    text = str(raw)
    # argparse liest ein führendes "-" als Option. Ein positionaler Wert wie
    # "--help" würde damit etwas anderes tun, als der Nutzer eingegeben hat.
    if param.positional and text.startswith("-"):
        raise ValueError(f"{param.label} darf nicht mit einem Bindestrich beginnen.")
    return text


def build_command(job: str, values: dict) -> list[str]:
    """Validiert die Eingaben und baut das argv. Wirft ValueError bei allem Unerwarteten."""
    spec = JOBS.get(job)
    if spec is None:
        raise ValueError(f"Unbekannter Schritt: {job}")

    known = {p.key: p for p in spec.params}
    for key in values:
        if key not in known:
            raise ValueError(f"Unbekannter Parameter für {job}: {key}")

    positional: list[str] = []
    options: list[str] = []
    for param in spec.params:
        raw = values.get(param.key, param.default)
        # Ein leeres Formularfeld ist keine Eingabe, sondern eine ausgelassene.
        if raw is None or raw == "":
            if param.required:
                raise ValueError(f"{spec.title}: {param.label} wird gebraucht.")
            continue
        value = str(_coerce(param, raw))
        if param.positional:
            positional.append(value)
        else:
            options += [param.name, value]

    script = config.PROJECT_ROOT / "scripts" / f"{spec.script}.py"
    return [sys.executable, "-u", str(script), *positional, *options]


def describe() -> list[dict]:
    """Der Katalog als JSON für das Frontend, das daraus seine Formulare baut."""
    return [
        {
            "job": job,
            "title": spec.title,
            "what": spec.what,
            "params": [
                {
                    "key": p.key,
                    "label": p.label,
                    "kind": p.kind,
                    "default": p.default,
                    "choices": list(p.choices),
                    "required": p.required,
                    "help": p.help,
                }
                for p in spec.params
            ],
        }
        for job, spec in JOBS.items()
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_jobs.py -v`
Expected: PASS, 11 Tests

- [ ] **Step 5: Commit**

```bash
git add magda/jobs.py tests/test_jobs.py
git commit -m "Beschreibe die Pipeline-Schritte samt Parametern"
```

---

### Task 2: Lauf-Historie auf Platte

**Files:**
- Create: `magda/runs.py`
- Modify: `magda/config.py` (nach `EVAL_DIR` eine Zeile `RUNS_DIR`)
- Create: `tests/test_runs.py`

**Interfaces:**
- Consumes: `magda.config.RUNS_DIR`
- Produces:
  - `new_run_id(job: str, when: datetime | None = None) -> str`
  - `write_meta(run_id: str, meta: dict) -> None`
  - `log_path(run_id: str) -> Path`
  - `list_runs(limit: int = 100) -> list[dict]` — neueste zuerst
  - `read_run(run_id: str) -> dict | None` — Metadaten plus `"log"`
  - `prune(keep: int = 100) -> None`

- [ ] **Step 1: Write the failing test**

`tests/test_runs.py`:

```python
"""Die Historie ist der einzige Ort, an dem ein Lauf nach dem Backend-Neustart
noch nachvollziehbar ist."""

import json
from datetime import datetime

import pytest

from magda import config, runs


@pytest.fixture(autouse=True)
def runs_dir(tmp_path, monkeypatch):
    d = tmp_path / "runs"
    monkeypatch.setattr(config, "RUNS_DIR", d)
    return d


def _record(job: str, when: datetime, exit_code: int = 0, log: str = "") -> str:
    run_id = runs.new_run_id(job, when)
    runs.write_meta(run_id, {
        "run_id": run_id, "job": job, "args": {}, "command": ["python", f"{job}.py"],
        "started": when.isoformat(timespec="seconds"), "finished": None,
        "exit_code": exit_code, "duration": 1.0,
    })
    runs.log_path(run_id).write_text(log)
    return run_id


def test_run_id_enthaelt_zeit_und_job():
    run_id = runs.new_run_id("04_train", datetime(2026, 7, 29, 14, 22, 1))

    assert run_id == "20260729-142201_04_train"


def test_run_id_weicht_bei_kollision_aus():
    when = datetime(2026, 7, 29, 14, 22, 1)
    first = _record("04_train", when)
    second = runs.new_run_id("04_train", when)

    assert second != first


def test_write_meta_legt_verzeichnis_an():
    run_id = _record("02_extract_words", datetime(2026, 7, 29, 10, 0, 0))

    with open(config.RUNS_DIR / f"{run_id}.json") as f:
        assert json.load(f)["job"] == "02_extract_words"


def test_list_runs_sortiert_neueste_zuerst():
    _record("02_extract_words", datetime(2026, 7, 29, 10, 0, 0))
    _record("04_train", datetime(2026, 7, 29, 12, 0, 0))

    assert [r["job"] for r in runs.list_runs()] == ["04_train", "02_extract_words"]


def test_list_runs_ohne_verzeichnis_ist_leer():
    assert runs.list_runs() == []


def test_list_runs_ueberspringt_kaputte_datei():
    _record("04_train", datetime(2026, 7, 29, 12, 0, 0))
    (config.RUNS_DIR / "20260729-090000_kaputt.json").write_text("{nicht json")

    assert [r["job"] for r in runs.list_runs()] == ["04_train"]


def test_read_run_liefert_log_dazu():
    run_id = _record("01_download_flyers", datetime(2026, 7, 29, 9, 0, 0), 2, "error: url fehlt")

    entry = runs.read_run(run_id)

    assert entry["exit_code"] == 2
    assert entry["log"] == "error: url fehlt"


def test_read_run_lehnt_pfadangaben_ab():
    """run_id ist ein opaker Schlüssel, kein Pfad."""
    assert runs.read_run("../../etc/passwd") is None
    assert runs.read_run("unbekannt") is None


def test_prune_behaelt_die_juengsten():
    for minute in range(5):
        _record("02_extract_words", datetime(2026, 7, 29, 10, minute, 0))

    runs.prune(keep=2)

    remaining = [r["run_id"] for r in runs.list_runs()]
    assert len(remaining) == 2
    assert remaining[0].startswith("20260729-1004")
    # Der Log verschwindet mit den Metadaten, sonst wächst das Verzeichnis weiter.
    assert len(list(config.RUNS_DIR.glob("*.log"))) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_runs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'magda.runs'`

- [ ] **Step 3: Add the config path**

In `magda/config.py`, direkt nach der `EVAL_DIR`-Zeile einfügen:

```python
RUNS_DIR = DATA_DIR / "runs"        # Lauf-Historie: je Lauf Metadaten-JSON + Log
```

- [ ] **Step 4: Write the implementation**

`magda/runs.py`:

```python
"""Lauf-Historie auf Platte.

Je Lauf zwei Dateien: ein kleines Metadaten-JSON und der vollständige Log.
Getrennt, weil ein Trainingslauf zehntausende Zeilen schreibt – die Liste in
der Steuerzentrale liest nur die JSON-Dateien und bleibt schnell. Der
Ringpuffer in runner.py bleibt für die Live-Ansicht; hier steht alles.

Pfade als config.X zur Laufzeit, damit Tests sie umbiegen können.
"""

import json
from datetime import datetime
from pathlib import Path

from magda import config


def new_run_id(job: str, when: datetime | None = None) -> str:
    """Sortierbarer Schlüssel aus Zeit und Job. Weicht aus, wenn er schon existiert."""
    stamp = (when or datetime.now()).strftime("%Y%m%d-%H%M%S")
    base = f"{stamp}_{job}"
    run_id, suffix = base, 2
    while (config.RUNS_DIR / f"{run_id}.json").exists():
        run_id = f"{base}-{suffix}"
        suffix += 1
    return run_id


def log_path(run_id: str) -> Path:
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return config.RUNS_DIR / f"{run_id}.log"


def write_meta(run_id: str, meta: dict) -> None:
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.RUNS_DIR / f"{run_id}.json", "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


def list_runs(limit: int = 100) -> list[dict]:
    """Metadaten aller Läufe, neueste zuerst. Der run_id sortiert lexikografisch
    richtig, weil er mit dem Zeitstempel beginnt."""
    entries = []
    if not config.RUNS_DIR.exists():
        return entries
    for meta_file in sorted(config.RUNS_DIR.glob("*.json"), reverse=True):
        try:
            with open(meta_file) as f:
                entries.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            # Ein abgebrochener Schreibvorgang darf nicht die ganze Liste kosten.
            continue
        if len(entries) >= limit:
            break
    return entries


def read_run(run_id: str) -> dict | None:
    """Metadaten samt vollständigem Log. None, wenn es den Lauf nicht gibt.

    run_id wird gegen die vorhandenen Dateien abgeglichen statt an Path
    übergeben – sonst wäre "../../etc/passwd" ein gültiger Schlüssel.
    """
    if not config.RUNS_DIR.exists():
        return None
    known = {p.stem for p in config.RUNS_DIR.glob("*.json")}
    if run_id not in known:
        return None
    with open(config.RUNS_DIR / f"{run_id}.json") as f:
        meta = json.load(f)
    log_file = config.RUNS_DIR / f"{run_id}.log"
    meta["log"] = log_file.read_text() if log_file.exists() else ""
    return meta


def prune(keep: int = 100) -> None:
    """Wirft die ältesten Läufe weg. data/ ist gitignored, aber nicht unbegrenzt."""
    if not config.RUNS_DIR.exists():
        return
    meta_files = sorted(config.RUNS_DIR.glob("*.json"), reverse=True)
    for meta_file in meta_files[keep:]:
        meta_file.unlink(missing_ok=True)
        meta_file.with_suffix(".log").unlink(missing_ok=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_runs.py -v`
Expected: PASS, 9 Tests

- [ ] **Step 6: Commit**

```bash
git add magda/runs.py magda/config.py tests/test_runs.py
git commit -m "Halte jeden Pipeline-Lauf auf der Platte fest"
```

---

### Task 3: Runner auf Job-Katalog und Historie umstellen

**Files:**
- Modify: `magda/runner.py` (vollständig ersetzt)
- Create: `tests/test_runner.py`

**Interfaces:**
- Consumes: `jobs.build_command(job, values) -> list[str]`, `jobs.JOBS`, `runs.new_run_id`, `runs.write_meta`, `runs.log_path`, `runs.prune`
- Produces:
  - `start(job: str, args: dict | None = None) -> None` — wirft `ValueError` (ungültige Eingabe) und `RuntimeError` (läuft schon)
  - `stop() -> None`
  - `status() -> dict` mit `running`, `job`, `args`, `run_id`, `lines`, `exit_code`, `elapsed`
  - `reset() -> None` (nur Tests)

- [ ] **Step 1: Write the failing test**

`tests/test_runner.py`:

```python
"""Der Runner startet nur, was jobs.py erlaubt – und schreibt jeden Lauf mit."""

import time

import pytest

from magda import config, runner, runs


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    runner.reset()
    yield
    runner.stop()
    runner.reset()


def _wait_until_done(timeout: float = 10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not runner.status()["running"]:
            return runner.status()
        time.sleep(0.05)
    raise AssertionError("Lauf wurde nicht fertig")


def test_start_lehnt_unbekannten_job_ab():
    with pytest.raises(ValueError, match="Unbekannter Schritt"):
        runner.start("rm -rf /")


def test_start_lehnt_unbekannten_parameter_ab():
    with pytest.raises(ValueError, match="Unbekannter Parameter"):
        runner.start("02_extract_words", {"outfile": "/etc/passwd"})


def test_start_verlangt_pflichtparameter():
    with pytest.raises(ValueError, match="URL"):
        runner.start("01_download_flyers", {})


def test_status_ist_leer_ohne_lauf():
    assert runner.status() == {
        "running": False, "job": None, "args": {}, "run_id": None,
        "lines": [], "exit_code": None, "elapsed": None,
    }


def test_lauf_landet_in_der_historie():
    """02_extract_words bricht ohne data/raw sofort ab – genau deshalb taugt es
    als schneller Testlauf: echter Subprozess, echter Exit-Code, kein Netz."""
    runner.start("02_extract_words")
    state = _wait_until_done()

    assert state["exit_code"] is not None
    history = runs.list_runs()
    assert len(history) == 1
    assert history[0]["job"] == "02_extract_words"
    assert history[0]["command"][-1].endswith("02_extract_words.py")
    assert history[0]["exit_code"] == state["exit_code"]
    assert runs.read_run(history[0]["run_id"])["log"] != ""


def test_zweiter_lauf_waehrend_eines_laufs_wird_abgelehnt():
    runner.start("02_extract_words")
    try:
        with pytest.raises(RuntimeError, match="läuft bereits"):
            runner.start("02_extract_words")
    finally:
        _wait_until_done()


def test_args_stehen_im_status_und_in_der_historie():
    runner.start("02_extract_words")
    _wait_until_done()

    assert runs.list_runs()[0]["args"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_runner.py -v`
Expected: FAIL — `TypeError: start() takes ... ` beziehungsweise `KeyError: 'args'` im Status

- [ ] **Step 3: Rewrite the runner**

`magda/runner.py` vollständig ersetzen:

```python
"""Pipeline-Schritte aus dem Frontend starten.

Dieses Modul kümmert sich um den Prozess-Lebenszyklus. *Was* startbar ist und
mit welchen Parametern, steht in jobs.py – und nur dort wird aus einer
Nutzereingabe ein Kommando. Es gibt keinen Weg, hier etwas Beliebiges
durchzureichen: die API ist ein Komfort-Knopf für das lokale Forschungssetup,
kein Remote-Shell-Ersatz.

Es läuft höchstens ein Job gleichzeitig. Die Skripte sind idempotent, ein
Abbruch ist also folgenlos: der nächste Lauf macht dort weiter, wo der
abgebrochene aufgehört hat.

Der Ringpuffer hält die letzten Zeilen für die Live-Ansicht; vollständig steht
jeder Lauf über runs.py auf der Platte.
"""

import subprocess
import threading
import time
from collections import deque
from datetime import datetime

from magda import config, jobs, runs

# Ringpuffer: bei mehreren tausend Seiten läuft die Live-Ansicht sonst voll.
_MAX_LINES = 400


class _State:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.job: str | None = None
        self.args: dict = {}
        self.run_id: str | None = None
        self.lines: deque[str] = deque(maxlen=_MAX_LINES)
        self.exit_code: int | None = None
        self.started_at: float | None = None


_state = _State()
_lock = threading.Lock()


def _pump(process: subprocess.Popen, lines: deque[str], run_id: str, meta: dict) -> None:
    """Liest stdout zeilenweise in Ringpuffer und Logdatei, bis der Prozess endet."""
    assert process.stdout is not None
    with open(runs.log_path(run_id), "w") as log:
        for raw in process.stdout:
            line = raw.rstrip("\n")
            lines.append(line)
            log.write(raw)
            log.flush()
    process.wait()
    with _lock:
        _state.exit_code = process.returncode
    meta["exit_code"] = process.returncode
    meta["finished"] = datetime.now().isoformat(timespec="seconds")
    meta["duration"] = round(time.time() - meta["_started_monotonic"], 1)
    del meta["_started_monotonic"]
    runs.write_meta(run_id, meta)
    runs.prune()


def start(job: str, args: dict | None = None) -> None:
    """Startet einen Pipeline-Schritt.

    ValueError bei ungültiger Eingabe, RuntimeError wenn schon etwas läuft.
    """
    values = dict(args or {})
    # Erst validieren, dann sperren: eine abgelehnte Eingabe soll den laufenden
    # Job nicht einmal berühren.
    command = jobs.build_command(job, values)

    with _lock:
        if _state.process is not None and _state.process.poll() is None:
            raise RuntimeError(f"Es läuft bereits ein Schritt: {_state.job}")

        started = datetime.now()
        run_id = runs.new_run_id(job, started)
        process = subprocess.Popen(
            command,
            cwd=config.PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _state.process = process
        _state.job = job
        _state.args = values
        _state.run_id = run_id
        _state.lines = deque(maxlen=_MAX_LINES)
        _state.exit_code = None
        _state.started_at = time.time()

    meta = {
        "run_id": run_id,
        "job": job,
        "title": jobs.JOBS[job].title,
        "args": values,
        "command": command,
        "started": started.isoformat(timespec="seconds"),
        "finished": None,
        "exit_code": None,
        "duration": None,
        "_started_monotonic": time.time(),
    }
    # Schon vor dem ersten Ausgabezeichen schreiben: ein Lauf, der das Backend
    # mit sich reißt, taucht sonst nirgends auf.
    runs.write_meta(run_id, {k: v for k, v in meta.items() if k != "_started_monotonic"})

    threading.Thread(
        target=_pump, args=(process, _state.lines, run_id, meta), daemon=True
    ).start()


def stop() -> None:
    with _lock:
        if _state.process is not None and _state.process.poll() is None:
            _state.process.terminate()


def status() -> dict:
    with _lock:
        running = _state.process is not None and _state.process.poll() is None
        return {
            "running": running,
            "job": _state.job,
            "args": dict(_state.args),
            "run_id": _state.run_id,
            "lines": list(_state.lines),
            "exit_code": None if running else _state.exit_code,
            "elapsed": round(time.time() - _state.started_at, 1) if _state.started_at else None,
        }


def reset() -> None:
    """Verwirft den Zustand. Nur für Tests – Produktivpfade brauchen das nicht."""
    global _state
    _state = _State()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_runner.py -v`
Expected: PASS, 7 Tests

- [ ] **Step 5: Run the whole backend suite**

Run: `.venv/bin/pytest`
Expected: PASS — aber aus dem falschen Grund. `api.py` ruft bis Task 5 noch
`runner.start(req.job, req.variant)` auf; ein String statt eines Dicts scheitert
in `dict("bash")` mit `ValueError` und die API antwortet zufällig mit demselben
400 wie vorher. Nicht als Bestätigung lesen — Task 5 stellt den Aufruf gerade.

- [ ] **Step 6: Commit**

```bash
git add magda/runner.py tests/test_runner.py
git commit -m "Reiche typisierte Parameter an die Pipeline-Schritte durch"
```

---

### Task 4: Scraping reparieren und Katalog-Verzeichnis

**Files:**
- Modify: `magda/scraping.py:23-42` (`get_catalog_version` wird auf `fetch_catalog_meta` zurückgeführt), neue Funktion `probe_catalog`
- Create: `magda/catalogs.py`
- Modify: `magda/config.py` (Zeile `CATALOGS_FILE` bei `GOLD_DIR`)
- Create: `tests/test_catalogs.py`

**Interfaces:**
- Produces:
  - `scraping.fetch_catalog_meta(catalog_id, session) -> dict` mit `found`, `version`, `title`
  - `scraping.probe_catalog(url, session) -> dict` mit `catalog_id`, `version`, `title`, `meta_found`, `page_1_status`, `page_1_bytes`
  - `catalogs.Registry(entries: list[dict], error: str | None)` (NamedTuple)
  - `catalogs.load() -> Registry`
  - `catalogs.add(entry: dict) -> dict` — wirft `KeyError` bei Duplikat
  - `catalogs.remove(catalog_id: str) -> bool`

- [ ] **Step 1: Write the failing test**

`tests/test_catalogs.py`:

```python
"""Katalog-Verzeichnis und der reparierte Versions-Fallback.

Kein Netz: die Tests fahren eine gefälschte requests.Session.
"""

import json

import pytest

from magda import catalogs, config, scraping


class _FakeResponse:
    def __init__(self, status_code=200, text="", content=b""):
        self.status_code = status_code
        self.text = text
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSession:
    def __init__(self, routes: dict):
        self.routes = routes
        self.seen: list[str] = []

    def get(self, url, timeout=None):
        self.seen.append(url)
        for fragment, response in self.routes.items():
            if fragment in url:
                return response
        return _FakeResponse(404)


@pytest.fixture(autouse=True)
def registry_file(tmp_path, monkeypatch):
    path = tmp_path / "catalogs.json"
    monkeypatch.setattr(config, "CATALOGS_FILE", path)
    return path


# --- scraping ---------------------------------------------------------------


def test_version_faellt_bei_404_auf_eins_zurueck():
    """Für Katalog 1342881 ist getcatalog.do inzwischen 404, die PDFs liegen aber
    noch da. raise_for_status() hätte den dokumentierten Fallback nie erreicht."""
    session = _FakeSession({})

    assert scraping.get_catalog_version("1342881", session) == "1"


def test_version_wirft_bei_serverfehler():
    session = _FakeSession({"getcatalog": _FakeResponse(500)})

    with pytest.raises(RuntimeError):
        scraping.get_catalog_version("1342881", session)


def test_meta_liest_version_und_titel():
    html = "<html><title>KW32 34835 SUEDBAYERN</title>catalogVersion = '2'</html>"
    session = _FakeSession({"getcatalog": _FakeResponse(200, html)})

    meta = scraping.fetch_catalog_meta("1350000", session)

    assert meta == {"found": True, "version": "2", "title": "KW32 34835 SUEDBAYERN"}


def test_probe_meldet_erreichbare_seite():
    html = "<html><title>KW33 NORD</title>catalogVersion = '1'</html>"
    session = _FakeSession({
        "getcatalog": _FakeResponse(200, html),
        "bk_1.pdf": _FakeResponse(200, content=b"x" * 4096),
    })

    probe = scraping.probe_catalog("https://x/?catalogId=1351234", session)

    assert probe["catalog_id"] == "1351234"
    assert probe["title"] == "KW33 NORD"
    assert probe["page_1_status"] == 200
    assert probe["page_1_bytes"] == 4096


def test_probe_meldet_gesperrte_seite():
    html = "<html><title>KW32</title>catalogVersion = '1'</html>"
    session = _FakeSession({
        "getcatalog": _FakeResponse(200, html),
        "bk_1.pdf": _FakeResponse(403),
    })

    probe = scraping.probe_catalog("https://x/?catalogId=1350000", session)

    assert probe["page_1_status"] == 403
    assert probe["page_1_bytes"] == 0


# --- Verzeichnis ------------------------------------------------------------


def test_load_ohne_datei_ist_leer():
    assert catalogs.load() == catalogs.Registry(entries=[], error=None)


def test_add_und_load():
    catalogs.add({"id": "1342881", "url": "https://x/?catalogId=1342881", "title": "KW30"})

    registry = catalogs.load()

    assert registry.error is None
    assert registry.entries[0]["id"] == "1342881"
    assert registry.entries[0]["added"] is not None


def test_add_lehnt_duplikat_ab():
    catalogs.add({"id": "1342881", "url": "https://x", "title": "KW30"})

    with pytest.raises(KeyError):
        catalogs.add({"id": "1342881", "url": "https://x", "title": "KW30 nochmal"})


def test_remove():
    catalogs.add({"id": "1342881", "url": "https://x", "title": "KW30"})

    assert catalogs.remove("1342881") is True
    assert catalogs.load().entries == []
    assert catalogs.remove("1342881") is False


def test_kaputte_datei_ergibt_leeres_verzeichnis_mit_fehler(registry_file):
    """catalogs.json wird gemergt – ein Konfliktmarker ist der wahrscheinlichste
    Fehlerfall und darf nicht die ganze Seite mitreißen."""
    registry_file.write_text("<<<<<<< HEAD\n[]\n=======")

    registry = catalogs.load()

    assert registry.entries == []
    assert "catalogs.json" in registry.error


def test_schreiben_ist_atomar(registry_file):
    catalogs.add({"id": "1", "url": "https://x", "title": "a"})
    catalogs.add({"id": "2", "url": "https://y", "title": "b"})

    with open(registry_file) as f:
        assert len(json.load(f)) == 2
    # Keine Temp-Reste neben der Datei.
    assert list(registry_file.parent.glob(".catalogs*")) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_catalogs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'magda.catalogs'`

- [ ] **Step 3: Add the config path**

In `magda/config.py`, direkt nach der `GOLD_DIR`-Zeile:

```python
# Katalog-Verzeichnis: gefundene Blätterkatalog-IDs. Versioniert wie gold/ –
# eine ID lässt sich nicht reproduzieren, nur wiederfinden.
CATALOGS_FILE = PROJECT_ROOT / "catalogs.json"
```

- [ ] **Step 4: Rework scraping**

In `magda/scraping.py` die Funktion `get_catalog_version` (Zeilen 23–42) durch Folgendes ersetzen und `probe_catalog` anhängen:

```python
def fetch_catalog_meta(catalog_id: str, session: requests.Session) -> dict:
    """Version und Titel aus der getcatalog-Seite.

    Ein 404 ist hier kein Fehler: geprüft am 29.07.2026 liefert die Seite für
    Katalog 1342881 längst 404, während die PDFs weiter abrufbar sind – die
    Metadatenseite läuft früher ab als der Inhalt. Fallback "1" hat bisher
    immer funktioniert. Bei 5xx wird dagegen geworfen: ein ausgefallener Server
    ist etwas anderes als eine abgelaufene Seite.

    Die Version steckt je nach Katalog an unterschiedlichen Stellen im HTML,
    daher zwei Regex-Versuche.
    """
    url = f"{CATALOG_BASE}?catalogId={catalog_id}"
    resp = session.get(url, timeout=15)
    if resp.status_code == 404:
        return {"found": False, "version": "1", "title": None}
    resp.raise_for_status()

    version = "1"
    match = re.search(r"catalogVersion\s*[=:]\s*['\"]?(\d+)['\"]?", resp.text)
    if match:
        version = match.group(1)
    else:
        match = re.search(rf"/catalogs/{catalog_id}/(\d+)/pdf/", resp.text)
        if match:
            version = match.group(1)

    title = re.search(r"<title>(.*?)</title>", resp.text, re.S)
    return {
        "found": True,
        "version": version,
        "title": title.group(1).strip() if title else None,
    }


def get_catalog_version(catalog_id: str, session: requests.Session) -> str:
    return fetch_catalog_meta(catalog_id, session)["version"]


def probe_catalog(url: str, session: requests.Session) -> dict:
    """Was bekäme man, wenn man diesen Katalog lädt?

    Prüft Metadaten und Seite 1, ohne etwas zu speichern. Damit ein
    unerreichbarer Katalog vor dem Lauf auffällt statt als Exit-Code danach.
    """
    catalog_id = extract_catalog_id(url)
    meta = fetch_catalog_meta(catalog_id, session)
    pdf_url = f"{PDF_BASE}/{catalog_id}/{meta['version']}/pdf/save/bk_1.pdf"
    resp = session.get(pdf_url, timeout=30)
    return {
        "catalog_id": catalog_id,
        "version": meta["version"],
        "title": meta["title"],
        "meta_found": meta["found"],
        "page_1_status": resp.status_code,
        "page_1_bytes": len(resp.content) if resp.status_code == 200 else 0,
    }
```

- [ ] **Step 5: Write the registry**

`magda/catalogs.py`:

```python
"""Verzeichnis gefundener Blätterkatalog-IDs.

Liegt als catalogs.json im Projektwurzelverzeichnis und ist versioniert –
dieselbe Begründung wie bei gold/: eine Katalog-ID lässt sich nicht erzeugen,
nur wiederfinden, und die Suche danach kostet Zeit. Geteilt wird deshalb das
Ergebnis, nicht der Weg dorthin.

Geschrieben wird atomar, gelesen fehlertolerant: Die Datei wird gemergt, ein
Konfliktmarker darin ist der wahrscheinlichste Fehlerfall überhaupt und darf
nicht die Steuerzentrale lahmlegen.
"""

import json
import os
import tempfile
from datetime import datetime
from typing import NamedTuple

from magda import config


class Registry(NamedTuple):
    entries: list[dict]
    error: str | None


def load() -> Registry:
    if not config.CATALOGS_FILE.exists():
        return Registry(entries=[], error=None)
    try:
        with open(config.CATALOGS_FILE) as f:
            entries = json.load(f)
        if not isinstance(entries, list):
            raise ValueError("kein JSON-Array")
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        return Registry(
            entries=[],
            error=f"catalogs.json ist nicht lesbar ({exc}). Merge-Konflikt?",
        )
    return Registry(entries=entries, error=None)


def _save(entries: list[dict]) -> None:
    """Erst in eine Nachbardatei, dann per os.replace umhängen – ein Abbruch
    mitten im Schreiben hinterlässt sonst einen Torso statt der Vorfassung."""
    directory = config.CATALOGS_FILE.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".catalogs.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
        # mkstemp legt 0600 an und os.replace nimmt den Modus mit; die Datei
        # wird aber geteilt und versioniert.
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, config.CATALOGS_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise


def add(entry: dict) -> dict:
    """Legt einen Eintrag an. KeyError, wenn die ID schon im Verzeichnis steht."""
    registry = load()
    if registry.error:
        raise ValueError(registry.error)
    if any(e.get("id") == entry["id"] for e in registry.entries):
        raise KeyError(f"Katalog {entry['id']} steht schon im Verzeichnis.")

    record = {
        "id": entry["id"],
        "url": entry.get("url", ""),
        "title": entry.get("title") or "",
        "version": entry.get("version") or "1",
        "pages": entry.get("pages"),
        "added": datetime.now().isoformat(timespec="seconds"),
        "added_by": entry.get("added_by", ""),
        "note": entry.get("note", ""),
    }
    _save([*registry.entries, record])
    return record


def remove(catalog_id: str) -> bool:
    """True, wenn etwas entfernt wurde."""
    registry = load()
    if registry.error:
        raise ValueError(registry.error)
    remaining = [e for e in registry.entries if e.get("id") != catalog_id]
    if len(remaining) == len(registry.entries):
        return False
    _save(remaining)
    return True
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_catalogs.py -v`
Expected: PASS, 12 Tests

- [ ] **Step 7: Commit**

```bash
git add magda/catalogs.py magda/scraping.py magda/config.py tests/test_catalogs.py
git commit -m "Merke gefundene Kataloge und ueberlebe abgelaufene Metadatenseiten"
```

---

### Task 5: API-Endpunkte

**Files:**
- Modify: `magda/api.py` (`start_run` umgebaut, neue Endpunkte am Ende)
- Modify: `magda/gold.py` (`count_by_status`)
- Modify: `tests/test_api.py:209-231` (Run-Tests auf `args` umgestellt) plus neue Tests

**Interfaces:**
- Consumes: `jobs.describe()`, `runner.start(job, args)`, `runs.list_runs()`, `runs.read_run(id)`, `catalogs.load/add/remove`, `scraping.probe_catalog`
- Produces: `GET /api/jobs`, `POST /api/run` (`{job, args}`), `GET /api/runs`, `GET /api/runs/{run_id}`, `GET /api/catalogs`, `POST /api/catalogs`, `DELETE /api/catalogs/{catalog_id}`, `POST /api/catalogs/probe`, `GET /api/labels/distribution`; `GET /api/status` mit `gold_done` und `gold_in_progress` in `totals`

- [ ] **Step 1: Write the failing tests**

Zuerst in `tests/test_api.py` die Fixture erweitern — `CATALOGS_FILE` und `RUNS_DIR` gehören dazu, sonst schreiben Tests ins echte Repo:

```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("RAW_DIR", "WORDS_DIR", "IMAGES_DIR", "LABELED_DIR", "EVAL_DIR", "CHECKPOINTS_DIR", "GOLD_DIR", "RUNS_DIR"):
        d = tmp_path / name.lower()
        d.mkdir()
        monkeypatch.setattr(config, name, d)
    monkeypatch.setattr(config, "CATALOGS_FILE", tmp_path / "catalogs.json")
    return TestClient(api.app)
```

Dann die beiden vorhandenen Run-Tests (Zeilen 216–227) ersetzen und die neuen anhängen:

```python
def test_run_lehnt_ungueltige_variante_ab(client, clean_runner):
    resp = client.post("/api/run", json={"job": "04_train", "args": {"variant": "bash"}})
    assert resp.status_code == 400


def test_run_verlangt_variante_wo_noetig(client, clean_runner):
    resp = client.post("/api/run", json={"job": "05_evaluate", "args": {}})
    assert resp.status_code == 400


def test_run_lehnt_unbekannten_parameter_ab(client, clean_runner):
    resp = client.post("/api/run", json={"job": "02_extract_words", "args": {"outfile": "/etc/passwd"}})
    assert resp.status_code == 400


def test_jobs_liefert_den_katalog(client):
    body = client.get("/api/jobs").json()

    jobs_by_name = {j["job"]: j for j in body}
    assert "07_flair_baseline" in jobs_by_name
    url_param = next(p for p in jobs_by_name["01_download_flyers"]["params"] if p["key"] == "url")
    assert url_param["required"] is True


def test_runs_ist_leer_ohne_laeufe(client):
    assert client.get("/api/runs").json() == []


def test_runs_liefert_historie_und_detail(client):
    from magda import runs

    runs.write_meta("20260729-120000_04_train", {
        "run_id": "20260729-120000_04_train", "job": "04_train", "args": {"variant": "gbert"},
        "command": ["python", "04_train.py"], "started": "2026-07-29T12:00:00",
        "finished": "2026-07-29T12:08:00", "exit_code": 0, "duration": 480.0,
    })
    runs.log_path("20260729-120000_04_train").write_text("Epoch 1/10")

    listing = client.get("/api/runs").json()
    assert listing[0]["job"] == "04_train"

    detail = client.get("/api/runs/20260729-120000_04_train").json()
    assert detail["log"] == "Epoch 1/10"


def test_run_detail_lehnt_pfadangabe_ab(client):
    assert client.get("/api/runs/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_catalogs_anlegen_listen_entfernen(client):
    created = client.post("/api/catalogs", json={
        "id": "1342881", "url": "https://x/?catalogId=1342881", "title": "KW30", "version": "1",
    })
    assert created.status_code == 200

    body = client.get("/api/catalogs").json()
    assert body["error"] is None
    assert body["entries"][0]["id"] == "1342881"

    assert client.delete("/api/catalogs/1342881").status_code == 200
    assert client.get("/api/catalogs").json()["entries"] == []


def test_catalogs_lehnt_duplikat_ab(client):
    payload = {"id": "1342881", "url": "https://x", "title": "KW30", "version": "1"}
    client.post("/api/catalogs", json=payload)

    assert client.post("/api/catalogs", json=payload).status_code == 409


def test_catalogs_zaehlt_lokale_seiten(client):
    (config.RAW_DIR / "1342881").mkdir()
    (config.RAW_DIR / "1342881" / "bk_1.pdf").write_bytes(b"x")
    client.post("/api/catalogs", json={"id": "1342881", "url": "https://x", "title": "KW30"})

    assert client.get("/api/catalogs").json()["entries"][0]["local_pages"] == 1


def test_probe_meldet_fehler_lesbar(client, monkeypatch):
    def boom(url, session):
        raise ValueError("Keine catalogId in URL gefunden: kaputt")

    monkeypatch.setattr(api.scraping, "probe_catalog", boom)

    resp = client.post("/api/catalogs/probe", json={"url": "kaputt"})

    assert resp.status_code == 400
    assert "catalogId" in resp.json()["detail"]


def test_status_zaehlt_gold(client):
    _write_words("462828_p1")
    with open(config.GOLD_DIR / "462828_p1.json", "w") as f:
        json.dump({"page_id": "462828_p1", "status": "done", "spans": []}, f)
    with open(config.GOLD_DIR / "462828_p2.json", "w") as f:
        json.dump({"page_id": "462828_p2", "status": "in_progress", "spans": []}, f)

    totals = client.get("/api/status").json()["totals"]

    assert totals["gold_done"] == 1
    assert totals["gold_in_progress"] == 1


def test_label_verteilung_zaehlt_entities(client):
    with open(config.LABELED_DIR / "462828_p1.json", "w") as f:
        json.dump({"tags": ["B-PRODUCT", "I-PRODUCT", "B-PRICE", "O", "B-PRODUCT"]}, f)

    body = client.get("/api/labels/distribution").json()

    assert body["pages"] == 1
    assert body["counts"]["PRODUCT"] == 2
    assert body["counts"]["PRICE"] == 1
    assert body["total"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_api.py -v`
Expected: FAIL — 404 für `/api/jobs`, `/api/runs`, `/api/catalogs`, `/api/labels/distribution`; `KeyError: 'gold_done'`

- [ ] **Step 3: Add the gold counter**

Am Ende von `magda/gold.py` anhängen:

```python
def count_by_status() -> dict[str, int]:
    """Wie viele Gold-Dateien in welchem Zustand? Für die Kennzahlkarte.

    Zählt nur die Statusfelder, ohne die Wortlisten zu laden – load_gold_pages
    wäre für eine Zahl auf der Startseite zu teuer.
    """
    counts = {"done": 0, "in_progress": 0, "broken": 0}
    if not config.GOLD_DIR.exists():
        return counts
    for gold_file in config.GOLD_DIR.glob("*.json"):
        try:
            with open(gold_file) as f:
                status = json.load(f).get("status", "in_progress")
        except (json.JSONDecodeError, OSError):
            counts["broken"] += 1
            continue
        if status in counts:
            counts[status] += 1
    return counts
```

- [ ] **Step 4: Rework the API**

In `magda/api.py` den Import-Block ergänzen:

```python
from magda import catalogs, config, jobs, runner, runs, scraping
from magda.gold import count_by_status, words_hash
```

`RunRequest` und `start_run` (Zeilen 189–202) ersetzen:

```python
class RunRequest(BaseModel):
    job: str
    args: dict = {}


@app.post("/api/run")
def start_run(req: RunRequest):
    try:
        runner.start(req.job, req.args)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return runner.status()


@app.get("/api/jobs")
def get_jobs():
    """Der Job-Katalog. Das Frontend baut seine Formulare daraus, damit ein
    neuer Parameter nicht an zwei Stellen gepflegt werden muss."""
    return jobs.describe()


@app.get("/api/runs")
def list_runs():
    return runs.list_runs()


@app.get("/api/runs/{run_id}")
def get_run_detail(run_id: str):
    entry = runs.read_run(run_id)
    if entry is None:
        raise HTTPException(404, f"Unbekannter Lauf: {run_id}")
    return entry
```

In `get_status` die `totals`-Zeile (Zeile 91) ersetzen:

```python
    totals = {k: sum(c[k] for c in rows) for k in ("raw", "words", "images", "labeled")}
    gold_counts = count_by_status()
    totals["gold_done"] = gold_counts["done"]
    totals["gold_in_progress"] = gold_counts["in_progress"]
    return {"catalogs": rows, "totals": totals}
```

Am Ende von `api.py` anhängen:

```python
# ---------------------------------------------------------------------------
# Katalog-Verzeichnis (versioniert, catalogs.json)
# ---------------------------------------------------------------------------


class CatalogEntry(BaseModel):
    id: str
    url: str = ""
    title: str = ""
    version: str = "1"
    pages: int | None = None
    added_by: str = ""
    note: str = ""


class ProbeRequest(BaseModel):
    url: str


@app.get("/api/catalogs")
def list_catalogs():
    """Verzeichnis samt lokal vorhandener Seitenzahl – erst damit sieht man,
    welcher eingetragene Katalog auch heruntergeladen ist."""
    registry = catalogs.load()
    entries = [
        {**entry, "local_pages": len(list((config.RAW_DIR / entry["id"]).glob("bk_*.pdf")))}
        for entry in registry.entries
    ]
    return {"entries": entries, "error": registry.error}


@app.post("/api/catalogs")
def add_catalog(entry: CatalogEntry):
    try:
        return catalogs.add(entry.model_dump())
    except KeyError as e:
        raise HTTPException(409, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.delete("/api/catalogs/{catalog_id}")
def delete_catalog(catalog_id: str):
    try:
        removed = catalogs.remove(catalog_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if not removed:
        raise HTTPException(404, f"Unbekannter Katalog: {catalog_id}")
    return {"removed": catalog_id}


@app.post("/api/catalogs/probe")
def probe_catalog(req: ProbeRequest):
    """Prüft eine Katalog-URL, ohne etwas zu laden.

    Netzfehler werden zu 400: für den Nutzer ist eine unerreichbare URL eine
    fehlerhafte Eingabe, kein Serverfehler.
    """
    import requests

    try:
        return scraping.probe_catalog(req.url, requests.Session())
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Katalog nicht erreichbar: {e}")


@app.get("/api/labels/distribution")
def get_label_distribution():
    """Wie oft kommt welcher Entity-Typ in data/labeled/ vor?

    Gezählt werden B-Tags, also Entities statt Wörter – ein sechswortiger
    Produktname soll nicht sechsmal zählen.
    """
    counts = {entity: 0 for entity in ENTITY_TYPES}
    pages = 0
    for labeled_file in config.LABELED_DIR.glob("*.json"):
        try:
            with open(labeled_file) as f:
                tags = json.load(f).get("tags") or []
        except (json.JSONDecodeError, OSError):
            continue
        pages += 1
        for tag in tags:
            if tag.startswith("B-") and tag[2:] in counts:
                counts[tag[2:]] += 1
    return {"pages": pages, "counts": counts, "total": sum(counts.values())}
```

- [ ] **Step 5: Run the whole backend suite**

Run: `.venv/bin/pytest`
Expected: PASS, alle Tests grün

- [ ] **Step 6: Commit**

```bash
git add magda/api.py magda/gold.py tests/test_api.py
git commit -m "Oeffne Job-Katalog, Historie und Katalogverzeichnis fuer das Frontend"
```

---

### Task 6: Frontend-Fundament — Typen, API-Client, Run-Hook, Formular

**Files:**
- Modify: `frontend/src/lib/types.ts` (neue Interfaces, `RunStatus` erweitert, `PipelineStatus.totals` erweitert)
- Modify: `frontend/src/lib/api.ts` (neue Aufrufe, `startRun` mit `args`)
- Create: `frontend/src/features/control/use-run.ts`
- Create: `frontend/src/features/control/job-form.tsx`
- Create: `frontend/src/features/control/job-form.test.tsx`

**Interfaces:**
- Consumes: `GET /api/jobs`, `POST /api/run` mit `{job, args}`
- Produces:
  - `JobDef`, `JobParam`, `RunRecord`, `CatalogEntry`, `ProbeResult`, `LabelDistribution` in `types.ts`
  - `api.jobs()`, `api.startRun(job, args)`, `api.runs()`, `api.runDetail(id)`, `api.catalogs()`, `api.addCatalog(e)`, `api.removeCatalog(id)`, `api.probeCatalog(url)`, `api.labelDistribution()`
  - `useRun()` → `{ status, running, start, stop, startError }`
  - `<JobForm job values onChange onStart disabled />`
  - `defaultValues(job: JobDef): Record<string, string>`
  - `missingRequired(job: JobDef, values): string[]`

- [ ] **Step 1: Write the failing test**

`frontend/src/features/control/job-form.test.tsx`:

```tsx
import { fireEvent, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { renderWithProviders } from "@/test/utils"
import type { JobDef } from "@/lib/types"
import { JobForm, defaultValues, missingRequired } from "./job-form"

const DOWNLOAD: JobDef = {
  job: "01_download_flyers",
  title: "Prospekte laden",
  what: "Holt einen Penny-Katalog.",
  params: [
    { key: "url", label: "Katalog-URL", kind: "str", default: null, choices: [], required: true, help: "mit catalogId" },
    { key: "max_pages", label: "Seiten höchstens", kind: "int", default: 40, choices: [], required: false, help: "" },
  ],
}

const TRAIN: JobDef = {
  job: "04_train",
  title: "Training",
  what: "Token-Klassifikation.",
  params: [
    { key: "variant", label: "Variante", kind: "choice", default: null, choices: ["gbert", "layoutxlm"], required: true, help: "" },
  ],
}

describe("defaultValues", () => {
  it("uebernimmt die Defaults aus dem Katalog", () => {
    expect(defaultValues(DOWNLOAD)).toEqual({ url: "", max_pages: "40" })
  })
})

describe("missingRequired", () => {
  it("meldet leere Pflichtfelder", () => {
    expect(missingRequired(DOWNLOAD, { url: "", max_pages: "40" })).toEqual(["Katalog-URL"])
    expect(missingRequired(DOWNLOAD, { url: "https://x", max_pages: "40" })).toEqual([])
  })
})

describe("JobForm", () => {
  it("rendert ein Feld je Parameter", () => {
    renderWithProviders(
      <JobForm job={DOWNLOAD} values={defaultValues(DOWNLOAD)} onChange={vi.fn()} onStart={vi.fn()} disabled={false} />,
    )
    expect(screen.getByLabelText("Katalog-URL")).toBeInTheDocument()
    expect(screen.getByLabelText("Seiten höchstens")).toHaveValue("40")
  })

  it("sperrt den Start bei leerem Pflichtfeld", () => {
    renderWithProviders(
      <JobForm job={DOWNLOAD} values={{ url: "", max_pages: "40" }} onChange={vi.fn()} onStart={vi.fn()} disabled={false} />,
    )
    expect(screen.getByRole("button", { name: /starten/i })).toBeDisabled()
    expect(screen.getByText(/Katalog-URL/)).toBeInTheDocument()
  })

  it("startet mit den eingegebenen Werten", () => {
    const onStart = vi.fn()
    renderWithProviders(
      <JobForm job={DOWNLOAD} values={{ url: "https://x", max_pages: "12" }} onChange={vi.fn()} onStart={onStart} disabled={false} />,
    )
    fireEvent.click(screen.getByRole("button", { name: /starten/i }))
    expect(onStart).toHaveBeenCalledWith({ url: "https://x", max_pages: "12" })
  })

  it("zeigt choice-Parameter als Auswahl", () => {
    renderWithProviders(
      <JobForm job={TRAIN} values={{ variant: "gbert" }} onChange={vi.fn()} onStart={vi.fn()} disabled={false} />,
    )
    const select = screen.getByLabelText("Variante")
    expect(select).toHaveValue("gbert")
    expect(screen.getByRole("option", { name: "layoutxlm" })).toBeInTheDocument()
  })

  it("zeigt Schritte ohne Parameter als reinen Knopf", () => {
    const plain: JobDef = { job: "02_extract_words", title: "Wörter", what: "PyMuPDF liest.", params: [] }
    renderWithProviders(
      <JobForm job={plain} values={{}} onChange={vi.fn()} onStart={vi.fn()} disabled={false} />,
    )
    expect(screen.getByRole("button", { name: /starten/i })).toBeEnabled()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- job-form`
Expected: FAIL — `Failed to resolve import "./job-form"`

- [ ] **Step 3: Extend the types**

In `frontend/src/lib/types.ts`: `PipelineStatus` und `RunStatus` ersetzen, den Rest anhängen:

```ts
export interface PipelineStatus {
  catalogs: CatalogStatus[]
  totals: {
    raw: number
    words: number
    images: number
    labeled: number
    gold_done: number
    gold_in_progress: number
  }
}

/** Ein Parameter eines Pipeline-Schritts, wie ihn /api/jobs beschreibt. */
export interface JobParam {
  key: string
  label: string
  kind: "str" | "int" | "float" | "choice"
  default: string | number | null
  choices: string[]
  required: boolean
  help: string
}

export interface JobDef {
  job: string
  title: string
  what: string
  params: JobParam[]
}

/** Zustand des laufenden Pipeline-Schritts (magda/runner.py). */
export interface RunStatus {
  running: boolean
  job: string | null
  args: Record<string, string>
  run_id: string | null
  lines: string[]
  exit_code: number | null
  elapsed: number | null
}

/** Ein Eintrag der Lauf-Historie (magda/runs.py). */
export interface RunRecord {
  run_id: string
  job: string
  title?: string
  args: Record<string, string>
  command: string[]
  started: string
  finished: string | null
  exit_code: number | null
  duration: number | null
}

export interface RunDetail extends RunRecord {
  log: string
}

/** Ein Katalog im Verzeichnis (catalogs.json). */
export interface CatalogEntry {
  id: string
  url: string
  title: string
  version: string
  pages: number | null
  added: string
  added_by: string
  note: string
  /** Serverseitig: wie viele Seiten liegen lokal unter data/raw/<id>? */
  local_pages: number
}

export interface CatalogRegistry {
  entries: CatalogEntry[]
  /** Gesetzt, wenn catalogs.json nicht lesbar ist (z.B. Merge-Konflikt). */
  error: string | null
}

export interface ProbeResult {
  catalog_id: string
  version: string
  title: string | null
  meta_found: boolean
  page_1_status: number
  page_1_bytes: number
}

export interface LabelDistribution {
  pages: number
  counts: Record<string, number>
  total: number
}
```

- [ ] **Step 4: Extend the API client**

In `frontend/src/lib/api.ts` den Import-Block um die neuen Typen ergänzen, `startRun` ersetzen und die neuen Aufrufe anhängen:

```ts
  startRun: (job: string, args: Record<string, string> = {}) =>
    fetchJson<RunStatus>("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job, args }),
    }),
  jobs: () => fetchJson<JobDef[]>("/api/jobs"),
  runs: () => fetchJson<RunRecord[]>("/api/runs"),
  runDetail: (id: string) => fetchJson<RunDetail>(`/api/runs/${id}`),
  catalogs: () => fetchJson<CatalogRegistry>("/api/catalogs"),
  addCatalog: (entry: Partial<CatalogEntry> & { id: string }) =>
    fetchJson<CatalogEntry>("/api/catalogs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    }),
  removeCatalog: (id: string) =>
    fetchJson<{ removed: string }>(`/api/catalogs/${id}`, { method: "DELETE" }),
  probeCatalog: (url: string) =>
    fetchJson<ProbeResult>("/api/catalogs/probe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }),
  labelDistribution: () => fetchJson<LabelDistribution>("/api/labels/distribution"),
```

- [ ] **Step 5: Write the run hook**

`frontend/src/features/control/use-run.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { api } from "@/lib/api"

/**
 * Start, Stopp und Zustand des laufenden Schritts.
 *
 * refetchIntervalInBackground: ein Trainingslauf dauert Minuten, in denen der
 * Tab im Hintergrund liegt – ohne das Flag pausiert das Polling und die Konsole
 * steht still.
 */
export function useRun() {
  const qc = useQueryClient()

  const status = useQuery({
    queryKey: ["run"],
    queryFn: api.run,
    refetchInterval: (q) => (q.state.data?.running ? 1500 : false),
    refetchIntervalInBackground: true,
  })

  const start = useMutation({
    mutationFn: ({ job, args }: { job: string; args: Record<string, string> }) =>
      api.startRun(job, args),
    onSuccess: (data) => qc.setQueryData(["run"], data),
  })

  const stop = useMutation({
    mutationFn: api.stopRun,
    onSuccess: (data) => qc.setQueryData(["run"], data),
  })

  // Nach dem Lauf alles neu laden, was der Schritt geschrieben haben könnte.
  const running = status.data?.running ?? false
  useEffect(() => {
    if (!running) {
      for (const key of ["status", "evaluation", "model", "runs", "catalogs", "labelDistribution"]) {
        qc.invalidateQueries({ queryKey: [key] })
      }
    }
  }, [running, qc])

  return {
    status: status.data,
    running,
    busy: running || start.isPending,
    start: (job: string, args: Record<string, string>) => start.mutate({ job, args }),
    stop: () => stop.mutate(),
    startError: start.error?.message ?? null,
  }
}
```

- [ ] **Step 6: Write the form**

`frontend/src/features/control/job-form.tsx`:

```tsx
import { Play } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { JobDef } from "@/lib/types"

/** Startwerte eines Schritts. Alles als String – ein Formularfeld liefert nur Strings,
 *  und die Typkonvertierung gehört ohnehin ins Backend (jobs.build_command). */
export function defaultValues(job: JobDef): Record<string, string> {
  return Object.fromEntries(
    job.params.map((p) => [p.key, p.default == null ? "" : String(p.default)]),
  )
}

/** Labels der leeren Pflichtfelder. Leer = startbar. */
export function missingRequired(job: JobDef, values: Record<string, string>): string[] {
  return job.params
    .filter((p) => p.required && !(values[p.key] ?? "").trim())
    .map((p) => p.label)
}

interface JobFormProps {
  job: JobDef
  values: Record<string, string>
  onChange: (key: string, value: string) => void
  onStart: (values: Record<string, string>) => void
  disabled: boolean
}

export function JobForm({ job, values, onChange, onStart, disabled }: JobFormProps) {
  const missing = missingRequired(job, values)

  return (
    <div className="space-y-3">
      {job.params.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {job.params.map((param) => {
            const id = `${job.job}-${param.key}`
            return (
              <div key={param.key} className="space-y-1">
                <label htmlFor={id} className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                  {param.label}
                  {param.required && <span className="text-destructive"> *</span>}
                </label>
                {param.kind === "choice" ? (
                  <select
                    id={id}
                    value={values[param.key] ?? ""}
                    onChange={(e) => onChange(param.key, e.target.value)}
                    className="h-9 w-full rounded-md border-2 border-foreground bg-card px-2 text-sm"
                  >
                    <option value="">– wählen –</option>
                    {param.choices.map((choice) => (
                      <option key={choice} value={choice}>
                        {choice}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    id={id}
                    value={values[param.key] ?? ""}
                    inputMode={param.kind === "str" ? "text" : "decimal"}
                    placeholder={param.help}
                    onChange={(e) => onChange(param.key, e.target.value)}
                  />
                )}
              </div>
            )
          })}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" disabled={disabled || missing.length > 0} onClick={() => onStart(values)}>
          <Play className="size-3.5" /> Starten
        </Button>
        {missing.length > 0 && (
          <p className="text-xs text-muted-foreground">Fehlt noch: {missing.join(", ")}</p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd frontend && npm test -- job-form`
Expected: PASS, 7 Tests

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/features/control/
git commit -m "Baue Pipeline-Formulare aus dem Job-Katalog"
```

---

### Task 7: Die Steuerzentrale

**Files:**
- Create: `frontend/src/features/control/console.tsx`
- Create: `frontend/src/features/control/run-history.tsx`
- Create: `frontend/src/features/control/catalog-manager.tsx`
- Create: `frontend/src/features/control/control-page.tsx`
- Create: `frontend/src/features/control/control-page.test.tsx`
- Modify: `frontend/src/app/router.tsx` (Route `/control`)
- Modify: `frontend/src/app/top-nav.tsx` (Eintrag „Steuerzentrale")
- Modify: `frontend/src/features/overview/steps.ts` (`07_flair_baseline` in `stepStates`)

**Interfaces:**
- Consumes: `useRun()`, `JobForm`, `defaultValues`, `api.jobs/runs/runDetail/catalogs/addCatalog/removeCatalog/probeCatalog`, `stepStates` aus `../overview/steps`
- Produces: `<ControlPage />` unter `/control`

- [ ] **Step 1: Write the failing test**

`frontend/src/features/control/control-page.test.tsx`:

```tsx
import { fireEvent, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { ControlPage } from "./control-page"

const IDLE_RUN = {
  running: false, job: null, args: {}, run_id: null, lines: [], exit_code: null, elapsed: null,
}

const JOBS = [
  {
    job: "01_download_flyers", title: "Prospekte laden", what: "Holt einen Katalog.",
    params: [
      { key: "url", label: "Katalog-URL", kind: "str", default: null, choices: [], required: true, help: "" },
      { key: "max_pages", label: "Seiten höchstens", kind: "int", default: 40, choices: [], required: false, help: "" },
    ],
  },
  { job: "02_extract_words", title: "Wörter extrahieren", what: "PyMuPDF liest.", params: [] },
]

const STATUS = {
  catalogs: [],
  totals: { raw: 0, words: 0, images: 0, labeled: 0, gold_done: 0, gold_in_progress: 0 },
}

function base(extra: Record<string, unknown> = {}) {
  return {
    "/api/jobs": JOBS,
    "/api/run": IDLE_RUN,
    "/api/runs": [],
    "/api/status": STATUS,
    "/api/evaluation": [],
    "/api/model": [],
    "/api/catalogs": { entries: [], error: null },
    ...extra,
  }
}

describe("ControlPage", () => {
  it("zeigt je Schritt ein Formular aus dem Job-Katalog", async () => {
    mockFetch(base())
    renderWithProviders(<ControlPage />)

    expect(await screen.findByLabelText("Katalog-URL")).toBeInTheDocument()
    expect(screen.getByLabelText("Seiten höchstens")).toHaveValue("40")
  })

  it("schickt die eingegebenen Werte beim Start", async () => {
    mockFetch(base())
    renderWithProviders(<ControlPage />)

    fireEvent.change(await screen.findByLabelText("Katalog-URL"), {
      target: { value: "https://x/?catalogId=42" },
    })
    fireEvent.click(screen.getAllByRole("button", { name: /starten/i })[0])

    await waitFor(() => {
      const call = vi.mocked(fetch).mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === "POST",
      )
      expect(JSON.parse((call?.[1] as RequestInit).body as string)).toEqual({
        job: "01_download_flyers",
        args: { url: "https://x/?catalogId=42", max_pages: "40" },
      })
    })
  })

  it("zeigt die Historie mit Exit-Code", async () => {
    mockFetch(base({
      "/api/runs": [{
        run_id: "20260729-142201_01_download_flyers", job: "01_download_flyers",
        title: "Prospekte laden", args: {}, command: ["python", "01_download_flyers.py"],
        started: "2026-07-29T14:22:01", finished: "2026-07-29T14:22:03",
        exit_code: 2, duration: 2.0,
      }],
    }))
    renderWithProviders(<ControlPage />)

    expect(await screen.findByText(/Abbruch \(2\)/)).toBeInTheDocument()
  })

  it("meldet ein kaputtes Katalog-Verzeichnis, ohne die Seite zu verlieren", async () => {
    mockFetch(base({
      "/api/catalogs": { entries: [], error: "catalogs.json ist nicht lesbar. Merge-Konflikt?" },
    }))
    renderWithProviders(<ControlPage />)

    expect(await screen.findByText(/Merge-Konflikt/)).toBeInTheDocument()
    expect(screen.getByLabelText("Katalog-URL")).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- control-page`
Expected: FAIL — `Failed to resolve import "./control-page"`

- [ ] **Step 3: Move the console out of the old runner**

`frontend/src/features/control/console.tsx` — der `Console`-Block aus `pipeline-runner.tsx:10-35`, unverändert bis auf den Export:

```tsx
import { useEffect, useRef } from "react"

export function Console({ lines, running }: { lines: string[]; running: boolean }) {
  const endRef = useRef<HTMLDivElement>(null)

  // Immer die letzte Zeile zeigen – bei einem Lauf über tausende Seiten ist
  // das Ende die einzige interessante Stelle.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" })
  }, [lines.length])

  return (
    <div className="max-h-[28rem] overflow-y-auto rounded-md bg-foreground p-4 font-mono text-xs leading-relaxed text-background">
      {lines.length === 0 && (
        <p className="text-background/50">{running ? "Warte auf Ausgabe…" : "Noch keine Ausgabe."}</p>
      )}
      {lines.map((line, i) => (
        <div key={i} className="whitespace-pre-wrap break-all">
          {line}
        </div>
      ))}
      {running && <span className="inline-block animate-pulse text-primary">▊</span>}
      <div ref={endRef} />
    </div>
  )
}
```

- [ ] **Step 4: Write the history**

`frontend/src/features/control/run-history.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query"
import { Check, X } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

function outcome(exitCode: number | null): { ok: boolean; text: string } {
  if (exitCode === 0) return { ok: true, text: "fertig" }
  if (exitCode == null) return { ok: false, text: "abgebrochen" }
  return { ok: false, text: `Abbruch (${exitCode})` }
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "–"
  if (seconds < 60) return `${seconds.toFixed(0)}s`
  return `${Math.floor(seconds / 60)}m ${String(Math.round(seconds % 60)).padStart(2, "0")}s`
}

export function RunHistory() {
  const [openId, setOpenId] = useState<string | null>(null)
  const { data } = useQuery({ queryKey: ["runs"], queryFn: api.runs })
  const detail = useQuery({
    queryKey: ["runDetail", openId],
    queryFn: () => api.runDetail(openId as string),
    enabled: openId != null,
  })

  const runs = data ?? []

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold tracking-tight">Läufe</h2>
      {runs.length === 0 && (
        <p className="text-sm text-muted-foreground">Noch kein Lauf aufgezeichnet.</p>
      )}
      <ol className="divide-y divide-border overflow-hidden rounded-lg border-2 border-foreground bg-card">
        {runs.map((run) => {
          const result = outcome(run.exit_code)
          const args = Object.entries(run.args)
          return (
            <li key={run.run_id} className="p-3 text-sm">
              <button
                type="button"
                onClick={() => setOpenId(openId === run.run_id ? null : run.run_id)}
                className="flex w-full items-baseline gap-2 text-left"
              >
                {result.ok ? (
                  <Check className="size-4 shrink-0 translate-y-0.5 text-[var(--riso-blue)]" />
                ) : (
                  <X className="size-4 shrink-0 translate-y-0.5 text-destructive" />
                )}
                <span className="min-w-0 flex-1">
                  <span className="font-mono text-xs">{run.job}</span>
                  <span className={cn("ml-2 text-xs", result.ok ? "text-muted-foreground" : "text-destructive")}>
                    {result.text}
                  </span>
                  {args.length > 0 && (
                    <span className="block truncate font-mono text-[11px] text-muted-foreground">
                      {args.map(([k, v]) => `${k}=${v}`).join(" ")}
                    </span>
                  )}
                </span>
                <span className="shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">
                  {run.started.slice(11, 16)} · {formatDuration(run.duration)}
                </span>
              </button>

              {openId === run.run_id && (
                <div className="mt-2 space-y-2">
                  <p className="break-all rounded bg-muted p-2 font-mono text-[11px]">
                    {detail.data?.command.join(" ") ?? "…"}
                  </p>
                  <pre className="max-h-72 overflow-auto rounded bg-foreground p-3 font-mono text-[11px] text-background">
                    {detail.isPending ? "Lade…" : detail.data?.log || "(keine Ausgabe)"}
                  </pre>
                  <Button variant="outline" size="sm" onClick={() => setOpenId(null)}>
                    Schließen
                  </Button>
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
```

- [ ] **Step 5: Write the catalog manager**

`frontend/src/features/control/catalog-manager.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import type { ProbeResult } from "@/lib/types"

export function CatalogManager({ onUse }: { onUse: (url: string) => void }) {
  const qc = useQueryClient()
  const [url, setUrl] = useState("")
  const [probe, setProbe] = useState<ProbeResult | null>(null)

  const { data } = useQuery({ queryKey: ["catalogs"], queryFn: api.catalogs })

  const check = useMutation({
    mutationFn: () => api.probeCatalog(url),
    onSuccess: setProbe,
  })
  const add = useMutation({
    mutationFn: () =>
      api.addCatalog({
        id: (probe as ProbeResult).catalog_id,
        url,
        title: probe?.title ?? "",
        version: probe?.version ?? "1",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["catalogs"] })
      setProbe(null)
      setUrl("")
    },
  })
  const drop = useMutation({
    mutationFn: (id: string) => api.removeCatalog(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["catalogs"] }),
  })

  const entries = data?.entries ?? []

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold tracking-tight">Kataloge</h2>

      {data?.error && (
        <Alert variant="destructive">
          <AlertTitle>Verzeichnis nicht lesbar</AlertTitle>
          <AlertDescription>{data.error}</AlertDescription>
        </Alert>
      )}

      {entries.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-lg border-2 border-foreground bg-card text-sm">
          {entries.map((entry) => (
            <li key={entry.id} className="flex items-center gap-3 p-3">
              <span className="font-mono text-xs">{entry.id}</span>
              <span className="min-w-0 flex-1 truncate">{entry.title || "ohne Titel"}</span>
              <span className="shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">
                {entry.local_pages} S. lokal
              </span>
              <Button variant="outline" size="sm" onClick={() => onUse(entry.url)}>
                Laden
              </Button>
              <Button variant="outline" size="sm" onClick={() => drop.mutate(entry.id)} aria-label={`${entry.id} entfernen`}>
                <Trash2 className="size-3.5" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2 rounded-lg border-2 border-dashed border-border p-3">
        <label htmlFor="new-catalog" className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
          Neuen Katalog eintragen
        </label>
        <div className="flex flex-wrap gap-2">
          <Input
            id="new-catalog"
            value={url}
            placeholder="https://…blaetterkatalog.de/…?catalogId=…"
            onChange={(e) => {
              setUrl(e.target.value)
              setProbe(null)
            }}
            className="min-w-0 flex-1"
          />
          <Button variant="outline" size="sm" disabled={!url.trim() || check.isPending} onClick={() => check.mutate()}>
            Prüfen
          </Button>
        </div>

        {check.isError && <p className="text-xs text-destructive">{check.error.message}</p>}
        {add.isError && <p className="text-xs text-destructive">{add.error.message}</p>}

        {probe && (
          <div className="space-y-2 text-xs">
            <p>
              <span className="font-mono">{probe.catalog_id}</span>
              {probe.title ? ` · ${probe.title}` : " · ohne Titel"} · Version {probe.version}
              {!probe.meta_found && " (Metadatenseite abgelaufen, Version geraten)"}
            </p>
            <p className={probe.page_1_status === 200 ? "text-[var(--riso-blue)]" : "text-destructive"}>
              {probe.page_1_status === 200
                ? `Seite 1 erreichbar (${Math.round(probe.page_1_bytes / 1024)} KB)`
                : `Seite 1 nicht abrufbar (HTTP ${probe.page_1_status})`}
            </p>
            <Button size="sm" onClick={() => add.mutate()}>
              Ins Verzeichnis
            </Button>
          </div>
        )}
      </div>
    </section>
  )
}
```

- [ ] **Step 6: Write the page**

`frontend/src/features/control/control-page.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query"
import { Loader2, Square } from "lucide-react"
import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { stepStates } from "../overview/steps"
import { CatalogManager } from "./catalog-manager"
import { Console } from "./console"
import { JobForm, defaultValues } from "./job-form"
import { RunHistory } from "./run-history"
import { useRun } from "./use-run"

export function ControlPage() {
  const jobsQ = useQuery({ queryKey: ["jobs"], queryFn: api.jobs })
  const statusQ = useQuery({ queryKey: ["status"], queryFn: api.status })
  const evalQ = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation })
  const modelQ = useQuery({ queryKey: ["model"], queryFn: api.model })
  const run = useRun()

  // Ein Wertesatz je Schritt, erst beim ersten Rendern aus dem Katalog befüllt.
  const [values, setValues] = useState<Record<string, Record<string, string>>>({})

  if (jobsQ.isPending) return <Skeleton className="h-96 w-full" />
  if (jobsQ.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Backend nicht erreichbar</AlertTitle>
        <AlertDescription>
          {jobsQ.error.message} — läuft <code>uvicorn magda.api:app --reload</code>?
        </AlertDescription>
      </Alert>
    )
  }

  const jobs = jobsQ.data
  const totals = statusQ.data?.totals
  const trained = (modelQ.data ?? []).filter((m) => m.trained).map((m) => m.variant)
  const states = totals ? stepStates(totals, evalQ.data ?? [], trained) : {}

  const valuesFor = (jobName: string) =>
    values[jobName] ?? defaultValues(jobs.find((j) => j.job === jobName)!)

  const setValue = (jobName: string, key: string, value: string) =>
    setValues((prev) => ({ ...prev, [jobName]: { ...valuesFor(jobName), [key]: value } }))

  const useCatalogUrl = (url: string) =>
    setValues((prev) => ({
      ...prev,
      "01_download_flyers": { ...valuesFor("01_download_flyers"), url },
    }))

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold tracking-tight">Steuerzentrale</h1>
        <p className="max-w-2xl text-muted-foreground">
          Jeder Schritt liest vom Vorgänger über die Platte. Parameter, laufender Job und
          vergangene Läufe stehen hier; die Übersicht zeigt nur den Stand.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div className="space-y-4">
          {jobs.map((job) => {
            const state = states[job.job]
            const isRunning = run.running && run.status?.job === job.job
            return (
              <section
                key={job.job}
                className={cn(
                  "space-y-3 rounded-lg border-2 border-foreground bg-card p-4",
                  isRunning && "bg-primary/10",
                )}
              >
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <h2 className="font-semibold">{job.title}</h2>
                  <code className="font-mono text-[11px] text-muted-foreground">
                    scripts/{job.job}.py
                  </code>
                  {state === "done" && (
                    <span className="font-mono text-[11px] text-[var(--riso-blue)]">· erledigt</span>
                  )}
                  {state === "blocked" && (
                    <span className="font-mono text-[11px] text-muted-foreground">
                      · Vorgänger fehlt
                    </span>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">{job.what}</p>

                {isRunning ? (
                  <Button variant="outline" size="sm" onClick={run.stop}>
                    <Square className="size-3.5" /> Stoppen
                  </Button>
                ) : (
                  <JobForm
                    job={job}
                    values={valuesFor(job.job)}
                    onChange={(key, value) => setValue(job.job, key, value)}
                    onStart={(v) => run.start(job.job, v)}
                    disabled={run.busy}
                  />
                )}
              </section>
            )
          })}

          <CatalogManager onUse={useCatalogUrl} />
        </div>

        <div className="space-y-6">
          <section className="space-y-2">
            <div className="flex items-baseline justify-between gap-2">
              <h2 className="text-lg font-bold tracking-tight">Live</h2>
              <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                {run.status?.job ?? "kein Lauf"}
                {run.status?.elapsed != null && ` · ${run.status.elapsed}s`}
                {run.running && <Loader2 className="ml-1 inline size-3 animate-spin" />}
              </p>
            </div>
            {run.startError && <p className="text-sm text-destructive">{run.startError}</p>}
            <Console lines={run.status?.lines ?? []} running={run.running} />
          </section>

          <RunHistory />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 7: Wire up route, navigation and the seventh step**

`frontend/src/app/router.tsx` — Import und Route ergänzen:

```tsx
import { ControlPage } from "@/features/control/control-page"
// …
      { path: "/control", element: <ControlPage /> },
```

`frontend/src/app/top-nav.tsx` — `items` ergänzen (nach „Übersicht"):

```tsx
  { title: "Steuerzentrale", url: "/control" },
```

`frontend/src/features/overview/steps.ts` — `STEPS` um den Flair-Arm ergänzen und in `stepStates` die Zeile davor einfügen:

```ts
  {
    job: "07_flair_baseline",
    title: "Flair-Vergleichsarm",
    what: "Fertiges deutsches NER-Modell ohne Anpassung – misst nur BRAND.",
    variants: [],
  },
```

und im Rückgabeobjekt von `stepStates`:

```ts
    "07_flair_baseline": totals.labeled > 0 ? "ready" : "blocked",
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd frontend && npm test`
Expected: `control-page` und `job-form` grün. `overview-page.test.tsx` läuft
weiter durch — die Übersicht benutzt bis Task 8 noch `pipeline-runner.tsx`, und
die neue Kachel `07_flair_baseline` bricht keine der bestehenden Zusicherungen.
Sollte `tsc` über die erweiterten `totals` klagen, ist das der Hinweis auf Task 8,
kein Fehler in dieser Aufgabe.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/control/ frontend/src/app/router.tsx frontend/src/app/top-nav.tsx frontend/src/features/overview/steps.ts
git commit -m "Gib der Pipeline eine Steuerzentrale"
```

---

### Task 8: Übersicht umbauen

**Files:**
- Create: `frontend/src/features/overview/pipeline-diagram.tsx`
- Create: `frontend/src/features/overview/label-distribution.tsx`
- Modify: `frontend/src/features/overview/overview-page.tsx`
- Modify: `frontend/src/features/overview/overview-page.test.tsx`
- Modify: `frontend/src/features/evaluation/evaluation-page.tsx` (drei Stellen `max-w-5xl`)
- Delete: `frontend/src/features/overview/pipeline-runner.tsx`

**Interfaces:**
- Consumes: `stepStates` aus `./steps`, `api.status/evaluation/model/labelDistribution`
- Produces: `<PipelineDiagram states />`, `<LabelDistribution />`

- [ ] **Step 1: Write the failing test**

`frontend/src/features/overview/overview-page.test.tsx` vollständig ersetzen:

```tsx
import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { OverviewPage } from "./overview-page"

const EMPTY_TOTALS = {
  raw: 0, words: 0, images: 0, labeled: 0, gold_done: 0, gold_in_progress: 0,
}

function base(extra: Record<string, unknown> = {}) {
  return {
    "/api/status": { catalogs: [], totals: EMPTY_TOTALS },
    "/api/evaluation": [],
    "/api/model": [],
    "/api/labels/distribution": { pages: 0, counts: {}, total: 0 },
    ...extra,
  }
}

describe("OverviewPage", () => {
  it("zeigt die Pipeline als Diagramm mit Skriptnamen", async () => {
    mockFetch(base())
    renderWithProviders(<OverviewPage />)

    expect(await screen.findByText(/01_download_flyers/)).toBeInTheDocument()
    expect(screen.getByText(/05_evaluate/)).toBeInTheDocument()
  })

  it("fuehrt nichts aus, sondern verlinkt in die Steuerzentrale", async () => {
    mockFetch(base())
    renderWithProviders(<OverviewPage />)

    await screen.findByText(/01_download_flyers/)
    expect(screen.queryByRole("button", { name: /starten/i })).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Steuerzentrale/ })).toHaveAttribute("href", "/control")
  })

  it("zeigt die Zahl handannotierter Seiten als eigene Kennzahl", async () => {
    mockFetch(base({
      "/api/status": {
        catalogs: [],
        totals: { ...EMPTY_TOTALS, raw: 40, words: 40, labeled: 40, gold_done: 7 },
      },
    }))
    renderWithProviders(<OverviewPage />)

    expect(await screen.findByText("Von Hand annotiert")).toBeInTheDocument()
    expect((await screen.findAllByText("7")).length).toBeGreaterThanOrEqual(1)
  })

  it("zeigt Kataloge und die Label-Verteilung", async () => {
    mockFetch(base({
      "/api/status": {
        catalogs: [{ id: "462828", raw: 10, words: 8, images: 8, labeled: 4, downloaded: "2026-07-23" }],
        totals: { ...EMPTY_TOTALS, raw: 10, words: 8, images: 8, labeled: 4 },
      },
      "/api/labels/distribution": {
        pages: 4, counts: { PRODUCT: 120, PRICE: 89 }, total: 209,
      },
    }))
    renderWithProviders(<OverviewPage />)

    expect(await screen.findByText("462828")).toBeInTheDocument()
    expect(screen.getByText("PRODUCT")).toBeInTheDocument()
    expect(screen.getByText("120")).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- overview-page`
Expected: FAIL — „Starten"-Knopf noch vorhanden, kein Link `/control`, keine Karte „Von Hand annotiert"

- [ ] **Step 3: Write the diagram**

`frontend/src/features/overview/pipeline-diagram.tsx`:

```tsx
import { Check } from "lucide-react"
import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"
import { STEPS, type StepState, stepProgress } from "./steps"
import type { PipelineStatus } from "@/lib/types"

/**
 * Die Pipeline als Zustandsbild – ohne Knöpfe. Ausgeführt wird in der
 * Steuerzentrale; hier steht nur, wie weit die Daten sind.
 */
export function PipelineDiagram({
  states, totals,
}: { states: Record<string, StepState>; totals: PipelineStatus["totals"] }) {
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold tracking-tight">Pipeline</h2>
        <Link
          to="/control"
          className="font-mono text-[11px] uppercase tracking-widest text-primary underline-offset-4 hover:underline"
        >
          In der Steuerzentrale ausführen →
        </Link>
      </div>

      <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {STEPS.map((step, i) => {
          const state = states[step.job] ?? "blocked"
          const progress = stepProgress(step.job, totals)
          return (
            <li
              key={step.job}
              className={cn(
                "flex items-start gap-3 rounded-lg border-2 p-3",
                state === "done" && "border-[var(--riso-blue)] bg-card",
                state === "ready" && "border-foreground bg-card",
                state === "blocked" && "border-border text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "flex size-8 shrink-0 items-center justify-center rounded-full border-2 font-mono text-xs font-bold",
                  state === "done" && "border-[var(--riso-blue)] bg-[var(--riso-blue)] text-white",
                  state === "ready" && "border-foreground",
                  state === "blocked" && "border-border",
                )}
              >
                {state === "done" ? <Check className="size-4" /> : `0${i + 1}`}
              </span>
              <div className="min-w-0">
                <h3 className="text-sm font-semibold">{step.title}</h3>
                <code className="block font-mono text-[11px] text-muted-foreground">
                  scripts/{step.job}.py
                </code>
                {progress && (
                  <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                    {progress}
                  </span>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
```

Hinweis: `STEPS[5]` ist der Flair-Arm, seine Nummer wäre „06". Damit die Kachel den echten Skriptnamen trägt, zeigt sie ohnehin `scripts/07_flair_baseline.py` — die Ziffer im Kreis ist die Position in der Liste, nicht die Dateinummer.

- [ ] **Step 4: Write the label distribution**

`frontend/src/features/overview/label-distribution.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { entityColor } from "@/lib/entities"

/**
 * Wie oft kommt welcher Entity-Typ in den LLM-Labels vor?
 *
 * Gezählt werden Entities, nicht Wörter. Lauter QUANTITY und kein PRODUCT wäre
 * ein Warnsignal für die Label-Qualität – das sieht man hier vor dem Training.
 */
export function LabelDistribution() {
  const { data } = useQuery({ queryKey: ["labelDistribution"], queryFn: api.labelDistribution })
  const schema = useQuery({ queryKey: ["schema"], queryFn: api.schema })

  if (!data || data.total === 0) {
    return (
      <section className="space-y-2">
        <h2 className="text-xl font-bold tracking-tight">Labelverteilung</h2>
        <p className="text-sm text-muted-foreground">
          Noch keine gelabelten Seiten. Schritt 03 in der Steuerzentrale starten.
        </p>
      </section>
    )
  }

  const types = schema.data?.entity_types ?? Object.keys(data.counts)
  const rows = types
    .map((type) => ({ type, count: data.counts[type] ?? 0 }))
    .sort((a, b) => b.count - a.count)
  const max = Math.max(...rows.map((r) => r.count), 1)

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold tracking-tight">Labelverteilung</h2>
        <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
          {data.total} Entities auf {data.pages} Seiten
        </p>
      </div>
      <ul className="space-y-1.5">
        {rows.map(({ type, count }) => (
          <li key={type} className="flex items-center gap-3">
            <span className="w-24 shrink-0 font-mono text-[11px]">{type}</span>
            <span className="h-3 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
              <span
                className="block h-full rounded-full"
                style={{ width: `${(count / max) * 100}%`, backgroundColor: entityColor(types, type) }}
              />
            </span>
            <span className="w-12 shrink-0 text-right font-mono text-xs tabular-nums">{count}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
```

- [ ] **Step 5: Rebuild the overview page**

In `frontend/src/features/overview/overview-page.tsx`:

Import `PipelineRunner` durch die beiden neuen ersetzen und `useQuery` für das Modell behalten:

```tsx
import { PipelineDiagram } from "./pipeline-diagram"
import { LabelDistribution } from "./label-distribution"
import { stepStates } from "./steps"
```

Den Wrapper (Zeile 58) von `mx-auto max-w-5xl space-y-10` auf `space-y-10` ändern, den Fließtext-Absatz auf `max-w-3xl` lassen. Die Kennzahlkarten (Zeilen 86–90) und den Runner (Zeile 92) ersetzen durch:

```tsx
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Heruntergeladen" value={t.raw} hint="Seiten in data/raw" />
        <StatCard label="Extrahiert" value={t.words} hint="mit Wörtern und Koordinaten" />
        <StatCard label="Gelabelt" value={t.labeled} hint={`${labeledPct}% aller Seiten`} />
        <StatCard
          label="Von Hand annotiert"
          value={t.gold_done}
          hint={
            t.gold_in_progress > 0
              ? `${t.gold_in_progress} angefangen · gold/`
              : "fertige Gold-Seiten"
          }
        />
      </div>

      <PipelineDiagram
        states={stepStates(t, evalQ.data ?? [], trainedVariants)}
        totals={t}
      />

      <div className="grid gap-8 lg:grid-cols-2">
        <LabelDistribution />
        <ModelSummary models={modelQ.data ?? []} reports={evalQ.data ?? []} />
      </div>
```

`trainedVariants` und `ModelSummary` oberhalb der Komponente ergänzen — `trainedVariants` direkt vor dem `return`:

```tsx
  const trainedVariants = (modelQ.data ?? []).filter((m) => m.trained).map((m) => m.variant)
```

und `ModelSummary` neben `StatCard`:

```tsx
function ModelSummary({ models, reports }: { models: ModelStatus[]; reports: EvalReport[] }) {
  const best = (variant: string) =>
    reports.find((r) => r.variant === variant)?.report["micro avg"]?.["f1-score"] ?? null

  return (
    <section className="space-y-3">
      <h2 className="text-xl font-bold tracking-tight">Modellstand</h2>
      <ul className="space-y-1.5 text-sm">
        {models.map((model) => {
          const f1 = best(model.variant)
          return (
            <li key={model.variant} className="flex items-baseline gap-3">
              <span className="w-24 shrink-0 font-mono text-xs">{model.variant}</span>
              <span className="min-w-0 flex-1 text-muted-foreground">
                {model.trained
                  ? `trainiert, ${model.epoch?.toFixed(0) ?? "?"} Epochen`
                  : "noch nicht trainiert"}
              </span>
              <span className="shrink-0 font-mono tabular-nums">
                {f1 == null ? "–" : `F1 ${f1.toFixed(3)}`}
              </span>
            </li>
          )
        })}
      </ul>
      <p className="text-xs text-muted-foreground">
        Der Flair-Arm misst nur BRAND und steht deshalb nur auf der Evaluationsseite.
      </p>
    </section>
  )
}
```

Der Import-Block braucht zusätzlich `import type { EvalReport, ModelStatus } from "@/lib/types"`.

- [ ] **Step 6: Widen the evaluation page and delete the old runner**

In `frontend/src/features/evaluation/evaluation-page.tsx` alle drei Vorkommen von `mx-auto max-w-5xl space-y-6` durch `space-y-6` ersetzen.

```bash
git rm frontend/src/features/overview/pipeline-runner.tsx
```

- [ ] **Step 7: Run the whole frontend suite**

Run: `cd frontend && npm test`
Expected: PASS, alle Tests grün

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/overview/ frontend/src/features/evaluation/evaluation-page.tsx
git commit -m "Mach die Uebersicht zur Lagebesprechung"
```

---

### Task 9: Dokumentation nachziehen

**Files:**
- Modify: `CLAUDE.md` (Struktur, Kommandos, Projektwissen)
- Modify: `.gitignore` (Prüfen, ob `data/` bereits `data/runs/` abdeckt)

- [ ] **Step 1: Check that the new run directory is ignored**

Run: `git check-ignore -v data/runs/x.json`
Expected: eine Zeile mit der `data/`-Regel. Falls nicht, `data/` in `.gitignore` ergänzen.

- [ ] **Step 2: Update CLAUDE.md**

Im Abschnitt **Struktur** die Pipeline-Zeile ergänzen:

```
Die Schritte lassen sich auch aus dem Frontend starten (`magda/runner.py`
startet sie als Subprozess und streamt die Ausgabe an `/api/run`). *Was*
startbar ist und mit welchen Parametern, steht deklarativ in `magda/jobs.py`;
`build_command` validiert und baut argv und ist die einzige Stelle, an der aus
einer Nutzereingabe ein Kommando wird. Das Frontend liest den Katalog über
`/api/jobs` und baut daraus seine Formulare – ein neuer Parameter wird nur im
Backend gepflegt.
```

Im Abschnitt **Kommandos** ergänzen (nach der Flair-Zeile):

```bash
git check-ignore -v data/runs/x.json       # Lauf-Historie darf nicht ins Repo
```

Im Abschnitt **Projektwissen** die Zeile zur API-Schreibbeschränkung ersetzen und die neuen Punkte anhängen:

```markdown
- **Die API ist nicht mehr read-only.** Geschrieben wird nach `gold/`
  (handannotierte Referenz), `catalogs.json` (Katalog-Verzeichnis) und
  `data/runs/` (Lauf-Historie). Das ist eine aufgezählte Erlaubnisliste, kein
  freier Schreibzugriff – dieselbe enge Beschränkung wie beim Runner.

- **Der Runner-Vertrag ist „nur deklarierte Parameter", nicht „nur Varianten".**
  `jobs.build_command` lehnt unbekannte Jobs, unbekannte Parameternamen, nicht
  konvertierbare Werte und Werte außerhalb von `choices` ab. Werte werden
  typkonvertiert und als eigene argv-Elemente übergeben, es gibt keine Shell.
  Ein freies Argument-Textfeld im Frontend wäre effektiv eine Remote-Shell und
  ist deshalb ausdrücklich nicht vorgesehen.
- **Positionale Werte dürfen nicht mit `-` beginnen.** argparse liest `--help`
  als Option, nicht als URL – der Lauf täte dann etwas anderes als eingegeben.
  `jobs._coerce` weist das zurück.
- **`getcatalog.do` läuft früher ab als die PDFs.** Geprüft am 29.07.2026:
  für Katalog 1342881 liefert die Metadatenseite 404, während `bk_1.pdf` weiter
  mit 200 antwortet. `scraping.fetch_catalog_meta` fängt den 404 ab und nutzt
  den Fallback `"1"`; bei 5xx wird weiterhin geworfen. Vorher lief das in
  `raise_for_status()` – ein erneuter Download des eigenen Katalogs wäre
  gecrasht.
- **Katalog-IDs lassen sich nicht erraten.** 14 Proben rund um eine gültige ID
  ergaben 0 Treffer; der ID-Raum ist dünn besetzt. Deshalb `catalogs.json`:
  gefundene IDs werden geteilt, nicht wiedergefunden. Versioniert aus demselben
  Grund wie `gold/`.
- **`data/runs/` ist die einzige Spur eines Laufs nach dem Backend-Neustart.**
  Der Ringpuffer in `runner.py` hält nur 400 Zeilen für die Live-Ansicht. Wer
  einen Fehlschlag untersucht, liest den Log auf der Platte. Aufgeräumt wird
  bei 100 Läufen.
```

- [ ] **Step 3: Run both suites one last time**

Run: `.venv/bin/pytest && cd frontend && npm test`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "Schreibe den erweiterten Runner-Vertrag fest"
```

---

## Selbstprüfung gegen die Spec

| Spec-Abschnitt | Aufgabe |
|---|---|
| Der Anlass (kaputter Download-Knopf) | Task 1 (`url` als Pflichtparameter), Task 6/7 (Formular) |
| Job-Katalog als Datenstruktur, `Param.key` | Task 1 |
| `build_command` als Sicherheitsgrenze | Task 1, geprüft in Task 3 und Task 5 |
| Alle sechs Jobs samt Parametertabelle | Task 1 |
| `variant` wird gewöhnlicher choice-Parameter | Task 1, API in Task 5 |
| Lauf-Historie, zwei Dateien je Lauf | Task 2, angebunden in Task 3 |
| Aufräumen bei 100 | Task 2 (`prune`), aufgerufen in Task 3 |
| `RUNS_DIR`, `CATALOGS_FILE` | Task 2, Task 4 |
| 404-Fallback in `get_catalog_version` | Task 4 |
| `probe_catalog` | Task 4, Oberfläche in Task 7 |
| Katalog-Verzeichnis, atomar, fehlertolerant | Task 4 |
| Alle neuen Endpunkte | Task 5 |
| `gold_done` / `gold_in_progress` in `totals` | Task 5 (`gold.count_by_status`), Karte in Task 8 |
| Frontend-Dateistruktur `features/control/` | Task 6, Task 7 |
| Dreispalter, Formular aus Schema | Task 7 |
| `steps.ts` bleibt, ergänzt um 07 | Task 7 |
| Übersicht ohne Ausführung, mit Diagramm | Task 8 |
| Label-Verteilung, Modellstand | Task 8 |
| Breite: `max-w-5xl` raus | Task 8 |
| `pipeline-runner.tsx` entfällt | Task 8 |
| Fehlerbehandlungstabelle | Task 1 (Validierung), Task 2 (`run_id`-Pfad), Task 4 (kaputte Datei), Task 5 (409/400/404), Task 6 (gesperrter Start), Task 7 (Verzeichnis-Warnung) |
| Vertragsänderung in CLAUDE.md | Task 9 |
| Nicht im Scope (Presets, SSE, ID-Scan, parallele Jobs, Auth) | in keiner Aufgabe — beabsichtigt |

**Offen geblieben, wie in der Spec vermerkt:** ob `catalogs.json` je Person
Einträge oder eine gemeinsame Liste führt. Umgesetzt ist die gemeinsame Liste
mit `added_by`-Feld; der Fehlerfall Merge-Konflikt ist abgefangen, die
Ergonomie entscheidet sich erst im Gebrauch.
