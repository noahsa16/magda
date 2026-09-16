"""Lokaler Blindeditor: ausschließlich Bilder, Wörter und leere Annotationen."""

import json
import os
from pathlib import Path

from magda import config
from magda.labels import ENTITY_TYPES


def write_editors(directory, manifest):
    template = (Path(__file__).parent / "templates" / "independent_review.html").read_text()
    pages = [{**page, "image": os.path.relpath(config.IMAGES_DIR / f"{page['page_id']}.png", directory)}
             for page in manifest["pages"]]
    for role in ("a", "b"):
        payload = {"packet_id": manifest["packet_id"], "pages": pages, "role": role, "labels": ENTITY_TYPES}
        content = template.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c"))
        (Path(directory) / f"review-{role}.html").write_text(content)
