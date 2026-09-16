"""Zieht benachbarte Gold-Spans mit gleichem Label zusammen.

Hintergrund: Ein Teil der Handannotation ist wortweise entstanden - "Eau de
Parfum" steht als drei Ein-Wort-Spans statt als einer. Der Annotator zeigt
beides identisch an (drei markierte Nachbarwoerter), fuer die Entity-Metrik
ist es aber etwas voellig anderes: ein Drei-Wort-Span der Vorhersage trifft
drei Ein-Wort-Spans der Referenz nie.

Zusammengezogen wird nur, wo die *Geometrie* es eindeutig macht. Bewusst
nicht herangezogen wird der Lehrer (data/labeled/): eine Referenz, die sich
nach dem richtet, wogegen sie messen soll, misst hinterher sich selbst -
dieselbe Begruendung, aus der `magda offers-report` eine Ablation braucht.

Zweiter Schritt, davor: Preis-Spans auf die Zahl kuerzen. Ausgezeichnet
wurde teils die ganze Phrase - "mit PENNY App 0.99" steht Wort fuer Wort als
APP_PRICE, ebenso "6 KAUFEN, 4 ZAHLEN" vor dem eigentlichen Preis. Konvention
ist die blosse Zahl (Teamentscheidung). Das ist mechanisch entscheidbar und
gehoert deshalb in Code, nicht in eine Annotationsanweisung - dieselbe
Begruendung wie bei `labeling.trim_spans()`.

UNIT_PRICE ist davon **ausgenommen**: dort gehoeren die Woerter dazu,
"(1 l = 366.33)" ist der ganze Span. Wer das mittrimmt, macht das Label
kaputt, das der Merge gerade erst von F1 0.01 auf 0.86 hebt.

Was beide Schritte NICHT koennen, und was deshalb Handarbeit bleibt:
  - Labelfehler. Steht der Preis faelschlich als QUANTITY, bleibt er es.
  - Gruppierungen in gold/offers/. Die haengen an Wortindizes und sind von
    der Span-Granularitaet unberuehrt.

Default ist ein Probelauf. Geschrieben wird nur mit --apply.
"""

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from magda import config
from magda.gold import words_hash

# Abstaende in Vielfachen der Medianworthoehe der Seite - die ist der
# Schriftgroesse proportional und traegt damit ueber verschiedene Layouts.
ENGE_LUECKE = 1.0        # gleiche Zeile: was enger steht, ist ein Wortabstand
UMBRUCH_HOEHE = 2.0      # bis hierhin gilt ein Zeilenwechsel als Umbruch
EINRUECKUNG = 2.0        # wie weit ein Umbruch nach rechts versetzt sein darf


def word_height(words: list[dict]) -> float:
    return statistics.median(w["bbox"][3] - w["bbox"][1] for w in words) or 1.0


def verbindung(links: dict, rechts: dict, h: float) -> str:
    """Wie stehen zwei benachbarte Woerter zueinander?

    Ein Zeilenumbruch *innerhalb* einer Entity ist normal - "Eau de Parfum*
    Versch. Sorten," laeuft selbst ueber zwei Zeilen. Verdaechtig ist nicht
    der Umbruch, sondern der Abstand: eine weite Luecke auf derselben Zeile
    trennt zwei Kacheln, ein Sprung ueber mehr als eine Zeile erst recht.
    """
    ax0, ay0, ax1, _ = links["bbox"]
    bx0, by0, _, _ = rechts["bbox"]
    dy = by0 - ay0

    if abs(dy) < 0.5 * h:
        luecke = bx0 - ax1
        if luecke < 0:
            return "ueberlappend"
        return "gleiche Zeile, eng" if luecke <= ENGE_LUECKE * h else "gleiche Zeile, weit"
    if 0.5 * h <= dy <= UMBRUCH_HOEHE * h:
        return "Umbruch" if bx0 <= ax1 + EINRUECKUNG * h else "Spaltensprung"
    return "Zeilensprung"


EINDEUTIG = {"gleiche Zeile, eng", "Umbruch", "ueberlappend"}

# Labels, deren Span genau die Preisangabe ist. UNIT_PRICE fehlt hier
# absichtlich - "(1 l = 366.33)" besteht zu Recht aus mehreren Woertern.
PREIS_LABELS = {"PRICE", "OLD_PRICE", "APP_PRICE"}

# `search`, nicht `fullmatch`: im aelteren Gold steht der Preis 293-mal als
# "12.99," - das Komma gehoert zum Token und darf den Preis nicht verwerfen.
PREIS_MUSTER = re.compile(r"\d+[.,]\d{2}")


