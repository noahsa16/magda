# Vertiefung: Destillation, Drift und Fehleranalyse — Umsetzungsplan

> **Für agentische Bearbeiter:** ERFORDERLICHER SUB-SKILL: `superpowers:subagent-driven-development` (empfohlen) oder `superpowers:executing-plans`. Die Schritte tragen Checkbox-Syntax (`- [ ]`).

**Ziel:** Aus einem solide gemessenen Projekt eines mit eigenen Befunden machen — und die eine Messung nachholen, die der Bewertungsbogen verlangt und die noch fehlt.

**Architektur:** Sieben Arbeitspakete. Aufgabe 1 ist Pflicht (offene Anforderung der Stufe „Excellent"), 2–4 sind die Erkenntniskapitel, 5–6 hängen an ihnen, 7 ist eine Sonde mit hartem Abbruch. Kein neues Modell und keine neue Architektur — alle Befunde liegen in vorhandenen Daten.

**Tech-Stack:** Python 3.12, PyTorch, transformers `>=4.44,<5`, pytest, OpenAI-Client gegen die GWDG-API. Alles aus `.venv/bin/`.

## Globale Randbedingungen

- **Immer `.venv/bin/python` und `.venv/bin/magda`**, nie `python`.
- **Immer aus dem Projektroot starten.**
- **`data/splits/split.json` bleibt eingefroren.** Woche 4 kommt nicht hinein.
- **Nichts schreibt nach `data/labeled/sonnet-5/`.**
- **Der Testsplit wird in diesem Plan GENAU EINMAL angefasst** — in Aufgabe 6, im gebündelten Schlussbatch. Jede Aufgabe, die eine Testzahl braucht, *bereitet vor* und wertet dort aus. Wer zwischendurch auf Test misst, verbrennt die Zahl.
- **Kommentare und Docstrings auf Deutsch, alle Identifier auf Englisch.**
- **Keine Zahl ohne das Skript, das sie erzeugt** — und immer dazuschreiben, *woran* gemessen wurde.
- Nach jeder Aufgabe: volle Suite grün (`.venv/bin/python -m pytest -q`), aktuell 420 Tests.

## Ausdrücklich nicht Teil dieses Plans

- **CO2-Zahlen.** Scheinpräzision für eine API mit unbekanntem Energieprofil. Im Bericht *erwähnen, warum sie fehlen* — das ist die ehrlichere Aussage.
- **LiLT als dritter Arm.** Beantwortet eine Frage, deren Negativbefund samt Intervall bereits steht.
- **„Distillation" als Umbenennung ohne die Lernkurve.** Framing ohne Messung ist ein Etikett, kein Beitrag.
- **Zweiter Händler als Aufbauprojekt** (Scraper, OCR-Fallback, eigene Prompts). Nur die Timebox-Sonde aus Aufgabe 7.
- **„+Geometrie schlägt Basis" als Befund.** Gruppen-F1-CIs [0.16, 0.65] gegen [0.21, 0.74] — Punktschätzer-Vergleich im Rauschen.

---

## Aufgabe 1 (PFLICHT): Blackbox-Vergleichsarm

**Warum:** Nachgeprüft und offen. [`CLAUDE.md:190`](../../../CLAUDE.md) („bleibt als Vergleichssystem für die Requirements-Stufe ‚Excellent'"), [`src/magda/cli/evaluate.py:34`](../../../src/magda/cli/evaluate.py) („**Noch offen** (Requirements-Stufe ‚Excellent')"), [`reports/woche-03.md:342`](../../../reports/woche-03.md) führt es als offenen Punkt — und in `data/eval/` liegt **kein** Blackbox-Report.

**Zwei Fallen, die den Vergleich sonst wertlos machen:**
1. Das Blackbox-Schema kennt per Design weder App-Preise noch Menge/Grundpreis (der Prompt sagt wörtlich „Skip … app labels"). Verglichen wird über die **gemeinsame Feldmenge**: `name`, `price`, `original_price`.
2. Dasselbe Matching muss **symmetrisch** auf die eigene Pipeline angewandt werden. Wer die Blackbox fuzzy matcht und die eigene Ausgabe exakt, verzerrt in unbekannte Richtung.

**Gratis-Nebenprodukt:** Dieser Lauf liefert erstmals die **LLM-seitige Ende-zu-Ende-Zeit**. Die 170×-Zahl vergleicht heute Labeling gegen Inferenz, nicht Produkt gegen Produkt.

**Dateien:**
- Erstellen: `src/magda/blackbox_eval.py`, `src/magda/cli/blackbox_eval.py`, `tests/test_blackbox_eval.py`
- Ändern: `src/magda/cli/__init__.py`
- Erzeugt: `data/eval/blackbox_test.json`

**Schnittstellen:**
- Nutzt: `blackbox.extract_deals_from_page(pdf_bytes, client, model) -> list[dict]`
- Liefert: `match_deals(system, reference, price_tolerance=0.0) -> dict` mit `matched`, `only_system`, `only_reference`

- [ ] **Schritt 1: Failing Test für das Matching**

```python
# tests/test_blackbox_eval.py
"""Blackbox gegen eigene Pipeline - ueber die gemeinsame Feldmenge.

Die Blackbox kennt per Design keine App-Preise und keinen Grundpreis; ihr
Prompt sagt "Skip ... app labels". Verglichen wird deshalb nur ueber
name/price/original_price - und dasselbe Matching gilt fuer BEIDE Seiten,
sonst ist der Vergleich in unbekannte Richtung unfair.
"""

import pytest

from magda import blackbox_eval


def test_gleicher_preis_und_aehnlicher_name_gilt_als_treffer():
    system = [{"name": "Landliebe Butter 250g", "price": 1.29}]
    reference = [{"name": "Landliebe Butter", "price": 1.29}]

    result = blackbox_eval.match_deals(system, reference)

    assert result["matched"] == 1
    assert result["only_system"] == 0


def test_ein_anderer_preis_ist_kein_treffer():
    """Der Preis ist der harte Anker - Namen variieren, Preise nicht."""
    system = [{"name": "Landliebe Butter", "price": 1.49}]
    reference = [{"name": "Landliebe Butter", "price": 1.29}]

    result = blackbox_eval.match_deals(system, reference)

    assert result["matched"] == 0


def test_jedes_angebot_wird_hoechstens_einmal_gepaart():
    """Sonst treibt ein System seinen Recall mit Duplikaten hoch."""
    system = [{"name": "Butter", "price": 1.29}, {"name": "Butter", "price": 1.29}]
    reference = [{"name": "Butter", "price": 1.29}]

    result = blackbox_eval.match_deals(system, reference)

    assert result["matched"] == 1
    assert result["only_system"] == 1


def test_leere_seiten_auf_beiden_seiten_ergeben_keine_quote():
    result = blackbox_eval.match_deals([], [])

    assert result["f1"] is None


def test_die_gemeinsame_feldmenge_ignoriert_app_preise():
    """Die Blackbox kann APP_PRICE gar nicht ausdruecken - das darf der
    eigenen Pipeline nicht als Fehler angelastet werden."""
    system = [{"name": "Butter", "price": 1.29, "app_price": 0.99}]
    reference = [{"name": "Butter", "price": 1.29}]

    assert blackbox_eval.match_deals(system, reference)["matched"] == 1
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `.venv/bin/python -m pytest tests/test_blackbox_eval.py -q`
Erwartet: FAIL mit `ModuleNotFoundError: No module named 'magda.blackbox_eval'`

- [ ] **Schritt 3: Matching implementieren**

```python
# src/magda/blackbox_eval.py
"""Die LLM-Blackbox gegen die eigene Pipeline messen.

Der Vergleich laeuft ueber die *gemeinsame* Feldmenge (name, price,
original_price). Das Blackbox-Schema kennt weder App-Preise noch
Menge/Grundpreis - ihr das anzulasten hiesse, sie an einer Aufgabe zu
messen, die sie nie hatte.

Gepaart wird ueber den Preis (exakt) und den Namen (unscharf): Preise sind
in einem Prospekt eindeutig, Namen variieren in Sortenzusaetzen - genau die
Grenzfrage, die im Projekt ohnehin offen ist. Jedes Angebot wird hoechstens
einmal gepaart, sonst treibt ein System seinen Recall mit Duplikaten hoch.
"""

from __future__ import annotations

from difflib import SequenceMatcher

NAME_SIMILARITY = 0.6


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def match_deals(system: list[dict], reference: list[dict],
                price_tolerance: float = 0.0) -> dict:
    """Paart zwei Angebotslisten einer Seite ueber Preis und Name."""
    unused = list(range(len(reference)))
    matched = 0
    for deal in system:
        best, best_score = None, 0.0
        for index in unused:
            other = reference[index]
            if abs(float(deal.get("price") or 0) - float(other.get("price") or 0)) > price_tolerance:
                continue
            score = _similar(deal.get("name", ""), other.get("name", ""))
            if score >= NAME_SIMILARITY and score > best_score:
                best, best_score = index, score
        if best is not None:
            unused.remove(best)
            matched += 1

    only_system = len(system) - matched
    only_reference = len(unused)
    if not system and not reference:
        f1 = None
    else:
        precision = matched / len(system) if system else 0.0
        recall = matched / len(reference) if reference else 0.0
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"matched": matched, "only_system": only_system,
            "only_reference": only_reference, "f1": f1}
```

- [ ] **Schritt 4: Tests laufen lassen, jetzt grün**

Run: `.venv/bin/python -m pytest tests/test_blackbox_eval.py -q`
Erwartet: 5 passed

- [ ] **Schritt 5: CLI schreiben, die BEIDE Seiten misst und die Zeit stoppt**

```python
# src/magda/cli/blackbox_eval.py
"""Blackbox gegen die eigene Pipeline - eine Seite je Testcluster."""

from __future__ import annotations

import argparse
import json
import time

from magda import blackbox_eval, config


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="magda blackbox-eval",
        description="LLM-Blackbox gegen die eigene Pipeline messen.")
    parser.add_argument("--pages", required=True,
                        help="Datei mit page_ids, eine je Zeile")
    parser.add_argument("--model", default=config.CHAT_AI_VISION_MODEL)
    parser.add_argument("--predictions", default="gbert")
    args = parser.parse_args(argv)

    page_ids = [line.strip() for line in open(args.pages) if line.strip()]
    # Die Zeitmessung ist der eigentliche Nebengewinn: sie vergleicht
    # erstmals Produkt gegen Produkt statt Labeling gegen Inferenz.
    started = time.perf_counter()
    # ... Blackbox je Seite aufrufen, Ergebnis sammeln ...
    blackbox_seconds = time.perf_counter() - started

    print(f"Blackbox: {blackbox_seconds/len(page_ids):.1f} s je Seite")
