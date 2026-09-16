"""Fasst gespeicherte Vergleichsläufe mit derselben Referenz zusammen.

Die Tabelle stammt aus den Reports; die Treffer werden mit dem unveränderten
Matching nachgerechnet. Unterschiede der Eingaben dürfen keine gemeinsame
Rangliste ergeben. Geschrieben wird nur auf stdout.
"""

import argparse
import json
from pathlib import Path

from magda import blackbox_eval, config, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--inputs", required=True, type=Path)
    args = parser.parse_args()
    inputs = json.loads(args.inputs.read_text())
    reports = [(path, json.loads(path.read_text())) for path in args.reports]
    baseline = reports[0][1]
    page_ids = baseline["pages"]
    assert baseline["evaluation_version"] == blackbox_eval.EVALUATION_VERSION
    assert inputs["ready_pages"] == inputs["requested_pages"] == len(page_ids)
    assert {row["page_id"] for row in inputs["pages"]} == set(page_ids)
    for row in inputs["pages"]:
        for prefix, directory in (("spans", config.GOLD_DIR), ("groups", config.GOLD_DIR / "offers")):
            assert row[f"{prefix}_sha256"] == provenance.file_digest(directory / f"{row['page_id']}.json")

    rows = [("LayoutXLM + Paarmodell", baseline["comparisons"]["eigene_vs_referenz"], 0)]
    keys = ("pages", "requested_pages", "evaluation_version", "matching_fields", "name_similarity",
            "price_tolerance", "reference_sha256", "prediction_sha256", "checkpoint_sha256",
            "code", "own_deals", "reference_deals")
    for path, report in reports:
        assert all(report[key] == baseline[key] for key in keys), path
        assert report["pages"] == report["requested_pages"] and not report["gold_missing"]
        assert report["reference_groups"] == "gold" and report["reference_is_llm"] is False
        assert report["seconds"]["blackbox"] is None
        assert report["replay_sha256"] == provenance.file_digest(Path(report["blackbox_from"]))
        assert report["reference_sha256"] == provenance.digest(report["reference_deals"])
        blackbox = {page_id: [deal for deal in deals if deal.get("name") and deal.get("price") is not None]
                    for page_id, deals in report["blackbox_deals"].items()}
        for key, system in (("eigene_vs_referenz", report["own_deals"]), ("blackbox_vs_referenz", blackbox)):
            counts = blackbox_eval.compare_pages({
                page_id: (system.get(page_id, []), report["reference_deals"][page_id])
                for page_id in page_ids
            })
            assert counts == report["comparisons"][key], (path, key)
        failures = len(set(page_ids) - set(report["blackbox_deals"]))
        rows.append((report["model"], report["comparisons"]["blackbox_vs_referenz"], failures))

    print("# Vorläufiger Blackbox-Vergleich gegen die Goldreferenz\n")
    print("**Status: explorativ.** Vollständigkeit, Dateihashes und Nachrechnung der Scores "
          "sind geprüft. Die fachliche Qualität der Referenz ist noch nicht ausreichend "
          "abgesichert; bei der Nachprüfung wurden Unstimmigkeiten in den Entity-Labels "
          "gefunden. Die Tabelle eignet sich derzeit nicht für eine abschließende Aussage "
          "über die Überlegenheit oder Gleichwertigkeit der Systeme.\n")
    print(f"Vollständige Vergleichsliste: **{len(page_ids)} Seiten**, "
          f"**{rows[0][1]['reference']} auswertbare Referenzeinträge**. "
          f"Protokoll: `{baseline['evaluation_version']}`.\n")
    print("| System | Treffer | Ausgaben | Precision | Recall | F1 | Seiten ohne Antwort |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for name, score, failures in sorted(rows, key=lambda row: row[1]["f1"], reverse=True):
        print(f"| {name} | {score['matched']} | {score['system']} | {score['precision']:.4f} "
              f"| {score['recall']:.4f} | {score['f1']:.4f} | {failures}/{len(page_ids)} |")

    print("\n## Was diese Zahlen bedeuten\n")
    print("Ein Treffer verlangt denselben Aktionspreis und die festgelegte Namensähnlichkeit "
          f"von mindestens {baseline['name_similarity']}. Je Preisvariante entsteht ein Eintrag. "
          "Altpreis, App-Preis, Menge, Grundpreis, Rabatt und Gültigkeit gehören nicht zum Haupt-F1.\n")
    print(f"{baseline['reference_fragments']} Referenzgruppen und {baseline['own_fragments']} "
          "Gruppen der eigenen Pipeline konnten nicht auf Name und Aktionspreis abgebildet werden "
          "und sind separat als Fragmente ausgewiesen. Der Score bewertet damit keine "
          "vollständig korrekten Datensätze über alle Felder.\n")
    print("Die Blackbox-Antworten wurden ohne erneute API-Aufrufe wiederverwendet. Fehlgeschlagene "
          "Seiten aus den ursprünglichen Läufen bleiben mit leerer Ausgabe im Vergleich; keine "
          "Seite wurde wegen eines Blackbox-Fehlers aus der Referenz entfernt.\n")
    print("Es sind Punktschätzungen ohne berechnetes Konfidenzintervall. Eine Rangfolge beweist "
          "keinen statistisch gesicherten Unterschied. Die Testseiten wurden schon in früheren "
          "Vergleichen betrachtet; dies ist eine Neubewertung gegen die neue Referenz. "
          "Modelle, Schwellen und Seitenliste wurden für diesen Lauf nicht geändert.\n")
    print("Replay liefert keine neue Blackbox-Laufzeit. Die gespeicherte eigene Zeit umfasst nur "
          "die Gruppierung. Daraus wird kein Ende-zu-Ende-Speedup abgeleitet. Die historischen "
          "v1-Ergebnisse sind wegen des anderen Bewertungsprotokolls nicht direkt vergleichbar.\n")

    print("## Herkunft und Abschluss der Referenz\n")
    print("Handspans und vorhandene Handgruppen stammen aus der Abgabe `origin/gold` "
          "bei `c606a17`, einschließlich der dort bereits vorgenommenen Span-Normalisierung "
          "durch `scripts/merge_gold_spans.py`.\n")
    print("Die Gruppierung von `1364390_p3` wurde KI-gestützt ergänzt und anschließend von Noah "
          "im Annotator geprüft und ausdrücklich bestätigt. Der versehentlich abgetrennte "
          "Salatname wurde auf seine Bestätigung wieder mit dem Preis verbunden. Die Gruppierung "
          "ist menschlich geprüft und wurde mit KI-Unterstützung erstellt. Diese Prüfung "
          "belegt keine vollständige Prüfung der bestehenden Entity-Labels.\n")
    print("Für `1364390_p15` und `1364390_p23` wurden leere Gruppen aus den fertig bestätigten "
          "leeren Handspans abgeleitet. Die Seitenbilder zeigen reine Werbung. Bei `1364390_p25` "
          "und `1364420_p8` wurden die offenen Abschlussmarkierungen auf Grundlage von Noahs "
          "Angabe zum fertigen Annotationsstand gesetzt; deren Gruppeninhalte blieben unverändert.\n")
    print(f"Dateihashes und Herkunft je Seite: [{args.inputs.name}](../{args.inputs.as_posix()}). "
          "Der alte Vorprüfungsbericht beschreibt den Stand vor diesen Abschlüssen.\n")

    print("## Reproduzieren\n\n```bash")
    for _, report in reports:
        print(".venv/bin/magda blackbox-eval --pages data/eval/test_cluster_pages.txt \\")
        print("  --reference-groups gold --predictions layoutxlm --grouper pair-model \\")
        print(f"  --blackbox-from {report['blackbox_from']}")
    print("```\n")
    print("Die Tabellenwerte werden aus den folgenden Reports geladen und mit "
          "`scripts/summarize_blackbox_gold.py` nachgerechnet:\n")
    for path, _ in reports:
        print(f"- [{path.name}](../{path.as_posix()})")
    print("\n```bash\n.venv/bin/python scripts/summarize_blackbox_gold.py \\")
    print(f"  --inputs {args.inputs.as_posix()} \\")
    for index, (path, _) in enumerate(reports):
        suffix = " \\" if index < len(reports) - 1 else ""
        print(f"  {path.as_posix()}{suffix}")
    print("```\n")
    print(f"Code-Commit: `{baseline['code']['git_revision']}`. "
          f"Paarmodell-SHA256: `{baseline['checkpoint_sha256']}`.")


if __name__ == "__main__":
    main()
