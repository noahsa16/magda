"""Gepaarte Cluster-Intervalle aus unveränderten, additiven Trefferzahlen.

Die Einheit ist eine Prospektvorlage. Innerhalb jedes Resamples werden die
Zähler summiert und erst danach Micro-F1 berechnet. Leere Stichproben sind
undefiniert; sie werden ausgewiesen und nicht als perfekte Treffer gezählt.
"""

import numpy as np


def _f1(counts):
    denominator = counts[..., 1] + counts[..., 2]
    return np.divide(2 * counts[..., 0], denominator,
                     out=np.full(denominator.shape, np.nan), where=denominator != 0)


def _interval(values, alpha):
    valid = values[np.isfinite(values)]
    if not len(valid):
        return None
    return np.quantile(valid, [alpha / 2, 1 - alpha / 2]).tolist()


def compare_counts(systems, clusters, pairs=(), *, resamples=10000, seed=42):
    """Marginale und Bonferroni-Intervalle; kein Gleichwertigkeitstest.

Alle Systeme erhalten dieselben Ziehungen. Bonferroni bezieht sich auf die
explizit angegebene Vergleichsfamilie, nicht auf nachträglich gewählte Sieger.
"""
    if not systems or resamples < 100:
        raise ValueError("Systeme und mindestens 100 Resamples werden benötigt.")
    size = len(next(iter(systems.values())))
    indices = [i for cluster in clusters for i in cluster]
    if not size or any(not cluster for cluster in clusters) or sorted(indices) != list(range(size)):
        raise ValueError("Cluster müssen jede Seite genau einmal enthalten.")
    arrays = {}
    for name, counts in systems.items():
        array = np.asarray(counts, dtype=float)
        if (array.shape != (size, 3) or not np.isfinite(array).all()
                or (array < 0).any() or (array[:, 0] > array[:, 1:3].min(axis=1)).any()):
            raise ValueError(f"Ungültige Trefferzahlen: {name}")
        arrays[name] = np.array([array[cluster].sum(axis=0) for cluster in clusters])
    pairs = list(pairs)
    if len(set(pairs)) != len(pairs) or any(a not in arrays or b not in arrays or a == b for a, b in pairs):
        raise ValueError("Ungültige Vergleichsfamilie.")
    count = len(clusters)
    weights = np.random.default_rng(seed).multinomial(count, [1 / count] * count, size=resamples)
    scores, points, summary = {}, {}, {}
    for name, array in arrays.items():
        scores[name] = _f1(weights @ array)
        point = float(_f1(array.sum(axis=0)))
        points[name] = point
        summary[name] = {
            "f1": point if np.isfinite(point) else None,
            "ci95": _interval(scores[name], 0.05) if count > 1 else None,
            "undefined_resamples": int((~np.isfinite(scores[name])).sum()),
            "counts": array.sum(axis=0).tolist(),
        }
    differences = []
    for a, b in pairs:
        draws = scores[a] - scores[b]
        point = points[a] - points[b]
        differences.append({
            "a": a, "b": b, "direction": "a_minus_b",
            "difference": point if np.isfinite(point) else None,
            "ci95": _interval(draws, 0.05) if count > 1 else None,
            "ci_familywise": _interval(draws, 0.05 / len(pairs)) if count > 1 else None,
            "undefined_resamples": int((~np.isfinite(draws)).sum()),
        })
    return {
        "method": "paired-cluster-percentile-bootstrap", "seed": seed,
        "resamples": resamples, "clusters": clusters, "num_clusters": count,
        "pages": size, "family_size": len(pairs), "familywise_method": "Bonferroni",
        "systems": summary, "comparisons": differences,
        "scope": "Stichprobenunsicherheit bei festen Modellen und fester Referenz; keine Seed-Streuung.",
    }