```

**Hinweis für den Bearbeiter:** Der Blackbox-Aufruf braucht PDF-Bytes je Seite (`data/raw/<katalog>/bk_<n>.pdf`) und einen `OpenAI`-Client wie in `labeling.py`. Die eigene Pipeline-Ausgabe kommt aus `magda offers --predictions gbert` und muss auf dieselben drei Felder projiziert werden.

- [ ] **Schritt 6: Seitenliste erzeugen — eine je Testcluster**

```bash
.venv/bin/python -c "
import json
from magda.cli.offers_model import SPLIT_FILE, _load_labeled_pages
from magda.dedupe import group
split = json.loads(SPLIT_FILE.read_text())
pages = {p['page_id']: p for p in _load_labeled_pages('sonnet-5')}
test = [pages[p] for p in split['test'] if p in pages]
words = {p['page_id']: [w['text'] for w in p.get('words') or []] for p in test}
clusters = [sorted(c) for c in group(words, threshold=0.7)]
known = {x for c in clusters for x in c}
clusters += [[p['page_id']] for p in test if p['page_id'] not in known]
print('\n'.join(sorted(c[0] for c in clusters)))
" > data/eval/test_cluster_pages.txt
wc -l data/eval/test_cluster_pages.txt
```

Erwartet: **43 Zeilen** (100 Testseiten in 43 Clustern).

- [ ] **Schritt 7: NICHT jetzt ausführen — für Aufgabe 6 vormerken**

Der Lauf berührt Test. Er gehört in den gebündelten Schlussbatch. Hier endet die Vorbereitung.

- [ ] **Schritt 8: Committen**

```bash
git add src/magda/blackbox_eval.py src/magda/cli/blackbox_eval.py \
        src/magda/cli/__init__.py tests/test_blackbox_eval.py data/eval/test_cluster_pages.txt
