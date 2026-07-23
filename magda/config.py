"""Zentrale Konfiguration für das Magda-Projekt.

API-Zugangsdaten liegen in einer lokalen .env (siehe .env.example), damit
keine Keys im Repo landen. Alles andere (Pfade, Modellnamen) steht direkt hier.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"          # heruntergeladene Flyer-PDFs (eine Seite pro Datei)
WORDS_DIR = DATA_DIR / "words"      # Wörter + Bounding-Boxen pro Seite (JSON)
IMAGES_DIR = DATA_DIR / "images"    # gerenderte Seitenbilder (PNG)
LABELED_DIR = DATA_DIR / "labeled"  # vom LLM gelabelte Seiten (BIO-Tags)
SPLITS_DIR = DATA_DIR / "splits"    # train/dev/test-Aufteilung
EVAL_DIR = DATA_DIR / "eval"        # Evaluations-Reports als JSON (fürs Frontend)
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"

# ---------------------------------------------------------------------------
# LLM-Zugang (GWDG Academic Cloud, OpenAI-kompatible API)
# ---------------------------------------------------------------------------
CHAT_AI_BASE_URL = os.getenv("CHAT_AI_BASE_URL", "https://chat-ai.academiccloud.de/v1")
CHAT_AI_API_KEY = os.getenv("CHAT_AI_API_KEY", "")

# Vision-Modell fürs Labeling.
#
# Von den 16 Modellen der GWDG (Stand 23.07.2026) nehmen nur drei Bilder an:
# gemma-4-31b-it, mistral-medium-3.5-128b und qwen3-omni-30b-a3b-instruct.
# Auf einer Testseite mit zwei Angeboten war gemma-4-31b-it am saubersten –
# als einziges hat es die BIO-Fortsetzung richtig gesetzt ("500"=B-QUANTITY,
# "g"=I-QUANTITY). Mistral vergab dort zweimal B-, was aus einer Mengenangabe
# zwei Entitäten macht; qwen3-omni hielt Streichpreise für Rabatte.
#
# Der Modellkatalog ändert sich – Namen nicht raten, sondern prüfen:
#   curl -H "Authorization: Bearer $CHAT_AI_API_KEY" $CHAT_AI_BASE_URL/models
CHAT_AI_VISION_MODEL = os.getenv("CHAT_AI_VISION_MODEL", "gemma-4-31b-it")

# ---------------------------------------------------------------------------
# Modelle (siehe Proposal, Abschnitt "Baseline Architecture")
# ---------------------------------------------------------------------------
LAYOUT_MODEL = "microsoft/layoutxlm-base"  # layout-aware, multilingual
TEXT_MODEL = "deepset/gbert-base"          # text-only Baseline ohne Positionsinfo

MAX_SEQ_LENGTH = 512
SEED = 13


def make_llm_client():
    """OpenAI-Client für die Academic Cloud. Wirft früh, wenn der Key fehlt.

    Timeout bewusst eng: die GWDG lädt Modelle bei Bedarf und hängt dabei
    gern minutenlang. Lieber nach 2 Minuten abbrechen und die Seite beim
    nächsten Lauf erneut versuchen (Skripte sind idempotent), als einen
    Batchlauf an einer einzigen Seite festhängen zu lassen.
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
        max_retries=2,
    )
