"""Reproduzierbare Fallstudie aus eingefrorenen Ausgaben und Referenzdateien.

Die Rechnung bleibt auch vor dem menschlichen Abgleich ausführbar. Dieser
Status reist mit den Ergebnissen; ein erfolgreiches Skript ersetzt keine
inhaltliche Freigabe der Referenz.
"""

import json
import platform
from collections import Counter
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

from magda import (annotation_review, blackbox_eval, config, dedupe, gold,
                   gold_evaluation, offers, offers_gold, provenance, reference_audit,
                   resampling, semeval)
from magda.labels import bio_to_spans

VARIANTS = ("gbert", "xlmr", "lilt", "layoutxlm")
MODELS = ("gemma-4-31b-it", "qwen3.6-35b-a3b", "mistral-medium-3.5-128b")
NER_PAIRS = (("xlmr", "gbert"), ("lilt", "xlmr"), ("layoutxlm", "lilt"), ("layoutxlm", "gbert"))


def verify_snapshot(study, *, require_same_revision=True):
    """Während der Rechnung bleibt alles fest; später darf nur der Commit weiterziehen.

    Ein Report-Commit oder Merge verändert den Quelleninhalt nicht. Die spätere
    Prüfung darf diesen zulassen, muss aber weiterhin alle Inhalts-Hashes prüfen.
    """
    def verify(path, expected):
        if provenance.file_digest(path) != expected:
            raise ValueError(f"Eingabe wurde während der Messung verändert: {path}")
    verify(config.DATA_DIR / "splits/split.json", study["split_sha256"])
    for pid, expected in study["cluster_word_hashes"].items():
        verify(config.WORDS_DIR / f"{pid}.json", expected)
    verify(config.CHECKPOINTS_DIR / "offer_pairs/model.pt", study["pair_checkpoint_sha256"])
    for row in study["reference_audit"]["pages"]:
        pid = row["page_id"]
        verify(config.GOLD_DIR / f"{pid}.json", row["hashes"]["spans"])
        verify(config.GOLD_DIR / "offers" / f"{pid}.json", row["hashes"]["groups"])
        verify(config.WORDS_DIR / f"{pid}.json", row["words_sha256"])
        if row["image_sha256"] is not None:
            verify(config.IMAGES_DIR / f"{pid}.png", row["image_sha256"])
    for variant, result in study["ner"].items():
        actual = provenance.prediction_identity(config.DATA_DIR / "predictions" / variant, study["pages"])
        if actual != result["predictions_sha256"]:
            raise ValueError(f"Vorhersagen während der Rechnung verändert: {variant}")
    for replay in study["replays"].values():
        verify(config.PROJECT_ROOT / replay["path"], replay["sha256"])
    current_code = provenance.code_version()
    if (current_code["source_sha256"] != study["code"]["source_sha256"]
            or (require_same_revision and current_code["git_revision"] != study["code"]["git_revision"])):
        raise ValueError("Quellcode während der Rechnung verändert; Messung erneut starten.")


def evaluation_clusters(page_ids, split):
    """Bildet Cluster im ganzen Testsplit, damit ausgelassene Brückenseiten bleiben."""
    if not page_ids or len(set(page_ids)) != len(page_ids):
        raise ValueError("Nichtleere, eindeutige Vergleichsliste benötigt.")
    partitions = {name: set(ids) for name, ids in split.items()}
    if any(partitions[a] & partitions[b] for a, b in (("train", "dev"), ("train", "test"), ("dev", "test"))):
        raise ValueError("Train, Dev und Test enthalten gemeinsame Seiten-IDs.")
    if not set(page_ids) <= partitions["test"]:
        raise ValueError("Vergleichsliste enthält Seiten außerhalb des eingefrorenen Tests.")
    texts = {pid: [w["text"] for w in json.loads((config.WORDS_DIR / f"{pid}.json").read_text())["words"]]
             for pid in sorted(partitions["test"])}
    position = {pid: index for index, pid in enumerate(page_ids)}
    full = dedupe.group(texts, threshold=0.7)
    selected = [[position[pid] for pid in cluster if pid in position] for cluster in full]
    return [cluster for cluster in selected if cluster], full


def _prediction_pages(variant, page_ids):
    result = []
    for page_id in page_ids:
        payload = json.loads((config.DATA_DIR / "predictions" / variant / f"{page_id}.json").read_text())
        tags = [w["label"] or "O" for w in payload["words"]]
        if payload.get("entities") is not None:
            canonical = lambda spans: sorted((s["start"], s["end"], s["label"]) for s in spans)
            if canonical(payload["entities"]) != canonical(bio_to_spans(tags)):
                raise ValueError(f"Entity-Export und Wortlabels widersprechen sich: {variant}/{page_id}")
        result.append({**payload, "tags": tags})
    return result