git commit -m "Baue den Blackbox-Vergleichsarm, ohne ihn schon auf Test zu fahren"
```

---

## Aufgabe 2: Lernkurve — wie viel Lehrer braucht der Schüler?

**Warum:** Das Projekt *ist* Knowledge Distillation mit LLM-Silberlabels. Es so zu nennen ist Verpackung; die Kurve ist der Befund. Man weiß vorher nicht, ob sie bei 50 Seiten sättigt oder bei 175 noch steigt — und FUNSD trainiert mit 149 Dokumenten, die Frage ist also literaturseitig interessant.

**Clusterweise ziehen, nicht seitenweise.** Sonst misst man Regionalfassungs-Duplikate als Datenmenge — derselbe Fehler wie beim Split-Leck.

**Dateien:**
- Ändern: `src/magda/dataset.py` (Funktion `subset_by_clusters`)
- Ändern: `src/magda/cli/train.py` (Option `--train-pages`)
- Erstellen: `tests/test_dataset_subset.py`

**Schnittstellen:**
- Liefert: `dataset.subset_by_clusters(pages: list[dict], limit: int) -> list[str]`

- [ ] **Schritt 1: Failing Test**

```python
# tests/test_dataset_subset.py
"""Trainingsteilmengen fuer die Lernkurve - ganze Duplikat-Cluster.

Seitenweise gezogen zaehlen elf Regionalfassungen derselben Vorlage als elf
Datenpunkte. Die Kurve saehe dann steiler aus, als sie ist - derselbe
Fehler, der schon den Seiten-Split lecken liess.
"""

