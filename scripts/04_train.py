"""Pipeline-Schritt 3: Token-Klassifikation trainieren.

Zwei Varianten (siehe Proposal, "Baseline Architecture"):
    python scripts/04_train.py gbert       # text-only Baseline
    python scripts/04_train.py layoutxlm   # layout-aware Modell

Beide bekommen denselben Klassifikationskopf und dieselben Labels – der
einzige Unterschied ist die Positionsinformation. Genau diesen Effekt
wollen wir messen.

Hinweis zu LayoutXLM: microsoft/layoutxlm-base baut auf LayoutLMv2 auf und
bringt einen visuellen Backbone mit, der detectron2 voraussetzt. Falls die
Installation auf unseren Rechnern zum Problem wird, wäre der Plan B ein
Wechsel auf LayoutLMv3-Architektur – vorher im Team besprechen, weil das
vom Proposal abweicht.
"""

import argparse
import sys

from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

from magda.config import (
    CHECKPOINTS_DIR,
    LAYOUT_MODEL,
    MAX_SEQ_LENGTH,
    SEED,
    TEXT_MODEL,
    default_labeled_model,
    labeled_models,
)
from magda.dataset import (
    LayoutDataset,
    TextDataset,
    get_or_create_splits,
    load_labeled_pages,
    select_split,
)
from magda.evaluation import compute_metrics
from magda.labels import LABELS, id2label, label2id


def build_datasets(variant: str, labels_from: str | None):
    model = labels_from or default_labeled_model()
    if model is None:
        sys.exit("Keine gelabelten Seiten in data/labeled/. Erst 03_label_words.py laufen lassen.")

    pages = load_labeled_pages(model)
    if not pages:
        sys.exit(
            f"Keine gelabelten Seiten in data/labeled/{model}/. "
            f"Vorhanden: {', '.join(labeled_models()) or 'nichts'}"
        )

    splits = get_or_create_splits(pages)
    train_pages = select_split(pages, splits, "train")
    dev_pages = select_split(pages, splits, "dev")

    # Welches Modell die Labels geliefert hat, gehört in die Ausgabe: sonst
    # steht am Ende ein F1-Wert im Bericht, dessen Trainingsdaten niemand mehr
    # zuordnen kann, sobald mehr als ein Ordner existiert. Gezählt wird, was
    # wirklich geladen wurde, nicht wie groß der Split ist – der deckt alle
    # extrahierten Seiten ab, auch die noch ungelabelten.
    print(
        f"{len(pages)} Seiten geladen, Labels von {model} "
        f"(train={len(train_pages)}/{len(splits['train'])}, "
        f"dev={len(dev_pages)}/{len(splits['dev'])}, "
        f"test={len(select_split(pages, splits, 'test'))}/{len(splits['test'])})"
    )

    if variant == "gbert":
        model_name, dataset_cls = TEXT_MODEL, TextDataset
    else:
        model_name, dataset_cls = LAYOUT_MODEL, LayoutDataset

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    train_ds = dataset_cls(train_pages, tokenizer, MAX_SEQ_LENGTH)
    dev_ds = dataset_cls(dev_pages, tokenizer, MAX_SEQ_LENGTH)
    return model_name, train_ds, dev_ds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=["gbert", "layoutxlm"])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument(
        "--labels-from",
        help="Modellordner unter data/labeled/, dessen Labels trainiert werden. "
        "Ohne Angabe das konfigurierte Vision-Modell, sonst der größte Ordner.",
    )
    args = parser.parse_args()

    model_name, train_ds, dev_ds = build_datasets(args.variant, args.labels_from)

    model = AutoModelForTokenClassification.from_pretrained(
        model_name,
        num_labels=len(LABELS),
        id2label=id2label,
        label2id=label2id,
    )

    output_dir = CHECKPOINTS_DIR / args.variant
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        save_total_limit=2,  # nur bestes + letztes Checkpoint behalten, spart Platz
        seed=SEED,
        logging_steps=20,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=dev_ds,
        compute_metrics=compute_metrics,
    )
    trainer.train()

    # bestes Modell separat ablegen, darauf zeigt dann 05_evaluate.py
    best_dir = output_dir / "best"
    trainer.save_model(str(best_dir))
    print(f"Bestes Modell gespeichert unter {best_dir}")


if __name__ == "__main__":
    main()
