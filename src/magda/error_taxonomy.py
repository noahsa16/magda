"""Fehler des Schülers ordnen — und je Klasse sagen, was sie lösen würde.

Die Einzelbefunde liegen verstreut im Repo: APP_PRICE-Fehler sind fast
ausschließlich Typverwechslungen bei null reinen Falsch-Negativen; 106 von
135 PRODUCT-Fehlern sind Grenzfehler an Sortenzusätzen; mindestens 60
PRICE-„Fehler" sind ungelabelte Badge-Preise, also **Lehrerfehler**. Was
fehlt, ist die Systematik – und vor allem die vierte Spalte.

**Die Lösbarkeit ist der eigentliche Gehalt.** Ob ein Fehler mit einer
Prompt-Regel, einem Code-Guard, mehr Daten oder gar nicht aus dem Text
behebbar ist, entscheidet über die Priorisierung. Der Befund „bei 33 % der
APP_PRICE-Spans steht ‚App' nicht im Fenster ±8 Wörter" ist der Kronzeuge:
dort ist das Label aus der Eingabe **prinzipiell nicht ableitbar**, und
weder mehr Trainingsseiten noch ein größeres Modell ändern daran etwas.

Gearbeitet wird auf **Spans**, nicht auf Wörtern. Ein um ein Wort
verschobener Sortenzusatz ist ein Fehler, nicht zwei – auf Wortebene zählte
er als Falsch-Positiv *und* Falsch-Negativ und erschiene doppelt so schwer
wie ein echter Fehlgriff.

Die Zuordnung zu `lehrerluecke` ist bewusst **konservativ**: sie verlangt ein
belegtes Muster im Text, nicht bloß „Referenz sagt O". Sonst hieße jede
Übervorhersage des Schülers „der Lehrer war schuld", und die Klasse würde zur
Ausrede statt zur Messung.
"""

from __future__ import annotations

from magda.labels import bio_to_spans

# Wie weit um einen Span herum nach einem Muster gesucht wird. Derselbe Wert
# wie in `label_audit.CONTEXT_WORDS`, damit beide Analysen dieselbe Umgebung
# meinen, wenn sie von "im Fenster" sprechen.
CONTEXT_WORDS = 8

# Preistypen: nur bei ihnen ist die Fussnoten-/Badge-Erklaerung ueberhaupt
# plausibel. Ein uebervorhergesagtes PRODUCT neben einer Ziffer ist kein
# Badge-Preis.
PRICE_TYPES = frozenset({"PRICE", "APP_PRICE", "OLD_PRICE"})

CLASSES = (
    "typverwechslung",
    "grenzfehler",
    "lehrerluecke",
    "echtes_falsch_negativ",
    "echtes_falsch_positiv",
)

# Was die Klasse lösen würde. Keine Vermutung, sondern die Konsequenz aus dem
# jeweils belegten Befund – die Belege stehen in CLAUDE.md.
SOLVABILITY = {
    "typverwechslung": "konsistentere Referenz (Handprüfung, Code-Guard)",
    "grenzfehler": "Annotationsregel entscheiden (Sortenzusatz-Frage)",
    "lehrerluecke": "Referenz korrigieren – der Schüler hat recht",
    "echtes_falsch_negativ": "mehr Daten oder Bildmerkmal",
    "echtes_falsch_positiv": "mehr Daten",
}


def _overlaps(a: dict, b: dict) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def _window(words: list[str], span: dict) -> list[str]:
    start = max(0, span["start"] - CONTEXT_WORDS)
    end = min(len(words), span["end"] + CONTEXT_WORDS)
    return words[start:end]


