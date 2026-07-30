"""Welche Seiten sind wirklich verschieden?

Penny gibt je Woche 44 Regionalausgaben heraus. Über 90 % der Seiten sind
identisch, und der Rest unterscheidet sich oft nur in Kleinigkeiten – eine
Herkunftsangabe („NRW" statt „Deutschland"), ein ausgetauschter Artikel. Für
ein Modell sind zwei Seiten mit 95 % gleichen Wörtern effektiv dieselbe Seite:
sie blähen den Datensatz auf, kosten LLM-Zeit beim Labeln und landen im
Zweifel gleichzeitig im Train- und im Testsplit. Dann misst das Test-F1
teilweise Auswendiglernen.

Zwei Stufen, weil sie verschiedene Fehler abfangen:

**Druckkennung entfernen.** Am rechten Seitenrand steht senkrecht ein Code der
Form ``25_02-09-10`` – Seite 25, gedruckt für die Regionen 02, 09 und 10. Er
steht im Textlayer, gehört aber nicht zum Prospekt. Ohne ihn zu entfernen gilt
jede geteilte Seite als 44-fach verschieden. Weggeworfen wird er nur für den
Vergleich; als Herkunftsangabe ist er wertvoll (siehe `print_marker`).

**Ähnlichkeit statt Gleichheit.** Nach der Bereinigung bleiben Seitenpaare mit
Jaccard-Ähnlichkeit über 0.9, die inhaltlich dieselbe Anzeige zeigen. Die
Schwelle ist eine Abwägung und deshalb ein Parameter, kein Naturgesetz –
gemessen am 29.07.2026 über 269 Seiten:

======  ===================
0.98    234 Gruppen
0.95    195 Gruppen
0.90    160 Gruppen
======  ===================
"""

import json
import re

# Senkrechter Code in der Beschnittzone: "<Seite>_<Region>-<Region>-…".
_PRINT_MARKER = re.compile(r"^\d{2}_\d{2}(-\d{2})*$")


def print_marker(words: list[str]) -> str | None:
    """Die Druckkennung der Seite, falls vorhanden.

    Sie nennt die Regionen, die sich diese Druckplatte teilen – die genaueste
    Herkunftsangabe, die eine einzelne Seite überhaupt hergibt.
    """
    for word in words:
        if _PRINT_MARKER.match(word):
            return word
    return None


def normalize(words: list[str]) -> list[str]:
    """Wortliste ohne Druckkennung – die Grundlage jedes Vergleichs."""
    return [w for w in words if not _PRINT_MARKER.match(w)]


def similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def group(pages: dict[str, list[str]], threshold: float = 0.95) -> list[list[str]]:
    """Gruppiert Seiten-IDs, die dieselbe Seite zeigen.

    Union-Find über die Ähnlichkeit: A~B und B~C legt A, B und C zusammen, auch
    wenn A und C knapp unter der Schwelle liegen. Das ist gewollt – eine Kette
    beinahe gleicher Regionalfassungen ist eine Seite, keine drei.

    Gruppen sind nach der ersten ID sortiert, innerhalb nach ID.
    """
    sets = {pid: set(normalize(words)) for pid, words in pages.items()}
    parent = {pid: pid for pid in sets}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ids = sorted(sets)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            sets_a, sets_b = sets[a], sets[b]
            if not sets_a or not sets_b:
                continue
            # Vorfilter: bei sehr verschiedener Wortzahl kann die Jaccard-Ähnlichkeit
            # die Schwelle nicht mehr erreichen. Spart den teuren Mengenschnitt.
            if min(len(sets_a), len(sets_b)) / max(len(sets_a), len(sets_b)) < threshold:
                continue
            if similarity(sets_a, sets_b) >= threshold:
                root_a, root_b = find(a), find(b)
                if root_a != root_b:
                    parent[root_b] = root_a

    groups: dict[str, list[str]] = {}
    for pid in ids:
        groups.setdefault(find(pid), []).append(pid)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: g[0])


def choose(group_ids: list[str], preferred: set[str]) -> str:
    """Wer vertritt die Gruppe?

    Bevorzugt wird, woran schon Arbeit hängt – eine gelabelte oder von Hand
    annotierte Seite. Sie wegzuwerfen hieße, diese Arbeit wegzuwerfen.
    """
    hits = [pid for pid in group_ids if pid in preferred]
    return sorted(hits)[0] if hits else group_ids[0]


# --- Ausschlussliste --------------------------------------------------------
#
# Löschen allein reicht nicht: Schritt 02 baut data/words aus data/raw wieder
# auf und erkennt dabei nur exakt gleiche Wortlisten. Ohne diese Liste kommt
# jedes Beinah-Duplikat beim nächsten Lauf zurück – und wird beim übernächsten
# gelabelt, also mit LLM-Zeit bezahlt.


def load_excluded() -> dict[str, str]:
    """Ausgeschlossene page_id -> die Seite, die sie vertritt."""
    from magda import config

    if not config.EXCLUDED_FILE.exists():
        return {}
    try:
        with open(config.EXCLUDED_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_excluded(excluded: dict[str, str]) -> None:
    from magda import config

    config.EXCLUDED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(config.EXCLUDED_FILE, "w") as f:
        json.dump(dict(sorted(excluded.items())), f, ensure_ascii=False, indent=1)