def _project(pages, assignments):
    result, fragments = {}, []
    for page in pages:
        deals = []
        for offer in offers_gold.offers_from_reference(page, assignments[page["page_id"]]):
            projected = blackbox_eval.deals_from_offer(offer)
            if not projected:
                fragments.append({"page_id": page["page_id"], "values": offer.values()})
            deals.extend(projected)
        result[page["page_id"]] = deals
    return result, fragments


def _grouping(pages, reference, grouping, clusters, resamples_count, seed):
    rows, assignments = [], {}
    for page in pages:
        grouped = grouping(page)
        rows.append(asdict(offers_gold.judge_page(page, reference.assignments[page["page_id"]], grouped)))
        assignments[page["page_id"]] = {
            index: group_id for group_id, offer in enumerate(grouped)
            for entity in offer.entities for index in range(entity.start, entity.end)
        }
    counts = {
        "pair": [(r["shared_pairs"], r["sys_pairs"], r["ref_pairs"]) for r in rows],
        "exact_group": [(r["exact_groups"], r["sys_groups"], r["ref_groups"]) for r in rows],
    }
    result = resampling.compare_counts(counts, clusters, resamples=resamples_count, seed=seed)
    result["per_page"] = rows
    result["totals"] = {key: sum(row[key] for row in rows) for key in rows[0] if key != "page_id"}
    return result, assignments


def _error_examples(reference_pages, predicted_pages):
    result = []
    for ref_page, pred_page in zip(reference_pages, predicted_pages, strict=True):
        ref = bio_to_spans(ref_page["tags"])
        pred = bio_to_spans(pred_page["tags"])
        for span in ref:
            if span in pred:
                continue
            overlapping = [s for s in pred if s["start"] < span["end"] and span["start"] < s["end"]]
            category = "missing" if not overlapping else (
                "type_at_exact_boundary" if any(s["start"] == span["start"] and s["end"] == span["end"] for s in overlapping)
                else "boundary_or_merge")
            result.append({"page_id": ref_page["page_id"], "category": category, "reference": span,
                           "predicted_overlaps": overlapping,
                           "text": " ".join(w["text"] for w in ref_page["words"][span["start"]:span["end"]])})
    return {"scope": "Nicht exakt getroffene Referenzentities; zusätzliche Systementities separat in Precision.",
            "counts": dict(Counter(r["category"] for r in result)), "cases": result}


