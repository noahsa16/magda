"""Phase 3: Evaluation auf dem Test-Split (Entity-Level P/R/F1 via seqeval).

Aufruf:
    magda eval gbert
    magda eval layoutxlm

Gemessen wird in drei Protokollen, weil eine einzelne Zahl hier in die Irre
führt. Seiten über 512 Subwords werden vom Tokenizer abgeschnitten – auf der
Testwoche betrifft das 31 von 100 Seiten und 186 der 5107 Entities:

  windowed   Überlappende Fenster über die ganze Seite, jedes Wort bekommt
             eine Vorhersage. **Primärmetrik** – sie misst genau das, was
             `magda predict` ausliefert.
  truncated  Nur die Wörter im ersten Fenster, gegen deren Referenz. Das war
             das bisherige Protokoll; die Anschlusszahl zu älteren Berichten.
             Achtung: Entities hinter dem Abschnitt fehlen hier im *Nenner*,
             die Zahl ist also systematisch zu gut.
  no-windows Vorhersage ohne Fenster, aber gegen die *vollständige* Referenz –
             abgeschnittene Wörter zählen als "O" und damit als Fehler. Das
             ist der ehrliche Wert eines Deployments ohne Fenster, und die
             Differenz zu `windowed` beziffert, was die Fenster bringen.

Noch offen (Requirements-Stufe "Excellent"): der Vergleich gegen die
LLM-Blackbox. Dafür müssen wir erst festlegen, wie wir die Angebots-JSONs
der Blackbox mit unseren Token-Entities matchen.
"""

import argparse
import json
import sys
from datetime import datetime

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
from magda.evaluation import (
    full_report,
    report_dict,
    word_level_report,
    word_level_report_dict,
)
from magda.predict import WINDOW_STRIDE, merge_windows, word_predictions
from magda.windows import WindowDataset


def logits_of(model, dataset) -> np.ndarray:
    output = Trainer(model=model).predict(dataset).predictions
    if isinstance(output, tuple):
        output = output[0]
    return np.asarray(output)


def as_tags(tags: list[str | None]) -> list[str]:
    """Ein Wort ohne Vorhersage ist im Ergebnis ein "O".

    Nur fürs Messen: hier *soll* ein abgeschnittenes Wort als Fehler zählen,
    denn die Referenz kennt dort sehr wohl ein Entity. Im Export bleibt es
    `null`, weil dort der Unterschied zwischen "nichts gesagt" und "nichts
    gefunden" für die Weiterverarbeitung zählt.
    """
    return [t if t is not None else "O" for t in tags]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("variant", choices=["gbert", "layoutxlm"])
    parser.add_argument("--split", default="test", choices=["dev", "test"])
    parser.add_argument(
        "--labels-from",
        help="Modellordner unter data/labeled/. Muss derselbe sein wie beim "
        "Training – sonst wird gegen andere Labels gemessen als gelernt wurde.",
    )
    args = parser.parse_args(argv)

    model_dir = CHECKPOINTS_DIR / args.variant / "best"
    if not model_dir.exists():
        sys.exit(f"Kein trainiertes Modell unter {model_dir}. Erst `magda train` laufen lassen.")

    pages = load_labeled_pages(args.labels_from)
    splits = get_or_create_splits(pages)
    eval_pages = select_split(pages, splits, args.split)
    print(f"Evaluiere '{args.variant}' auf {len(eval_pages)} Seiten ({args.split}-Split).")

    # Tokenizer kommt vom Basismodell, nicht aus dem Checkpoint –
    # wir speichern in `magda train` nur die Modellgewichte.
    base_model = TEXT_MODEL if args.variant == "gbert" else LAYOUT_MODEL
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    layout = args.variant == "layoutxlm"
    model = AutoModelForTokenClassification.from_pretrained(model_dir)

    reference = [page["tags"] for page in eval_pages]

    # --- Protokoll 1+3: ein Durchlauf ohne Fenster, zwei Auswertungen -------
    plain_ds = (LayoutDataset if layout else TextDataset)(
        eval_pages, tokenizer, MAX_SEQ_LENGTH
    )
    plain_logits = logits_of(model, plain_ds)
    censored = np.argmax(plain_logits, axis=-1)

    plain_raw = [
        word_predictions(plain_logits[i], plain_ds.word_ids[i], len(page["words"]))[0]
        for i, page in enumerate(eval_pages)
    ]
    plain_tags = [as_tags(t) for t in plain_raw]
    fehlend = sum(t.count(None) for t in plain_raw)

    # --- Protokoll 2: überlappende Fenster ---------------------------------
    window_ds = WindowDataset(eval_pages, tokenizer, MAX_SEQ_LENGTH, WINDOW_STRIDE, layout)
    window_logits = logits_of(model, window_ds)
    windowed_tags = []
    for i, page in enumerate(eval_pages):
        windows = window_ds.windows_of(i)
        tags, _ = merge_windows(
            [window_logits[w] for w in windows],
            [window_ds.word_ids[w] for w in windows],
            len(page["words"]),
        )
        windowed_tags.append(as_tags(tags))

    print(f"\n{len(window_ds)} Fenster über {len(eval_pages)} Seiten "
          f"(Überlappung {WINDOW_STRIDE}). Ohne Fenster hätten "
          f"{fehlend} Wörter keine Vorhersage.")

    print("\n########## windowed (Primärmetrik) ##########")
    print(word_level_report(reference, windowed_tags))
    print("########## no-windows, gegen volle Referenz ##########")
    print(word_level_report(reference, plain_tags))
    print("########## truncated (altes Protokoll, zu optimistisch) ##########")
    print(full_report(censored, np.array([e["labels"] for e in plain_ds.encodings])))

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_file = EVAL_DIR / f"{args.variant}_{args.split}.json"
    with open(out_file, "w") as f:
        json.dump(
            {
                "variant": args.variant,
                "split": args.split,
                "num_pages": len(eval_pages),
                "created": datetime.now().isoformat(timespec="seconds"),
                "protocol": "windowed",
                "window_stride": WINDOW_STRIDE,
                "words_without_prediction_unwindowed": fehlend,
                # `report` bleibt die windowed-Zahl: das Frontend liest dieses
                # Feld, und dort soll die Primärmetrik stehen.
                "report": word_level_report_dict(reference, windowed_tags),
                "report_no_windows": word_level_report_dict(reference, plain_tags),
                "report_truncated": report_dict(
                    censored, np.array([e["labels"] for e in plain_ds.encodings])
                ),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Report gespeichert: {out_file}")
