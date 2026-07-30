"""Pipeline-Schritt 3: Wörter per LLM labeln -> Trainingsdaten in data/labeled/<modell>/.

    python scripts/03_label_words.py                      # konfiguriertes Vision-Modell
    python scripts/03_label_words.py --model qwen3.6-27b  # zum Vergleich
    python scripts/03_label_words.py --only-gold          # nur die Gold-Seiten, für Probeläufe

Jedes Modell schreibt in seinen eigenen Ordner, damit sich die Läufe hinterher
vergleichen lassen (scripts/08_compare_labels.py). Seiten, die dort schon
liegen, werden übersprungen – ein Abbruch kostet also nur die laufenden Seiten,
nicht den ganzen Durchgang.
"""

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tqdm import tqdm

from magda.config import (
    CHAT_AI_VISION_MODEL,
    GOLD_DIR,
    IMAGES_DIR,
    VISION_MODELS,
    WORDS_DIR,
    labeled_dir,
    make_llm_client,
)
from magda.labeling import label_page_with_retry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=CHAT_AI_VISION_MODEL,
        help=f"Vision-Modell der GWDG. Bekannt bildfähig: {', '.join(VISION_MODELS)}",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Parallele Anfragen. Höher ist schneller, riskiert aber 429er.",
    )
    parser.add_argument(
        "--limit", type=int, help="Höchstens so viele Seiten labeln (für Probeläufe)."
    )
    parser.add_argument(
        "--only-gold",
        action="store_true",
        help="Nur Seiten labeln, für die eine Gold-Annotation existiert.",
    )
    args = parser.parse_args()

    out_dir = labeled_dir(args.model)
    out_dir.mkdir(parents=True, exist_ok=True)
    # max_retries=0: label_page_with_retry wiederholt selbst, verschachtelt
    # wären es bis zu neun Anläufe à 120 Sekunden für eine Seite.
    client = make_llm_client(max_retries=0)

    word_files = sorted(WORDS_DIR.glob("*.json"))
    if args.only_gold:
        gold_ids = {f.stem for f in GOLD_DIR.glob("*.json")}
        word_files = [p for p in word_files if p.stem in gold_ids]
    todo = [p for p in word_files if not (out_dir / p.name).exists()]
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        sys.exit(f"Nichts zu tun – alle Seiten sind mit {args.model} bereits gelabelt.")

    print(f"{len(todo)} von {len(word_files)} Seiten zu labeln mit {args.model}.")
    print(f"Ziel: {out_dir.relative_to(Path.cwd())} · {args.workers} parallele Anfragen")

    # Schreibt der Pool gleichzeitig in die Fortschrittsanzeige, zerfasert die
    # Ausgabe. tqdm.write ist selbst nicht threadsicher genug dafür.
    write_lock = threading.Lock()
    failures: list[tuple[str, str]] = []

    def process(path: Path) -> bool:
        with open(path) as f:
            page = json.load(f)

        png_path = IMAGES_DIR / f"{page['page_id']}.png"
        if not png_path.exists():
            with write_lock:
                failures.append((page["page_id"], "Seitenbild fehlt"))
            return False

        try:
            page["tags"] = label_page_with_retry(
                page["words"], png_path.read_bytes(), client, args.model
            )
        except Exception as e:
            with write_lock:
                failures.append((page["page_id"], f"{type(e).__name__}: {e}"))
            return False

        # Welches Modell die Tags erzeugt hat, gehört in die Datei und nicht nur
        # in den Ordnernamen: eine einzeln herumgereichte Seite verliert sonst
        # ihre Herkunft.
        page["model"] = args.model
        # Erst daneben schreiben, dann umbenennen: ein Abbruch mitten im
        # json.dump hinterlässt sonst eine halbe Datei, die beim nächsten Lauf
        # als "schon erledigt" durchgeht.
        tmp = out_dir / f".{path.name}.tmp"
        with open(tmp, "w") as f:
            json.dump(page, f, ensure_ascii=False)
        tmp.replace(out_dir / path.name)
        return True

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, p): p for p in todo}
        with tqdm(total=len(todo), desc="LLM-Labeling", unit="Seite") as bar:
            for future in as_completed(futures):
                try:
                    if future.result():
                        done += 1
                except Exception as e:  # darf den Lauf nie beenden
                    with write_lock:
                        failures.append((futures[future].stem, f"unerwartet: {e}"))
                bar.update(1)
                bar.set_postfix(ok=done, fehler=len(failures))

    print(f"\nFertig. {done} gelabelt, {len(failures)} fehlgeschlagen.")
    for page_id, reason in failures[:20]:
        print(f"  [{page_id}] {reason[:120]}")
    if len(failures) > 20:
        print(f"  ... und {len(failures) - 20} weitere")


if __name__ == "__main__":
    main()
