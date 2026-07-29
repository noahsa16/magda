"""Wozu gehört ein Katalog? Verkaufsregion, Bundesland, Märkte.

Ohne das ist ein Katalog nach einer Woche nur noch eine sechsstellige Nummer.
Die Markt-API von Penny kennt ausschließlich die laufende Woche – wer die
Zuordnung nicht festhält, kann sie nie wieder herstellen. Deshalb liegt sie
versioniert im Projektwurzelverzeichnis, aus demselben Grund wie `gold/` und
`catalogs.json`: nicht reproduzierbar.

Ein Eintrag beantwortet die Frage, die man vor einer Kachel mit „1 Seite"
zwangsläufig stellt – nämlich welche Region das ist und warum sie sich nur an
einer einzigen Seite vom Rest der Republik unterscheidet.
"""

import json
import os
import tempfile

from magda import config


def load() -> dict[str, dict]:
    if not config.CATALOG_META_FILE.exists():
        return {}
    try:
        with open(config.CATALOG_META_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Wie bei gold/ und catalogs.json: eine kaputte Datei darf die
        # Oberfläche nicht mitreißen, die Kacheln zeigen dann eben keine Region.
        return {}
    return data if isinstance(data, dict) else {}


def save(meta: dict[str, dict]) -> None:
    """Atomar, wie bei den Gold-Dateien – die Datei wird versioniert und gemergt."""
    directory = config.CATALOG_META_FILE.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".catalog_meta.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(dict(sorted(meta.items())), f, ensure_ascii=False, indent=1)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, config.CATALOG_META_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise


def merge(neu: dict[str, dict]) -> dict[str, dict]:
    """Nimmt neue Einträge auf, ohne bestätigte durch vermutete zu ersetzen."""
    bestand = load()
    for catalog_id, eintrag in neu.items():
        vorhanden = bestand.get(catalog_id)
        if vorhanden and vorhanden.get("confirmed") and not eintrag.get("confirmed"):
            continue
        bestand[catalog_id] = eintrag
    save(bestand)
    return bestand


def label(catalog_id: str, meta: dict[str, dict] | None = None) -> str:
    """Kurzbeschriftung für eine Kachel, z. B. "Bayern · 153 Märkte"."""
    entry = (meta if meta is not None else load()).get(catalog_id)
    if not entry:
        return ""
    laender = entry.get("states") or []
    kopf = ", ".join(laender[:2]) if laender else entry.get("example_city", "")
    if len(laender) > 2:
        kopf += f" +{len(laender) - 2}"
    teile = [t for t in (kopf, f"{entry.get('markets', 0)} Märkte") if t]
    return " · ".join(teile)