def run_study(page_ids, *, resamples_count=10000, seed=42):
    from magda import offer_model

    code = provenance.code_version()
    split_path = config.DATA_DIR / "splits" / "split.json"
    split = json.loads(split_path.read_text())
    cluster_word_hashes = {pid: provenance.file_digest(config.WORDS_DIR / f"{pid}.json") for pid in split["test"]}
    clusters, full_clusters = evaluation_clusters(page_ids, split)
    audit = reference_audit.audit_reference(page_ids)
    if any(i["code"] in {"invalid_structure", "invalid_status_or_hash"} for i in audit["issues"]):
        raise ValueError("Referenz ist strukturell ungültig; Hinweise vor der Messung beheben.")
    reference = offers_gold.load_reference()
    gold_by_id = {p["page_id"]: p for p in gold.load_gold_pages().pages}
    reference_pages = [gold_by_id[pid] for pid in page_ids]
    ner, predictions = {}, {}
    for variant in VARIANTS:
        ner[variant] = gold_evaluation.score_predictions(config.DATA_DIR / "predictions" / variant, page_ids)
        predictions[variant] = _prediction_pages(variant, page_ids)
    ner_uncertainty = resampling.compare_counts({
        variant: [semeval.count_triple(ner[variant]["per_page"][pid]["strict"]) for pid in page_ids]
        for variant in VARIANTS
    }, clusters, NER_PAIRS, resamples=resamples_count, seed=seed)

    checkpoint_path = config.CHECKPOINTS_DIR / "offer_pairs" / "model.pt"
    checkpoint_sha256 = provenance.checkpoint_digest(checkpoint_path)
    model = offer_model.load(checkpoint_path)
    pair_grouping = offers.pair_model_grouping(model)
    grouping, projected = {}, {}
    for name, pages, method in (
        ("heuristic_on_gold", reference_pages, offers.cluster_page),
        ("pair_model_on_gold", reference_pages, pair_grouping),
        ("pair_model_on_layoutxlm", predictions["layoutxlm"], pair_grouping),
    ):
        print(f"Gruppierung: {name}", flush=True)
        grouping[name], projected[name] = _grouping(pages, reference, method, clusters, resamples_count, seed)
    reference_deals, reference_fragments = _project(reference_pages, reference.assignments)
    own_deals, own_fragments = _project(predictions["layoutxlm"], projected["pair_model_on_layoutxlm"])
    offer_counts, replays = {}, {}
    counts = lambda system: [blackbox_eval.match_deals(system.get(pid, []), reference_deals[pid]) for pid in page_ids]
    own_rows = counts(own_deals)
    offer_counts["layoutxlm_pair_model"] = [(r["matched"], r["system"], r["reference"]) for r in own_rows]
    for name in MODELS:
        path = config.EVAL_DIR / f"blackbox_test_{name}_pair-model_ref-teacher.json"
        replay = json.loads(path.read_text())
        if not set(page_ids) <= set(replay["pages"]) or replay["model"] != name:
            raise ValueError(f"Blackbox-Replay passt nicht zur Studie: {path}")
        raw = replay["blackbox_deals"]
        valid = {pid: [d for d in raw.get(pid, []) if d.get("name") and d.get("price") is not None] for pid in page_ids}
        rows = counts(valid)
        offer_counts[name] = [(r["matched"], r["system"], r["reference"]) for r in rows]
        replays[name] = {
            "path": str(path.relative_to(config.PROJECT_ROOT)), "sha256": provenance.file_digest(path),
            "prompt_version": replay.get("prompt_version"), "missing_responses": [pid for pid in page_ids if pid not in raw],
            "fragments": sum(len(raw.get(pid, [])) - len(valid[pid]) for pid in page_ids),
            "per_page": dict(zip(page_ids, rows, strict=True)),
        }
    offer_uncertainty = resampling.compare_counts(offer_counts, clusters,
        [(name, "layoutxlm_pair_model") for name in MODELS], resamples=resamples_count, seed=seed)
    study = {
        "protocol": "magda-study-v1", "status": "completed_exploratory",
        "reference_policy": {
            "mode": "existing_reference_with_limitations",
            "reference_changed": False,
            "interpretation": "Abschluss der Auswertung, keine Bestätigung einer fehlerfreien Referenz.",
        },
        "pages": page_ids, "clusters": clusters, "full_test_clusters": full_clusters,
        "cluster_word_hashes": cluster_word_hashes,
        "split": {key: len(ids) for key, ids in split.items()}, "split_sha256": provenance.file_digest(split_path),
        "reference_audit": audit, "ner": ner, "ner_uncertainty": ner_uncertainty,
        "grouping": grouping, "offer_uncertainty": offer_uncertainty, "replays": replays,
        "reference_deals": reference_deals, "own_deals": own_deals,
        "reference_fragments": reference_fragments, "own_fragments": own_fragments,
        "offer_protocol": {"version": blackbox_eval.EVALUATION_VERSION,
                           "fields": blackbox_eval.COMMON_FIELDS, "name_similarity": blackbox_eval.NAME_SIMILARITY,
                           "price_tolerance": 0.0},
        "error_analysis": {variant: _error_examples(reference_pages, predictions[variant]) for variant in VARIANTS},
        "pair_checkpoint_sha256": checkpoint_sha256,
        "pair_threshold": model.threshold,
        "pair_model": {"hidden": list(model.hidden), "decoder": model.decoder,
                       "blocks": list(model.blocks), "feature_names": model.feature_names,
                       "provenance": model.provenance},
        "code": code,
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "packages": {name: version(name) for name in ("numpy", "torch", "transformers", "seqeval", "nervaluate")}},
        "limitations": [
            "Keine systematische unabhängige Doppelannotation des Referenzkorpus; die Zuverlässigkeit der Annotation ist nicht durch Inter-Annotator-Übereinstimmung quantifiziert.",
            "Die Zugehörigkeit zu einem Angebot ist bei gemeinsamen Preisen, Varianten und Mehrfachkäufen teilweise mehrdeutig. Der Score gilt für die gespeicherten Gruppen und deren Projektion auf Name und PRICE.",
            "Uneinheitliche Spangrenzen, offene Labelkonventionen und bekannte Referenzfehler bleiben unverändert. Abweichungen vom Goldstandard sind deshalb nicht durchweg Modellfehler; Richtung und Größe der Gesamtverzerrung sind unbekannt.",
            "Bootstrap-Intervalle erfassen Stichprobenunsicherheit innerhalb dieser Referenz, keine Unsicherheit durch fehlerhafte Labels oder alternative Angebotsdefinitionen.",
            "Testseiten wurden bereits betrachtet; Modell- und Schwellenwahl wird hier nicht optimiert.",
            "Ein Händler und eine Testwoche; keine allgemeine Aussage über neue Händler oder Wochen.",
            "Ein gespeicherter Lauf je System; Bootstrap misst keine Trainings- oder API-Seed-Streuung.",
            "NER-Exporte enthalten teilweise keine Checkpoint-Fingerabdrücke; heutige Gewichte werden ihnen nicht zugeschrieben.",
            "Architekturvergleich mit unterschiedlichen Vortrainingsverfahren; keine kontrollierte kausale Layout-/Bildablation.",
            "Blackbox sieht Bilder und kann Logos ohne PDF-Text erkennen; lokale Ausgaben sind an Textlayer-Wörter gebunden.",
            "Name und PRICE sind die gemeinsamen Felder; keine vollständige Feldgenauigkeit und kein gemessener Ende-zu-Ende-Speedup.",
        ],
    }
    verify_snapshot(study)
    return study
