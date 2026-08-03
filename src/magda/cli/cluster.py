"""Clustert extrahierte Prospektseiten nach Textinhalt.

Aufruf:
    magda cluster
    magda cluster --k 12 --source words

Das Ergebnis landet in data/clusters/pages.json und pages.md. Es ist eine
explorative Gruppierung, keine Entdopplung: zum Loeschen bleibt `magda dedupe`
das konservative Werkzeug.
"""

import argparse
import json

from magda import clustering
from magda.config import DATA_DIR, LABELED_DIR, SEED, WORDS_DIR, labeled_dir


CLUSTERS_DIR = DATA_DIR / "clusters"


def _load_words() -> list[clustering.Page]:
    pages = []
    for path in sorted(WORDS_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        pages.append(
            clustering.Page(
                page_id=data.get("page_id") or path.stem,
                words=[word["text"] for word in data.get("words", [])],
            )
        )
    return pages


def _load_labeled(model: str) -> list[clustering.Page]:
    pages = []
    for path in sorted(labeled_dir(model).glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        pages.append(
            clustering.Page(
                page_id=data.get("page_id") or path.stem,
                words=[word["text"] for word in data.get("words", [])],
            )
        )
    return pages


def _default_k(n_pages: int) -> int:
    return max(2, min(20, round(n_pages ** 0.5)))


def _write_markdown(result: dict, path) -> None:
    lines = [
        "# Seiten-Cluster",
        "",
        f"Seiten: {result['pages']}",
        f"Cluster: {result['k']}",
        "",
    ]
    for cluster in result["clusters"]:
        keywords = ", ".join(cluster["keywords"]) if cluster["keywords"] else "-"
        examples = ", ".join(cluster["pages"][:12])
        more = len(cluster["pages"]) - 12
        if more > 0:
            examples += f", ... (+{more})"
        lines += [
            f"## Cluster {cluster['id']} ({cluster['size']} Seiten)",
            "",
            f"Keywords: {keywords}",
            "",
            f"Beispiele: {examples}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=None,
                        help="Anzahl Cluster; Default: sqrt(Seiten), gedeckelt bei 20")
    parser.add_argument("--max-features", type=int, default=1200,
                        help="Maximale Zahl der TF-IDF-Merkmale")
    parser.add_argument("--seed", type=int, default=SEED,
                        help="Seed fuer reproduzierbare Initialisierung")
    parser.add_argument("--source", default="words",
                        help="'words' oder Name eines Labelordners unter data/labeled/")
    args = parser.parse_args(argv)

    if args.source == "words":
        pages = _load_words()
    else:
        if not (LABELED_DIR / args.source).is_dir():
            parser.error(f"Labelquelle nicht gefunden: {args.source}")
        pages = _load_labeled(args.source)

    if not pages:
        parser.exit(1, "Keine Seiten gefunden. Erst `magda extract` laufen lassen.\n")

    k = args.k or _default_k(len(pages))
    result = clustering.cluster_pages(
        pages,
        k=k,
        max_features=args.max_features,
        seed=args.seed,
    )
    result["source"] = args.source

    CLUSTERS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = CLUSTERS_DIR / "pages.json"
    md_path = CLUSTERS_DIR / "pages.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(result, md_path)

    print(f"{result['pages']} Seiten in {result['k']} Cluster gruppiert.")
    print(f"JSON: {json_path}")
    print(f"Bericht: {md_path}")
    print()
    for cluster in result["clusters"][:8]:
        keywords = ", ".join(cluster["keywords"][:6]) if cluster["keywords"] else "-"
        print(f"{cluster['id']:>2}: {cluster['size']:>3} Seiten  {keywords}")
