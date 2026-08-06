"""Welche Gold-Seite gehört als Nächstes von Hand durchgesehen?

193 der 196 Gold-Seiten sind maschinell vorannotiert und tragen
`status: "in_progress"`; sie zählen für keine Messung, bis ein Mensch sie
freigibt. Alle durchzusehen ist unnötig – für eine belastbare Zahl reichen
20 bis 30 Seiten. Welche 30, entscheidet über den Wert der Messung.

Drei Kriterien, in dieser Reihenfolge:

1. **Eine Seite je Duplikat-Cluster.** Penny druckt 44 fast gleiche
   Regionalausgaben. Wer 30 Seiten aus demselben Cluster freigibt, hat 30-mal
   dieselbe Seite gemessen. Der Testsatz zeigt das Problem in Zahlen: 107
   Seiten, aber nur 66 unabhängige Cluster.
2. **Testseiten zuerst.** Gemessen wird auf dem Test-Split; eine freigegebene
   Trainingsseite verbessert die Trainingsdaten, aber keine einzige Metrik.
3. **Uneinigkeit der Labeling-Modelle.** Wo zwei unabhängige Modelle
   dasselbe sagen, bestätigt Handarbeit meist nur, was ohnehin feststeht. Wo
   sie sich widersprechen, ist mindestens eines falsch.

Kriterium 3 ist eine Heuristik: zwei Modelle können sich einig und gemeinsam
irren. Es sortiert nur die Reihenfolge innerhalb der ersten beiden.
"""

import json
from pathlib import Path

from magda import agreement, config, dedupe

# Schwelle für die Clusterbildung. Nicht 0.95 wie in der Entdopplung: dort
# geht es darum, was gelöscht werden darf, hier darum, was sich beim Messen
# gegenseitig vertritt. Bei 0.7 zählen zwei Seiten als dieselbe Vorlage, auch
# wenn ein Artikel ausgetauscht wurde.
CLUSTER_THRESHOLD = 0.7


def default_pair() -> tuple[str | None, str | None]:
    """Zwei möglichst unabhängige Labelordner für das Uneinigkeitsmass.

    Nicht schlicht die zwei grössten: `mistral-medium-3.5-128b` und
    `mistral-medium-3.5-128b-promptv1` sind dasselbe Modell mit zwei Prompts,
    und der zweite ist der bekannt schlechte (F1 0.306 gegen Gold). Ihre
    Uneinigkeit misst die Prompt-Überarbeitung, nicht die Schwierigkeit der
    Seite. Deshalb muss der zweite Ordner von einem anderen Modell stammen.
    """
    nach_umfang = sorted(
        config.labeled_models(),
        key=lambda m: (len(list(config.labeled_dir(m).glob("*.json"))), m),
        reverse=True,
    )
    if not nach_umfang:
        return None, None

    erster = nach_umfang[0]
    for kandidat in nach_umfang[1:]:
        # Gemeinsamer Präfix heisst: dasselbe Modell, andere Einstellung.
        if not (kandidat.startswith(erster) or erster.startswith(kandidat)):
            return erster, kandidat
    return erster, None


def _wortlisten(page_ids: list[str]) -> dict[str, list[str]]:
    listen = {}
    for pid in page_ids:
        f = config.WORDS_DIR / f"{pid}.json"
        if f.exists():
            with open(f) as fh:
                listen[pid] = [w["text"] for w in json.load(fh)["words"]]
    return listen


def _split_rollen() -> dict[str, str]:
    """page_id -> "test" / "dev" / "train". Leer, wenn es keinen Split gibt."""
    split_file = config.SPLITS_DIR / "split.json"
    if not split_file.exists():
        return {}
    with open(split_file) as f:
        splits = json.load(f)
    return {pid: rolle for rolle, ids in splits.items() for pid in ids}


def _uneinigkeit(model_a: str | None, model_b: str | None) -> dict[str, float]:
    """page_id -> Anteil uneiniger Wörter unter denen, die überhaupt ein Label tragen."""
    if not model_a or not model_b:
        return {}
    werte = {}
    for pid in agreement.common_pages(model_a, model_b):
        tags_a = agreement._load_tags(model_a, pid)
        tags_b = agreement._load_tags(model_b, pid)
        if tags_a is None or tags_b is None:
            continue
        vergleich = agreement.compare_page(tags_a, tags_b)
        if vergleich is not None:
            werte[pid] = 1 - vergleich["agreement_on_labeled"]
    return werte


def _offene_gold_seiten() -> list[str]:
    offen = []
    for f in sorted(Path(config.GOLD_DIR).glob("*.json")):
        with open(f) as fh:
            if json.load(fh).get("status") != "done":
                offen.append(f.stem)
    return offen


