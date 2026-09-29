"""Hält Tabellen und Abbildungen an die gespeicherten Messungen gebunden.

Der Export liest ausschließlich bestehende Ergebnisse. Er trainiert nichts,
bewertet keine Testseite neu und verändert weder Labels noch Studienartefakte.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent / "generated"
INPUTS = {
    "study": "data/eval/study-2026-09-16/study.json",
    "features": "data/eval/offers_grid_dev_ilp.json",
    "decoder": "data/eval/offers_grid_dev_cv_union-ilp.json",
    "qwen_later": "data/eval/runtime_thl_qwen3.8-27b_score_2026-09-24.json",
    "astra": "data/eval/codex_astra_score_2026-09-25.json",
}
NAMES = {
    "gbert": "GBERT", "xlmr": "XLM-R", "lilt": "LiLT", "layoutxlm": "LayoutXLM",
    "layoutxlm_pair_model": "Magda", "gemma-4-31b-it": "Gemma-4-31B-IT",
    "qwen3.6-35b-a3b": "Qwen3.6-35B-A3B", "mistral-medium-3.5-128b": "Mistral-Medium-3.5-128B",
}
VARIANTS = {
    "basis": "Base", "farbe": "Base + colour", "geometrie": "Base + geometry",
    "beide": "Base + geometry + colour", "anker": "Base + geometry + anchor",
    "lexik": "Base + geometry + lexical",
    "anker+lexik": "Base + geometry + anchor + lexical",
}


def number(value, signed=False):
    return f"{value:+.4f}" if signed else f"{value:.4f}"


def interval(values, signed=False):
    return "$[" + r",\,".join(number(v, signed) for v in values) + "]$"


def table(name, columns, headers, rows):
    lines = [r"% Automatisch aus gespeicherten Ergebnissen erzeugt.",
             r"\begin{tabular}{@{}" + columns + r"@{}}", r"\toprule",
             " & ".join(headers) + r" \\", r"\midrule"]
    lines += [r"\midrule" if row is None else
              " & ".join(str(cell) for cell in row) + r" \\" for row in rows]
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    (OUTPUT / f"{name}.tex").write_text("\n".join(lines))


def check_counts(study):
    """Abweichende Nenner oder veraltete F1-Werte sollen den Export stoppen."""
    groups = [study["ner_uncertainty"], study["offer_uncertainty"]]
    groups.extend(study["grouping"].values())
    for group in groups:
        for score in group["systems"].values():
            hits, predicted, reference = score["counts"]
            if not math.isclose(score["f1"], 2 * hits / (predicted + reference)):
                raise ValueError("Gespeicherte Zähler und F1 widersprechen sich.")


def export_tables(study, features, decoder):
    models = ("gbert", "xlmr", "lilt", "layoutxlm")
    rows = []
    for model in models:
        schemes = study["ner"][model]["matching_schemes"]
        score = schemes["strict"]
        rows.append([NAMES[model], number(score["precision"]), number(score["recall"]),
                     number(score["f1"]), interval(study["ner_uncertainty"]["systems"][model]["ci95"])])
    table("ner", "lrrrl", ["Model", "Precision", "Recall", "Strict F1", "95\\% CI"], rows)
    table("schemes", "lrrrr", ["Model", "Strict", "Exact", "Partial", "Type"], [
        [NAMES[m]] + [number(study["ner"][m]["matching_schemes"][s]["f1"])
                     for s in ("strict", "exact", "partial", "type")] for m in models])
    table("labels", "lrrrrr", ["Entity type", "Reference spans"] + [NAMES[m] for m in models], [
        [label.replace("_", r"\_"), scores["strict"]["possible"]] +
        [number(study["ner"][m]["matching_schemes_per_label"][label]["strict"]["f1"]) for m in models]
        for label, scores in study["ner"]["gbert"]["matching_schemes_per_label"].items()])
    for key, name in [("ner_uncertainty", "ner_differences"), ("offer_uncertainty", "offer_differences")]:
        columns = r">{\raggedright\arraybackslash}p{39mm}rll" if key == "offer_uncertainty" else "lrll"
        table(name, columns, ["Comparison", r"$\Delta$F1", "95\\% CI", "Bonferroni CI"], [
            [NAMES[c["a"]] + " $-$ " + NAMES[c["b"]], "$" + number(c["difference"], True) + "$",
             interval(c["ci95"], True), interval(c["ci_familywise"], True)] for c in study[key]["comparisons"]])
    rows = []
    for key, method, entity_input in [
        ("heuristic_on_gold", "Rule-based", "Human-annotated entities"),
        ("pair_model_on_gold", "MLP + ILP", "Human-annotated entities"),
        ("pair_model_on_layoutxlm", "MLP + ILP", "LayoutXLM predictions"),
    ]:
        entry = study["grouping"][key]
        scores = entry["systems"]
        rows.append([method, entity_input, number(scores["pair"]["f1"]), number(scores["exact_group"]["f1"]),
                     interval(scores["exact_group"]["ci95"]), entry["totals"]["unassignable"]])
    table("grouping", r"l>{\raggedright\arraybackslash}p{29mm}rrlr",
          ["Grouping method", "Entity input", "Pair F1", "Group F1", "95\\% CI (group)", "Unmapped"], rows)
    rows = []
    for key, score in study["offer_uncertainty"]["systems"].items():
        hits, predicted, reference = score["counts"]
        missing = len(study["replays"][key]["missing_responses"]) if key in study["replays"] else 0
        rows.append([NAMES[key], int(hits), int(predicted), number(hits/predicted), number(hits/reference),
                     number(score["f1"]), missing])
    table("offers", "lrrrrrr", ["System", "Hits", "Outputs", "Precision", "Recall", "F1", "Failed pages"], rows)
    table("offer_intervals", "lrl", ["System", "F1", "95\\% CI"], [
        [NAMES[k], number(v["f1"]), interval(v["ci95"])] for k,v in study["offer_uncertainty"]["systems"].items()])
    rows = []
    for key, label in VARIANTS.items():
        entry = features["variants"][key]
        diff = features["paired_vs_baseline"].get(f"{key}_vs_basis_total")
        rows.append([label, entry["features"], number(entry["total"]["group_f1"]),
                     "$" + number(diff["difference"], True) + "$" if diff else "--",
                     interval([diff["low"], diff["high"]], True) if diff else "--"])
    table("features", "lrrrl", ["Feature set", "Count", "Group F1", r"$\Delta$ vs. base", "95\\% CI"], rows)
    table("decoder", "lrrrr", ["Decoder", r"Mean $\tau$", "Pair F1", "Group F1", "Groups"], [
        [key.split("/")[1].upper(), f"{value['threshold']:.3f}", number(value["total"]["pair_f1"]),
         number(value["total"]["group_f1"]), value["total"]["sys_groups"]]
        for key,value in decoder["variants"].items()])
    table("errors", "lrrr", ["Model", "No overlap", "Type only", "Boundary / merge"], [
        [NAMES[k], v["counts"]["missing"], v["counts"]["type_at_exact_boundary"], v["counts"]["boundary_or_merge"]]
        for k,v in study["error_analysis"].items()])


def export_figures(study, features):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "serif", "font.size": 10, "pdf.fonttype": 42,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.4))
    for ax, key, title in zip(axes, ("ner_uncertainty", "offer_uncertainty"),
                               ("(a) Entity recognition", "(b) Offer reconstruction")):
        items = list(study[key]["systems"].items())
        for position, (name, entry) in enumerate(items):
            low, high = entry["ci95"]; point = entry["f1"]
            ax.errorbar(point, position, xerr=[[point-low], [high-point]], fmt="o",
                        color="#253f4c", capsize=3, markersize=5)
        ax.set_yticks(range(len(items)), [NAMES[name] for name,_ in items]); ax.invert_yaxis()
        ax.set_xlim(.55,.90); ax.set_xlabel("F1 with 95% cluster interval")
        ax.set_title(title, fontsize=11, pad=14); ax.grid(axis="x", color=".9")
    fig.tight_layout(w_pad=2)
    fig.savefig(OUTPUT / "results.pdf", bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(fig)
    keys = [key for key in VARIANTS if key != "basis"]
    labels = [VARIANTS[key].replace("Base + ", "+ ") for key in keys]
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.5), sharey=True)
    for ax, scope, title in zip(axes, ("blind", "checkable"),
                               ("No unit-price reference", "Unit-price reference available")):
        for position,key in enumerate(keys):
            entry=features["paired_vs_baseline"][f"{key}_vs_basis_{scope}"]
            point=entry["difference"]
            ax.errorbar(point,position,xerr=[[point-entry["low"]],[entry["high"]-point]],
                        fmt="o",color="#253f4c",capsize=3,markersize=4)
        ax.axvline(0,color=".6",linewidth=.8); ax.set_xlabel(r"$\Delta$ exact group F1")
        ax.set_title(title.replace(" reference", "\nreference"),fontsize=10,pad=12); ax.grid(axis="x",color=".9")
    axes[0].set_yticks(range(len(keys)),labels); axes[0].invert_yaxis()
    fig.tight_layout(w_pad=1)
    fig.savefig(OUTPUT / "features.pdf",bbox_inches="tight",metadata={"CreationDate": None})
    plt.close(fig)


def export_record_comparison(study, supplementary):
    """Führt getrennte Läufe nur bei unveränderter Bewertungsgrundlage zusammen."""
    local = study["offer_uncertainty"]["systems"]["layoutxlm_pair_model"]
    study_hash = hashlib.sha256((ROOT / INPUTS["study"]).read_bytes()).hexdigest()
    names = {
        "layoutxlm_pair_model": "Magda",
        "gemma-4-31b-it": "Gemma-4-31B-IT",
        "qwen3.6-35b-a3b": "Qwen3.6-35B-A3B",
        "mistral-medium-3.5-128b": "Mistral-Medium-3.5-128B",
    }
    rows = []
    for key, score in study["offer_uncertainty"]["systems"].items():
        hits, predicted, reference = score["counts"]
        rows.append([names[key], int(hits), int(predicted), number(hits / predicted),
                     number(hits / reference), number(score["f1"])])
    for name, report in supplementary:
        counts = report["counts"]
        paired = report["paired_with_local"]["systems"]["local_pipeline"]
        if (report["study_sha256"] != study_hash or report["protocol"] != "offer-price-v2"
                or counts["pages"] != len(study["pages"])
                or counts["reference"] != local["counts"][2]
                or paired["counts"] != local["counts"]):
            raise ValueError("Ergänzender Lauf verwendet eine andere Bewertungsgrundlage.")
        if not math.isclose(counts["f1"], 2 * counts["matched"] /
                            (counts["system"] + counts["reference"])):
            raise ValueError("Ergänzende Zähler und F1 widersprechen sich.")
        if report["raw_records"] - report["unscored_fragments"] != counts["system"]:
            raise ValueError("Ergänzende Ausgaben und ausgeschlossene Fragmente widersprechen sich.")
        rows.extend([None, [name, counts["matched"], counts["system"],
                           number(counts["precision"]), number(counts["recall"]),
                           number(counts["f1"])]])
    table("offers_all", "lrrrrr", ["System", "Matches", "Outputs", "Precision", "Recall", "F1"], rows)


def main():
    OUTPUT.mkdir(exist_ok=True)
    data={key:json.loads((ROOT/path).read_text()) for key,path in INPUTS.items()}
    check_counts(data["study"])
    export_tables(data["study"],data["features"],data["decoder"])
    export_record_comparison(data["study"], [
        ("Qwen3.8-27B (later API run)", data["qwen_later"]),
        ("GPT-6 Astra (Codex)", data["astra"]),
    ])
    export_figures(data["study"],data["features"])
    manifest={key:{"path":path,"sha256":hashlib.sha256((ROOT/path).read_bytes()).hexdigest()}
              for key,path in INPUTS.items()}
    (OUTPUT/"sources.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(f"Tabellen, Abbildungen und Quellenfingerabdrücke: {OUTPUT}")


if __name__ == "__main__":
    main()
