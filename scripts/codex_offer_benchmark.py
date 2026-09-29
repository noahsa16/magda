"""Trennt einen bildbasierten Codex-Vergleich von seiner späteren Bewertung.

Die Eingabemappe enthält ausschließlich Originalbilder, den unveränderten
Extraktionsprompt und Herkunftsangaben. Referenzlabels werden weder gelesen
noch kopiert. Ein Chatlauf ist keine API-Laufzeitmessung.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "data/eval/test_cluster_pages.txt"
FIELDS = {
    "brand", "product", "quantity", "price", "old_price", "app_price",
    "discount_pct", "unit_price", "valid",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def prepare(directory: Path) -> None:
    if directory.exists():
        raise SystemExit("Laufverzeichnis existiert bereits, kein Überschreiben")
    page_ids = PAGES.read_text().splitlines()
    if not page_ids or len(page_ids) != len(set(page_ids)):
        raise SystemExit("Seitenliste fehlt oder enthält Duplikate")
    images = [ROOT / "data/images" / f"{page_id}.png" for page_id in page_ids]
    if any(not image.is_file() for image in images):
        raise SystemExit("Mindestens ein Seitenbild fehlt")
    constants = {}
    for node in ast.parse((ROOT / "src/magda/blackbox.py").read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "_EXTRACT_PROMPT", "PROMPT_VERSION"
                }:
                    constants[target.id] = ast.literal_eval(node.value)
    prompt = constants["_EXTRACT_PROMPT"]
    input_dir = directory / "input"
    input_dir.mkdir(parents=True)
    (directory / "predictions").mkdir()
    (input_dir / "prompt.txt").write_text(prompt)
    copied = []
    for page_id, image in zip(page_ids, images):
        target = input_dir / image.name
        shutil.copyfile(image, target)
        if digest(image) != digest(target):
            raise SystemExit(f"Bildkopie weicht ab: {page_id}")
        copied.append({"page_id": page_id, "image": image.name,
                       "sha256": digest(target)})
    save_new(input_dir / "manifest.json", {
        "protocol": "codex-image-offer-extraction-v1",
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "requested_model": "gpt-6-astra",
        "requested_reasoning_effort": "high",
        "surface": "Codex desktop, fresh projectless task",
        "context": "One fresh task, pages processed sequentially in shared context",
        "prompt_version": constants["PROMPT_VERSION"],
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "page_list_sha256": digest(PAGES),
        "images": copied,
        "numeric_timing_comparison": False,
    })
    print(f"Eingabemappe mit {len(copied)} unveränderten Bildern: {input_dir}")


def collect(directory: Path, output: Path, thread_id: str, predictions: Path | None) -> None:
    input_dir = directory / "input"
    manifest = json.loads((input_dir / "manifest.json").read_text())
    if manifest["page_list_sha256"] != digest(PAGES):
        raise SystemExit("Seitenliste wurde seit der Vorbereitung verändert")
    if manifest["prompt_sha256"] != digest(input_dir / "prompt.txt"):
        raise SystemExit("Prompt wurde seit der Vorbereitung verändert")
    page_ids = PAGES.read_text().splitlines()
    if [entry["page_id"] for entry in manifest["images"]] != page_ids:
        raise SystemExit("Manifest enthält andere Seiten oder eine andere Reihenfolge")
    expected_files = {f"{page_id}.json" for page_id in page_ids}
    source_dir = predictions or directory / "predictions"
    prediction_files = {path.name for path in source_dir.glob("*.json")}
    if prediction_files != expected_files:
        raise SystemExit(f"Vorhersagedateien unvollständig oder zusätzlich: "
                         f"{sorted(prediction_files ^ expected_files)}")
    rows = []
    for entry in manifest["images"]:
        if digest(input_dir / entry["image"]) != entry["sha256"]:
            raise SystemExit(f"Bild wurde verändert: {entry['page_id']}")
        prediction_path = source_dir / f"{entry['page_id']}.json"
        records = json.loads(prediction_path.read_text())
        if not isinstance(records, list):
            raise SystemExit(f"Kein Array: {prediction_path}")
        for record in records:
            if not isinstance(record, dict) or set(record) != FIELDS:
                raise SystemExit(f"Abweichende Ausgabefelder: {prediction_path}")
        rows.append({
            "page_id": entry["page_id"], "records": records,
            "error": None, "seconds": None,
            "image_sha256": entry["sha256"],
            "raw_response_sha256": digest(prediction_path),
        })
    if source_dir.resolve() != (directory / "predictions").resolve():
        for page_id in page_ids:
            target = directory / "predictions" / f"{page_id}.json"
            with target.open("xb") as handle:
                handle.write((source_dir / target.name).read_bytes())
    save_new(output, {
        **{key: value for key, value in manifest.items() if key != "images"},
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "system": "codex_chat",
        "api_model": manifest["requested_model"],
        "api_host": None,
        "model_attribution": "Explicit model setting on the created Codex task",
        "thread_id": thread_id,
        "per_page": rows,
    })
    print(f"{len(rows)} Antworten vor der Bewertung eingefroren: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "collect"):
        subparser = commands.add_parser(command)
        subparser.add_argument("directory", type=Path)
        if command == "collect":
            subparser.add_argument("--output", type=Path, required=True)
            subparser.add_argument("--thread-id", required=True)
            subparser.add_argument("--predictions", type=Path,
                                   help="Ausgabeordner des unabhängigen Chats")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.directory)
    else:
        collect(args.directory, args.output, args.thread_id, args.predictions)


if __name__ == "__main__":
    main()
