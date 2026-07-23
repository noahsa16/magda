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
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"

# ---------------------------------------------------------------------------
# LLM-Zugang (GWDG Academic Cloud, OpenAI-kompatible API)
# ---------------------------------------------------------------------------
CHAT_AI_BASE_URL = os.getenv("CHAT_AI_BASE_URL", "https://chat-ai.academiccloud.de/v1")
CHAT_AI_API_KEY = os.getenv("CHAT_AI_API_KEY", "")

# Vision-Modell fürs Labeling. Welche Modelle verfügbar sind, listet
# https://docs.hpc.gwdg.de/services/chat-ai/ – ggf. hier anpassen.
CHAT_AI_VISION_MODEL = os.getenv("CHAT_AI_VISION_MODEL", "qwen2.5-vl-72b-instruct")

# ---------------------------------------------------------------------------
# Modelle (siehe Proposal, Abschnitt "Baseline Architecture")
# ---------------------------------------------------------------------------
LAYOUT_MODEL = "microsoft/layoutxlm-base"  # layout-aware, multilingual
TEXT_MODEL = "deepset/gbert-base"          # text-only Baseline ohne Positionsinfo

MAX_SEQ_LENGTH = 512
SEED = 13


def make_llm_client():
    """OpenAI-Client für die Academic Cloud. Wirft früh, wenn der Key fehlt."""
    from openai import OpenAI

    if not CHAT_AI_API_KEY:
        raise RuntimeError(
            "CHAT_AI_API_KEY ist nicht gesetzt. .env anlegen, siehe .env.example."
        )
    return OpenAI(base_url=CHAT_AI_BASE_URL, api_key=CHAT_AI_API_KEY)
