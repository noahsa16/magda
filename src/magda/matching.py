"""Vier Auswertungsschemata nach SemEval-2013 Task 9.1 (MUC-5-Konvention).

Warum nicht eine Zahl: seqeval wertet strikt – Span *und* Typ müssen exakt
stimmen, ein Wort daneben zählt doppelt als Fehler (Falsch-Positiv *und*
Falsch-Negativ). Gemessen über die Testwoche sind 159 der 5107 Entitäten
genau das: richtiger Typ, Grenze verschoben. Und die Verschiebung ist meist
keine Modellschwäche, sondern die offene Frage, ob Sortenangaben ins PRODUCT
gehören – die Referenz selbst schwankt dort in beide Richtungen
(`"Frische Lammspieße* Mariniert, …"` gegen `"Frische Lammspieße*"`).

Für den Zweck des Projekts ist das folgenlos: ob der Sortenzusatz im
Produktstring steht, macht den Angebotsdatensatz nicht falsch. Ob ein Preis
als Streichpreis gilt, sehr wohl. Eine Metrik, die beides gleich hart
bestraft, misst am Zweck vorbei – eine, die beides gleich mild behandelt,
aber auch.

    strict    Grenze und Typ exakt. Strengste Lesart, Anschluss an die
              bisher berichteten Zahlen und an die Literatur.
    exact     Grenze exakt, Typ wird ignoriert. Findet das Modell die
              richtigen Textstellen?
    partial   Überlappung genügt, Typ ignoriert; teilweise Treffer zählen
              nach MUC-Konvention 0.5. Bestraft grobe Abweichung noch.
    type      Typ stimmt und die Spans überlappen irgendwie. Beantwortet:
              Ist an dieser Stelle inhaltlich das richtige Feld erkannt?

**Es werden immer alle vier berichtet.** Wer sich eine aussucht, weil sie
besser aussieht, betreibt Metrik-Shopping; das Kriterium gehört vorab aus dem
Anwendungsfall begründet, nicht nachträglich aus dem Ergebnis. Aus demselben
Grund steht in jedem Report, nach welchem Schema gemessen wurde.

Zählweise (SemEval-2013): COR korrekt, INC falscher Typ, PAR teilweise,
MIS übersehen, SPU erfunden. POSSIBLE = COR+INC+PAR+MIS (Referenzseite),
ACTUAL = COR+INC+PAR+SPU (Vorhersageseite).

Quelle: Segura-Bedmar, Martínez & Herrero-Zazo (2013), SemEval-2013 Task 9;
Zählschema wie in der MUC-5-Evaluation.
"""

from dataclasses import dataclass

SCHEMES = ("strict", "exact", "partial", "type")


@dataclass
class Counts:
    correct: int = 0
    incorrect: int = 0
    partial: int = 0
    missing: int = 0
    spurious: int = 0

    @property
    def possible(self) -> int:
        return self.correct + self.incorrect + self.partial + self.missing

    @property
    def actual(self) -> int:
        return self.correct + self.incorrect + self.partial + self.spurious

    def scores(self) -> dict:
        """Teiltreffer zählen halb – die MUC-Konvention für `partial`."""
        hits = self.correct + 0.5 * self.partial
        precision = hits / self.actual if self.actual else 0.0
        recall = hits / self.possible if self.possible else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "correct": self.correct,
            "incorrect": self.incorrect,
            "partial": self.partial,
            "missing": self.missing,
            "spurious": self.spurious,
            "possible": self.possible,
            "actual": self.actual,
        }


def _overlaps(a: dict, b: dict) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def _same_span(a: dict, b: dict) -> bool:
    return a["start"] == b["start"] and a["end"] == b["end"]


def count_page(reference: list[dict], predicted: list[dict]) -> dict[str, Counts]:
    """Zählt eine Seite in allen vier Schemata.

    Jede Vorhersage wird höchstens einer Referenz zugeordnet und umgekehrt:
    zuerst die deckungsgleichen Spans, danach der Rest über Überlappung. Ohne
    diese Reihenfolge könnte ein zufällig überlappender Nachbar den exakten
    Treffer wegschnappen und das Ergebnis hinge an der Sortierung.
    """
    counts = {scheme: Counts() for scheme in SCHEMES}

    offen_ref = list(reference)
    offen_pred = list(predicted)
    paare: list[tuple[dict, dict]] = []

    for exakt in (True, False):
        rest_ref, genommen = [], set()
        for r in offen_ref:
            partner = None
            for i, p in enumerate(offen_pred):
                if i in genommen:
                    continue
                if _same_span(r, p) if exakt else _overlaps(r, p):
                    partner = (i, p)
                    break
            if partner is None:
                rest_ref.append(r)
            else:
                genommen.add(partner[0])
                paare.append((r, partner[1]))
        offen_ref = rest_ref
        offen_pred = [p for i, p in enumerate(offen_pred) if i not in genommen]

    for r, p in paare:
        gleicher_span = _same_span(r, p)
        gleicher_typ = r["label"] == p["label"]

        if gleicher_span and gleicher_typ:
            counts["strict"].correct += 1
        elif gleicher_span:
            counts["strict"].incorrect += 1
        else:
            counts["strict"].incorrect += 1

        if gleicher_span:
            counts["exact"].correct += 1
        else:
            counts["exact"].incorrect += 1

        if gleicher_span:
            counts["partial"].correct += 1
        else:
            counts["partial"].partial += 1

        if gleicher_typ:
            counts["type"].correct += 1
        else:
            counts["type"].incorrect += 1

    for scheme in SCHEMES:
        counts[scheme].missing += len(offen_ref)
        counts[scheme].spurious += len(offen_pred)
    return counts


def evaluate(
    reference: list[list[dict]], predicted: list[list[dict]]
) -> dict[str, dict]:
    """Alle vier Schemata über einen ganzen Split.

    `reference` und `predicted` sind je Seite eine Span-Liste
    (`{"start", "end", "label"}`), wie `labels.bio_to_spans` sie liefert.
    """
    gesamt = {scheme: Counts() for scheme in SCHEMES}
    for ref_page, pred_page in zip(reference, predicted):
        seite = count_page(ref_page, pred_page)
        for scheme in SCHEMES:
            c, s = gesamt[scheme], seite[scheme]
            c.correct += s.correct
            c.incorrect += s.incorrect
            c.partial += s.partial
            c.missing += s.missing
            c.spurious += s.spurious
    return {scheme: gesamt[scheme].scores() for scheme in SCHEMES}


def evaluate_per_label(
    reference: list[list[dict]], predicted: list[list[dict]], scheme: str = "type"
) -> dict[str, dict]:
    """Dasselbe je Entity-Typ – für den Vergleich, wo ein Schema wie wirkt.

    Beim Aufteilen nach Label zählt die Referenzseite: eine Vorhersage mit
    falschem Typ erscheint beim Label der *Referenz*. Sonst tauchte derselbe
    Fehler zweimal auf und die Summe der Labels wiche vom Gesamtwert ab.
    """
    labels = {s["label"] for page in reference for s in page}
    ergebnis = {}
    for label in sorted(labels):
        ref = [[s for s in page if s["label"] == label] for page in reference]
        pred = [[s for s in page if s["label"] == label] for page in predicted]
        ergebnis[label] = evaluate(ref, pred)[scheme]
    return ergebnis
