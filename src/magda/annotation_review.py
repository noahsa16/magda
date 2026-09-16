"""Blindaufgaben und Übereinstimmung mit getrennten Originalurteilen.

Leere Vorlagen bleiben offen. Nur abgegebene Dateien zweier benannter
Personen werden ausgewertet; Einigkeit ist keine Garantie für Richtigkeit.
"""

import json
import random
from collections import Counter
from pathlib import Path

from magda import config, gold, offers_gold, provenance, semeval
from magda.labels import validate_spans


def select_pages(page_ids, clusters, count=10, seed=20260915):
    """Zieht Vorlagen ohne Modell- oder Goldinhalte zu lesen."""
    if count < 1 or not clusters:
        raise ValueError("Positive Stichprobengröße und Cluster benötigt.")
    representatives = sorted(min(page_ids[index] for index in cluster) for cluster in clusters)
    return sorted(random.Random(seed).sample(representatives, min(count, len(representatives))))


def create_packet(directory, page_ids, clusters, count=10, seed=20260915):
    directory = Path(directory)
    selected = select_pages(page_ids, clusters, count, seed)
    pages = []
    for page_id in selected:
        path = config.WORDS_DIR / f"{page_id}.json"
        page = json.loads(path.read_text())
        pages.append({
            "page_id": page_id, "width": page["width"], "height": page["height"],
            "words": [{"text": word["text"], "bbox": word["bbox"]} for word in page["words"]],
            "words_hash": gold.words_hash(page["words"]),
            "image_sha256": provenance.file_digest(config.IMAGES_DIR / f"{page_id}.png"),
        })
    manifest = {"protocol": "independent-review-v1", "selection_seed": seed,
                "selection": "uniform-template-sample-without-model-outputs",
                "requested_pages": page_ids, "selected_pages": selected, "pages": pages,
                "guidelines_sha256": provenance.file_digest(config.PROJECT_ROOT / "docs/annotation-guidelines-v1.md")}
    manifest["packet_id"] = provenance.digest(manifest)
    path = directory / "manifest.json"
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError("Prüfpaket hat andere Eingaben; neuen Ausgabeordner verwenden.")
    else:
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def _group_scores(a, b):
    """Wortpaare und exakte Wortgruppen; Gruppennummern sind austauschbar."""
    def pairs(size):
        return size * (size - 1) // 2
    assignment = {word: i for i, group in enumerate(a) for word in group}
    shared = sum(sum(pairs(count) for count in Counter(assignment[w] for w in group if w in assignment).values())
                 for group in b)
    ref_pairs, sys_pairs = sum(pairs(len(g)) for g in a), sum(pairs(len(g)) for g in b)
    exact = len({frozenset(g) for g in a} & {frozenset(g) for g in b})
    return {"word_pairs": [shared, sys_pairs, ref_pairs], "exact_word_groups": [exact, len(b), len(a)]}


def score_reviews(manifest, directory_a=None, directory_b=None):
    if directory_a is None or directory_b is None:
        return {"status": "awaiting_two_human_submissions", "scores": None,
                "selected_pages": manifest["selected_pages"]}
    records, names, differences = [[], []], [set(), set()], []
    files = {}
    for role, directory in enumerate((directory_a, directory_b)):
        bundle = json.loads(Path(directory).read_text()) if Path(directory).is_file() else None
        for page in manifest["pages"]:
            path = Path(directory) if bundle is not None else Path(directory) / f"{page['page_id']}.json"
            matches = [r for r in bundle.get("pages", []) if r.get("page_id") == page["page_id"]] if bundle is not None else []
            if bundle is not None and len(matches) != 1:
                raise ValueError(f"Seite fehlt oder ist doppelt: {page['page_id']}")
            record = matches[0] if bundle is not None else json.loads(path.read_text())
            if (record.get("packet_id") != manifest["packet_id"]
                    or record.get("page_id") != page["page_id"]
                    or record.get("words_hash") != page["words_hash"]
                    or record.get("status") != "done"
                    or record.get("independent_annotation") is not True
                    or not isinstance(record.get("spans"), list)
                    or not isinstance(record.get("groups"), list)
                    or not str(record.get("annotator") or "").strip()):
                raise ValueError(f"Unvollständige oder nicht unabhängig erklärte Abgabe: {path}")
            errors = validate_spans(record.get("spans", []), len(page["words"]))
            errors += offers_gold.validate_groups(record.get("groups", []), len(page["words"]))
            if errors:
                raise ValueError(f"Ungültige Abgabe {path}: {errors}")
            records[role].append(record)
            names[role].add(record["annotator"].strip().casefold())
            files[f"{role}/{page['page_id']}"] = provenance.file_digest(path)
    if any(len(group) != 1 for group in names) or names[0] & names[1]:
        raise ValueError("Benötigt werden zwei verschiedene Personen, jeweils für das ganze Prüfpaket.")
    scores = semeval.evaluate([r["spans"] for r in records[0]], [r["spans"] for r in records[1]])
    group_counts = {"word_pairs": [0, 0, 0], "exact_word_groups": [0, 0, 0]}
    for a, b in zip(*records, strict=True):
        for key, values in _group_scores(a["groups"], b["groups"]).items():
            group_counts[key] = [x + y for x, y in zip(group_counts[key], values, strict=True)]
        span_key = lambda s: (s["start"], s["end"], s["label"])
        if ({span_key(s) for s in a["spans"]} != {span_key(s) for s in b["spans"]}
                or {frozenset(g) for g in a["groups"]} != {frozenset(g) for g in b["groups"]}):
            differences.append({"page_id": a["page_id"], "a": a, "b": b,
                                "decision": None, "reason": None})
    return {"status": "awaiting_adjudication" if differences else "agreement_measured",
            "independence": "self-declared-by-annotators", "annotators": [sorted(n) for n in names],
            "prior_exposure": [[r.get("prior_exposure", "unknown") for r in group] for group in records],
            "scores": scores, "group_counts": group_counts, "differences": differences,
            "submission_hashes": files, "packet_id": manifest["packet_id"]}