def trim_price_spans(spans: list[dict], words: list[dict]) -> tuple[list[dict], list[tuple]]:
    """Wirft aus Preis-Spans alles, was keine Preisangabe ist.

    Betrifft nur Ein-Wort-Spans: bei mehrwortigen wuerde ein Zuschnitt raten,
    welches Wort gemeint war, und das ist keine mechanische Entscheidung mehr.
    """
    behalten, entfernt = [], []
    for span in spans:
        text = " ".join(w["text"] for w in words[span["start"]:span["end"]])
        if (span["label"] in PREIS_LABELS
                and span["end"] - span["start"] == 1
                and not PREIS_MUSTER.search(text)):
            entfernt.append((span["label"], text))
            continue
        behalten.append(span)
    return behalten, entfernt


def merge_page(spans: list[dict], words: list[dict]) -> tuple[list[dict], int, list[tuple]]:
    """Zusammengezogene Spans, Zahl der Verschmelzungen, offene Zweifelsfaelle."""
    spans = sorted(spans, key=lambda s: s["start"])
    if not spans:
        return spans, 0, []
    h = word_height(words)
    ergebnis: list[dict] = []
    offen: list[tuple] = []
    aktuell = dict(spans[0])
    for links, rechts in zip(spans, spans[1:]):
        gleiche_entity = links["label"] == rechts["label"] and links["end"] == rechts["start"]
        art = (verbindung(words[links["end"] - 1], words[rechts["start"]], h)
               if gleiche_entity else None)
        if gleiche_entity and art in EINDEUTIG:
            aktuell["end"] = rechts["end"]
        else:
            if gleiche_entity:
                offen.append((links["label"], art, words[links["end"] - 1]["text"],
                              words[rechts["start"]]["text"]))
            ergebnis.append(aktuell)
            aktuell = dict(rechts)
    ergebnis.append(aktuell)
    return ergebnis, len(spans) - len(ergebnis), offen


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="merge_gold_spans",
        description="Benachbarte gleichlabelige Gold-Spans zusammenziehen (Default: Probelauf).")
    parser.add_argument("--apply", action="store_true", help="Aenderungen wirklich schreiben")
    parser.add_argument("--only-word-level", action="store_true", default=True,
                        help="nur Seiten anfassen, deren Spans samtlich ein Wort lang sind")
    args = parser.parse_args(argv)

    veraendert = verschmolzen = 0
    getrimmt_gesamt: list[tuple] = []
    offen_gesamt: list[tuple] = []
    seiten_mit_zweifel: list[str] = []

    for path in sorted(Path("gold").glob("*.json")):
        annotation = json.loads(path.read_text())
        spans = annotation.get("spans") or []
        if not spans:
            continue
        if args.only_word_level and any(s["end"] - s["start"] != 1 for s in spans):
            continue

        words_path = config.WORDS_DIR / f"{path.stem}.json"
        if not words_path.is_file():
            print(f"  ! {path.stem}: keine Wortliste, uebersprungen")
            continue
        words = json.loads(words_path.read_text())["words"]
        if annotation.get("words_hash") != words_hash(words):
            print(f"  ! {path.stem}: words_hash passt nicht, uebersprungen")
            continue

        spans, entfernt = trim_price_spans(spans, words)
        getrimmt_gesamt.extend(entfernt)
        neu, anzahl, offen = merge_page(spans, words)
        if offen:
            seiten_mit_zweifel.append(path.stem)
            offen_gesamt.extend(offen)
        if not anzahl and not entfernt:
            continue
        veraendert += 1
        verschmolzen += anzahl
        print(f"  {path.stem:<16} {len(neu) + anzahl + len(entfernt):>4} -> {len(neu):>4} Spans"
              + (f", {len(entfernt)} Preis-Beiwerk entfernt" if entfernt else "")
              + (f"   ({len(offen)} Zweifelsfall/-faelle bleiben)" if offen else ""))
        if args.apply:
            annotation["spans"] = neu
            path.write_text(json.dumps(annotation, ensure_ascii=False, indent=2) + "\n")

    print()
    print(f"{veraendert} Seiten betroffen, {verschmolzen} Verschmelzungen, "
          f"{len(getrimmt_gesamt)} Nicht-Preis-Woerter aus Preis-Spans entfernt.")
    if getrimmt_gesamt:
        from collections import Counter
        haeufig = Counter(text for _, text in getrimmt_gesamt)
        print("   entfernt: " + ", ".join(f"{t!r}x{n}" for t, n in haeufig.most_common(12)))
    print(f"{len(offen_gesamt)} Zweifelsfaelle auf {len(seiten_mit_zweifel)} Seiten bleiben "
          f"unangetastet: {', '.join(seiten_mit_zweifel) or '-'}")
    for label, art, links, rechts in offen_gesamt[:20]:
        print(f"   {label:<11} {art:<20} {links!r} + {rechts!r}")
    print("\nProbelauf - nichts geschrieben. Mit --apply ausfuehren."
          if not args.apply else "\nGeschrieben.")


if __name__ == "__main__":
    main()
