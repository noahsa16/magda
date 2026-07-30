"""Schnürt ein Trainingspaket für eine fremde Maschine (RunPod, Uni-Cluster).

Warum überhaupt ein Bündel und nicht `git clone` plus `rsync`: Der Code liegt
nur lokal, solange nicht gepusht wurde, und `data/` ist gitignored. Wer beides
von Hand zusammensucht, vergisst genau einmal den Split – und trainiert dann
gegen eine andere Aufteilung als zu Hause, ohne dass es auffällt.

Die Seitenbilder werden auf 224×224 vorskaliert. Das ist keine Sparmaßnahme,
sondern genau die Größe, auf die `LayoutLMv2ImageProcessor` sie ohnehin bringt
– mit demselben Filter (bilinear). Aus 390 MB werden so rund 20 MB, ohne dass
sich am Modelleingang ein Pixel ändert.
"""

import io
import subprocess
import tarfile
from pathlib import Path

from PIL import Image

from magda.config import IMAGES_DIR, PROJECT_ROOT, SPLITS_DIR, labeled_dir

# Kantenlänge und Filter von LayoutLMv2ImageProcessor. Weichen sie ab, sieht
# das Modell auf dem Pod andere Pixel als zu Hause.
IMAGE_SIZE = 224
RESAMPLE = Image.BILINEAR

BOOTSTRAP = """#!/usr/bin/env bash
# Auf dem Pod ausfuehren: bash bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "########## Abhaengigkeiten ##########"
pip install -q -r requirements.txt
# Der visuelle Backbone von LayoutLMv2/LayoutXLM. Wird uebersetzt, dauert
# einige Minuten. Ohne ihn laeuft nur die GBERT-Variante.
pip install -q "git+https://github.com/facebookresearch/detectron2.git" \\
  || echo "WARNUNG: detectron2 fehlgeschlagen - layoutxlm wird nicht laufen."

# Der teuerste denkbare Fehler: PyTorch findet die GPU nicht, trainiert
# stillschweigend auf der CPU, und die gemietete Karte steht daneben. Lieber
# hier abbrechen als eine Stunde spaeter ein Ergebnis haben, das nichts
# gekostet haette.
python - <<'PRUEFUNG' || exit 1
import sys, torch
if not torch.cuda.is_available():
    sys.exit("ABBRUCH: torch.cuda.is_available() ist False. Ohne GPU zahlst du "
             "GPU-Stunden fuer CPU-Training. Falsches Image, oder pip hat das "
             "CUDA-Torch durch ein CPU-Rad ersetzt.")
print(f"GPU: {torch.cuda.get_device_name(0)}, torch {torch.__version__}")
PRUEFUNG

for variante in gbert layoutxlm; do
  echo ""
  echo "########## $variante ##########"
  python scripts/04_train.py "$variante" --labels-from {model} --epochs {epochs} \\
    || {{ echo "$variante: Training fehlgeschlagen"; continue; }}
  python scripts/05_evaluate.py "$variante" --split test --labels-from {model}
done

echo ""
echo "########## Ergebnisse einpacken ##########"
tar czf ergebnisse.tgz data/eval checkpoints
echo "Fertig: $(pwd)/ergebnisse.tgz"
"""


def _tracked_files() -> list[Path]:
    """Alles, was unter Versionskontrolle steht – inklusive lokaler Commits.

    `git archive HEAD` wäre kürzer, liefert aber ein zweites Tar-Format im Tar
    und macht das Entpacken zweistufig.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
    )
    return [PROJECT_ROOT / name for name in out.stdout.split("\0") if name]


def _shrink(image_file: Path) -> bytes:
    with Image.open(image_file) as page:
        small = page.convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE), RESAMPLE)
    buffer = io.BytesIO()
    small.save(buffer, format="PNG")
    return buffer.getvalue()


def build(target: Path, model: str, epochs: int = 10) -> dict:
    """Schreibt das Tar und meldet, was drinsteckt."""
    labels = sorted(labeled_dir(model).glob("*.json"))
    if not labels:
        raise ValueError(f"Keine Labels in data/labeled/{model}/.")

    split_file = SPLITS_DIR / "split.json"
    if not split_file.exists():
        raise ValueError(
            "data/splits/split.json fehlt. Erst lokal einmal 04_train starten, "
            "sonst würfelt der Pod einen eigenen Split und die Zahlen sind "
            "nicht mit deinen vergleichbar."
        )

    zaehler = {"code": 0, "labels": 0, "bilder": 0, "fehlende_bilder": []}
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target, "w:gz") as tar:
        for path in _tracked_files():
            if not path.is_file():
                continue  # gelöscht, aber noch im Index
            tar.add(path, arcname=str(path.relative_to(PROJECT_ROOT)))
            zaehler["code"] += 1

        for label_file in labels:
            tar.add(label_file, arcname=f"data/labeled/{model}/{label_file.name}")
            zaehler["labels"] += 1

            image_file = IMAGES_DIR / f"{label_file.stem}.png"
            if not image_file.exists():
                zaehler["fehlende_bilder"].append(label_file.stem)
                continue
            data = _shrink(image_file)
            info = tarfile.TarInfo(f"data/images/{image_file.name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
            zaehler["bilder"] += 1

        tar.add(split_file, arcname="data/splits/split.json")

        script = BOOTSTRAP.format(model=model, epochs=epochs).encode()
        info = tarfile.TarInfo("bootstrap.sh")
        info.size = len(script)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(script))

    zaehler["groesse_mb"] = round(target.stat().st_size / 1e6, 1)
    return zaehler
