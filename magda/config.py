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
# Handannotierte Referenz. Liegt bewusst außerhalb von data/ und wird
# versioniert: generierte Artefakte sind reproduzierbar, Handarbeit nicht.
GOLD_DIR = PROJECT_ROOT / "gold"
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"

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
