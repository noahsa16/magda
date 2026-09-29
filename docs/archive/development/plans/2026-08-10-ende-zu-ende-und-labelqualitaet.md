# Ende-zu-Ende-Messung und Labelqualität — Umsetzungsplan

> **Für agentische Bearbeiter:** ERFORDERLICHER SUB-SKILL: `superpowers:subagent-driven-development` (empfohlen) oder `superpowers:executing-plans`, um diesen Plan Aufgabe für Aufgabe umzusetzen. Die Schritte tragen Checkbox-Syntax (`- [ ]`).

**Ziel:** Die Zahl beschaffen, die der Bericht braucht und die es bisher nicht gibt — was die *ganze* Pipeline leistet, wenn ein Prospekt hineingeht — und die zwei Labelmaßnahmen umsetzen, die ohne neues Modell messbar etwas bringen.

**Architektur:** Vier unabhängige Arbeitspakete, jedes mit eigenem Deliverable. Kein neues Modell, keine neue Architektur. Aufgabe 1 verbindet zwei fertige Werkzeuge, die nie zusammengeschaltet wurden; Aufgabe 2 wendet fertige Handurteile an; Aufgabe 3 und 4 sind Datenläufe mit Buchführung.

**Tech-Stack:** Python 3.12, PyTorch, transformers 4.x (`<5` gepinnt), pytest. Alles aus `.venv/bin/`.

## Globale Randbedingungen

- **Immer `.venv/bin/python` und `.venv/bin/magda`**, nie `python`. `which python` zeigt auf Anaconda; dort fehlt `seqeval`.
- **Immer aus dem Projektroot starten** — die Schritte lesen und schreiben relativ zu `config.PROJECT_ROOT`.
- **`data/splits/split.json` bleibt eingefroren.** Kein Schritt in diesem Plan würfelt neu.
- **Nichts schreibt nach `data/labeled/sonnet-5/`.** Das ist die Referenz, gegen die gemessen wird. Korrigierte Labels kommen in einen *neuen* Ordner.
- **Der Testsplit wird in diesem Plan nicht angefasst.** Keine Aufgabe hier misst auf Test.
- **`__pycache__` vor Konstanten-Experimenten löschen** — veralteter Bytecode lässt Verstell-Prüfungen fälschlich „wirkungslos" melden.
- **Kommentare und Docstrings auf Deutsch, alle Identifier auf Englisch.**
- Nach jeder Aufgabe: volle Suite grün (`​.venv/bin/python -m pytest -q`), aktuell 420 Tests.

## Ausdrücklich nicht Teil dieses Plans

Diese Dinge sehen nach Fortschritt aus und sind hier keiner. Sie werden **nicht** gemacht:

- **Weitere Paar-Merkmale.** `beide` (39 Merkmale) liegt unter der Basis (30) — Überanpassung bei ~20 unabhängigen Vorlagen. Erst Referenz vergrößern (Aufgabe 3), dann eventuell Merkmale.
- **LiLT als dritter Arm, Sliding Window im Training, OFFER-Kopf.** Adressieren die bereits gelöste Stufe 1.
- **Split neu würfeln, um Woche 4 aufzunehmen.** Alle bisherigen Zahlen wären unvergleichbar.
- **Eine Gittervariante auf Dev auswählen und die Dev-Zahl als Ergebnis berichten.** Die Gruppen-CIs überlappen massiv; Variantenwahl gehört out-of-fold auf Train.

---

## Aufgabe 1: Ende-zu-Ende-Messung auf Dev

**Warum:** Die Projektaussage lautet „90 % dessen, was das große Modell liefert". Belegt ist das für *Wortlabels*. Was das LLM liefert, ist aber eine *Angebotszeile*. Die Gruppierung (Gruppen-F1 0.477) wurde auf **Lehrer-Entities** gemessen, nicht auf GBERTs Ausgabe. Nachgerechnet: `data/predictions/gbert` hat 101 Seiten (alle Test), `data/offer_groups/claude-sonnet-5` hat 51 (alle Train/Dev), **Schnittmenge null**. Die Zahl ist mit den vorhandenen Artefakten unmöglich — und kostet null LLM-Kontingent.

**Dateien:**
- Erzeugt: `data/predictions/gbert/<dev-seiten>.json` (21 Dateien)
- Erzeugt: `data/eval/offers_grid_dev_predictions.json`
- Ändern: `CLAUDE.md` (Befund eintragen)
- Test: `tests/test_offer_grid.py`

