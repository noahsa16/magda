"""Erstellt die lesbare Zusammenfassung aus eingefrorenen Auswertungsdateien."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASTRA = ROOT / "data/eval/codex_astra_score_2026-09-25.json"
QWEN = ROOT / "data/eval/runtime_thl_qwen3.8-27b_score_2026-09-24.json"
OUTPUT = ROOT / "reports/astra_codex_benchmark_2026-09-25.md"


def main() -> None:
    astra = json.loads(ASTRA.read_text())
    qwen = json.loads(QWEN.read_text())
    if astra["study_sha256"] != qwen["study_sha256"]:
        raise SystemExit("Vergleiche verwenden unterschiedliche Studienreferenzen")
    if astra["protocol"] != qwen["protocol"]:
        raise SystemExit("Vergleiche verwenden unterschiedliche Bewertungsprotokolle")
    source = ROOT / "data/eval/codex_astra_2026-09-25.json"
    if hashlib.sha256(source.read_bytes()).hexdigest() != astra["runtime_sha256"]:
        raise SystemExit("Astra-Antworten wurden seit der Bewertung verändert")
    local = astra["paired_with_local"]["systems"]["local_pipeline"]
    matched, predicted, reference = map(int, local["counts"])
    systems = [
        ("Magda", {"matched": matched, "system": predicted,
                   "precision": matched / predicted, "recall": matched / reference,
                   "f1": local["f1"]}),
        ("Qwen3.8-27B, TH Lübeck API", qwen["counts"]),
        ("GPT-6 Astra, Codex, high reasoning", astra["counts"]),
    ]
    lines = [
        "# Ergänzender GPT-6-Astra-Vergleich, 25. September 2026",
        "",
        f"Bewertet wurden dieselben {astra['counts']['pages']} Seiten gegen "
        f"{reference} menschlich annotierte Referenzdatensätze. Ein Treffer betrifft "
        "Produktname und regulären Preis, nicht die vollständige Richtigkeit aller Angebotsfelder.",
        "",
        "| System | Bewertete Ausgaben | Referenztreffer | Precision | Recall | F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, counts in systems:
        lines.append(f"| {name} | {counts['system']} | {counts['matched']} | "
                     f"{counts['precision']:.4f} | {counts['recall']:.4f} | {counts['f1']:.4f} |")
    comparison = astra["paired_with_local"]["comparisons"][0]
    lower, upper = comparison["ci95"]
    astra_counts = astra["counts"]
    qwen_counts = qwen["counts"]
    lines.extend([
        "",
        "## Einordnung",
        "",
        f"Astra findet {astra_counts['matched'] - matched} mehr Referenzdatensätze als Magda. "
        f"Gegenüber Qwen beträgt der Unterschied {astra_counts['matched'] - qwen_counts['matched']} Referenztreffer "
        f"bei {qwen_counts['system'] - astra_counts['system']} weniger bewerteten Ausgaben. "
        "Der höhere F1-Punktwert gegenüber Qwen entsteht damit vor allem durch höhere Precision.",
        "",
        f"{astra_counts['only_system']} Astra-Ausgaben lassen sich nach dem festen "
        f"Bewertungskriterium keinem Referenzdatensatz zuordnen. Bei Qwen sind es "
        f"{qwen_counts['only_system']}. Das macht diese Ausgaben nicht automatisch "
        "inhaltlich falsch oder zu Dubletten. Referenzfehler, unterschiedliche Angebotsgrenzen "
        "und abweichende Namen können ebenfalls zu fehlenden Treffern führen.",
        "",
        f"Die F1-Differenz Astra minus Magda beträgt {comparison['difference']:+.4f}. "
        f"Das gepaarte 95-%-Bootstrap-Intervall beträgt [{lower:+.4f}, {upper:+.4f}]. "
        "Es enthält null. Der numerische Vorsprung belegt daher in diesem Vergleich "
        "weder eine verlässliche Überlegenheit noch Gleichwertigkeit. Für Astra gegen Qwen "
        "wurde hier kein weiterer gepaarter Test durchgeführt.",
        "",
        "## Ablauf und Grenzen",
        "",
        "- Eine frische projektlose Codex-Aufgabe wurde explizit mit `gpt-6-astra` und "
        "Reasoning `high` gestartet. Die bisherige Unterhaltung wurde nicht übernommen.",
        "- Bereitgestellt wurden bytegleiche Seitenbilder und der bisherige Extraktionsprompt "
        "in Version 1. Die zusätzliche Anweisung zum Lesen und Speichern ist in `launch.json` dokumentiert.",
        "- Die Aufgabe verarbeitete alle Seiten in einem gemeinsamen Gesprächskontext und "
        "verwendete Bildanzeige und Dateischreibwerkzeuge. Das unterscheidet sich von den "
        "separaten API-Anfragen an Qwen. Die Ergebnisse sind ein ergänzender Codex-Vergleich.",
        "- Laut Abschlussmeldung wurden keine gespeicherten Vorhersagen nachträglich "
        "überarbeitet oder überschrieben. Die Aufgabe erhielt keine Referenzantworten "
        "und war angewiesen, keine anderen Projektdateien oder externen Dienste zu verwenden.",
        f"- Alle {astra['counts']['pages']} Dateien waren lesbar und entsprachen dem "
        f"verlangten JSON-Feldschema. Gespeichert wurden {astra['raw_records']} Datensätze "
        f"mit {astra['unscored_fragments']} unbewerteten Fragmenten und "
        f"{len(astra['failed_pages'])} technischen Seitenausfällen.",
        "- Die Aufgabe meldete, dass Kategorieaktionen mit ausschließlich prozentualem "
        "Rabatt ohne konkreten Zahlenpreis ausgelassen wurden. Solche Aktionen erfüllen "
        "auch nicht das hier verwendete Kriterium eines Datensatzes mit Name und regulärem Preis.",
        "- Alle Antworten wurden vor der Bewertung mit SHA-256-Prüfsummen gesichert. "
        "Das bestehende Auswertungsskript wurde lediglich um einen frei wählbaren Systemnamen "
        "erweitert. Die bisherige Qwen-Auswertung wurde damit unverändert reproduziert.",
        "- Der gepaarte Vergleich verwendet die vorhandenen Seitencluster, "
        f"{astra['paired_with_local']['resamples']} Bootstrap-Ziehungen und Seed "
        f"{astra['paired_with_local']['seed']}. Er berücksichtigt weder die Streuung zwischen "
        "erneuten Modellläufen noch mögliche Kontexteffekte zwischen Seiten und korrigiert "
        "keine Fehler der Referenz.",
        "- Bekannte Annotationsfehler und die frühere Inspektion von Testseiten bleiben "
        "Einschränkungen. API-Laufzeit oder API-Kosten lassen sich aus diesem Codex-Lauf nicht ableiten.",
        "",
        "## Artefakte und Reproduktion",
        "",
        "- Eingabemanifest, Arbeitsanweisung, Abschlussmeldung und Originalantworten: "
        "`output/benchmarks/astra-codex-2026-09-25/`.",
        "- Eingefrorene Antworten: `data/eval/codex_astra_2026-09-25.json`.",
        "- Auswertung: `data/eval/codex_astra_score_2026-09-25.json`.",
        "- Codex-Aufgabe: `01a0d8ec-3749-7d73-83f1-9d3c8b0242f7`.",
        "",
        "```sh",
        ".venv/bin/python scripts/score_runtime_offers.py data/eval/codex_astra_2026-09-25.json "
        "--system-name astra_codex --output data/eval/codex_astra_score_2026-09-25.json",
        ".venv/bin/python scripts/summarize_astra_benchmark.py",
        "```",
        "",
        "Die Bewertung ist aus den gespeicherten Antworten reproduzierbar. Eine bitgleiche "
        "erneute Modellausgabe wird nicht behauptet.",
    ])
    OUTPUT.write_text("\n".join(lines) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
