"""Legt die Train/Dev/Test-Aufteilung neu fest.

    magda split --strategy week
    magda split --strategy week --force

Ein bestehender Split wird nicht überschrieben, ohne dass man `--force` sagt:
Er ist eingefroren, damit alle im Team auf denselben Testseiten messen. Die
alte Datei wird als `split.json.<zeitstempel>` daneben gelegt.

Strategien:

  week    Älteste Woche(n) trainieren, jüngste testen. Empfohlen. Der
          Seiten-Split leckt, weil Penny je Woche 44 fast identische
          Regionalausgaben herausgibt; über Wochen getrennt sinkt die
          Median-Ähnlichkeit zwischen Test und Train von 0.851 auf 0.257.

  random  80/10/10 über Seiten, das bisherige Verhalten. Nur noch für den
          Vergleich mit älteren Zahlen sinnvoll.
"""

import argparse
import json
import sys
from datetime import datetime

from magda.config import SPLITS_DIR, WORDS_DIR
from magda.dataset import group_by_week, split_by_week


def zufaellig(page_ids: list[str]) -> dict:
    """Das bisherige Verhalten: 80/10/10 über Seiten."""
    import random

    from magda.config import SEED

    ids = sorted(page_ids)
    random.Random(SEED).shuffle(ids)
    n_dev = max(1, len(ids) // 10)
    return {
        "train": sorted(ids[: len(ids) - 2 * n_dev]),
        "dev": sorted(ids[len(ids) - 2 * n_dev : len(ids) - n_dev]),
        "test": sorted(ids[len(ids) - n_dev :]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strategy", choices=("week", "random"), default="week")
    parser.add_argument("--dev-share", type=float, default=0.1)
    parser.add_argument("--force", action="store_true",
                        help="Bestehenden Split ersetzen (Sicherung wird angelegt).")
    args = parser.parse_args(argv)

    page_ids = sorted(p.stem for p in WORDS_DIR.glob("*.json"))
    if not page_ids:
        sys.exit("Keine extrahierten Seiten in data/words/. Erst Schritt 02 laufen lassen.")

    split_file = SPLITS_DIR / "split.json"
    if split_file.exists() and not args.force:
        sys.exit(
            f"{split_file} existiert bereits. Der Split ist eingefroren, damit alle "
            f"im Team auf denselben Testseiten messen.\nMit --force ersetzen "
            f"(die alte Datei wird gesichert)."
        )

    if args.strategy == "week":
        wochen = group_by_week(page_ids)
        print(f"{len(wochen)} Erscheinungswochen erkannt:")
        for i, woche in enumerate(wochen):
            kataloge = {p.rsplit("_p", 1)[0] for p in woche}
            rolle = "Test" if i == len(wochen) - 1 else "Train/Dev"
            print(f"  {min(kataloge)}–{max(kataloge)}: {len(woche):>4} Seiten, "
                  f"{len(kataloge):>2} Kataloge  -> {rolle}")
        splits = split_by_week(page_ids, args.dev_share)
    else:
        splits = zufaellig(page_ids)

    if split_file.exists():
        sicherung = split_file.with_suffix(f".json.{datetime.now():%Y%m%d-%H%M%S}")
        split_file.rename(sicherung)
        print(f"\nAlter Split gesichert als {sicherung.name}")

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    with open(split_file, "w") as f:
        json.dump(splits, f, indent=2)

    print(f"\n{split_file}: " + ", ".join(f"{k}={len(v)}" for k, v in splits.items()))

