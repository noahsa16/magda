"""Misst Angebotsausgabe ab gespeicherten Wortlisten und Seitenbildern.

Die Original-PDFs sind nicht im Checkout. Deshalb beginnt diese Messung nach
PDF-Textextraktion und Bildrendering und beansprucht keinen PDF-Ende-zu-Ende-
Vergleich. Beide Systeme verarbeiten dieselben Seiten nacheinander.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import statistics
import time
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAGES = ROOT / "data/eval/test_cluster_pages.txt"


def _save(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def _summary(report: dict) -> None:
    values = [row["seconds"] for row in report["per_page"] if row["error"] is None]
    ordered = sorted(values)
    report["summary"] = {
        "successful_pages": len(values),
        "failed_pages": len(report["per_page"]) - len(values),
        "total_seconds": round(sum(values), 3),
        "mean_seconds_per_page": round(statistics.mean(values), 3) if values else None,
        "median_seconds_per_page": round(statistics.median(values), 3) if values else None,
        "p90_seconds_per_page": round(ordered[int(0.9 * (len(ordered) - 1))], 3)
        if values else None,
    }


def _local_runner():
    from magda import offer_model, offers, offers_verify
    from magda.labels import spans_to_bio
    from magda.predict import load_ner_model, page_output, predict_pages

    started = time.perf_counter()
    model, tokenizer, spec = load_ner_model("layoutxlm")
    pair_model = offer_model.load(ROOT / "checkpoints/offer_pairs/model.pt")
    load_seconds = time.perf_counter() - started
    grouping = offers.pair_model_grouping(pair_model)

    def run(page_id: str) -> int:
        page = json.loads((ROOT / "data/words" / f"{page_id}.json").read_text())
        tags, scores = predict_pages(
            [page], model, tokenizer, spec, images_dir=ROOT / "data/images"
        )[0]
        output = page_output(page, tags, scores, "layoutxlm", None)
        output["tags"] = spans_to_bio(len(output["words"]), output["entities"])
        groups = grouping(output)
        offers_verify.judge_offers(output, groups)
        return len(groups)

    return run, load_seconds


def _api_runner(base_url: str | None, model: str, timeout: float):
    from magda import blackbox, config
    from openai import OpenAI

    client = (OpenAI(base_url=base_url, api_key="dummy", timeout=timeout,
                     max_retries=0) if base_url else
              config.make_llm_client(max_retries=0))

    def run(page_id: str) -> int:
        png = (ROOT / "data/images" / f"{page_id}.png").read_bytes()
        encoded = base64.b64encode(png).decode("ascii")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + encoded}},
                {"type": "text", "text": blackbox._EXTRACT_PROMPT},
            ]}],
            temperature=0.2,
            max_tokens=8192,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}}
            if "qwen" in model.lower() else None,
        )
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ValueError("Antwort abgeschnitten")
        deals = json.loads(blackbox._extract_json_array(choice.message.content or ""))
        if not isinstance(deals, list):
            raise ValueError("Antwort ist keine Angebotsliste")
        return len(deals), deals

    return run, 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("system", choices=("local", "api"))
    parser.add_argument("--pages", type=Path, default=DEFAULT_PAGES)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", help="OpenAI-compatible API endpoint")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--min-interval", type=float, default=4.1,
                        help="Minimum seconds between API request starts")
    args = parser.parse_args()

    page_ids = [line.strip() for line in args.pages.read_text().splitlines()
                if line.strip()]
    if not page_ids or len(page_ids) != len(set(page_ids)):
        parser.error("Seitenliste fehlt oder enthält Duplikate")
    for page_id in page_ids:
        image = ROOT / "data/images" / f"{page_id}.png"
        words = ROOT / "data/words" / f"{page_id}.json"
        if not image.is_file() or (args.system == "local" and not words.is_file()):
            parser.error(f"Eingabedatei fehlt für {page_id}")

    if args.system == "local":
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        run, load_seconds = _local_runner()
        run(page_ids[0])  # Aufwärmlauf für Modell und Bibliotheken
    else:
        run, load_seconds = _api_runner(args.base_url, args.model, args.timeout)

    report = {
        "protocol": "prepared-page-offer-runtime-v1",
        "system": args.system,
        "input_scope": "Gespeicherte PDF-Wortlisten und PNGs" if args.system == "local"
        else "Gespeicherte PNGs, externer API-Aufruf und JSON-Antwort",
        "excluded": "PDF-Download, Textextraktion, Bildrendering und Trainingszeit",
        "hardware": platform.platform(),
        "python": platform.python_version(),
        "page_list": str(args.pages.relative_to(ROOT))
        if args.pages.is_relative_to(ROOT) else str(args.pages),
        "page_list_sha256": hashlib.sha256(args.pages.read_bytes()).hexdigest(),
        "model_load_seconds": round(load_seconds, 3),
        "api_model": args.model if args.system == "api" else None,
        "api_host": urlsplit(args.base_url).hostname if args.base_url else None,
        "per_page": [],
    }
    previous_start = None
    for number, page_id in enumerate(page_ids, 1):
        if args.system == "api" and previous_start is not None:
            time.sleep(max(0, args.min_interval - (time.perf_counter() - previous_start)))
        started = time.perf_counter()
        previous_start = started
        count = None
        records = None
        error = None
        try:
            if args.system == "api":
                count, records = run(page_id)
            else:
                count = run(page_id)
        except Exception as exc:
            error = type(exc).__name__
        elapsed = time.perf_counter() - started
        report["per_page"].append({
            "page_id": page_id,
            "seconds": round(elapsed, 3),
            "offer_groups_or_responses": count,
            "error": error,
            **({"records": records} if args.system == "api" else {}),
        })
        _summary(report)
        _save(args.output, report)
        print(f"{number}/{len(page_ids)} {page_id}: {elapsed:.2f}s"
              + (f" ({error})" if error else ""), flush=True)
    if report["summary"]["failed_pages"]:
        raise SystemExit("Messung enthält fehlgeschlagene Seiten")


if __name__ == "__main__":
    main()
