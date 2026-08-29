"""Traegt ein eingefrorenes Span-Embedding die Relation, die die Geometrie nicht sieht?

Eine Sonde, kein Einsatzmodell. Sie beantwortet die Vorfrage, bevor ein
Embedding-Cache und ein Merkmalsblock gebaut werden: Bringt
`[|h_i - h_j|, h_i * h_j]` aus einem der trainierten Encoder etwas, das die
35 bestehenden Merkmale nicht schon haben?

**Warum nicht gleich den Block bauen.** Der volle Weg ist teuer: 768
Dimensionen mal vier Kombinationen mal 780000 Trainingspaare sind rund
10 GB, es braucht also eine Reduktion, und die ist eine
Entwurfsentscheidung mit eigenen Freiheitsgraden. Die Sonde umgeht sie,
indem sie auf wenigen Seiten ohne Reduktion rechnet. Faellt sie negativ
aus, ist die Reduktion gegenstandslos.

**Was die Sonde nicht misst, und das gehoert zu jeder Nennung.** Es gibt
keinen Dekoder; gemessen wird Paar-F1 auf einer Schwelle, nicht
Gruppen-F1 nach ILP. Merkmale, die *trennen*, wirken aber ueber den
Dekoder auf die Gruppe und schlagen sich in Paar-F1 kaum nieder. Die
Sonde taugt deshalb fuer den Vergleich zweier Merkmalsmengen derselben
Art, nicht als Ersatz fuer `magda offers-grid`.

Gerechnet wird auf Train-Seiten, aufgeteilt nach Duplikat-Clustern. Der
Testsplit bleibt unberuehrt.
"""

from __future__ import annotations

# Wie viele Fenster auf einmal durch den Encoder gehen. Groesser ist
# schneller und kostet Speicher; 8 haelt einen 16-GB-Rechner frei.
BATCH = 8

# Schwellen, ueber die das beste Paar-F1 gesucht wird. Eine feste Schwelle
# waere hier irrefuehrend: `pos_weight` verschiebt die Wahrscheinlichkeiten,
# und die Sonde soll Merkmale vergleichen, nicht Schwellen.
THRESHOLDS = [i / 20 for i in range(1, 20)]

PROBE_EPOCHS = 400
PROBE_HIDDEN = (64, 32)


def word_vectors(window_hidden, window_word_ids, count: int):
    """Je Wort der Mittelwert seiner Subword-Vektoren, ueber alle Fenster.

    Fenster ueberlappen (Stride 128), ein Wort kann also mehrfach
    vorkommen. Gemittelt statt das erste genommen: welches Fenster ein Wort
    besser sieht, ist nicht entscheidbar, und der Mittelwert ist die
    Variante ohne willkuerliche Wahl.
    """
    import numpy as np

    total = np.zeros((count, window_hidden[0].shape[-1]), dtype="float32")
    hits = np.zeros(count, dtype="float32")
    for hidden, ids in zip(window_hidden, window_word_ids):
        for position, word in enumerate(ids):
            if word is None or word >= count:
                continue
            total[word] += hidden[position]
            hits[word] += 1
    seen = hits > 0
    total[seen] /= hits[seen][:, None]
    return total, seen


def span_vectors(pages: list[dict], arm: str, checkpoint):
    """Je Seite ein Vektor pro Entity - der Mittelwert ihrer Wortvektoren.

    Gefenstert wie in `magda predict`, nicht abgeschnitten: sonst haetten
    Entities hinter Subword 512 kein Embedding, und die Sonde vergliche
    Merkmalsmengen auf verschiedenen Paarmengen.
    """
    import numpy as np
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    from magda import config
    from magda.windows import WindowDataset

    spec = config.variant_spec(arm)
    tokenizer = AutoTokenizer.from_pretrained(spec.model_name)
    model = AutoModelForTokenClassification.from_pretrained(
        checkpoint, output_hidden_states=True)
    model.eval()

    data = WindowDataset(pages, tokenizer, config.MAX_SEQ_LENGTH, 128, spec)
    hidden_of_window = []
    with torch.no_grad():
        for start in range(0, len(data), BATCH):
            batch = [data[i] for i in range(start, min(start + BATCH, len(data)))]
            inputs = {key: torch.stack([entry[key] for entry in batch])
                      for key in batch[0] if key != "labels"}
            output = model(**inputs)
            hidden_of_window.extend(
                output.hidden_states[-1].numpy().astype("float32"))

    result = {}
    for index, page in enumerate(pages):
        vectors, seen = word_vectors(
            [hidden_of_window[w] for w in data.windows_of(index)],
            [data.word_ids[w] for w in data.windows_of(index)],
            len(page["words"]))
        result[page["page_id"]] = (vectors, seen)
    return result