**Schnittstellen:**
- Nutzt: `magda predict` (`--split {train,dev,test}` existiert bereits), `magda offers-grid --predictions` (existiert bereits)
- Liefert: die erste Ende-zu-Ende-Zahl des Projekts

- [ ] **Schritt 1: Ausgangslage festhalten**

```bash
.venv/bin/python -c "
from pathlib import Path
pred = {p.stem for p in Path('data/predictions/gbert').glob('*.json')}
grp  = {p.stem for p in Path('data/offer_groups/claude-sonnet-5').glob('*.json')}
print(f'Vorhersagen {len(pred)}, Gruppierung {len(grp)}, Schnittmenge {len(pred & grp)}')
"
```

Erwartet: `Vorhersagen 101, Gruppierung 51, Schnittmenge 0`

- [ ] **Schritt 2: Regressionstest für die Schnittmenge schreiben**

Dieser Test hält fest, *warum* Aufgabe 1 nötig war, und schlägt an, wenn die Kette wieder auseinanderfällt.

```python
# tests/test_offer_grid.py, ans Ende anhaengen
def test_vorhersagen_und_gruppierung_treffen_sich_auf_dev():
    """Ohne Schnittmenge ist keine Ende-zu-Ende-Messung moeglich.

    Belegter Ausgangszustand (10.08.2026): 101 Vorhersagen, alle im
    Testsplit; 51 Gruppierungen, alle in Train/Dev; Schnittmenge null.
    Die Kette war gebaut, aber nie zusammengeschaltet.
    """
    import json
    from pathlib import Path

    from magda.cli.offers_model import SPLIT_FILE

    prediction_dir = Path("data/predictions/gbert")
    grouping_dir = Path("data/offer_groups/claude-sonnet-5")
    if not prediction_dir.is_dir() or not grouping_dir.is_dir():
        pytest.skip("Vorhersagen oder Gruppierung fehlen")

    split = json.loads(SPLIT_FILE.read_text())
    dev = set(split["dev"])
    predicted = {p.stem for p in prediction_dir.glob("*.json")} & dev
    grouped = {p.stem for p in grouping_dir.glob("*.json")} & dev

    assert predicted & grouped, (
        "Keine Dev-Seite hat Vorhersage und Gruppierung. "
        "`magda predict gbert --split dev --labels-from sonnet-5` laufen lassen."
    )
```

- [ ] **Schritt 3: Test laufen lassen, Fehlschlag bestätigen**

Run: `.venv/bin/python -m pytest tests/test_offer_grid.py::test_vorhersagen_und_gruppierung_treffen_sich_auf_dev -q`
Erwartet: FAIL mit „Keine Dev-Seite hat Vorhersage und Gruppierung."

- [ ] **Schritt 4: Vorhersagen für Dev erzeugen**

```bash
.venv/bin/magda predict gbert --split dev --labels-from sonnet-5
```

Erwartet: 21 neue Dateien in `data/predictions/gbert/`. Dauer: Sekunden.
Die vorhandenen 100 Testvorhersagen bleiben unberührt (andere `page_id`).

- [ ] **Schritt 5: Test laufen lassen, jetzt grün**

Run: `.venv/bin/python -m pytest tests/test_offer_grid.py::test_vorhersagen_und_gruppierung_treffen_sich_auf_dev -q`
Erwartet: PASS

- [ ] **Schritt 6: Ende-zu-Ende messen**

```bash
.venv/bin/magda offers-grid --predictions gbert --variants basis,geometrie \
  > /tmp/endtoend.txt 2>&1; tail -30 /tmp/endtoend.txt
```

Das Gitter läuft mit GBERTs Entities statt der Lehrer-Entities. **Die Differenz zur bestehenden Zahl aus `data/eval/offers_grid_dev.json` ist die bezifferte Fehlerfortpflanzung Stufe 1 → Stufe 2.**

- [ ] **Schritt 7: Report umbenennen, damit er den Lehrerlauf nicht überschreibt**

```bash
mv data/eval/offers_grid_dev.json data/eval/offers_grid_dev_predictions.json
```

Prüfen, dass in der Datei `"source"` auf die Vorhersagen zeigt, nicht auf `sonnet-5`.

- [ ] **Schritt 8: Befund in CLAUDE.md eintragen**

