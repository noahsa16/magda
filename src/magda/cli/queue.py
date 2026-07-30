"""Welche Gold-Seiten als Nächstes von Hand durchzusehen sind.

Aufruf:
    magda queue                                  # die nächsten 30
    magda queue --limit 10
    magda queue --models sonnet-5 qwen3.5-397b-a17b   # andere Modellpaarung

Ausgegeben wird eine Seite je Duplikat-Cluster, Testseiten zuerst, darin die
uneinigsten. Die Links führen direkt in den Annotator.
"""

import argparse
import sys

from magda import config, review

ANNOTATOR = "http://localhost:5173/annotate?page="


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=30,
                        help="wie viele Seiten vorschlagen (Vorgabe 30)")
    parser.add_argument("--models", nargs=2, metavar=("A", "B"),
                        help="Modellpaar für die Uneinigkeit; ohne Angabe die "
                             "zwei vollständigsten Labelordner")
    parser.add_argument("--ids-only", action="store_true",
                        help="nur die page_id je Zeile, für Skripte")
    args = parser.parse_args(argv)

    model_a, model_b = args.models if args.models else review.default_pair()

    vorschlaege = review.queue(model_a, model_b, args.limit)
    if not vorschlaege:
        sys.exit("Nichts offen – alle Gold-Seiten sind freigegeben.")

    if args.ids_only:
        print("\n".join(v["page_id"] for v in vorschlaege))
        return

    deckung = review.abdeckung()
    if model_a and model_b:
        print(f"Uneinigkeit gemessen zwischen {model_a} und {model_b}.")
    else:
        print("Nur ein Labelordner vorhanden – ohne Uneinigkeitsmass sortiert.")
    print(
        f"Test-Split: {deckung['abgedeckt']} von {deckung['cluster']} Clustern "
        f"abgedeckt ({deckung['test_seiten']} Seiten).\n"
    )

    print(f"{'#':>3}  {'Seite':<16} {'Split':<6} {'uneinig':>8}  Cluster")
    print("-" * 58)
    for rang, v in enumerate(vorschlaege, 1):
        weitere = len(v["represents"])
        cluster = "einzeln" if weitere == 0 else f"+{weitere} gleiche"
        print(
            f"{rang:>3}  {v['page_id']:<16} {v['split']:<6} "
            f"{v['disagreement']:>7.1%}  {cluster}"
        )

    print(f"\nZum Öffnen (Frontend muss laufen: magda serve --frontend):")
    for v in vorschlaege[:5]:
        print(f"  {ANNOTATOR}{v['page_id']}")
    if len(vorschlaege) > 5:
        print(f"  … und {len(vorschlaege) - 5} weitere")

    print(
        "\nDurchsehen heisst nicht neu annotieren: Spans gegen das Bild pruefen, "
        "Falsches korrigieren, mit 'f' freigeben."
    )
