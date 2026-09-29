"""Zählt die gespeicherten Sonnet-5-Entitäten nach Typ und Datensplit."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from magda.labels import ENTITY_TYPES, bio_to_spans


ROOT = Path(__file__).resolve().parents[1]
LABELS_DIR = ROOT / "data/labeled/sonnet-5"
SPLIT_PATH = ROOT / "data/splits/split.json"


def main() -> None:
    split = json.loads(SPLIT_PATH.read_text())
    split_by_page = {
        page_id: name
        for name, page_ids in split.items()
        for page_id in page_ids
    }
    pages = Counter()
    entities = Counter()
    by_type = Counter()

    for path in sorted(LABELS_DIR.glob("*.json")):
        page = json.loads(path.read_text())
        page_id = path.stem
        if page["page_id"] != page_id:
            raise ValueError(f"Seiten-ID stimmt nicht: {path}")
        if len(page["words"]) != len(page["tags"]):
            raise ValueError(f"Wörter und Tags haben verschiedene Längen: {path}")
        if page_id not in split_by_page:
            raise ValueError(f"Seite fehlt im eingefrorenen Split: {page_id}")

        spans = bio_to_spans(page["tags"])
        if len(spans) != sum(tag.startswith("B-") for tag in page["tags"]):
            raise ValueError(f"Ungültige BIO-Folge: {path}")
        if any(span["label"] not in ENTITY_TYPES for span in spans):
            raise ValueError(f"Unbekannter Entitätstyp: {path}")

        split_name = split_by_page[page_id]
        pages[split_name] += 1
        entities[split_name] += len(spans)
        by_type.update(span["label"] for span in spans)

    result = {
        "source": str(LABELS_DIR.relative_to(ROOT)),
        "split": str(SPLIT_PATH.relative_to(ROOT)),
        "pages": dict(sorted(pages.items())),
        "entities": dict(sorted(entities.items())),
        "total_pages": sum(pages.values()),
        "total_entities": sum(entities.values()),
        "by_type": dict(sorted(by_type.items())),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