Unter „Projektwissen, das nicht im Code steht" ergänzen — mit beiden Zahlen (auf Lehrer-Entities und auf Vorhersagen), der Differenz, und der Einschränkung: **Dev stammt aus den Trainingswochen, die Entity-Qualität ist dort in-distribution-optimistisch; die Zahl ist eine Obergrenze.**

- [ ] **Schritt 9: Committen**

```bash
git add tests/test_offer_grid.py data/predictions/gbert data/eval CLAUDE.md
git commit -m "Miss die Kette erstmals ende-zu-ende statt stufenweise"
```

---

## Aufgabe 2: APP_PRICE-Übernahme in einen neuen Labelordner

**Warum:** Die Handprüfung ist durch — 374 von 374 Kandidaten beurteilt, die Urteile liegen in `data/audit/APP_PRICE.json` (292 `correct`, **82 `wrong` mit `should_be: APP_PRICE`**). Die Übernahme trifft **72 Train, 9 Dev, 0 Test**: die Messlatte bleibt liegen, das Training des schwächsten Labels wächst um 62 % (115 → 186 Spans). GBERT-Nachtraining kostet 96 Sekunden.

**Kritisch:** `data/labeled/sonnet-5/` wird **nicht** verändert. CLAUDE.md: „Nichts schreibt nach `data/labeled/`." Die korrigierten Labels kommen nach `data/labeled/sonnet-5-app/`. So bleiben alle bisherigen Messungen gültig und beide Varianten vergleichbar.

**Dateien:**
- Erstellen: `src/magda/audit_apply.py`
- Erstellen: `src/magda/cli/audit_apply.py`
- Ändern: `src/magda/cli/__init__.py` (Befehl registrieren)
- Erstellen: `tests/test_audit_apply.py`
- Erzeugt: `data/labeled/sonnet-5-app/` (296 Dateien)

**Schnittstellen:**
- Nutzt: `data/audit/<LABEL>.json` mit `{"verdicts": {"<page_id>:<word_index>": {"verdict": "correct"|"wrong", "should_be": str}}}`
- Liefert: `apply_verdicts(label: str, source: str, target: str) -> dict` mit Schlüsseln `pages`, `changed`, `unchanged`, `missing`

- [ ] **Schritt 1: Failing Test schreiben**

```python
# tests/test_audit_apply.py
"""Handurteile auf Labels anwenden - in einen neuen Ordner, nie in den alten.

`data/labeled/sonnet-5/` ist die Referenz, gegen die gemessen wird. Wer sie
in place korrigiert, verschiebt still die Grundlage aller frueheren Zahlen.
"""

import json

import pytest

from magda import audit_apply


def _labels(tmp_path, page_id, tags):
    directory = tmp_path / "labeled" / "quelle"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{page_id}.json").write_text(json.dumps({
        "page_id": page_id, "tags": tags,
    }))
    return directory


def test_ein_wrong_urteil_setzt_das_neue_label(tmp_path):
    source = _labels(tmp_path, "p1", ["O", "B-PRICE", "O"])
    verdicts = {"p1:1": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    result = audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")

    written = json.loads((tmp_path / "ziel" / "p1.json").read_text())
    assert written["tags"] == ["O", "B-APP_PRICE", "O"]
    assert result["changed"] == 1


def test_ein_correct_urteil_laesst_alles_stehen(tmp_path):
    source = _labels(tmp_path, "p1", ["O", "B-APP_PRICE", "O"])
    verdicts = {"p1:1": {"verdict": "correct", "should_be": "APP_PRICE"}}

    result = audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")

    written = json.loads((tmp_path / "ziel" / "p1.json").read_text())
    assert written["tags"] == ["O", "B-APP_PRICE", "O"]
    assert result["changed"] == 0


def test_die_quelle_bleibt_unberuehrt(tmp_path):
    """Die Regel, wegen der es ueberhaupt einen zweiten Ordner gibt."""
    source = _labels(tmp_path, "p1", ["O", "B-PRICE", "O"])
    before = (source / "p1.json").read_text()
    verdicts = {"p1:1": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")

    assert (source / "p1.json").read_text() == before


def test_seiten_ohne_urteil_werden_unveraendert_kopiert(tmp_path):
    """Der Zielordner muss vollstaendig sein, sonst trainiert man auf weniger."""
    source = _labels(tmp_path, "p1", ["O", "B-PRICE"])
    _labels(tmp_path, "p2", ["B-PRODUCT", "O"])

    result = audit_apply.apply_verdicts({}, source, tmp_path / "ziel")

    assert (tmp_path / "ziel" / "p2.json").is_file()
    assert result["pages"] == 2


def test_ein_urteil_auf_eine_unbekannte_seite_bricht_ab(tmp_path):
    """Halb angewandte Urteile machen den Ordner um genau den Betrag falsch,
    den niemand sieht - dieselbe Regel wie in `offer_teacher`."""
    source = _labels(tmp_path, "p1", ["O", "B-PRICE"])
    verdicts = {"gibtsnicht:0": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    with pytest.raises(ValueError, match="gibtsnicht"):
        audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")


def test_ein_urteil_hinter_dem_seitenende_bricht_ab(tmp_path):
    source = _labels(tmp_path, "p1", ["O", "B-PRICE"])
    verdicts = {"p1:99": {"verdict": "wrong", "should_be": "APP_PRICE"}}

    with pytest.raises(ValueError, match="99"):
        audit_apply.apply_verdicts(verdicts, source, tmp_path / "ziel")
```