def queue(model_a: str | None = None, model_b: str | None = None,
          limit: int = 30) -> list[dict]:
    """Die nächsten Seiten zur Durchsicht, wichtigste zuerst.

    Je Duplikat-Cluster erscheint höchstens eine Seite: sind die anderen
    freigegeben, misst man dieselbe Vorlage mehrfach.
    """
    offen = set(_offene_gold_seiten())
    if not offen:
        return []

    # Cluster über *alle* extrahierten Seiten, nicht nur die offenen: eine
    # bereits freigegebene Seite vertritt ihren Cluster schon.
    alle = sorted(p.stem for p in config.WORDS_DIR.glob("*.json"))
    cluster = dedupe.group(_wortlisten(alle), threshold=CLUSTER_THRESHOLD)

    rollen = _split_rollen()
    uneinig = _uneinigkeit(model_a, model_b)
    erledigt = {pid for pid in alle if pid not in offen and (config.GOLD_DIR / f"{pid}.json").exists()}

    vorschlaege = []
    for gruppe in cluster:
        if set(gruppe) & erledigt:
            continue  # Cluster hat schon einen freigegebenen Vertreter
        kandidaten = [pid for pid in gruppe if pid in offen]
        if not kandidaten:
            continue
        # Innerhalb des Clusters die uneinigste Seite als Vertreter
        vertreter = max(kandidaten, key=lambda pid: (uneinig.get(pid, 0.0), pid))
        vorschlaege.append({
            "page_id": vertreter,
            "split": rollen.get(vertreter, "?"),
            "cluster_size": len(gruppe),
            "disagreement": round(uneinig.get(vertreter, 0.0), 3),
            "represents": sorted(p for p in gruppe if p != vertreter),
        })

    # Testseiten zuerst, darin die uneinigsten, darin die grössten Cluster:
    # eine Seite, die für elf andere steht, ist mehr wert als eine Einzelseite.
    vorschlaege.sort(
        key=lambda v: (v["split"] != "test", -v["disagreement"], -v["cluster_size"], v["page_id"])
    )
    return vorschlaege[:limit]


def offer_queue(pages: list[dict], limit: int = 40) -> list[dict]:
    """Welche Seiten die Gruppierungsreferenz zuerst braucht.

    Anders als `queue()` sortiert das nicht nach Uneinigkeit zweier Modelle,
    sondern nach dem gemessenen blinden Fleck: `magda offers-report` urteilt
    nur, wo ein Grundpreis steht, und ueber die Haelfte der Zuordnungen bleibt
    deshalb unbeurteilt. Dort ist Handarbeit alternativlos.

    Nur nach dieser Luecke zu sortieren, ergaebe aber eine reine
    Non-Food-Referenz - ueber Lebensmittel sagte sie nichts, und gerade dort
    liegt die Masse der Seiten. Deshalb kommen zwei Ranglisten abwechselnd zum
    Zug: die groesste Luecke und die groesste Vorlage. Welche einen Vorschlag
    hervorgebracht hat, steht als `reason` dabei.

    Train und Dev, nie Test: eine Referenz, an der Heuristiken entwickelt
    werden, gehoert nicht auf die Seiten, an denen am Ende gemessen wird.
    """
    from magda import offers_gold, offers_report

    roles = _split_rollen()
    if not roles:
        raise FileNotFoundError(
            f"{config.SPLITS_DIR / 'split.json'} fehlt. Erst `magda split` laufen lassen."
        )

    eligible = [p for p in pages if roles.get(p.get("page_id")) in ("train", "dev")]
    if not eligible:
        return []

    texts = {p["page_id"]: [w["text"] for w in p["words"]] for p in eligible}
    clusters = dedupe.group(texts, threshold=CLUSTER_THRESHOLD)
    annotated = {f.stem for f in offers_gold.reference_dir().glob("*.json")}

    verdicts = {p["page_id"]: offers_report.judge_page(p) for p in eligible}

    candidates = []
    for group in clusters:
        if set(group) & annotated:
            continue  # Ein fertiger Vertreter deckt den Cluster ab
        representative = min(
            group, key=lambda pid: (-verdicts[pid].unjudgeable, pid)
        )
        verdict = verdicts[representative]
        candidates.append({
            "page_id": representative,
            "split": roles.get(representative, "?"),
            "cluster_size": len(group),
            "unjudgeable": verdict.unjudgeable,
            "judgeable": verdict.confirmed + verdict.contradicted,
            "represents": sorted(p for p in group if p != representative),
        })

    by_gap = sorted(candidates, key=lambda c: (-c["unjudgeable"], -c["cluster_size"], c["page_id"]))
    by_mass = sorted(candidates, key=lambda c: (-c["cluster_size"], -c["judgeable"], c["page_id"]))

    selection, taken = [], set()
    for rank in range(len(candidates)):
        for ranking, reason in ((by_gap, "luecke"), (by_mass, "masse")):
            if rank >= len(ranking):
                continue
            entry = ranking[rank]
            if entry["page_id"] in taken:
                continue
            taken.add(entry["page_id"])
            selection.append({**entry, "reason": reason})
            if len(selection) >= limit:
                return selection
    return selection


def abdeckung() -> dict:
    """Wie viel des Testsplits ist durch freigegebene Seiten schon abgedeckt?"""
    rollen = _split_rollen()
    test = {pid for pid, rolle in rollen.items() if rolle == "test"}
    if not test:
        return {"test_seiten": 0, "cluster": 0, "abgedeckt": 0}

    offen = set(_offene_gold_seiten())
    freigegeben = {
        f.stem for f in Path(config.GOLD_DIR).glob("*.json") if f.stem not in offen
    }
    cluster = dedupe.group(_wortlisten(sorted(test)), threshold=CLUSTER_THRESHOLD)
    return {
        "test_seiten": len(test),
        "cluster": len(cluster),
        "abgedeckt": sum(1 for g in cluster if set(g) & freigegeben),
    }
