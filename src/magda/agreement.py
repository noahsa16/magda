"""Wo widersprechen sich zwei Labeling-Modelle?

Der Modellvergleich in `magda gold` misst gegen `gold/` –
also gegen drei Seiten. Das ist die verlässlichste Zahl, die wir haben, aber
eine schmale. Über die Übereinstimmung zweier Modelle lässt sich dagegen auf
*allen* Seiten etwas sagen, ohne eine einzige davon zu annotieren.

Zwei Dinge kommen dabei heraus. Erstens eine Zuverlässigkeitszahl für den
Bericht: einig sind sich zwei unabhängige Labeler dort, wo die Seite eindeutig
ist. Zweitens – und praktisch wichtiger – eine Rangliste, welche Seite als
Nächstes von Hand annotiert gehört. Genau die Seiten, an denen sich die
Modelle uneins sind, bringen pro Annotationsstunde am meisten; auf den
einigen Seiten bestätigt Handarbeit nur, was ohnehin feststeht.

Ausdrücklich keine Qualitätsaussage: zwei Modelle können sich einig und
gemeinsam falsch sein. Übereinstimmung ist eine Obergrenze für Vertrauen,
kein Ersatz für Gold.
"""

import json

from magda import config
from magda.labels import ENTITY_TYPES, bio_to_spans


def _load_tags(model: str, page_id: str) -> list[str] | None:
    path = config.labeled_dir(model) / f"{page_id}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f).get("tags")
    except (json.JSONDecodeError, OSError):
        return None


def common_pages(model_a: str, model_b: str) -> list[str]:
    """Seiten, die beide Modelle gelabelt haben – alphabetisch."""
    a = {f.stem for f in config.labeled_dir(model_a).glob("*.json")}
    b = {f.stem for f in config.labeled_dir(model_b).glob("*.json")}
    return sorted(a & b)


def compare_page(tags_a: list[str], tags_b: list[str]) -> dict | None:
    """Übereinstimmung auf einer Seite, wortweise.

    Gibt None zurück, wenn die Tag-Listen unterschiedlich lang sind: dann
    zeigen die Indizes auf verschiedene Wörter, und jeder Vergleich wäre
    ausgedacht. Das passiert, wenn Schritt 02 zwischen zwei Labeling-Läufen
    neu gelaufen ist – derselbe Grund, aus dem Gold-Dateien einen
    words_hash tragen.
    """
    if len(tags_a) != len(tags_b):
        return None

    # Verglichen wird auf Wortebene und nicht auf Span-Ebene, weil ein
    # einziges Wort Unterschied sonst zwei ganze Spans als uneinig zählt und
    # die Zahl dramatischer aussieht, als die Lage ist.
    conflicts = [i for i, (a, b) in enumerate(zip(tags_a, tags_b)) if a != b]

    # "Beide sagen O" ist die häufigste Übereinstimmung und die
    # uninteressanteste – auf einer Prospektseite trägt jedes dritte Wort
    # kein Label. Ohne diese zweite Zahl sieht jedes Modellpaar einig aus.
    relevant = [i for i, (a, b) in enumerate(zip(tags_a, tags_b)) if a != "O" or b != "O"]
    relevant_conflicts = [i for i in conflicts if i in set(relevant)]

    return {
        "words": len(tags_a),
        "conflicts": conflicts,
        "agreement": 1 - len(conflicts) / max(1, len(tags_a)),
        "agreement_on_labeled": 1 - len(relevant_conflicts) / max(1, len(relevant)),
        "labeled_words": len(relevant),
    }


def compare_models(model_a: str, model_b: str) -> dict:
    """Übereinstimmung über alle gemeinsamen Seiten, plus Aufschlüsselung.

    Die Verwechslungsmatrix zählt Wörter, bei denen beide ein Label vergeben
    haben, es aber ein anderes ist – das ist die interessante Sorte
    Uneinigkeit. Ob ein Modell ein Wort gar nicht labelt, steht separat.
    """
    pages, skipped = [], []
    confusion: dict[str, dict[str, int]] = {}
    only_a: dict[str, int] = {}
    only_b: dict[str, int] = {}

    for page_id in common_pages(model_a, model_b):
        tags_a, tags_b = _load_tags(model_a, page_id), _load_tags(model_b, page_id)
        if not tags_a or not tags_b:
            skipped.append(page_id)
            continue
        result = compare_page(tags_a, tags_b)
        if result is None:
            skipped.append(page_id)
            continue

        for i in result["conflicts"]:
            type_a = tags_a[i][2:] if tags_a[i] != "O" else None
            type_b = tags_b[i][2:] if tags_b[i] != "O" else None
            if type_a and type_b and type_a != type_b:
                confusion.setdefault(type_a, {}).setdefault(type_b, 0)
                confusion[type_a][type_b] += 1
            elif type_a and not type_b:
                only_a[type_a] = only_a.get(type_a, 0) + 1
            elif type_b and not type_a:
                only_b[type_b] = only_b.get(type_b, 0) + 1

        pages.append({
            "page_id": page_id,
            "words": result["words"],
            "conflicts": len(result["conflicts"]),
            "agreement": result["agreement"],
            "agreement_on_labeled": result["agreement_on_labeled"],
        })

    total_words = sum(p["words"] for p in pages)
    total_conflicts = sum(p["conflicts"] for p in pages)

    return {
        "model_a": model_a,
        "model_b": model_b,
        "pages_compared": len(pages),
        "skipped": skipped,
        "agreement": 1 - total_conflicts / max(1, total_words),
        "confusion": confusion,
        "only_a": only_a,
        "only_b": only_b,
        # Uneinigste Seite zuerst: das ist die Annotationsreihenfolge, die pro
        # Stunde Handarbeit am meisten bringt.
        "pages": sorted(pages, key=lambda p: p["agreement"]),
    }


def disagreement_ranking(model_a: str, model_b: str, limit: int = 20) -> list[dict]:
    """Die Seiten, deren Handannotation am meisten brächte."""
    return compare_models(model_a, model_b)["pages"][:limit]


def label_agreement(model_a: str, model_b: str) -> dict[str, float]:
    """Je Entity-Typ: wie oft sind sich beide über ein Wort einig?

    Beantwortet, *wo* die Unsicherheit sitzt. Wenn zwei Modelle sich bei
    Preisen zu 95 % und bei Produkten zu 40 % einig sind, ist klar, welches
    Label das Projektrisiko trägt.
    """
    hits: dict[str, int] = {}
    totals: dict[str, int] = {}

    for page_id in common_pages(model_a, model_b):
        tags_a, tags_b = _load_tags(model_a, page_id), _load_tags(model_b, page_id)
        if not tags_a or not tags_b or len(tags_a) != len(tags_b):
            continue
        for a, b in zip(tags_a, tags_b):
            for tag in {a, b}:
                if tag == "O":
                    continue
                entity = tag[2:]
                totals[entity] = totals.get(entity, 0) + 1
                if a == b:
                    hits[entity] = hits.get(entity, 0) + 1

    return {
        entity: hits.get(entity, 0) / totals[entity]
        for entity in ENTITY_TYPES
        if totals.get(entity)
    }


def spans_of(model: str, page_id: str) -> list[dict]:
    """Spans eines Modells auf einer Seite – für die Anzeige im Inspektor."""
    tags = _load_tags(model, page_id)
    return bio_to_spans(tags) if tags else []
