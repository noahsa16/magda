"""Gruppiert gelabelte Entities zu Angeboten und schreibt SQLite.

Aufruf:
    magda offers
    magda offers --source layoutxlm-test
    magda offers --predictions gbert
    magda offers --db data/offers/offers.sqlite
    magda offers --grouper heuristic
    magda offers --grouper pair-model --checkpoint checkpoints/offer_pairs/model.pt

Quelle ist standardmaessig ein Labelordner unter data/labeled/ (words[] mit
bbox und tags[] als BIO-Folge). Mit --predictions wird stattdessen
data/predictions/<variante>/ gelesen, das Ausgabeformat von `magda predict`:
Labels stehen dort direkt am Wort statt als BIO-Folge, dazu liegen die Spans
schon als entities[] vor. _load_predicted_pages baut daraus tags[], damit
cluster_page beide Quellen gleich behandelt.

`--grouper` waehlt das Verfahren, das Entities zu Angeboten zusammenfasst.
Default ist `pair-model`: das gelernte Paarmodell erreicht Gruppen-F1 0.821
gegen 0.524 der Heuristik (Stand 30.08.2026, siehe CLAUDE.md). Fehlt der
Checkpoint, bricht der Lauf mit einer klaren Meldung ab statt still auf die
Heuristik zurueckzufallen - eine andere Gruppierung als die gewaehlte
still auszuliefern waere schlimmer als ein Abbruch.
"""

import argparse
import json
from pathlib import Path

from magda import config, offers
from magda.labels import spans_to_bio


DEFAULT_DB = config.DATA_DIR / "offers" / "offers.sqlite"
DEFAULT_CHECKPOINT = config.PROJECT_ROOT / "checkpoints" / "offer_pairs" / "model.pt"
GROUPERS = ("heuristic", "pair-model")


def _load_labeled_pages(source: str) -> list[dict]:
    directory = config.labeled_dir(source)
    pages = []
    for path in sorted(directory.glob("*.json")):
        with open(path) as f:
            page = json.load(f)
        if page.get("words") and page.get("tags"):
            pages.append(page)
    return pages


def _load_predicted_pages(variant: str) -> list[dict]:
    directory = config.DATA_DIR / "predictions" / config.model_slug(variant)
    pages = []
    for path in sorted(directory.glob("*.json")):
        if path.name == "index.json":
            continue
        with open(path) as f:
            page = json.load(f)
        words = page.get("words")
        if not words or page.get("entities") is None:
            continue
        page["tags"] = spans_to_bio(len(words), page["entities"])
        pages.append(page)
    return pages


def _pair_model_grouping(checkpoint_path, parser):
    """Baut die Gruppierungsfunktion aus dem gelernten Paarmodell.

    Bricht sofort ab, wenn der Checkpoint fehlt - eine falsche Gruppierung
    still als Ergebnis der Heuristik auszugeben waere schlimmer als ein
    klarer Abbruch. `offer_model` importiert torch nur bei Bedarf, deshalb
    erst hier und nicht am Modulkopf.
    """
    from magda import offer_model

    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.is_file():
        parser.exit(
            1,
            f"Checkpoint fehlt: {checkpoint_path}. Erst `magda offers-model train` "
            "laufen lassen oder --checkpoint auf einen vorhandenen Pfad zeigen.\n",
        )
    model = offer_model.load(checkpoint_path)

    def grouping(page: dict) -> list[offers.Offer]:
        entities = [e for e in offers.entities_from_page(page) if e.type in offers.VALUE_TYPES]
        page_id = page.get("page_id") or "unknown"
        groups = model.group_page(page, model.threshold)
        return [
            offers._make_offer(page_id, index, [entities[i] for i in group])
            for index, group in enumerate(groups)
        ]

    return grouping


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=None,
                        help="Labelordner unter data/labeled/. Default: konfiguriertes/groesstes Modell")
    parser.add_argument("--predictions", default=None,
                        help="Variante unter data/predictions/ statt data/labeled/ (z.B. gbert)")
    parser.add_argument("--db", default=str(DEFAULT_DB),
                        help="SQLite-Zieldatei")
    parser.add_argument("--grouper", choices=GROUPERS, default="pair-model",
                        help="Wie Entities zu Angeboten werden. Default pair-model "
                             "(Gruppen-F1 0.821 gegen 0.524 der Heuristik)")
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT),
                        help="Paarmodell-Checkpoint fuer --grouper pair-model")
    args = parser.parse_args(argv)

    grouping = (
        offers.cluster_page if args.grouper == "heuristic"
        else _pair_model_grouping(args.checkpoint, parser)
    )

    if args.predictions:
        source = args.predictions
        directory = config.DATA_DIR / "predictions" / config.model_slug(source)
        if not directory.is_dir():
            parser.error(f"Vorhersagequelle nicht gefunden: {directory}")
        pages = _load_predicted_pages(source)
        if not pages:
            parser.exit(1, f"Keine Vorhersagen in {directory} gefunden. Erst `magda predict {source}` laufen lassen.\n")
    else:
        source = args.source or config.default_labeled_model()
        if source is None:
            parser.exit(1, "Keine Labelquelle gefunden. Erst `magda label` laufen lassen.\n")
        if not config.labeled_dir(source).is_dir():
            parser.error(f"Labelquelle nicht gefunden: {source}")
        pages = _load_labeled_pages(source)
        if not pages:
            parser.exit(1, f"Keine gelabelten Seiten in {config.labeled_dir(source)} gefunden.\n")

    stats = offers.write_sqlite(
        pages, db_path=Path(args.db), source=source, grouping=grouping, grouper=args.grouper
    )
    print(
        f"{stats['offers']} Angebote aus {stats['entities']} Entities "
        f"auf {stats['pages']} Seiten geschrieben (Gruppierung: {args.grouper})."
    )
    print(f"DB: {args.db}")
