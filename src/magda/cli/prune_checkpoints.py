"""Alte Checkpoint-Ordner entfernen, `best/` behalten.

    magda prune-checkpoints            # nur berichten
    magda prune-checkpoints --apply    # wirklich löschen

`save_total_limit=2` lässt je Lauf bis zu zwei `checkpoint-N/` liegen, jeder
mit dem Optimizer-State: 1,2 GB gegen 417 MB in `best/`. Gebraucht wird davon
nach dem Training nur noch der Trainingsverlauf – den sichert dieser Schritt
nach `<lauf>/trainer_state.json`, bevor er löscht. Warum genau dorthin und
nicht nach `best/`, steht in `magda.checkpoints`.

Berichten ist der Default, wie bei `magda dedupe`: `checkpoints/` ist
gitignored, es gibt also keine Wiederherstellung.
"""

from __future__ import annotations

import argparse

from magda import checkpoints, config

GIGABYTE = 1024 ** 3


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magda prune-checkpoints",
        description="checkpoint-N-Ordner entfernen, best/ und den Verlauf behalten.")
    parser.add_argument("--apply", action="store_true",
                        help="wirklich löschen (ohne die Option wird nur berichtet)")
    args = parser.parse_args(argv)

    if not config.CHECKPOINTS_DIR.is_dir():
        print(f"Kein Checkpoint-Verzeichnis: {config.CHECKPOINTS_DIR}")
        return 0

    plan = checkpoints.plan_prune(config.CHECKPOINTS_DIR)
    if not plan:
        print("Nichts aufzuräumen – kein Lauf hat noch checkpoint-N-Ordner.")
        return 0

    print(f"Checkpoints in {config.CHECKPOINTS_DIR}\n")
    for entry in plan:
        source = entry["state_source"] or "liegt schon im Lauf-Ordner"
        best = "best/ da" if entry["has_best"] else "BEST FEHLT"
        print(f"  {entry['run']:<24}{entry['bytes'] / GIGABYTE:>7.1f} GB  "
              f"{', '.join(entry['checkpoints'])}")
        print(f"  {'':<24}{'':>7}     Verlauf: {source}; {best}")

    total = sum(e["bytes"] for e in plan) / GIGABYTE
    print(f"\n  Frei würden {total:.1f} GB in {len(plan)} Läufen.")

    if not args.apply:
        print("\n  Nur berichtet. Mit --apply wird gelöscht – checkpoints/ ist")
        print("  gitignored, eine Wiederherstellung gibt es nicht.")
        return 0

    try:
        checkpoints.apply_prune(config.CHECKPOINTS_DIR)
    except ValueError as error:
        print(f"\nAbgebrochen: {error}")
        return 1

    print(f"\n  Gelöscht. Der Trainingsverlauf steht jetzt in <lauf>/trainer_state.json;")
    print("  `magda curve` und /api/model lesen ihn dort.")
    return 0