from magda import dataset


def _page(page_id, texts):
    return {"page_id": page_id,
            "words": [{"text": t, "bbox": [0, 0, 1, 1]} for t in texts]}


def test_es_werden_ganze_cluster_gezogen():
    zwillinge = ["Butter", "Milch", "Kaese", "Brot"]
    pages = [_page("a", zwillinge), _page("b", zwillinge),
             _page("c", ["Wein", "Bier", "Saft", "Wasser"])]

    chosen = dataset.subset_by_clusters(pages, limit=2)

    # a und b sind ein Cluster - entweder beide oder keiner.
    assert set(chosen) in ({"a", "b"}, {"c"})


def test_die_grenze_wird_nicht_ueberschritten_wenn_ein_cluster_passt():
    pages = [_page(str(i), [f"w{i}", "x", "y", "z"]) for i in range(5)]

    assert len(dataset.subset_by_clusters(pages, limit=3)) <= 3


def test_dieselbe_grenze_ergibt_dieselbe_teilmenge():
    """Sonst ist die Lernkurve zwischen zwei Laeufen nicht vergleichbar."""
    pages = [_page(str(i), [f"w{i}", "x", "y", "z"]) for i in range(8)]

    assert dataset.subset_by_clusters(pages, 4) == dataset.subset_by_clusters(pages, 4)
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `.venv/bin/python -m pytest tests/test_dataset_subset.py -q`
Erwartet: FAIL — `subset_by_clusters` existiert nicht

- [ ] **Schritt 3: Implementieren**

