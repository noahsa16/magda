"""SemEval-Schemata mit fest versioniertem Evaluator und unserem Span-Vertrag.

Magda speichert exklusive Endindizes, nervaluate inklusive. Die Umrechnung
bleibt an dieser einen Grenze; benachbarte Wörter dürfen nicht überlappen.
Historische Reports aus matching.py werden dadurch nicht umgeschrieben.
"""

from dataclasses import asdict
from importlib.metadata import version

from nervaluate import Evaluator
from nervaluate.strategies import StrictEvaluation, ExactEvaluation, PartialEvaluation, EntityTypeEvaluation

from magda.labels import ENTITY_TYPES, validate_spans

SCHEMES = ("strict", "exact", "partial", "type")


class _AnyOverlap:
    """SemEval verlangt Überlappung, nicht die Bibliotheksvorgabe von einem Prozent.

    Bei Spans über hundert Wörtern wäre ein einziges gemeinsames Wort sonst
    kein Treffer. Alle übrigen Zuordnungs- und Zählregeln bleiben unverändert.
    """

    def _has_sufficient_overlap(self, predicted, reference):
        return predicted.start <= reference.end and reference.start <= predicted.end


class _Strict(_AnyOverlap, StrictEvaluation):
    pass


class _Exact(_AnyOverlap, ExactEvaluation):
    pass


class _Partial(_AnyOverlap, PartialEvaluation):
    pass


class _Type(_AnyOverlap, EntityTypeEvaluation):
    pass


def _convert(pages):
    result = []
    for page in pages:
        if not isinstance(page, list) or any(
                not isinstance(s, dict) or type(s.get("start")) is not int or type(s.get("end")) is not int
                for s in page):
            raise ValueError("Evaluationsspans benötigen ganzzahlige Wortindizes.")
        errors = validate_spans(page, max((s["end"] for s in page), default=0))
        if errors:
            raise ValueError("Ungültige Evaluationsspans: " + "; ".join(errors))
        result.append([
            {"start": s["start"], "end": s["end"] - 1, "label": s["label"]}
            for s in sorted(page, key=lambda s: (s["start"], s["end"], s["label"]))
        ])
    return result


def _scores(results):
    mapped = {}
    for scheme in SCHEMES:
        row = asdict(results["ent_type" if scheme == "type" else scheme])
        row["missing"] = row.pop("missed")
        mapped[scheme] = row
    return mapped


def evaluate(reference, predicted):
    """Alle vier Schemata samt Labelauflösung; keine stille Schnittmenge."""
    if len(reference) != len(predicted) or not reference:
        raise ValueError("Referenz und Vorhersage brauchen dieselbe nichtleere Seitenliste.")
    evaluator = Evaluator(_convert(reference), _convert(predicted), tags=ENTITY_TYPES, loader="dict")
    evaluator.strategies = {"strict": _Strict(), "exact": _Exact(), "partial": _Partial(), "ent_type": _Type()}
    result = evaluator.evaluate()
    return {
        "implementation": f"nervaluate-{version('nervaluate')}",
        "overlap_policy": "any-word-overlap; explicit adapter overriding the default 1-percent minimum",
        "primary_scheme": "strict",
        "matching_schemes": _scores(result["overall"]),
        "matching_schemes_per_label": {
            label: _scores(rows) for label, rows in sorted(result["entities"].items())
        },
    }


def count_triple(score):
    """Treffer, Systemumfang, Referenzumfang tragen auch halbe Teiltreffer."""
    return (score["correct"] + 0.5 * score["partial"], score["actual"], score["possible"])