- [ ] **Schritt 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `.venv/bin/python -m pytest tests/test_audit_apply.py -q`
Erwartet: FAIL mit `ModuleNotFoundError: No module named 'magda.audit_apply'`

- [ ] **Schritt 3: Modul schreiben**

```python
# src/magda/audit_apply.py
"""Urteile der Handpruefung auf einen Labelordner anwenden.

Geschrieben wird immer in einen *neuen* Ordner. `data/labeled/sonnet-5/`
ist die Referenz, gegen die alle bisherigen Zahlen gemessen wurden; wer sie
in place korrigiert, verschiebt deren Grundlage, ohne dass es jemand sieht.
Zwei Ordner nebeneinander machen den Effekt der Uebernahme dagegen messbar.

Ein Urteil, das nicht anwendbar ist, bricht ab statt uebersprungen zu
werden: Eine halb angewandte Korrektur macht den Ordner um genau den Betrag
falsch, den niemand bemerkt.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def apply_verdicts(verdicts: dict, source, target) -> dict:
    """Wendet `{"<page_id>:<index>": {...}}` auf einen Labelordner an."""
    source, target = Path(source), Path(target)
    target.mkdir(parents=True, exist_ok=True)

    by_page: dict[str, list[tuple[int, dict]]] = {}
    for key, verdict in verdicts.items():
        page_id, _, index = key.rpartition(":")
        if not page_id or not index.isdigit():
            raise ValueError(f"Unlesbarer Urteilsschluessel: {key}")
        by_page.setdefault(page_id, []).append((int(index), verdict))

    known = {p.stem for p in source.glob("*.json")}
    unknown = sorted(set(by_page) - known)
    if unknown:
        raise ValueError(
            f"Urteile fuer unbekannte Seiten: {', '.join(unknown[:5])}. "
            f"Passt die Labelquelle zu `labels_from` in der Auditdatei?"
        )

    changed = pages = 0
    for path in sorted(source.glob("*.json")):
        pages += 1
        payload = json.loads(path.read_text())
        tags = payload.get("tags") or []
        for index, verdict in by_page.get(path.stem, []):
            if index >= len(tags):
                raise ValueError(
                    f"Urteil {path.stem}:{index} liegt hinter dem Seitenende "
                    f"({len(tags)} Woerter). Hat sich Schritt 02 geaendert?"
                )
            if verdict.get("verdict") != "wrong":
                continue
            wanted = f"B-{verdict['should_be']}"
            if tags[index] != wanted:
                tags[index] = wanted
                changed += 1
        payload["tags"] = tags
        (target / path.name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False))

    return {"pages": pages, "changed": changed,
            "unchanged": pages - len(by_page), "missing": 0}
```

- [ ] **Schritt 4: Tests laufen lassen, jetzt grün**

Run: `.venv/bin/python -m pytest tests/test_audit_apply.py -q`
Erwartet: 6 passed

- [ ] **Schritt 5: CLI schreiben**