def teacher_gap_reason(span: dict, words: list[str]) -> str | None:
    """Belegtes Muster, das eine Lehrerlücke erklärt – sonst `None`.

    Zwei Muster, beide gemessen und in CLAUDE.md begründet:

    `badge_ziffer` – Penny kennzeichnet den App-Preis mal mit dem Text „mit
    PENNY App", mal nur mit einer Fußnotenziffer hinter der Zahl. Das Muster
    `<preis> <ziffer>` ist in den sonnet-5-Labels 1x als APP_PRICE und 60x
    als O vergeben; wo der Schüler dort einen Preis sieht, liegt er eher
    richtig als die Referenz.

    `app_im_fenster` – steht „App" in der Umgebung und die Referenz schweigt,
    ist das dieselbe Inkonsistenz von der anderen Seite.
    """
    if span["label"] not in PRICE_TYPES:
        return None
    nachbarn = words[span["end"]:span["end"] + 2] + words[max(0, span["start"] - 2):span["start"]]
    if any(w.strip().isdigit() and len(w.strip()) <= 2 for w in nachbarn):
        return "badge_ziffer"
    if any("app" in w.lower() for w in _window(words, span)):
        return "app_im_fenster"
    return None


def classify_page(words: list[str], reference: list[str],
                  predicted: list[str]) -> list[dict]:
    """Alle Fehler einer Seite, je einer als Datensatz.

    Exakte Treffer (Grenze *und* Typ) tauchen nicht auf – gefragt sind die
    Fehler, nicht die Trefferquote; die misst `magda eval`.
    """
    ref = bio_to_spans(reference)
    pred = bio_to_spans(predicted)
    exact = {(s["start"], s["end"], s["label"]) for s in ref}

    errors: list[dict] = []
    matched_ref: set[int] = set()
    for span in pred:
        if (span["start"], span["end"], span["label"]) in exact:
            for index, other in enumerate(ref):
                if (other["start"], other["end"], other["label"]) == (
                        span["start"], span["end"], span["label"]):
                    matched_ref.add(index)
                    break
            continue

        # Der *am stärksten* überlappende Referenz-Span, nicht der erste.
        # Gierig nach Reihenfolge gepaart zerfiele eine PRODUCT-Vorhersage
        # über BRAND+PRODUCT in eine Typverwechslung (mit BRAND) *plus* ein
        # Falsch-Negativ (PRODUCT), statt ein Grenzfehler zu sein – die
        # Klassenverteilung verschöbe sich systematisch zu den schwereren
        # Klassen hin, und zwar genau dort, wo Marken vor Produktnamen
        # stehen, also überall im Prospekt.
        kandidaten = [(min(span["end"], o["end"]) - max(span["start"], o["start"]), -i, i)
                      for i, o in enumerate(ref)
                      if i not in matched_ref and _overlaps(span, o)]
        if not kandidaten:
            reason = teacher_gap_reason(span, words)
            errors.append({
                "klasse": "lehrerluecke" if reason else "echtes_falsch_positiv",
                "label": span["label"], "referenz_label": None,
                "muster": reason,
                "text": " ".join(words[span["start"]:span["end"]]),
            })
            continue

        index = max(kandidaten)[2]
        other = ref[index]
        matched_ref.add(index)
        gleich = other["label"] == span["label"]
        errors.append({
            "klasse": "grenzfehler" if gleich else "typverwechslung",
            "label": span["label"], "referenz_label": other["label"],
            "muster": None,
            "text": " ".join(words[span["start"]:span["end"]]),
        })

    for index, span in enumerate(ref):
        if index in matched_ref:
            continue
        errors.append({
            "klasse": "echtes_falsch_negativ",
            "label": None, "referenz_label": span["label"], "muster": None,
            "text": " ".join(words[span["start"]:span["end"]]),
        })
    return errors


def summarize(errors: list[dict]) -> dict:
    """Häufigkeiten je Klasse, je Label und je belegtem Muster."""
    from collections import Counter

    per_class = Counter(e["klasse"] for e in errors)
    per_label: dict[str, Counter] = {}
    for error in errors:
        label = error["referenz_label"] or error["label"] or "?"
        per_label.setdefault(label, Counter())[error["klasse"]] += 1

    total = sum(per_class.values())
    return {
        "total": total,
        "classes": {
            name: {
                "count": per_class.get(name, 0),
                "share": round(per_class.get(name, 0) / total, 4) if total else None,
                "solvability": SOLVABILITY[name],
            }
            for name in CLASSES
        },
        "per_label": {label: dict(counts) for label, counts in sorted(per_label.items())},
        "patterns": dict(Counter(e["muster"] for e in errors if e["muster"])),
    }
