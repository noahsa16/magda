"""Einstieg für alle Pipeline-Schritte: `magda <befehl>`.

Die Schritte lagen früher als nummerierte Dateien in `scripts/`. Die Nummern
gaben die Reihenfolge vor, aber dreizehn Dateien in einem Ordner sind eine
Liste, keine Struktur — und die Reihenfolge stand nirgends, wo man sie sucht.
Hier steht sie in `BEFEHLE` und damit in `magda --help`.

Die Module werden erst beim Aufruf importiert. Das ist keine Feinheit: `train`
zieht torch und transformers herein, und `magda --help` würde sonst gut zehn
Sekunden brauchen, um eine Liste auszugeben.
"""

import importlib
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Befehl:
    name: str
    modul: str
    hilfe: str


# Reihenfolge = Reihenfolge der Pipeline. Wer sie ändert, ändert die Hilfe.
PIPELINE = (
    Befehl("harvest", "harvest", "Prospektwoche ernten, alle 44 Regionen"),
    Befehl("download", "download", "Einen einzelnen Katalog über seine URL holen"),
    Befehl("extract", "extract", "Wörter und Boxen aus dem PDF-Textlayer ziehen"),
    Befehl("dedupe", "duplicates", "Beinah-Duplikate finden und aussortieren"),
    Befehl("label", "label", "Seiten vom Vision-LLM labeln lassen"),
    Befehl("split", "split", "Train/Dev/Test festlegen"),
    Befehl("train", "train", "Token-Klassifikation trainieren"),
    Befehl("eval", "evaluate", "Entity-Level-F1 auf einem Split messen"),
    Befehl("predict", "predict", "Modellausgabe je Seite exportieren (Wort, Box, Label)"),
)

VERGLEICH = (
    Befehl("flair", "flair", "Fertiges deutsches NER-Modell als Vergleich (nur BRAND)"),
    Befehl("gold", "compare", "Labeling-Modelle gegen die Handannotation messen"),
    Befehl("agreement", "agreement", "Zwei Labeling-Modelle gegeneinander halten"),
    Befehl("queue", "queue", "Welche Gold-Seiten als Nächstes durchzusehen sind"),
    Befehl("audit", "audit", "Ein Label zur Handprüfung vorsortieren (Kandidaten)"),
    Befehl("significance", "significance",
           "Konfidenzintervall und gepaarter Modellvergleich über Cluster"),
)

WERKZEUGE = (
    Befehl("serve", "serve", "API starten (--frontend startet auch die Oberfläche)"),
    Befehl("cluster", "cluster", "Prospektseiten explorativ nach Textinhalt clustern"),
    Befehl("offers", "offers", "Gelabelte Entities zu Angeboten clustern und als SQLite speichern"),
    Befehl("offers-report", "offers_report", "Angebots-Clustering per Ablation messen (Train+Dev)"),
    Befehl("bundle", "export", "Trainingspaket für eine fremde GPU schnüren"),
    Befehl("import-gold", "import_gold", "Handannotationen als Labelordner ablegen"),
)

GRUPPEN = (
    ("Pipeline (in dieser Reihenfolge)", PIPELINE),
    ("Vergleichsarme", VERGLEICH),
    ("Werkzeuge", WERKZEUGE),
)

BEFEHLE = {b.name: b for gruppe in GRUPPEN for b in gruppe[1]}


def _hilfe() -> str:
    zeilen = ["magda <befehl> [optionen]", ""]
    for titel, befehle in GRUPPEN:
        zeilen.append(f"{titel}:")
        zeilen += [f"  {b.name:<12} {b.hilfe}" for b in befehle]
        zeilen.append("")
    zeilen.append("magda <befehl> --help zeigt die Optionen eines Schritts.")
    return "\n".join(zeilen)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        print(_hilfe())
        return 0

    name, rest = argv[0], argv[1:]
    befehl = BEFEHLE.get(name)
    if befehl is None:
        print(f"Unbekannter Befehl: {name}\n", file=sys.stderr)
        print(_hilfe(), file=sys.stderr)
        return 2

    modul = importlib.import_module(f"magda.cli.{befehl.modul}")
    # argparse nennt sich sonst nach dem Interpreter statt nach dem Befehl.
    sys.argv[0] = f"magda {name}"
    ergebnis = modul.main(rest)
    return 0 if ergebnis is None else int(ergebnis)


__all__ = ["BEFEHLE", "GRUPPEN", "main"]
