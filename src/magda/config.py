"""Zentrale Konfiguration für das Magda-Projekt.

API-Zugangsdaten liegen in einer lokalen .env (siehe .env.example), damit
keine Keys im Repo landen. Alles andere (Pfade, Modellnamen) steht direkt hier.
"""

from dataclasses import dataclass
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
# src/magda/config.py -> src/magda -> src -> Projektwurzel. Die Daten liegen
# neben dem Paket, nicht darin: data/ und checkpoints/ sind Arbeitsstände, die
# beim Installieren nichts zu suchen haben.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
# Abgeschlossene Vergleichsarme. Ein Geschwisterordner, bewusst nicht
# data/labeled/archiv/: `model_slug` verbietet Pfadtrenner (sonst waere
# "../../gold" ein Modellname), also waere ein verschachtelter Archivordner
# ueber `--labels-from` nicht erreichbar, und `labeled_models` listete
# "archiv" selbst als Modell. Getrennt bleibt data/labeled/ eine Antwort auf
# "womit wird gerade gearbeitet", ohne dass Erledigtes verschwindet.
LABELED_ARCHIVE_DIR = DATA_DIR / "labeled_archive"
SPLITS_DIR = DATA_DIR / "splits"    # train/dev/test-Aufteilung
EVAL_DIR = DATA_DIR / "eval"        # Evaluations-Reports als JSON (fürs Frontend)
RUNS_DIR = DATA_DIR / "runs"        # Lauf-Historie: je Lauf Metadaten-JSON + Log
AUDIT_DIR = DATA_DIR / "audit"      # Handprüfung einzelner Labels (Kandidaten + Urteile)
# Maschinell erzeugte Angebots-Gruppierungen, je Quelle ein Ordner. Bewusst
# nicht unter gold/offers/: eine Referenz, die selbst aus einem Modell kommt,
# misst Übereinstimmung und nicht Richtigkeit. Der getrennte Pfad zwingt jede
# Zahl dazu, ihre Herkunft mitzunennen.
OFFER_GROUPS_DIR = DATA_DIR / "offer_groups"
# Seiten, die magda dedupe als Beinah-Duplikat aussortiert hat. Löschen
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
# Von der Demo hochgeladene oder aus einer Katalog-URL zusammengesetzte PDFs
# samt ihrem Ergebnis-JSON und Seitenbildern. Anders als data/raw/ keine
# Ernte, sondern beliebiger Nutzer-Input mit einer vom Server vergebenen ID
# (siehe magda.uploads) statt eines Dateinamens - deshalb gitignored statt
# versioniert.
UPLOADS_DIR = DATA_DIR / "uploads"


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
    """Ordner mit den Labels genau eines Modells, aktiv oder archiviert.

    Der Rueckfall ins Archiv haelt `magda agreement` und `magda gold` fuer
    abgeschlossene Arme am Leben, ohne dass jemand einen Pfad tippen muss.
    Aktiv hat Vorrang, und die Richtung ist nicht beliebig: andersherum
    schriebe ein Labellauf nach data/labeled/ und gelesen wuerde aus dem
    Archiv - eine Differenz, die an keiner Zahl auffaellt.

    Ein unbekannter Name zeigt auf den aktiven Ordner, damit ein neuer Lauf
    nicht ins Archiv schreibt.
    """
    slug = model_slug(model)
    archived = LABELED_ARCHIVE_DIR / slug
    if archived.is_dir() and not (LABELED_DIR / slug).is_dir():
        return archived
    return LABELED_DIR / slug


