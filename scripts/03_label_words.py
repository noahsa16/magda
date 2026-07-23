"""Pipeline-Schritt 2: Wörter per LLM labeln -> Trainingsdaten in data/labeled/.

Nimmt sich alle Seiten aus data/words/ vor, die noch kein Gegenstück in
data/labeled/ haben. Fehlgeschlagene Seiten werden übersprungen und beim
nächsten Lauf erneut versucht – bei ein paar tausend Seiten will man nicht,
dass ein einzelner API-Schluckauf den ganzen Lauf abbricht.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tqdm import tqdm

from magda.config import (
    CHAT_AI_VISION_MODEL,
    IMAGES_DIR,
    LABELED_DIR,
    WORDS_DIR,
    make_llm_client,
)
from magda.labeling import label_page


def main():
    LABELED_DIR.mkdir(parents=True, exist_ok=True)
    client = make_llm_client()

    word_files = sorted(WORDS_DIR.glob("*.json"))
    todo = [p for p in word_files if not (LABELED_DIR / p.name).exists()]
    if not todo:
        sys.exit("Nichts zu tun – alle Seiten sind bereits gelabelt.")

    print(f"{len(todo)} von {len(word_files)} Seiten noch zu labeln.")

    failed = 0
    for path in tqdm(todo, desc="LLM-Labeling", unit="Seite"):
        with open(path) as f:
            page = json.load(f)

        png_path = IMAGES_DIR / f"{page['page_id']}.png"
        if not png_path.exists():
            tqdm.write(f"  [{page['page_id']}] Seitenbild fehlt, übersprungen.")
            failed += 1
            continue

        try:
            page["tags"] = label_page(
                page["words"], png_path.read_bytes(), client, CHAT_AI_VISION_MODEL
            )
        except Exception as e:
            tqdm.write(f"  [{page['page_id']}] Labeling fehlgeschlagen: {e}")
            failed += 1
            continue

        with open(LABELED_DIR / path.name, "w") as f:
            json.dump(page, f, ensure_ascii=False)

    print(f"Fertig. {len(todo) - failed} gelabelt, {failed} fehlgeschlagen.")


if __name__ == "__main__":
    main()
