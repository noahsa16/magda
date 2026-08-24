"""Token-Klassifikation trainieren.

Zwei Varianten (siehe Proposal, "Baseline Architecture"):
    magda train gbert       # text-only Baseline
    magda train layoutxlm   # layout-aware Modell

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
    duplicate_clusters,
    select_split,
    subset_by_clusters,
)
from magda.evaluation import compute_metrics
from magda.labels import LABELS, id2label, label2id


def build_datasets(variant: str, labels_from: str | None,
                   train_pages: int | None = None):
    model = labels_from or default_labeled_model()
    if model is None:
        sys.exit("Keine gelabelten Seiten in data/labeled/. Erst `magda label` laufen lassen.")

    pages = load_labeled_pages(model)
    if not pages:
        sys.exit(
            f"Keine gelabelten Seiten in data/labeled/{model}/. "
            f"Vorhanden: {', '.join(labeled_models()) or 'nichts'}"
        )

    splits = get_or_create_splits(pages)
    train_split = select_split(pages, splits, "train")
    dev_pages = select_split(pages, splits, "dev")

    # Die Lernkurve zieht clusterweise. Dev bleibt in jedem Fall vollständig –
    # sonst wechselte mit der Trainingsmenge auch das Auswahlkriterium für den
    # Checkpoint, und die Kurve mischte zwei Effekte.
    if train_pages is not None:
        wanted = set(subset_by_clusters(train_split, train_pages))
        train_split = [p for p in train_split if p["page_id"] in wanted]
        # Die Clusterzahl gehört daneben, sonst ist "p25" eine Seitenzahl
        # ohne das, woran gemessen wurde: 25 Seiten können neun unabhängige
        # Vorlagen sein oder drei.
        print(f"Lernkurve: {len(train_split)} von {len(splits['train'])} "
              f"Trainingsseiten in {len(duplicate_clusters(train_split))} "
              f"Duplikat-Clustern (von "
              f"{len(duplicate_clusters(select_split(pages, splits, 'train')))}).")
    train_pages_list = train_split

    # Welches Modell die Labels geliefert hat, gehört in die Ausgabe: sonst
    # steht am Ende ein F1-Wert im Bericht, dessen Trainingsdaten niemand mehr
    # zuordnen kann, sobald mehr als ein Ordner existiert. Gezählt wird, was
    # wirklich geladen wurde, nicht wie groß der Split ist – der deckt alle
    # extrahierten Seiten ab, auch die noch ungelabelten.
    print(
        f"{len(pages)} Seiten geladen, Labels von {model} "
        f"(train={len(train_pages_list)}/{len(splits['train'])}, "
        f"dev={len(dev_pages)}/{len(splits['dev'])}, "
        f"test={len(select_split(pages, splits, 'test'))}/{len(splits['test'])})"
    )

    if variant == "gbert":
        model_name, dataset_cls = TEXT_MODEL, TextDataset
    else:
        model_name, dataset_cls = LAYOUT_MODEL, LayoutDataset

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    train_ds = dataset_cls(train_pages_list, tokenizer, MAX_SEQ_LENGTH)
    dev_ds = dataset_cls(dev_pages, tokenizer, MAX_SEQ_LENGTH)
    return model_name, train_ds, dev_ds


def checkpoint_name(variant: str, labels_from: str | None,
                    train_pages: int | None) -> str:
    """Ordnername unter `checkpoints/` – abweichende Läufe bekommen einen eigenen.

    `checkpoints/gbert` trägt den eingefrorenen KW30/31-Stand, an dem die
    berichteten Zahlen hängen und auf dem die Drift-Messung aufsetzt. Ohne
    diese Namensgebung überschriebe ihn jeder Nebenlauf – der APP_PRICE-Arm
    genau das Modell, gegen das er verglichen werden soll, und jeder
    Kurvenpunkt den vorigen.

    Der Standardlauf behält seinen Namen: eine Umbenennung machte alle
    bisherigen Zahlen unreproduzierbar. `--labels-from sonnet-5` *ist* der
    Standardlauf und zählt deshalb nicht als Abweichung – Anker ist
    `config.CANONICAL_LABELS`, nicht `default_labeled_model()`. Letzteres
    folgt `CHAT_AI_VISION_MODEL` und zeigt auf ein Modell, mit dem hier gar
    nicht gelabelt wird.

    **`labels_from=None` ist deshalb keine Zusicherung, sondern eine Lücke.**
    `build_datasets` löst `None` über genau dieses `default_labeled_model()`
    auf; `magda train gbert` ohne Argumente trainierte also auf
    Mistral-Labels und schriebe nach `checkpoints/gbert` – den Ordner, an dem
    die berichteten Zahlen hängen. Aufgelöst wird die Quelle deshalb *vor*
    dem Namen, und `None` gilt nur dann als kanonisch, wenn die aufgelöste
    Quelle es auch ist.
    """
    from magda.config import CANONICAL_LABELS, default_labeled_model, model_slug

    resolved = labels_from or default_labeled_model()
    name = variant
    if resolved and model_slug(resolved) != model_slug(CANONICAL_LABELS):
        name += f"-{model_slug(resolved)}"
    if train_pages is not None:
        name += f"-p{train_pages}"
    return name


def main(argv=None):
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
    parser.add_argument(
        "--train-pages",
        type=int,
        help="Trainingsseiten auf N begrenzen, clusterweise gezogen – für die "
        "Lernkurve. Schreibt in einen eigenen Checkpoint-Ordner.",
    )
    args = parser.parse_args(argv)

    model_name, train_ds, dev_ds = build_datasets(
        args.variant, args.labels_from, args.train_pages)

    model = AutoModelForTokenClassification.from_pretrained(
        model_name,
        num_labels=len(LABELS),
        id2label=id2label,
        label2id=label2id,
    )

    output_dir = CHECKPOINTS_DIR / checkpoint_name(
        args.variant, args.labels_from, args.train_pages)
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

    # bestes Modell separat ablegen, darauf zeigt dann `magda eval`
    best_dir = output_dir / "best"
    trainer.save_model(str(best_dir))
    print(f"Bestes Modell gespeichert unter {best_dir}")

