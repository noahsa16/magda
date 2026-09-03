"""Grouper x Referenzquelle im Blackbox-Vergleich getrennt ausweisen.

    .venv/bin/python scripts/blackbox_decompose.py

Rechnet aus den gespeicherten Blackbox-Antworten (`blackbox_deals` in
`data/eval/blackbox_test_*.json`) nach, wie viel vom Unterschied zwischen
dem ersten Lauf (Heuristik als Grouper, cluster_page-Referenz) und dem
zweiten (Paarmodell, Teacher-Referenz) an welcher der beiden Einstellungen
haengt - ohne einen einzigen API-Aufruf. Beleg fuer die 2x2-Tabelle in
`reports/woche-08.md`.

Braucht `checkpoints/offer_pairs/model.pt` und die LayoutXLM-Vorhersagen
fuer die Seiten aus `data/eval/test_cluster_pages.txt`.
"""

import json

from magda import blackbox_eval, config, offer_model
from magda.cli.blackbox_eval import _deals_by_page, _teacher_deals_by_page
from magda.cli.evaluate import read_page_ids
from magda.cli.offers import _load_labeled_pages, _load_predicted_pages
from magda.cli.offers_model import DEFAULT_CHECKPOINT

MODELS = ("qwen3.6-35b-a3b", "mistral-medium-3.5-128b", "gemma-4-31b-it")


def main():
    page_ids = read_page_ids(config.EVAL_DIR / "test_cluster_pages.txt")
    wanted = set(page_ids)
    reference_pages = [p for p in _load_labeled_pages("sonnet-5") if p["page_id"] in wanted]
    predicted_pages = [p for p in _load_predicted_pages("layoutxlm") if p["page_id"] in wanted]
    model = offer_model.load(DEFAULT_CHECKPOINT)

    references = {"heuristik-Ref": _deals_by_page(reference_pages),
                  "teacher-Ref": _teacher_deals_by_page(reference_pages, "claude-sonnet-5")}
    owns = {"heuristik": _deals_by_page(predicted_pages, "heuristic"),
            "paarmodell": _deals_by_page(predicted_pages, "pair-model", model)}
    for deals in (*references.values(), *owns.values()):
        deals.pop("__fragments__", None)

    def paired(system, reference):
        return blackbox_eval.compare_pages(
            {p: (system.get(p) or [], reference.get(p) or []) for p in page_ids})

    def cell(counts):
        return f"{counts['f1']:.3f} ({counts['system']}/{counts['reference']})"

    print("eigene Pipeline gegen Referenz  (F1, Angebote System/Referenz)")
    print(f"{'Grouper':<14}" + "".join(f"{name:>24}" for name in references))
    for grouper, own in owns.items():
        print(f"{grouper:<14}" + "".join(f"{cell(paired(own, ref)):>24}" for ref in references.values()))

    for name in MODELS:
        runs = {"Lauf 1 (Heuristik-Lauf)": config.EVAL_DIR / f"blackbox_test_{name}.json",
                "Lauf 2 (Paarmodell-Lauf)": config.EVAL_DIR / f"blackbox_test_{name}_pair-model_ref-teacher.json"}
        print(f"\n{name}  (Blackbox gegen ...)")
        print(f"{'Antworten aus':<26}" + "".join(f"{col:>24}" for col in references)
              + f"{'eigene: paarmodell':>24}{'eigene: heuristik':>24}")
        for label, path in runs.items():
            report = json.loads(path.read_text())
            deals = report["blackbox_deals"]
            row = f"{label:<26}" + "".join(f"{cell(paired(deals, ref)):>24}" for ref in references.values())
            row += f"{cell(paired(deals, owns['paarmodell'])):>24}{cell(paired(deals, owns['heuristik'])):>24}"
            print(row + f"   [{len(deals)} Seiten, {len(report['errors'])} Fehler]")


if __name__ == "__main__":
    main()