```python
# in src/magda/dataset.py ergaenzen
def subset_by_clusters(pages: list[dict], limit: int) -> list[str]:
    """Die ersten `limit` Seiten, aber nur in ganzen Duplikat-Clustern.

    Fuer die Lernkurve: Seitenweise gezogen zaehlen elf Regionalfassungen
    derselben Vorlage als elf Datenpunkte, und die Kurve saehe steiler aus,
    als sie ist. Deterministisch sortiert, damit zwei Laeufe dieselbe
    Teilmenge ergeben - sonst ist die Kurve nicht vergleichbar.
    """
    from magda.dedupe import group

    words = {p["page_id"]: [w["text"] for w in (p.get("words") or [])] for p in pages}
    clusters = [sorted(c) for c in group(words, threshold=0.7)]
    known = {page_id for cluster in clusters for page_id in cluster}
    clusters += [[p["page_id"]] for p in pages if p["page_id"] not in known]

    chosen: list[str] = []
    for cluster in sorted(clusters, key=lambda c: (-len(c), c[0])):
        if len(chosen) + len(cluster) > limit:
            continue
        chosen.extend(cluster)
    return sorted(chosen)
```

- [ ] **Schritt 4: Tests grün**

Run: `.venv/bin/python -m pytest tests/test_dataset_subset.py -q`
Erwartet: 3 passed

- [ ] **Schritt 5: `--train-pages` in `cli/train.py` ergänzen**

Die Option beschränkt die Trainingsseiten auf `subset_by_clusters(train_pages, N)` und schreibt die tatsächlich benutzte Zahl in den Checkpoint-Namen (`checkpoints/gbert-p50/`), damit vier Läufe nebeneinander bestehen.

- [ ] **Schritt 6: Vier Modelle trainieren**

```bash
for n in 25 50 100 175; do
  .venv/bin/magda train gbert --labels-from sonnet-5 --train-pages $n
done
```

96 s je Lauf. Alle vier passen in eine GPU-Session — zusammen mit dem APP_PRICE-Nachtraining aus dem anderen Plan.

- [ ] **Schritt 7: NICHT auf Test auswerten**

Die Kurvenpunkte werden **einmal, im Schlussbatch** ausgewertet (Aufgabe 6). Vier Einzelauswertungen wären vier Test-Berührungen.

**In den Bericht gehört ausdrücklich:** Die Kurve ist **deskriptiv, nicht selektiv** — an ihrem Ergebnis hängt keine Entscheidung. Nur so ist die Mehrfachauswertung regelkonform.

- [ ] **Schritt 8: Committen**

```bash
git add src/magda/dataset.py src/magda/cli/train.py tests/test_dataset_subset.py
git commit -m "Ziehe Trainingsteilmengen clusterweise fuer die Lernkurve"
```

---

## Aufgabe 3: Drift-Kurve — wie schnell veraltet der Schüler?

