"""Exploratives Clustering von Prospektseiten.

Die Pipeline hat mit `dedupe` schon ein hartes Werkzeug fuer Beinah-Duplikate.
Dieses Modul ist weicher: Es gruppiert Seiten nach Textinhalt, damit sichtbar
wird, welche Seitentypen im Korpus stecken und ob Split oder Gold-Auswahl
inhaltlich einseitig sind.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np

from magda import dedupe

TOKEN_RE = re.compile(r"[\wÄÖÜäöüß]+(?:[-/][\wÄÖÜäöüß]+)*", re.UNICODE)

STOPWORDS = {
    "ab",
    "alle",
    "als",
    "am",
    "app",
    "auf",
    "aus",
    "bei",
    "bis",
    "der",
    "die",
    "do",
    "ein",
    "eine",
    "fuer",
    "für",
    "gueltig",
    "gültig",
    "im",
    "in",
    "je",
    "kg",
    "l",
    "mo",
    "mit",
    "nur",
    "oder",
    "penny",
    "pro",
    "sa",
    "sorten",
    "und",
    "versch",
    "von",
    "zu",
    "zzgl",
}


@dataclass(frozen=True)
class Page:
    page_id: str
    words: list[str]


def tokenize(words: list[str]) -> list[str]:
    """Normalisierte Tokens fuer Seitenvergleich und Clusterbenennung."""
    tokens: list[str] = []
    for word in dedupe.normalize(words):
        text = word.casefold().replace("\xad", "")
        for match in TOKEN_RE.finditer(text):
            token = match.group(0).strip("_")
            if len(token) < 2 or token in STOPWORDS:
                continue
            if token.replace(",", "").replace(".", "").isdigit():
                continue
            tokens.append(token)
    return tokens


def _tfidf_matrix(pages: list[Page], max_features: int) -> tuple[np.ndarray, list[str]]:
    docs = [tokenize(page.words) for page in pages]
    df = Counter(token for doc in docs for token in set(doc))
    if not df:
        return np.zeros((len(pages), 0), dtype=np.float32), []

    # Sehr seltene Tokens sind oft OCR- oder Regionrauschen; zu haeufige Tokens
    # beschreiben den Prospekt als Ganzes, nicht den Seitentyp.
    n_docs = len(docs)
    vocab = [
        token
        for token, count in df.items()
        if count >= 2 and count <= max(2, int(n_docs * 0.85))
    ]
    vocab.sort(key=lambda token: (df[token], token), reverse=True)
    vocab = sorted(vocab[:max_features])
    index = {token: i for i, token in enumerate(vocab)}

    matrix = np.zeros((len(pages), len(vocab)), dtype=np.float32)
    idf = {token: math.log((1 + n_docs) / (1 + df[token])) + 1.0 for token in vocab}
    for row, doc in enumerate(docs):
        counts = Counter(token for token in doc if token in index)
        if not counts:
            continue
        length = sum(counts.values())
        for token, count in counts.items():
            matrix[row, index[token]] = (count / length) * idf[token]

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.divide(matrix, norms, out=matrix, where=norms > 0)
    return matrix, vocab


def _initial_centroids(matrix: np.ndarray, k: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    non_empty = np.flatnonzero(np.linalg.norm(matrix, axis=1) > 0)
    if len(non_empty) < k:
        non_empty = np.arange(len(matrix))
    first = int(non_empty[rng.integers(len(non_empty))])
    chosen = [first]

    distances = np.full(len(matrix), np.inf, dtype=np.float32)
    for _ in range(1, k):
        similarity = matrix @ matrix[chosen[-1]]
        distances = np.minimum(distances, 1.0 - similarity)
        weights = np.maximum(distances, 0.0) ** 2
        total = float(weights.sum())
        if total == 0.0:
            remaining = [i for i in range(len(matrix)) if i not in chosen]
            chosen.append(remaining[0])
        else:
            chosen.append(int(rng.choice(len(matrix), p=weights / total)))
    return matrix[chosen].copy()


def kmeans(matrix: np.ndarray, k: int, seed: int = 13, iterations: int = 50) -> np.ndarray:
    """K-Means auf L2-normalisierten TF-IDF-Vektoren."""
    if len(matrix) == 0:
        return np.array([], dtype=np.int64)
    k = max(1, min(k, len(matrix)))
    if matrix.shape[1] == 0:
        return np.arange(len(matrix), dtype=np.int64) % k

    centroids = _initial_centroids(matrix, k, seed)
    labels = np.zeros(len(matrix), dtype=np.int64)
    for _ in range(iterations):
        new_labels = np.argmax(matrix @ centroids.T, axis=1)
        if np.array_equal(labels, new_labels):
            break
        labels = new_labels
        for cluster_id in range(k):
            members = matrix[labels == cluster_id]
            if len(members) == 0:
                continue
            centroid = members.mean(axis=0)
            norm = np.linalg.norm(centroid)
            centroids[cluster_id] = centroid / norm if norm > 0 else centroid
    return labels


def cluster_pages(
    pages: list[Page],
    k: int,
    max_features: int = 1200,
    seed: int = 13,
) -> dict:
    """Gruppiert Seiten und liefert JSON-faehige Cluster-Metadaten."""
    pages = sorted(pages, key=lambda page: page.page_id)
    matrix, vocab = _tfidf_matrix(pages, max_features=max_features)
    labels = kmeans(matrix, k=k, seed=seed)

    clusters = []
    for cluster_id in sorted(set(labels.tolist())):
        indices = [i for i, label in enumerate(labels) if label == cluster_id]
        centroid = matrix[indices].mean(axis=0) if len(vocab) else np.zeros(0)
        top = []
        if len(vocab):
            top_indices = np.argsort(centroid)[::-1][:12]
            top = [vocab[i] for i in top_indices if centroid[i] > 0]

        page_ids = [pages[i].page_id for i in indices]
        clusters.append(
            {
                "id": len(clusters),
                "size": len(page_ids),
                "keywords": top,
                "pages": page_ids,
            }
        )

    clusters.sort(key=lambda c: (-c["size"], c["pages"][0]))
    for i, cluster in enumerate(clusters):
        cluster["id"] = i
    return {
        "pages": len(pages),
        "k": len(clusters),
        "max_features": max_features,
        "clusters": clusters,
    }