```python
# src/magda/cli/audit_apply.py
"""Urteile der Handpruefung als neuen Labelordner ablegen."""

from __future__ import annotations

import argparse
import json

from magda import audit_apply, config


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="magda audit-apply",
        description="Urteile der Handpruefung auf einen Labelordner anwenden.",
    )
    parser.add_argument("label", help="z. B. APP_PRICE")
    parser.add_argument("--labels-from", required=True, help="Quellordner")
    parser.add_argument("--target", required=True,
                        help="Zielordner, NICHT die Quelle")
    args = parser.parse_args(argv)

    if config.model_slug(args.target) == config.model_slug(args.labels_from):
        parser.exit(1, "Ziel und Quelle sind derselbe Ordner. `data/labeled/` "
                       "ist die Referenz und wird nicht ueberschrieben.\n")

    path = config.PROJECT_ROOT / "data" / "audit" / f"{args.label}.json"
    if not path.is_file():
        parser.exit(1, f"{path} fehlt. Erst `magda audit {args.label}` laufen lassen.\n")

    data = json.loads(path.read_text())
    result = audit_apply.apply_verdicts(
        data.get("verdicts") or {},
        config.labeled_dir(args.labels_from),
        config.labeled_dir(args.target),
    )
    print(f"{result['pages']} Seiten geschrieben, {result['changed']} Label geaendert.")
    print(f"Ziel: {config.labeled_dir(args.target)}")
    print(f"Die Quelle {config.labeled_dir(args.labels_from)} ist unveraendert.")
```

- [ ] **Schritt 6: Befehl registrieren**

In `src/magda/cli/__init__.py` nach dem `audit`-Eintrag ergänzen:

```python
    Befehl("audit-apply", "audit_apply",
           "Urteile der Handprüfung als neuen Labelordner ablegen"),
```

- [ ] **Schritt 7: Volle Suite + echter Lauf**

```bash
.venv/bin/python -m pytest -q
.venv/bin/magda audit-apply APP_PRICE --labels-from sonnet-5 --target sonnet-5-app
```

Erwartet: 296 Seiten geschrieben, **82 Label geändert**.

- [ ] **Schritt 8: Gegenprobe, dass die Quelle unberührt ist**

```bash
git status --short data/labeled/sonnet-5 | head
```

Erwartet: leer.

- [ ] **Schritt 9: GBERT auf beiden Varianten trainieren und vergleichen**

```bash
.venv/bin/magda train gbert --labels-from sonnet-5-app
.venv/bin/magda eval gbert --split dev --labels-from sonnet-5-app
```

**Wichtig:** Gemessen wird auf **Dev**, nicht Test. Die Übernahme trifft 0 Testseiten, aber der Testsplit bleibt in diesem Plan grundsätzlich unangetastet.

- [ ] **Schritt 10: Committen**

```bash
git add src/magda/audit_apply.py src/magda/cli/audit_apply.py \
        src/magda/cli/__init__.py tests/test_audit_apply.py data/labeled/sonnet-5-app
git commit -m "Uebernimm die APP_PRICE-Handurteile in einen zweiten Labelordner"
```

---

## Aufgabe 3: Teacher-Referenz von 51 auf 80–100 Seiten ausbauen

**Warum:** Die Gruppen-CIs des Gitters sind [0.16, 0.65] für Basis gegen [0.21, 0.74] für +Geometrie — die Varianten sind **innerhalb des Rauschens nicht unterscheidbar**. „+Geometrie schlägt Basis" ist eine Punktschätzer-Lesart, kein Befund. Der Weg zu einem Befund führt über mehr Referenzseiten, nicht über den nächsten Merkmalsblock. 30 Trainingsseiten und 14 Dev-Cluster sind das eigentliche Limit.

**Dateien:**
- Erzeugt: `data/offer_groups/claude-sonnet-5/<neue Seiten>.json`
- Ändern: `CLAUDE.md`

**Abbruchkriterium:** LLM-Kontingent erschöpft → mit dem Erreichten weiterarbeiten. Nichts in diesem Plan hängt daran.

- [ ] **Schritt 1: Warteschlange abfragen**

```bash
.venv/bin/magda offers-queue --limit 50
```

Die Reihenfolge wechselt zwischen „blinder Fleck" (kein Grundpreis) und Clustergröße. Nur Train und Dev, nie Test.

- [ ] **Schritt 2: Seiten in Blöcken gruppieren lassen**

Für jede vorgeschlagene Seite:

```bash
.venv/bin/magda offers-teacher task <page_id>
```

In Blöcken von zehn arbeiten und nach jedem Block Schritt 3 laufen lassen — so ist bei einer Kontingentsperre nichts verloren.

- [ ] **Schritt 3: Nach jedem Block den Bestand prüfen**

```bash
.venv/bin/python -c "
import json
from pathlib import Path
from magda.cli.offers_model import SPLIT_FILE
split = json.loads(SPLIT_FILE.read_text())
grp = {p.stem for p in Path('data/offer_groups/claude-sonnet-5').glob('*.json')}
for name in ('train','dev'):
    print(f'{name}: {len(grp & set(split[name]))}')
"
```