**Warum:** Der stärkste vorhandene Einzelbefund („die Pipeline hinkt Sortimentsänderungen eine Woche hinterher", APP_PRICE 2 → 57 → 98 Spans) lässt sich mit Woche 4 zur Kurve ausbauen: das eingefrorene KW30/31-Modell auf KW32 (liegt vor) **und** KW33/34. Zwei Zeitabstände.

**Die Aussage entsteht erst durch die Aufschlüsselung je Label.** „F1 sinkt" ist banal; „BRAND und PRICE altern nicht, APP_PRICE altert schnell — das Modell veraltet nicht sprachlich, sondern sortimentsseitig" ist ein Befund.

**Voraussetzung:** `magda eval` kennt nur `--split {dev,test}` (geprüft). Woche 4 steht in keinem Split — es braucht `--pages`.

**Dateien:**
- Ändern: `src/magda/cli/evaluate.py` (Option `--pages`)
- Erstellen: `tests/test_evaluate_pages.py`
- Erzeugt: `data/eval/drift_gbert.json`

- [ ] **Schritt 1: Failing Test für die Seitenauswahl**

```python
# tests/test_evaluate_pages.py
"""Auswerten auf einer freien Seitenmenge statt auf einem Split.

Woche 4 steht bewusst in keinem Split - sie ist die unberuehrte
Frischwoche. Fuer die Drift-Messung muss `magda eval` sie trotzdem
auswerten koennen, ohne dass jemand den eingefrorenen Split anfasst.
"""

import pytest

from magda.cli import evaluate


def test_eine_seitenliste_schlaegt_den_split(tmp_path):
    listing = tmp_path / "pages.txt"
    listing.write_text("1355990_p1\n1355990_p2\n")

    assert evaluate.read_page_ids(listing) == ["1355990_p1", "1355990_p2"]


def test_leerzeilen_und_kommentare_werden_uebergangen(tmp_path):
    listing = tmp_path / "pages.txt"
    listing.write_text("# Woche 4\n1355990_p1\n\n  1355990_p2  \n")

    assert evaluate.read_page_ids(listing) == ["1355990_p1", "1355990_p2"]


def test_eine_leere_liste_bricht_ab(tmp_path):
    listing = tmp_path / "pages.txt"
    listing.write_text("# nur ein Kommentar\n")

    with pytest.raises(ValueError, match="keine Seiten"):
        evaluate.read_page_ids(listing)
```

- [ ] **Schritt 2: Fehlschlag bestätigen**

Run: `.venv/bin/python -m pytest tests/test_evaluate_pages.py -q`

- [ ] **Schritt 3: `read_page_ids` und `--pages` implementieren**

```python
# in src/magda/cli/evaluate.py ergaenzen
def read_page_ids(path) -> list[str]:
    """Seitenliste aus einer Datei - eine je Zeile, `#` ist Kommentar.

    Gebraucht fuer Seitenmengen, die in keinem Split stehen: Woche 4 ist
    die unberuehrte Frischwoche und soll es bleiben.
    """
    from pathlib import Path

    lines = [line.split("#")[0].strip() for line in Path(path).read_text().splitlines()]
    page_ids = [line for line in lines if line]
    if not page_ids:
        raise ValueError(f"{path} enthaelt keine Seiten.")
    return page_ids
```

- [ ] **Schritt 4: Tests grün**

Run: `.venv/bin/python -m pytest tests/test_evaluate_pages.py -q`
Erwartet: 3 passed

- [ ] **Schritt 5: Woche-4-Seitenliste erzeugen**

```bash
.venv/bin/python -c "
import json
from pathlib import Path
from magda.cli.offers_model import SPLIT_FILE
split = json.loads(SPLIT_FILE.read_text())
im_split = {p for n in ('train','dev','test') for p in split[n]}
alle = {p.stem for p in Path('data/words').glob('*.json')}
print('\n'.join(sorted(alle - im_split)))
" > data/eval/woche4_pages.txt
wc -l data/eval/woche4_pages.txt
```

Erwartet: **126 Zeilen**.

- [ ] **Schritt 6: Drift messen — je Label**

```bash
.venv/bin/magda eval gbert --split test --labels-from sonnet-5      # KW32, liegt vor
.venv/bin/magda eval gbert --pages data/eval/woche4_pages.txt --labels-from sonnet-5
```

**Achtung:** Der erste Befehl berührt Test — er gehört deshalb in den Schlussbatch (Aufgabe 6) oder nutzt den bereits vorhandenen Report.

- [ ] **Schritt 7: Kurve je Label auswerten und committen**

Tabelle: Label × Zeitabstand (0 / 1 / 2 Wochen), F1 je Zelle. Woche 4 bleibt danach **entwicklungsfrei** — einmal messen ja, daran drehen nein, sonst ist die Frischwochen-Demo verbrannt.

```bash
git add src/magda/cli/evaluate.py tests/test_evaluate_pages.py data/eval
git commit -m "Miss die zeitliche Drift ueber zwei Wochenabstaende je Label"
```

---

## Aufgabe 4: Fehler-Taxonomie mit Lösbarkeits-Spalte

**Warum:** Die Einzelbefunde liegen verstreut im Repo: APP_PRICE-Fehler sind zu 100 % Typverwechslungen bei null reinen Falsch-Negativen; 106 von 135 PRODUCT-Fehlern sind Sortenzusatz-Grenzfehler; ≥60 PRICE-„Fehler" sind ungelabelte Badge-Preise, also **Lehrerfehler**; der Legendenversatz ist eine eigene Klasse. Was fehlt, ist die Systematik.

**Die vierte Spalte ist der wissenschaftliche Gehalt:** *womit ist diese Klasse überhaupt lösbar* — Prompt-Regel / Code-Guard / mehr Daten / Bildmerkmal / **prinzipiell unlösbar aus Text**. Sie trennt behebbare von strukturellen Fehlern. Der 33-%-Befund („App-Kasten steht nicht im Textlayer") ist ihr Kronzeuge.

**Repo-Regel beachten:** Jede Häufigkeit braucht ihr erzeugendes Skript. Die in CLAUDE.md verstreuten Zählungen qualifizieren sich so **nicht**.

**Dateien:**
- Erstellen: `src/magda/error_taxonomy.py`, `src/magda/cli/taxonomy.py`, `tests/test_error_taxonomy.py`
- Erzeugt: `data/eval/error_taxonomy.json`

- [ ] **Schritt 1: Klassen festlegen** (im Modul-Docstring, mit Beleg je Klasse)

```
typverwechslung      Vorhersage und Referenz sind beide != O, Typ verschieden
grenzfehler          gleicher Typ, verschobene Span-Grenze
lehrerluecke         Vorhersage != O, Referenz == O, aber Muster bekannt
                     (Badge-Preis, App-Kasten)
echtes_falsch_negativ Referenz != O, Vorhersage == O
echtes_falsch_positiv Vorhersage != O, Referenz == O, kein bekanntes Muster
```

- [ ] **Schritt 2: Failing Test je Klasse schreiben** (fünf Tests, je ein synthetisches Beispiel)

- [ ] **Schritt 3: Klassifikation implementieren, Tests grün**

- [ ] **Schritt 4: Auf Dev auswerten** (nicht Test — das kommt im Schlussbatch)

- [ ] **Schritt 5: Committen**

```bash
git add src/magda/error_taxonomy.py src/magda/cli/taxonomy.py \
        tests/test_error_taxonomy.py data/eval/error_taxonomy.json
git commit -m "Ordne die Fehlerklassen und sage je Klasse, was sie loesen wuerde"
```

---

## Aufgabe 5: „Wie viel Schülerfehler sind Lehrerfehler?"

**Warum:** Möglicherweise der eigenständigste Befund des Projekts. Der naheliegende Weg über `data/audit/APP_PRICE.json` **funktioniert nicht**: die dortigen Kandidaten liegen 72/9/**0** in Train/Dev/Test — auf Train wäre die Messung in-sample, auf Dev ist n=9, und Test enthält per Konstruktion keinen lehrer-inkonsistenten Fall.

Die machbare Fassung: eine **frische Handprüfung der Schüler-Abweichungen auf dem Testsplit** — die ~40 überzähligen APP_PRICEs und eine Stichprobe der ~263 PRICE-Falsch-Positiven. Ergebnis: „X % der dem Schüler angelasteten Fehler sind Lehrerfehler; die lehrerreferenzierte Metrik unterschätzt den Schüler um bis zu Y Punkte."

**Das ist keine Test-Entwicklung:** Beurteilt wird die *Referenz*, nichts wird geändert und keine Entscheidung daran geknüpft. Das ist regelkonform.

**Offenlegen:** Die Stichprobe ist disagreement-only, also eine **Schranke, kein Punktwert**.

- [ ] **Schritt 1: Kandidaten vorsortieren** (`magda audit`-Mechanik auf Abweichungen statt auf ein Label)
- [ ] **Schritt 2: Im vorhandenen `/audit`-UI durchsehen** — Timebox **4 Stunden**, danach wird ausgewertet, was beurteilt ist
- [ ] **Schritt 3: Anteil berechnen und als Schranke berichten**
- [ ] **Schritt 4: Committen**

---

## Aufgabe 6: Der EINE Schlussbatch auf Test

**Warum:** Aufgaben 1, 2, 3 und 5 brauchen alle Testzahlen. Einzeln ausgeführt wären das vier bis sechs Test-Berührungen. Gebündelt ist es eine.

**Vorbedingung:** Alles eingefroren. Nach diesem Batch wird **nichts mehr geändert** — jede Änderung danach hieße, Test zweimal anzufassen.

- [ ] **Schritt 1: Einfrieren bestätigen** — `git status` sauber, alle Aufgaben 1–5 committet
- [ ] **Schritt 2: Ende-zu-Ende auf Test** (aus dem anderen Plan: Teacher-Gruppierung für die 43 Clusterseiten, dann `predict --split test` → Paarmodell → `offers-gold --predictions gbert` → `offers-verify`)
- [ ] **Schritt 3: Blackbox-Lauf** über `data/eval/test_cluster_pages.txt`, mit Zeitmessung beider Seiten
- [ ] **Schritt 4: Lernkurve** — die vier Checkpoints auf Test auswerten
- [ ] **Schritt 5: Drift** — KW32-Punkt
- [ ] **Schritt 6: Alle Reports committen**

```bash
git add data/eval
git commit -m "Werte den Testsplit einmal gebuendelt aus"
```

---

## Aufgabe 7 (Timebox, 1 Tag): Sonde auf einen zweiten Händler

**Warum:** Alles ist Penny. Ein Transfertest zeigt, ob die Pipeline eine Eigenschaft *dieses* Händlers gelernt hat.

**Harter Abbruch:** Nach einem Tag ohne lauffähige Extraktion wird abgebrochen und der Grund dokumentiert. Kein Scraper, kein OCR-Fallback, keine eigenen Prompts.

- [ ] **Schritt 1: Einen Prospekt von Hand herunterladen** (Lidl, REWE oder Netto)
- [ ] **Schritt 2: Textlayer prüfen**

```bash
.venv/bin/python -c "
import fitz, sys
doc = fitz.open(sys.argv[1])
print(len(doc[0].get_text('words')), 'Woerter auf Seite 1')
" /pfad/zum/prospekt.pdf
```

**Kein Textlayer → das Ergebnis ist ein *Satz* im Bericht** („die Pipeline setzt einen Textlayer voraus; Händler X liefert Bild-PDFs, der Transfer bräuchte OCR"), kein Kapitel. Hier ist Schluss.

- [ ] **Schritt 3 (nur bei Textlayer): 5–10 Seiten extrahieren, LLM-labeln, GBERT zero-shot messen, Einbruch berichten**

---

## Selbstprüfung

**Abdeckung:** Alle sieben Ränge aus der Beratung sind abgebildet — Rang 0 → Aufgabe 1, Rang 1 → Aufgabe 2, Rang 2 → Aufgabe 3, Rang 3 → Aufgabe 4, Rang 4 → Aufgabe 5, Rang 5 (Ökonomie) → ergibt sich aus Aufgabe 2 und der Zeitmessung in Aufgabe 1, Rang 6 → Aufgabe 7. Die als Effekthascherei benannten Punkte stehen im Abschnitt „Ausdrücklich nicht Teil dieses Plans".

**Platzhalter:** Aufgabe 1 Schritt 5, Aufgabe 4 Schritte 2–4 und Aufgabe 5 sind bewusst gröber gehalten — sie hängen an Entscheidungen, die erst nach den vorigen Schritten fallen (welches Modell, welche Fehlerklassen tatsächlich auftreten, wie viele Kandidaten die Vorsortierung liefert). **Der Bearbeiter verfeinert sie, bevor er sie angeht**, statt sie zu raten.

**Typkonsistenz:** `match_deals(system, reference, price_tolerance)` ist in Test und Implementierung deckungsgleich; `subset_by_clusters(pages, limit) -> list[str]` und `read_page_ids(path) -> list[str]` ebenso.

**Reihenfolgezwang:** Aufgabe 6 ist der einzige Test-Kontakt und setzt 1, 2, 3 und 5 als abgeschlossen voraus. Aufgabe 4 und 7 sind davon unabhängig.