def pair_rows(page: dict, assignment: dict, vectors, blocks):
    """Merkmale, Embedding-Paar und Label je trainierbarem Paar der Seite."""
    import numpy as np

    from magda import offer_pairs

    pairs = offer_pairs.page_pairs(page, assignment, blocks=blocks)
    words, seen = vectors
    spans = []
    for entity in pairs.entities:
        inside = [w for w in range(entity.start, entity.end) if seen[w]]
        spans.append(words[inside].mean(axis=0) if inside else None)

    rows = []
    for (i, j), features, label in zip(pairs.index_pairs, pairs.features,
                                       pairs.labels):
        if label is None or spans[i] is None or spans[j] is None:
            continue
        rows.append((features,
                     np.concatenate([np.abs(spans[i] - spans[j]),
                                     spans[i] * spans[j]]),
                     label))
    return rows


def roc_auc(labels, scores) -> float:
    """Flaeche unter der ROC-Kurve ueber die Rangfolge, mit Bindungsmittelung.

    Selbst gerechnet statt aus sklearn: das haengt hier nur als
    Weiterleitung von seqeval mit drin, und eine Sonde soll keine
    undeklarierte Abhaengigkeit einfuehren.
    """
    order = sorted(range(len(scores)), key=lambda k: scores[k])
    ranks = [0.0] * len(scores)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and scores[order[end + 1]] == scores[order[position]]:
            end += 1
        shared = (position + end) / 2 + 1
        for k in range(position, end + 1):
            ranks[order[k]] = shared
        position = end + 1

    positive = sum(labels)
    negative = len(labels) - positive
    if not positive or not negative:
        return float("nan")
    total = sum(rank for rank, label in zip(ranks, labels) if label)
    return (total - positive * (positive + 1) / 2) / (positive * negative)


def best_f1(labels, scores) -> tuple[float, float]:
    """Bestes Paar-F1 ueber die Schwellen, samt der Schwelle."""
    best = (0.0, THRESHOLDS[0])
    for threshold in THRESHOLDS:
        hits = sum(1 for label, score in zip(labels, scores)
                   if label and score >= threshold)
        predicted = sum(1 for score in scores if score >= threshold)
        reference = sum(labels)
        if not predicted or not reference or not hits:
            continue
        precision, recall = hits / predicted, hits / reference
        f1 = 2 * precision * recall / (precision + recall)
        if f1 > best[0]:
            best = (f1, threshold)
    return best


def fit_and_score(train_x, train_y, test_x, hidden, seed: int = 13):
    """Dasselbe Netz wie im Einsatzmodell, auf einer fremden Merkmalsmatrix.

    Standardisiert wird an den Trainingszeilen: die Embedding-Spalten
    liegen auf ganz anderen Skalen als die Merkmale, und ungewichtet
    dominierten sie das erste Gewicht allein durch ihre Groesse.
    """
    import numpy as np
    import torch
    from torch import nn

    from magda.offer_model import DROPOUT, LEARNING_RATE, _build_network  # noqa: F401

    mean = train_x.mean(axis=0)
    spread = train_x.std(axis=0)
    spread[spread == 0] = 1.0

    torch.manual_seed(seed)
    x = torch.tensor((train_x - mean) / spread, dtype=torch.float32)
    y = torch.tensor(train_y, dtype=torch.float32).unsqueeze(-1)
    positive = float(y.sum())
    weight = torch.tensor([(len(train_y) - positive) / positive]) if positive else None

    network = _build_network(train_x.shape[1], tuple(hidden))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=weight)
    optimizer = torch.optim.Adam(network.parameters(), lr=LEARNING_RATE)
    network.train()
    for _ in range(PROBE_EPOCHS):
        optimizer.zero_grad()
        loss_fn(network(x), y).backward()
        optimizer.step()

    network.eval()
    with torch.no_grad():
        scores = torch.sigmoid(network(
            torch.tensor((test_x - mean) / spread, dtype=torch.float32)))
    return np.asarray(scores).ravel()