Ziel: Train 60–70, Dev 25–30.

- [ ] **Schritt 4: Gitter mit der größeren Referenz wiederholen**

```bash
.venv/bin/magda offers-grid --labels-from sonnet-5
```

**Die eigentliche Frage:** Werden die Konfidenzintervalle schmaler, und trennen sich die Varianten jetzt? Wenn nicht, ist auch das ein Befund — dann ist die Gruppierungsfrage mit dieser Datenmenge nicht entscheidbar, und genau das gehört in den Bericht.

- [ ] **Schritt 5: Committen**

```bash
git add data/offer_groups data/eval CLAUDE.md
git commit -m "Verdopple die Gruppierungsreferenz und miss das Gitter neu"
```

---

## Aufgabe 4: Woche 4 labeln und als Frischwochen-Demo fahren

**Warum:** 126 Seiten liegen extrahiert, aber ungelabelt (`data/words` hat 422, der eingefrorene Split 296). Sie kommen **nicht** in den Split — Stufe 1 ist nicht der Engpass, und Neuwürfeln entwertet alle Zahlen. Ihr Wert ist ein anderer: eine **nie gesehene Woche**, auf der die ganze Pipeline einmal durchläuft. Das ist das überzeugendste Artefakt, das ein Bericht für „Einsatzfall" haben kann.

**Dateien:**
- Erzeugt: `data/labeled/sonnet-5/<126 neue Seiten>.json`
- Erzeugt: `data/offers.sqlite` (Frischwochen-Stand)
- Ändern: `CLAUDE.md`

**Abbruchkriterium:** Kontingentsperre → verschieben. Nichts anderes in diesem Plan hängt daran.

- [ ] **Schritt 1: Labeln (nachts, wegen Kontingent)**

```bash
.venv/bin/magda label --model sonnet-5
```

Der Schritt ist idempotent und überspringt die 296 bereits gelabelten Seiten.

- [ ] **Schritt 2: Prüfen, dass der Split unberührt blieb**

```bash
.venv/bin/python -c "
import json
from magda.cli.offers_model import SPLIT_FILE
split = json.loads(SPLIT_FILE.read_text())
print(sum(len(split[n]) for n in ('train','dev','test')), 'Seiten im Split')
"
```

Erwartet: **296** — unverändert.

- [ ] **Schritt 3: Ganze Pipeline auf der Frischwoche**

```bash
.venv/bin/magda predict gbert --all-words
.venv/bin/magda offers --predictions gbert
.venv/bin/magda offers-verify --reference-from claude-sonnet-5
```

- [ ] **Schritt 4: Kennzahlen der Demo festhalten**

Für den Bericht notieren: Zahl der Seiten, Zahl der erzeugten Angebotszeilen, **Anteil vollständiger Zeilen (Produkt *und* Preis) gegen Fragmente**, dazu `offers-verify` mit `accuracy` **und** `coverage`. Die Fragmentquote gehört ausdrücklich dazu — sie war zuletzt 777 von 1283.

- [ ] **Schritt 5: Committen**

```bash
git add data/labeled data/offers.sqlite CLAUDE.md
git commit -m "Labele die vierte Woche und fahre sie als Frischwochen-Demo"
```

---

## Selbstprüfung

**Abdeckung:** Alle fünf Empfehlungen sind abgebildet — (1) Aufgabe 1, (2) Aufgabe 3, (3) Aufgabe 2, (4) Aufgabe 4, (5) als eigener Abschnitt „Ausdrücklich nicht Teil dieses Plans".

**Platzhalter:** keine. Jeder Schritt trägt den auszuführenden Befehl oder den zu schreibenden Code.

**Typkonsistenz:** `apply_verdicts(verdicts, source, target)` ist in Aufgabe 2 Schritt 1 (Test), Schritt 3 (Implementierung) und Schritt 5 (CLI) mit derselben Signatur benutzt. Rückgabeschlüssel `pages`, `changed`, `unchanged`, `missing` sind in Test und Implementierung deckungsgleich.

**Reihenfolge:** Aufgabe 1 zuerst, weil sie nichts kostet und die Zahl liefert, die der Bericht in jedem Fall braucht. Aufgabe 4 kann parallel nachts laufen. Aufgabe 2 und 3 sind unabhängig voneinander.
