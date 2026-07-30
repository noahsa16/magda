"""Packt Code, Labels, Split und verkleinerte Seitenbilder in ein Tar.

    python scripts/11_export_bundle.py --labels-from sonnet-5
    python scripts/11_export_bundle.py --labels-from sonnet-5 --epochs 20

Gedacht für das Training auf einer fremden GPU (RunPod, Uni-Cluster). Auf der
Gegenseite reicht:

    tar xzf magda-training.tgz && bash bootstrap.sh

Anleitung mit allen Schritten: docs/runpod.md
"""

import argparse
import sys
from pathlib import Path

from magda import bundle
from magda.config import DATA_DIR, labeled_models


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels-from", required=True,
        help=f"Modellordner unter data/labeled/. Vorhanden: {', '.join(labeled_models())}",
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument(
        "--out", type=Path, default=DATA_DIR / "magda-training.tgz",
        help="Zieldatei (Standard: data/magda-training.tgz)",
    )
    args = parser.parse_args()

    try:
        zaehler = bundle.build(args.out, args.labels_from, args.epochs)
    except ValueError as fehler:
        sys.exit(str(fehler))

    print(f"{args.out} – {zaehler['groesse_mb']} MB")
    print(f"  {zaehler['code']} Dateien Code, {zaehler['labels']} Labels, "
          f"{zaehler['bilder']} Bilder (auf {bundle.IMAGE_SIZE}px verkleinert)")
    if zaehler["fehlende_bilder"]:
        # Ohne Bild kann LayoutXLM diese Seite nicht laden - lieber jetzt
        # wissen als nach dem Hochladen.
        fehlend = zaehler["fehlende_bilder"]
        print(f"  ACHTUNG: {len(fehlend)} Seiten ohne Bild, "
              f"LayoutXLM bricht daran ab: {', '.join(fehlend[:5])}")


if __name__ == "__main__":
    main()
