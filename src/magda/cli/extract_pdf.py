"""Fremdes PDF direkt zu Angeboten - ohne Umweg über data/.

Aufruf:
    magda extract-pdf katalog.pdf
    magda extract-pdf katalog.pdf --variant layoutxlm --out angebote.sqlite
    magda extract-pdf katalog.pdf --out angebote.csv

Anders als `magda extract` + `magda predict` + `magda offers` liest dieser
Befehl kein `data/raw`, schreibt kein `data/words`, `data/images` oder
`data/predictions` - alles bleibt im Speicher (`magda.pipeline.extract_offers`).
Gedacht für ein einzelnes fremdes PDF, nicht für einen Katalog aus der
laufenden Prospektwoche; dafür bleibt die reguläre Pipeline zuständig, weil
sie versioniert, was `magda dedupe` und `magda split` später brauchen.

Ohne --out geht das Ergebnis als JSON auf stdout (Seitenbilder base64-kodiert,
also nicht zum bloßen Ansehen gedacht) - --out mit .json/.csv/.sqlite
schreibt stattdessen in eine Datei.
"""

import argparse
import sys
import time
from pathlib import Path

from magda import pipeline


def _progress(page_index: int, page_count: int, seconds: float) -> None:
    print(f"  Seite {page_index + 1}/{page_count}: {seconds:.2f}s", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pdf", help="Pfad zu einem (mehrseitigen) PDF")
    parser.add_argument(
        "--variant", default="gbert", choices=["gbert", "layoutxlm"],
        help="NER-Modell aus checkpoints/<variante>/best. Default gbert.",
    )
    parser.add_argument(
        "--checkpoint",
        help="Abweichender Checkpoint-Ordnername unter checkpoints/, falls nicht der gleichnamige.",
    )
    parser.add_argument(
        "--pairs-checkpoint",
        help="Paarmodell-Checkpoint (Default checkpoints/offer_pairs/model.pt).",
    )
    parser.add_argument(
        "--out",
        help="Zieldatei: .json, .csv oder .sqlite. Ohne Angabe: JSON auf stdout.",
    )
    parser.add_argument(
        "--images-dir",
        help="Gerenderte Seitenbilder zusätzlich hier ablegen (sonst nur "
             "temporär für LayoutXLM/Farbmerkmale genutzt und verworfen).",
    )
    parser.add_argument(
        "--render-images", action="store_true",
        help="Seitenbild auch rendern, wenn weder Variante noch Paarmodell es "
             "brauchen (z.B. gbert) - für --images-dir ohne eigenen Bildbedarf.",
    )
    parser.add_argument(
        "--no-embed-images", action="store_true",
        help="Seitenbilder nicht base64-kodiert in --out .json einbetten. Nur "
             "sinnvoll zusammen mit --images-dir, sonst gehen sie verloren.",
    )
    args = parser.parse_args(argv)

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        parser.exit(1, f"PDF nicht gefunden: {pdf_path}\n")

    print(f"Lade Modelle ({args.variant}) ...", file=sys.stderr)
    t0 = time.perf_counter()
    try:
        models = pipeline.load_models(
            variant=args.variant, checkpoint=args.checkpoint,
            pairs_checkpoint=args.pairs_checkpoint,
        )
    except FileNotFoundError as error:
        parser.exit(1, f"{error}\n")
    print(f"Modelle geladen in {time.perf_counter() - t0:.1f}s.", file=sys.stderr)

    pdf_bytes = pdf_path.read_bytes()
    result = pipeline.extract_offers(
        pdf_bytes, models, progress=_progress, render_images=args.render_images,
    )

    print(
        f"\n{len(result.pages)} Seiten, {len(result.offers)} Angebote "
        f"({len(result.pages_without_text)} ohne Textlayer).",
        file=sys.stderr,
    )
    print(
        "Zeiten: extract {extract:.2f}s, ner {ner:.2f}s, grouping {grouping:.2f}s".format(
            **result.timing
        ),
        file=sys.stderr,
    )

    if args.images_dir:
        images_dir = Path(args.images_dir)
        images_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        for page in result.pages:
            if page.png_bytes:
                (images_dir / f"{result.doc_id}_p{page.page_index + 1}.png").write_bytes(
                    page.png_bytes
                )
                written += 1
        print(f"{written} Seitenbilder -> {images_dir}", file=sys.stderr)

    embed_images = not args.no_embed_images

    if not args.out:
        print(pipeline.to_json(result, embed_images=embed_images))
        return

    out_path = Path(args.out)
    suffix = out_path.suffix.lower()
    if suffix == ".json":
        out_path.write_text(pipeline.to_json(result, embed_images=embed_images), encoding="utf-8")
    elif suffix == ".csv":
        out_path.write_text(pipeline.to_csv(result), encoding="utf-8")
    elif suffix in (".sqlite", ".db"):
        pipeline.to_sqlite(result, out_path)
    else:
        parser.exit(1, f"Unbekanntes Ausgabeformat: {suffix} (erlaubt: .json, .csv, .sqlite)\n")
    print(f"Geschrieben: {out_path}", file=sys.stderr)
