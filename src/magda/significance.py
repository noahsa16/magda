"""Unsicherheit und Modellvergleich – über Cluster, nicht über Seiten.

Der Testsatz hat 100 Seiten, aber nur 43 Duplikat-Cluster (Jaccard 0.7, größter
Cluster 11 Seiten): Penny gibt je Woche 44 fast gleiche Regionalausgaben
heraus. Ein Bootstrap über *Seiten* täte so, als wären die 11 Kopien einer
Vorlage elf unabhängige Beobachtungen, und meldete ein zu enges Intervall. Die
unabhängige Einheit ist der Cluster.

Micro-F1 wird nicht je Resample neu von seqeval berechnet, sondern aus
vorberechneten TP/FP/FN je Cluster aufaddiert. Das ist exakt dasselbe Ergebnis
und macht 10 000 Resamples zur Sache von Sekunden statt Minuten.

Für den Vergleich zweier Modelle zählt nur der *gepaarte* Bootstrap: beide
Modelle werden auf denselben gezogenen Clustern ausgewertet. Zwei getrennte
Intervalle zu vergleichen wäre der klassische Fehler – sie können sich
überlappen, während die Differenz trotzdem verlässlich von null verschieden
ist, weil beide Modelle auf denselben Seiten schwach sind.
"""

import random
from collections import Counter

from magda.labels import bio_to_spans


def counts_per_page(reference: list[list[str]], predicted: list[list[str]]) -> list[tuple]:
    """(TP, FP, FN) je Seite auf Entity-Ebene – Span *und* Typ müssen stimmen."""
    result = []
    for ref_tags, pred_tags in zip(reference, predicted):
        ref = Counter(
            (s["label"], s["start"], s["end"]) for s in bio_to_spans(ref_tags)
        )
        pred = Counter(
            (s["label"], s["start"], s["end"]) for s in bio_to_spans(pred_tags)
        )
        tp = sum((ref & pred).values())
        result.append((tp, sum(pred.values()) - tp, sum(ref.values()) - tp))
    return result


def f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    return 2 * precision * recall / (precision + recall)


def _by_cluster(counts: list[tuple], clusters: list[list[int]]) -> list[tuple]:
    """Faltet die Seitenzahlen auf die Clusterebene."""
    grouped = []
    for cluster in clusters:
        tp = sum(counts[i][0] for i in cluster)
        fp = sum(counts[i][1] for i in cluster)
        fn = sum(counts[i][2] for i in cluster)
        grouped.append((tp, fp, fn))
    return grouped


def bootstrap_f1(
    reference: list[list[str]],
    predicted: list[list[str]],
    clusters: list[list[int]],
    resamples: int = 10000,
    seed: int = 42,
) -> dict:
    """Micro-F1 mit 95-%-Perzentilintervall über Cluster-Resampling."""
    per_cluster = _by_cluster(counts_per_page(reference, predicted), clusters)
    total = tuple(sum(x) for x in zip(*per_cluster))
    point = f1(*total)

    rng = random.Random(seed)
    n = len(per_cluster)
    scores = []
    for _ in range(resamples):
        tp = fp = fn = 0
        for _ in range(n):
            a, b, c = per_cluster[rng.randrange(n)]
            tp += a
            fp += b
            fn += c
        scores.append(f1(tp, fp, fn))
    scores.sort()

    return {
        "f1": round(point, 4),
        "ci95": [
            round(scores[int(0.025 * resamples)], 4),
            round(scores[int(0.975 * resamples)], 4),
        ],
        "clusters": n,
        "pages": sum(len(c) for c in clusters),
        "resamples": resamples,
    }


def paired_bootstrap(
    reference: list[list[str]],
    predicted_a: list[list[str]],
    predicted_b: list[list[str]],
    clusters: list[list[int]],
    resamples: int = 10000,
    seed: int = 42,
) -> dict:
    """Differenz A − B mit Intervall und zweiseitigem Bootstrap-p-Wert.

    Beide Modelle sehen in jedem Resample dieselben Cluster. Der p-Wert ist der
    Anteil der Resamples, in denen die Differenz das Vorzeichen wechselt (auf
    die Null zentriert) – überlappt das Intervall die Null, ist der Unterschied
    mit diesen Daten nicht belegbar. Das ist dann ein Befund, kein Versäumnis.
    """
    counts_a = _by_cluster(counts_per_page(reference, predicted_a), clusters)
    counts_b = _by_cluster(counts_per_page(reference, predicted_b), clusters)

    observed = f1(*[sum(x) for x in zip(*counts_a)]) - f1(*[sum(x) for x in zip(*counts_b)])

    rng = random.Random(seed)
    n = len(clusters)
    differences = []
    for _ in range(resamples):
        indices = [rng.randrange(n) for _ in range(n)]
        a = [sum(counts_a[i][k] for i in indices) for k in range(3)]
        b = [sum(counts_b[i][k] for i in indices) for k in range(3)]
        differences.append(f1(*a) - f1(*b))
    differences.sort()

    # Zweiseitig: wie oft weicht die zentrierte Differenz mindestens so weit
    # von null ab wie die beobachtete?
    extreme = sum(1 for d in differences if abs(d - observed) >= abs(observed))
    return {
        "difference": round(observed, 4),
        "ci95": [
            round(differences[int(0.025 * resamples)], 4),
            round(differences[int(0.975 * resamples)], 4),
        ],
        "p_value": round(extreme / resamples, 4),
        "significant": not (
            differences[int(0.025 * resamples)] <= 0 <= differences[int(0.975 * resamples)]
        ),
        "clusters": n,
    }
