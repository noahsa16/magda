"""Phase 3: Evaluation auf dem Test-Split (Entity-Level P/R/F1 via seqeval).

Aufruf:
    python scripts/05_evaluate.py gbert
    python scripts/05_evaluate.py layoutxlm

Noch offen (Requirements-Stufe "Excellent"): der Vergleich gegen die
LLM-Blackbox. Dafür müssen wir erst festlegen, wie wir die Angebots-JSONs
der Blackbox mit unseren Token-Entities matchen – kommt in Phase 3.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from transformers import AutoModelForTokenClassification, AutoTokenizer, Trainer

from magda.config import CHECKPOINTS_DIR, EVAL_DIR, LAYOUT_MODEL, MAX_SEQ_LENGTH, TEXT_MODEL
from magda.dataset import (
    LayoutDataset,
    TextDataset,
    get_or_create_splits,
    load_labeled_pages,
    select_split,
)
from magda.evaluation import full_report, report_dict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=["gbert", "layoutxlm"])
    parser.add_argument("--split", default="test", choices=["dev", "test"])
    args = parser.parse_args()

    model_dir = CHECKPOINTS_DIR / args.variant / "best"
    if not model_dir.exists():
        sys.exit(f"Kein trainiertes Modell unter {model_dir}. Erst 04_train.py laufen lassen.")

    pages = load_labeled_pages()
    splits = get_or_create_splits(pages)
    eval_pages = select_split(pages, splits, args.split)
    print(f"Evaluiere '{args.variant}' auf {len(eval_pages)} Seiten ({args.split}-Split).")

    # Tokenizer kommt vom Basismodell, nicht aus dem Checkpoint –
    # wir speichern in 04_train.py nur die Modellgewichte.
    base_model = TEXT_MODEL if args.variant == "gbert" else LAYOUT_MODEL
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    dataset_cls = TextDataset if args.variant == "gbert" else LayoutDataset
    eval_ds = dataset_cls(eval_pages, tokenizer, MAX_SEQ_LENGTH)

    model = AutoModelForTokenClassification.from_pretrained(model_dir)
    trainer = Trainer(model=model)
    output = trainer.predict(eval_ds)

    predictions = np.argmax(output.predictions, axis=-1)
    print(full_report(predictions, output.label_ids))

    # Zusätzlich als JSON für das Frontend-Dashboard.
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_file = EVAL_DIR / f"{args.variant}_{args.split}.json"
    with open(out_file, "w") as f:
        json.dump(
            {
                "variant": args.variant,
                "split": args.split,
                "num_pages": len(eval_pages),
                "created": datetime.now().isoformat(timespec="seconds"),
                "report": report_dict(predictions, output.label_ids),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Report gespeichert: {out_file}")


if __name__ == "__main__":
    main()
