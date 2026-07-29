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
    mengen = {pid: set(normalize(words)) for pid, words in pages.items()}
    eltern = {pid: pid for pid in mengen}

    def find(x: str) -> str:
        while eltern[x] != x:
            eltern[x] = eltern[eltern[x]]
            x = eltern[x]
        return x

    ids = sorted(mengen)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            mengen_a, mengen_b = mengen[a], mengen[b]
            if not mengen_a or not mengen_b:
                continue
            # Vorfilter: bei sehr verschiedener Wortzahl kann die Jaccard-Ähnlichkeit
            # die Schwelle nicht mehr erreichen. Spart den teuren Mengenschnitt.
            if min(len(mengen_a), len(mengen_b)) / max(len(mengen_a), len(mengen_b)) < threshold:
                continue
            if similarity(mengen_a, mengen_b) >= threshold:
                wurzel_a, wurzel_b = find(a), find(b)
                if wurzel_a != wurzel_b:
                    eltern[wurzel_b] = wurzel_a

    gruppen: dict[str, list[str]] = {}
    for pid in ids:
        gruppen.setdefault(find(pid), []).append(pid)
    return sorted((sorted(g) for g in gruppen.values()), key=lambda g: g[0])


def choose(group_ids: list[str], preferred: set[str]) -> str:
    """Wer vertritt die Gruppe?

    Bevorzugt wird, woran schon Arbeit hängt – eine gelabelte oder von Hand
    annotierte Seite. Sie wegzuwerfen hieße, diese Arbeit wegzuwerfen.
    """
    treffer = [pid for pid in group_ids if pid in preferred]
    return sorted(treffer)[0] if treffer else group_ids[0]
