"""Zentrale Konfiguration für das Magda-Projekt.

API-Zugangsdaten liegen in einer lokalen .env (siehe .env.example), damit
keine Keys im Repo landen. Alles andere (Pfade, Modellnamen) steht direkt hier.
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _project_python() -> str:
    """Der Interpreter, mit dem Pipeline-Schritte laufen sollen.

    Nicht sys.executable: die API wird oft aus einem anderen Env gestartet
    (`which python` zeigt hier auf Anaconda), und dort fehlen openai,
    transformers und seqeval. Schritt 02 lief trotzdem durch, weil PyMuPDF
    zufällig vorhanden war – die Schritte 03 bis 07 starben an Importfehlern,
    die wie Codefehler aussehen. Das .venv des Projekts hat Vorrang.
    """
    candidate = PROJECT_ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


PYTHON = _project_python()

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"          # heruntergeladene Flyer-PDFs (eine Seite pro Datei)
WORDS_DIR = DATA_DIR / "words"      # Wörter + Bounding-Boxen pro Seite (JSON)
IMAGES_DIR = DATA_DIR / "images"    # gerenderte Seitenbilder (PNG)
# Wurzel der LLM-Labels. Darunter liegt je Modell ein Ordner, nicht die Seiten
# selbst: welches Modell ein Label erzeugt hat, ist der interessanteste Teil
# davon. Flach gespeichert überschreibt der zweite Lauf den ersten, und die
# Frage "labelt Qwen näher am Goldstandard als Mistral?" ist nicht mehr
# beantwortbar, weil die Vergleichsgrundlage weg ist.
LABELED_DIR = DATA_DIR / "labeled"
SPLITS_DIR = DATA_DIR / "splits"    # train/dev/test-Aufteilung
EVAL_DIR = DATA_DIR / "eval"        # Evaluations-Reports als JSON (fürs Frontend)
RUNS_DIR = DATA_DIR / "runs"        # Lauf-Historie: je Lauf Metadaten-JSON + Log
# Seiten, die 06_check_duplicates als Beinah-Duplikat aussortiert hat. Löschen
# allein genügt nicht: Schritt 02 erzeugt sie aus data/raw jederzeit neu, weil
# sein eigener Filter nur exakt gleiche Wortlisten erkennt.
EXCLUDED_FILE = DATA_DIR / "excluded.json"
# Handannotierte Referenz. Liegt bewusst außerhalb von data/ und wird
# versioniert: generierte Artefakte sind reproduzierbar, Handarbeit nicht.
GOLD_DIR = PROJECT_ROOT / "gold"
# Katalog-Verzeichnis: gefundene Blätterkatalog-IDs. Versioniert wie gold/ –
# eine ID lässt sich nicht reproduzieren, nur wiederfinden.
CATALOGS_FILE = PROJECT_ROOT / "catalogs.json"
# Katalog -> Verkaufsregion. Penny's Markt-API kennt nur die laufende Woche;
# ungespeichert ist die Zuordnung nach sieben Tagen unwiederbringlich weg.
CATALOG_META_FILE = PROJECT_ROOT / "catalog_meta.json"
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"


def model_slug(model: str) -> str:
    """Modellname als Ordnername.

    Die GWDG-IDs sind schon dateisystemtauglich ("qwen3.5-397b-a17b"), aber der
    Name kommt aus einer Nutzereingabe – über /api und über den Job-Parameter
    von Schritt 03. Ohne Filter wäre "../../etc" ein gültiger Modellname und
    LABELED_DIR / model ein Schreibzugriff außerhalb von data/. Deshalb bleibt
    nur ein enges Alphabet stehen; alles andere wird zu "_".
    """
    slug = re.sub(r"[^A-Za-z0-9._-]", "_", model.strip())
    slug = slug.strip(".")  # ".", ".." und führende Punkte sind keine Ordner
    if not slug:
        raise ValueError(f"Unbrauchbarer Modellname: {model!r}")
    return slug


def labeled_dir(model: str) -> Path:
    """Ordner mit den Labels genau eines Modells."""
    return LABELED_DIR / model_slug(model)


def labeled_models() -> list[str]:
    """Modelle, für die Labels auf der Platte liegen – alphabetisch.

    Liest die Ordnernamen, nicht eine Registry: was gelabelt wurde, steht im
    Dateisystem, und eine zweite Buchführung daneben driftet auseinander.
    """
    if not LABELED_DIR.is_dir():
        return []
    return sorted(d.name for d in LABELED_DIR.iterdir() if d.is_dir())

# ---------------------------------------------------------------------------
# LLM-Zugang (GWDG Academic Cloud, OpenAI-kompatible API)
# ---------------------------------------------------------------------------
CHAT_AI_BASE_URL = os.getenv("CHAT_AI_BASE_URL", "https://chat-ai.academiccloud.de/v1")
CHAT_AI_API_KEY = os.getenv("CHAT_AI_API_KEY", "")

# Vision-Modell fürs Labeling.
#
# Von den 16 Modellen der GWDG (Stand 23.07.2026) nehmen nur drei Bilder an:
# mistral-medium-3.5-128b, gemma-4-31b-it und qwen3-omni-30b-a3b-instruct.
#
# Gemessen auf echten Prospektseiten (150-220 Wörter, je 3 Seiten):
#   mistral-medium-3.5-128b   3/3 erfolgreich, 67-89 % der Wörter getaggt
#   qwen3-omni-30b-a3b        2/3, 49-53 %
#   gemma-4-31b-it            1/3, und dabei nur 4 % getaggt
#
# Achtung, daraus gelernt: auf einer kleinen synthetischen Testseite (23 Wörter)
# sah gemma am besten aus. Erst die echten Seiten mit 50-80 nötigen Spans pro
# Antwort zeigen, welches Modell das durchhält – gemma lief dort in
# Endlosschleifen, qwen schnitt ab. Modellwahl nie an Spielzeugbeispielen
# entscheiden.
#
# Der Modellkatalog ändert sich – Namen nicht raten, sondern prüfen:
#   curl -H "Authorization: Bearer $CHAT_AI_API_KEY" $CHAT_AI_BASE_URL/models
CHAT_AI_VISION_MODEL = os.getenv("CHAT_AI_VISION_MODEL", "mistral-medium-3.5-128b")

# Modelle der GWDG, die Bilder wirklich verarbeiten. Geprüft am 29.07.2026 mit
# einem 8x8-Testbild ("Welche Farbe hat das Bild?") gegen alle 16 Modelle.
#
# Achtung, der Test braucht zwei Runden: Mit max_tokens=20 antworteten fünf
# Modelle mit leerem Text, weil sie ihr Budget fürs Reasoning verbrauchen. Erst
# mit 800 Token zeigte sich, dass vier davon "Rot" sagen – und dass
# openai-gpt-oss-120b die Anfrage zwar ohne Fehler annimmt, aber "Ich kann das
# Bild nicht sehen" antwortet. Wer nur auf HTTP 400 prüft, hält es für ein
# Vision-Modell und labelt einen halben Korpus blind.
VISION_MODELS = [
    "mistral-medium-3.5-128b",
    "qwen3.5-397b-a17b",
    "qwen3.5-122b-a10b",
    "qwen3.6-35b-a3b",
    "qwen3.6-27b",
    "qwen3-omni-30b-a3b-instruct",
    "gemma-4-31b-it",
]


def labeled_page_ids() -> set[str]:
    """Seiten, die von *irgendeinem* Modell gelabelt sind.

    Für Entdopplung und Extraktion zählt nur, ob in eine Seite schon Arbeit
    geflossen ist – von welchem Modell, ist dort egal. Würde man hier nur ein
    Modell betrachten, könnte Schritt 06 eine Seite als Duplikat entfernen, die
    ein anderes Modell bereits gelabelt hat, und dessen Arbeit wäre weg.
    """
    return {f.stem for m in labeled_models() for f in (LABELED_DIR / m).glob("*.json")}


def default_labeled_model() -> str | None:
    """Welche Labels nimmt ein Schritt, der keinen Modellnamen bekommen hat?

    Vorrang hat das konfigurierte Vision-Modell – wer CHAT_AI_VISION_MODEL
    setzt, meint dessen Labels. Liegen die nicht vor, gewinnt der Ordner mit
    den meisten Seiten: das ist der vollständigste Datensatz und damit die
    einzige Wahl, die nicht stillschweigend auf einem Zehn-Seiten-Probelauf
    trainiert.
    """
    models = labeled_models()
    if not models:
        return None
    if model_slug(CHAT_AI_VISION_MODEL) in models:
        return model_slug(CHAT_AI_VISION_MODEL)
    return max(models, key=lambda m: len(list((LABELED_DIR / m).glob("*.json"))))

# ---------------------------------------------------------------------------
# Modelle (siehe Proposal, Abschnitt "Baseline Architecture")
# ---------------------------------------------------------------------------
LAYOUT_MODEL = "microsoft/layoutxlm-base"  # layout-aware, multilingual
TEXT_MODEL = "deepset/gbert-base"          # text-only Baseline ohne Positionsinfo

MAX_SEQ_LENGTH = 512
SEED = 13


def make_llm_client(max_retries: int = 2):
    """OpenAI-Client für die Academic Cloud. Wirft früh, wenn der Key fehlt.

    Timeout bewusst eng: die GWDG lädt Modelle bei Bedarf und hängt dabei
    gern minutenlang. Lieber nach 2 Minuten abbrechen und die Seite beim
    nächsten Lauf erneut versuchen (Skripte sind idempotent), als einen
    Batchlauf an einer einzigen Seite festhängen zu lassen.

    max_retries=0 gehört überall dorthin, wo schon eine eigene Wiederholung
    darüberliegt – etwa labeling.label_page_with_retry. Sonst multiplizieren
    sich die Versuche: dreimal außen mal dreimal innen mal 120 Sekunden sind
    18 Minuten für eine einzige Seite. Genau das hat einen Probelauf über drei
    Seiten 45 Minuten dauern lassen.
    """
    from openai import OpenAI

    if not CHAT_AI_API_KEY:
        raise RuntimeError(
            "CHAT_AI_API_KEY ist nicht gesetzt. .env anlegen, siehe .env.example."
        )
    return OpenAI(
        base_url=CHAT_AI_BASE_URL,
        api_key=CHAT_AI_API_KEY,
        timeout=120.0,
        max_retries=max_retries,
    )