def archived_models() -> list[str]:
    """Modelle, deren Arm abgeschlossen ist - alphabetisch."""
    if not LABELED_ARCHIVE_DIR.is_dir():
        return []
    return sorted(d.name for d in LABELED_ARCHIVE_DIR.iterdir() if d.is_dir())


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

    Das Archiv zählt mit. Es aus dem Scan zu nehmen wäre genau derselbe
    Fehler, nur eine Ebene höher: die Seite ist gelabelt, der Ordner steht
    bloß woanders.
    """
    return {
        f.stem
        for root, models in ((LABELED_DIR, labeled_models()),
                             (LABELED_ARCHIVE_DIR, archived_models()))
        for m in models
        for f in (root / m).glob("*.json")
    }


# Die Referenz des Projekts (Teamentscheidung, 30.07.2026), bekräftigt am
# 10.08.2026: gelabelt wird mit sonnet-5, nie mit mistral oder qwen. Alle
# berichteten Zahlen hängen daran, dass dieselbe Quelle benutzt wurde.
#
# Bewusst *nicht* `default_labeled_model()`: das gibt CHAT_AI_VISION_MODEL den
# Vorrang und liefert deshalb `mistral-medium-3.5-128b`. Wer den kanonischen
# Lauf daran festmacht, gibt dem Inhalt einer .env Namensgewalt über
# Checkpoints, an denen berichtete Zahlen hängen.
CANONICAL_LABELS = "sonnet-5"


def default_labeled_model() -> str | None:
    """Welche Labels nimmt ein Schritt, der keinen Modellnamen bekommen hat?

    Vorrang hat `CANONICAL_LABELS`, also die Referenz des Projekts. Erst
    danach das konfigurierte Vision-Modell, zuletzt der Ordner mit den
    meisten Seiten.

    Die erste Stufe fehlte lange, und sie hat leise Zahlen verschoben: mit
    `CHAT_AI_VISION_MODEL` an der Spitze zeigte der Default auf
    `mistral-medium-3.5-128b` – ein Modell, mit dem hier gar nicht gelabelt
    wird. Gemessen am 11.08.2026: `magda offers-verify` fand über dieselbe
    Gruppierung mit Mistral-Labels **399** Preise (Genauigkeit 0.927,
    Abdeckung 0.446), mit sonnet-5 dagegen **494** (0.936, 0.478). Ein
    Viertel mehr Preise, dieselbe Rechnung – die Zahl beantwortete eine
    andere Frage, ohne dass irgendwo „mistral" stand.
    Über die Größe allein wäre es auch nicht gutgegangen: `sonnet-5`,
    `sonnet-5-app` und der Mistral-Ordner haben alle 296 Seiten, und dann
    entscheidet die Sortierreihenfolge.
    """
    models = labeled_models()
    if not models:
        return None
    if model_slug(CANONICAL_LABELS) in models:
        return model_slug(CANONICAL_LABELS)
    if model_slug(CHAT_AI_VISION_MODEL) in models:
        return model_slug(CHAT_AI_VISION_MODEL)
    return max(models, key=lambda m: len(list((LABELED_DIR / m).glob("*.json"))))

# ---------------------------------------------------------------------------
# Modelle (siehe Proposal, Abschnitt "Baseline Architecture")
# ---------------------------------------------------------------------------
LAYOUT_MODEL = "microsoft/layoutxlm-base"  # layout-aware, multilingual
TEXT_MODEL = "deepset/gbert-base"          # text-only Baseline ohne Positionsinfo
LILT_MODEL = "nielsr/lilt-xlm-roberta-base"  # Layout ohne visuellen Backbone
XLMR_MODEL = "xlm-roberta-base"            # derselbe Textencoder, ohne Layout


@dataclass(frozen=True)
class Variant:
    """Ein Trainingsarm: welches Vormodell, welche Eingaben es braucht.

    Vier Arme, deren Sinn in den *Unterschieden* liegt – jeder Schritt der
    Kette fügt genau eine Sache hinzu:

        xlmr  ──+Layout──▶  lilt  ──+Vision──▶  layoutxlm

    Deshalb teilen sich `xlmr`, `lilt` und `layoutxlm` den Textencoder. Ohne
    `xlmr` wäre "LayoutXLM gegen GBERT" eine Differenz mit zwei Ursachen
    gleichzeitig, und keine davon zuschreibbar; `gbert` steht daneben als der
    beste deutsche Textencoder, nicht als Glied dieser Kette.

    `boxes` sagt, *wie* die Positionen ins Modell kommen, und das ist kein
    Detail: LayoutXLMs Tokenizer breitet sie über `boxes=` selbst auf die
    Subwords aus, LiLTs XLM-R-Tokenizer kennt das Argument nicht und braucht
    `alignment.subword_boxes`. Ein Boolean reichte, solange es zwei Arme gab.
    """

    name: str
    model_name: str
    boxes: str  # "none" | "manual" | "tokenizer"
    image: bool


VARIANTS = {
    "gbert": Variant("gbert", TEXT_MODEL, "none", False),
    "xlmr": Variant("xlmr", XLMR_MODEL, "none", False),
    "lilt": Variant("lilt", LILT_MODEL, "manual", False),
    "layoutxlm": Variant("layoutxlm", LAYOUT_MODEL, "tokenizer", True),
}


def variant_spec(name: str) -> Variant:
    """Wirft bei unbekanntem Namen, statt still auf einen Default zu fallen –
    ein Tippfehler soll nicht einen anderen Arm trainieren als gemeint."""
    return VARIANTS[name]

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
