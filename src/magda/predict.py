"""Modellausgabe je Seite: Wort, Koordinate, Label – die Übergabe an Phase 4.

Das Projektziel endet nicht beim F1. Aus getaggten Wörtern muss am Ende ein
strukturiertes Angebot werden ("Rinderhack, 400 g, 3.99, statt 4.99"), und
diesen Schritt baut jemand anders auf dieser Datei auf. Deshalb schreibt der
Export mehr als die reine Tag-Folge:

- **Koordinaten je Wort und je Entity.** Ein Angebot ist ein räumlicher
  Block auf der Seite, kein Textabschnitt. Ohne Boxen müsste die
  Gruppierung über die Wortreihenfolge raten, und die läuft in einem
  mehrspaltigen Prospekt quer durch fremde Anzeigen.
- **Konfidenz je Wort.** Erlaubt der nächsten Stufe, unsichere Entities zu
  verwerfen, statt jede Vorhersage gleich ernst zu nehmen.
- **`label: null` statt `"O"` für abgeschnittene Wörter.** Seiten über 512
  Subwords werden truncated; für die hinteren Wörter hat das Modell gar
  nichts gesagt. Als "O" ausgegeben sähe das aus wie eine Entscheidung
  gegen ein Entity und würde still Angebote verschlucken.
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np

from magda.labels import bio_to_spans, id2label


# Überlappung zweier benachbarter Fenster in Subwords. Ein Wort am Rand eines
# Fensters sieht nur die halbe Umgebung; mit 128 Subwords Überlappung liegt es
# im Nachbarfenster tief im Kontext, und `merge_windows` nimmt dort die
# Vorhersage her.
WINDOW_STRIDE = 128


def merge_windows(
    window_logits: list[np.ndarray],
    window_word_ids: list[list[int | None]],
    num_words: int,
) -> tuple[list[str | None], list[float | None]]:
    """Führt die Vorhersagen überlappender Fenster zu einer Seite zusammen.

    Ein Wort kann in zwei Fenstern liegen. Maßgeblich ist das Fenster, in dem
    es am weitesten von beiden Rändern entfernt sitzt: dort hat das Modell den
    meisten Kontext nach links *und* rechts gesehen. Die Konfidenz zu
    vergleichen wäre die schlechtere Regel – ein Modell ist am Rand oft
    zuversichtlich und trotzdem falsch, weil ihm die halbe Anzeige fehlt.
    """
    tags: list[str | None] = [None] * num_words
    scores: list[float | None] = [None] * num_words
    margins: list[int] = [-1] * num_words

    # Wie viele Fenster decken ein Wort ab? Nötig für den Guard unten: das
    # erste Wort eines Folgefensters darf nur dann verworfen werden, wenn es
    # anderswo noch vorkommt.
    coverage = [0] * num_words
    for word_ids in window_word_ids:
        for w in set(w for w in word_ids if w is not None):
            if w < num_words:
                coverage[w] += 1

    for window_nr, (logits, word_ids) in enumerate(zip(window_logits, window_word_ids)):
        covered = [w for w in word_ids if w is not None]
        if not covered:
            continue
        low, high = min(covered), max(covered)
        window_tags, window_scores = word_predictions(logits, word_ids, num_words)
        for i, tag in enumerate(window_tags):
            if tag is None:
                continue
            # Fenstergrenzen liegen auf Subwords, nicht auf Wörtern: das erste
            # Wort eines Folgefensters beginnt dort womöglich mitten drin, und
            # was `word_predictions` für sein "erstes" Subword hält, war im
            # Training mit -100 maskiert. Solange ein anderes Fenster das Wort
            # ganz sieht, ist dessen Vorhersage die definierte.
            if i == low and window_nr > 0 and coverage[i] > 1:
                continue
            margin = min(i - low, high - i)
            if margin > margins[i]:
                margins[i] = margin
                tags[i] = tag
                scores[i] = window_scores[i]
    return tags, scores


def bounding_box(boxes: list[list[float]]) -> list[float]:
    """Kleinste Box, die alle Wörter einer Entity umschließt."""
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def word_predictions(
    logits: np.ndarray, word_ids: list[int | None], num_words: int
) -> tuple[list[str | None], list[float | None]]:
    """Faltet Subword-Vorhersagen auf Wortebene zurück.

    Maßgeblich ist das *erste* Subword eines Wortes – dieselbe Konvention, mit
    der `alignment.align_word_labels` die Labels hinlegt. Ein Wort, das der
    Tokenizer abgeschnitten hat, bleibt None.
    """
    tags: list[str | None] = [None] * num_words
    scores: list[float | None] = [None] * num_words

    exp = np.exp(logits - logits.max(axis=-1, keepdims=True))
    probs = exp / exp.sum(axis=-1, keepdims=True)

    previous = None
    for position, word_id in enumerate(word_ids):
        if word_id is not None and word_id != previous and word_id < num_words:
            best = int(probs[position].argmax())
            tags[word_id] = id2label[best]
            scores[word_id] = round(float(probs[position][best]), 4)
        previous = word_id
    return tags, scores


def page_output(page: dict, tags, scores, variant: str, labels_from: str) -> dict:
    """Baut die JSON-Struktur einer Seite zusammen."""
    words = page["words"]
    predicted = [i for i, t in enumerate(tags) if t is not None]

    # bio_to_spans kennt kein None; abgeschnittene Wörter beenden eine Entity,
    # statt sie stillschweigend über die Lücke hinweg fortzusetzen.
    spans = bio_to_spans([t if t is not None else "O" for t in tags])

    entities = []
    for span in spans:
        indices = list(range(span["start"], span["end"]))
        confidences = [scores[i] for i in indices if scores[i] is not None]
        entities.append(
            {
                "label": span["label"],
                "start": span["start"],
                "end": span["end"],
                "text": " ".join(words[i]["text"] for i in indices),
                "bbox": bounding_box([words[i]["bbox"] for i in indices]),
                "confidence": round(sum(confidences) / len(confidences), 4)
                if confidences
                else None,
            }
        )

    catalog_id, _, page_number = page["page_id"].rpartition("_p")
    return {
        "page_id": page["page_id"],
        "catalog_id": catalog_id,
        "page": int(page_number) if page_number.isdigit() else None,
        "width": page["width"],
        "height": page["height"],
        "model": variant,
        "labels_from": labels_from,
        "created": datetime.now().isoformat(timespec="seconds"),
        "num_words": len(words),
        "num_words_predicted": len(predicted),
        "truncated": len(predicted) < len(words),
        "words": [
            {
                "i": i,
                "text": w["text"],
                "bbox": w["bbox"],
                "label": tags[i],
                "confidence": scores[i],
            }
            for i, w in enumerate(words)
        ],
        "entities": entities,
    }


def load_ner_model(variant: str, checkpoint: str | None = None):
    """Laedt Tokenizer und Modell einer Variante aus checkpoints/<name>/best.

    Eine Stelle fuer `magda predict` und `magda.pipeline.load_models` – beide
    sollen bei einem fehlenden Checkpoint dieselbe Meldung sehen, nicht zwei
    Formulierungen, die auseinanderlaufen. Importe bleiben in der Funktion:
    ein blosses `import magda.predict` soll kein transformers ziehen.
    """
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    from magda.config import CHECKPOINTS_DIR, variant_spec

    spec = variant_spec(variant)
    model_dir = CHECKPOINTS_DIR / (checkpoint or variant) / "best"
    if not model_dir.exists():
        raise FileNotFoundError(
            f"Kein trainiertes Modell unter {model_dir}. Erst `magda train` laufen lassen."
        )
    tokenizer = AutoTokenizer.from_pretrained(spec.model_name)
    model = AutoModelForTokenClassification.from_pretrained(model_dir)
    return model, tokenizer, spec


def predict_pages(
    pages: list[dict], model, tokenizer, spec, *, no_windows: bool = False, images_dir=None,
    on_windows_built=None,
) -> list[tuple[list[str | None], list[float | None]]]:
    """Sagt BIO-Tags und Konfidenzen fuer eine Liste Seiten voraus.

    Die Inferenzschleife von `magda predict` an einer Stelle, damit
    `magda.pipeline.extract_offers` exakt dieselbe Vorhersage bekommt wie ein
    Lauf über `data/predictions/` – dieselben Fenster, dieselbe Merge-Regel.
    `images_dir` reicht nur für LayoutXLM (`spec.image`) an `WindowDataset`
    durch; ohne Angabe bleibt es beim bisherigen `config.IMAGES_DIR`.
    `on_windows_built(len(ds))` erlaubt `cli/predict.py` die frühere
    Fortschrittszeile ("N Fenster über M Seiten") weiterzugeben, ohne das
    Fenster-Dataset dafür ein zweites Mal zu bauen.
    """
    from transformers import Trainer

    from magda.config import MAX_SEQ_LENGTH
    from magda.dataset import dataset_for
    from magda.windows import WindowDataset

    if no_windows:
        ds = dataset_for(spec, pages, tokenizer, MAX_SEQ_LENGTH)
    else:
        ds = WindowDataset(pages, tokenizer, MAX_SEQ_LENGTH, WINDOW_STRIDE, spec,
                           images_dir=images_dir)
        if on_windows_built is not None:
            on_windows_built(len(ds))

    logits = Trainer(model=model).predict(ds).predictions
    if isinstance(logits, tuple):
        logits = logits[0]
    logits = np.asarray(logits)

    results = []
    for i, page in enumerate(pages):
        if no_windows:
            results.append(word_predictions(logits[i], ds.word_ids[i], len(page["words"])))
        else:
            windows = ds.windows_of(i)
            results.append(
                merge_windows(
                    [logits[w] for w in windows],
                    [ds.word_ids[w] for w in windows],
                    len(page["words"]),
                )
            )
    return results


def write_pages(outputs: list[dict], target: Path) -> dict:
    """Schreibt je Seite eine Datei plus einen Index über den ganzen Lauf."""
    target.mkdir(parents=True, exist_ok=True)
    for out in outputs:
        with open(target / f"{out['page_id']}.json", "w") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    per_label: dict[str, int] = {}
    for out in outputs:
        for entity in out["entities"]:
            per_label[entity["label"]] = per_label.get(entity["label"], 0) + 1

    index = {
        "model": outputs[0]["model"] if outputs else None,
        "labels_from": outputs[0]["labels_from"] if outputs else None,
        "created": datetime.now().isoformat(timespec="seconds"),
        "num_pages": len(outputs),
        "num_words": sum(o["num_words"] for o in outputs),
        "num_entities": sum(len(o["entities"]) for o in outputs),
        "entities_per_label": dict(sorted(per_label.items())),
        "truncated_pages": sorted(o["page_id"] for o in outputs if o["truncated"]),
        "catalogs": sorted({o["catalog_id"] for o in outputs}),
        "pages": sorted(o["page_id"] for o in outputs),
    }
    with open(target / "index.json", "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    return index
