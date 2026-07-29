"""Was sich aus dem Frontend starten lässt – und mit welchen Parametern.

Der Runner kümmert sich um Prozesse, dieses Modul um Erlaubnis. `build_command`
ist die einzige Stelle, an der aus einer Nutzereingabe ein Kommando wird, und
damit die Sicherheitsgrenze: unbekannte Jobs, unbekannte Parameternamen, nicht
konvertierbare Werte und Werte außerhalb von `choices` kommen nicht durch.
Werte werden typkonvertiert und als eigene argv-Elemente übergeben, nie zu
einem String zusammengeklebt – es gibt keine Shell, die etwas interpretieren
könnte.

Pfade als config.X zur Laufzeit, damit Tests sie umbiegen können.
"""


from dataclasses import dataclass, field

from magda import config


@dataclass(frozen=True)
class Param:
    name: str
    kind: str
    label: str
    default: object | None = None
    choices: tuple[str, ...] = ()
    required: bool = False
    help: str = ""

    @property
    def key(self) -> str:
        """Name in JSON und Formular: "--max-pages" -> "max_pages"."""
        return self.name.lstrip("-").replace("-", "_")

    @property
    def positional(self) -> bool:
        return not self.name.startswith("-")


@dataclass(frozen=True)
class Job:
    script: str
    title: str
    what: str
    params: tuple[Param, ...] = field(default_factory=tuple)


VARIANTS = ("gbert", "layoutxlm")

JOBS: dict[str, Job] = {
    "00_harvest_week": Job(
        script="00_harvest_week",
        title="Woche ernten",
        what="Holt alle 44 Regionalausgaben einer Woche und behält nur die Seiten, "
             "die es noch nicht gibt. Ohne Angabe die laufende Woche.",
        params=(
            Param("--seed", "str", "Bekannte ID einer älteren Woche",
                  help="leer lassen für die laufende Woche"),
        ),
    ),
    "01_download_flyers": Job(
        script="01_download_flyers",
        title="Prospekte laden",
        what="Holt einen Penny-Katalog und legt jede Seite einzeln als PDF in data/raw ab.",
        params=(
            Param("url", "str", "Katalog-URL", required=True,
                  help="Blätterkatalog-Adresse mit catalogId"),
            Param("--max-pages", "int", "Seiten höchstens", default=40),
        ),
    ),
    "02_extract_words": Job(
        script="02_extract_words",
        title="Wörter extrahieren",
        what="PyMuPDF liest Text und Koordinaten aus dem PDF-Textlayer und rendert je ein PNG.",
    ),
    "03_label_words": Job(
        script="03_label_words",
        title="LLM-Labeling",
        what="Ein Vision-Modell markiert Spans auf dem Seitenbild, daraus werden BIO-Tags.",
        params=(
            # choices statt Freitext: der Wert wird zum Ordnernamen unter
            # data/labeled/. Eine Auswahlliste ist hier nicht nur bequemer,
            # sie hält auch Modelle draußen, die gar keine Bilder annehmen –
            # die labelten sonst einen ganzen Ordner blind voll.
            Param(
                "--model", "choice", "Vision-Modell",
                choices=tuple(config.VISION_MODELS), default=config.CHAT_AI_VISION_MODEL,
            ),
            Param("--workers", "int", "Parallele Anfragen", default=6),
            Param("--limit", "int", "Nur so viele Seiten (Probelauf)"),
            Param("--only-gold", "flag", "Nur Gold-Seiten"),
        ),
    ),
    "04_train": Job(
        script="04_train",
        title="Training",
        what="Token-Klassifikation auf den gelabelten Seiten – einmal mit, einmal ohne Layout.",
        params=(
            Param("variant", "choice", "Variante", choices=VARIANTS, required=True),
            Param("--epochs", "int", "Epochen", default=10),
            Param("--batch-size", "int", "Batch-Größe", default=8),
            Param("--lr", "float", "Lernrate", default=5e-5),
            Param("--labels-from", "str", "Labels von Modell"),
        ),
    ),
    "05_evaluate": Job(
        script="05_evaluate",
        title="Evaluation",
        what="Entity-Level-F1 auf dem eingefrorenen Test-Split, als Report nach data/eval.",
        params=(
            Param("variant", "choice", "Variante", choices=VARIANTS, required=True),
            Param("--split", "choice", "Split", choices=("dev", "test"), default="test"),
        ),
    ),
    "06_check_duplicates": Job(
        script="06_check_duplicates",
        title="Duplikate prüfen",
        what="Findet Seiten, die sich nur in der Druckkennung oder in Kleinigkeiten "
             "unterscheiden. Ohne Häkchen wird nur berichtet, nichts gelöscht.",
        params=(
            Param("--threshold", "float", "Ähnlichkeit ab", default=0.95,
                  help="0.98 streng, 0.90 großzügig"),
            Param("--apply", "flag", "Duplikate entfernen"),
        ),
    ),
    "07_flair_baseline": Job(
        script="07_flair_baseline",
        title="Flair-Vergleichsarm",
        what="Fertiges deutsches NER-Modell ohne Anpassung. Misst nur BRAND – "
             "flair/ner-german-large kennt PER/LOC/ORG/MISC, nur ORG hat eine Entsprechung.",
        params=(
            Param("--reference", "choice", "Referenz", choices=("gold", "llm"), default="gold"),
            Param("--split", "choice", "Split", choices=("dev", "test", "all"), default="test"),
            Param("--model", "str", "Modell", default="flair/ner-german-large"),
        ),
    ),
}


def _coerce(param: Param, raw: object) -> object:
    if param.kind == "choice":
        text = str(raw)
        if text not in param.choices:
            raise ValueError(
                f"{param.label}: {text!r} ist nicht erlaubt "
                f"({' oder '.join(param.choices)})."
            )
        return text
    if param.kind in ("int", "float"):
        caster = int if param.kind == "int" else float
        try:
            return caster(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(f"{param.label}: {raw!r} ist keine Zahl.") from None
    text = str(raw)
    # argparse liest ein führendes "-" als Option. Ein positionaler Wert wie
    # "--help" würde damit etwas anderes tun, als der Nutzer eingegeben hat.
    if param.positional and text.startswith("-"):
        raise ValueError(f"{param.label} darf nicht mit einem Bindestrich beginnen.")
    return text


def build_command(job: str, values: dict) -> list[str]:
    """Validiert die Eingaben und baut das argv. Wirft ValueError bei allem Unerwarteten."""
    spec = JOBS.get(job)
    if spec is None:
        raise ValueError(f"Unbekannter Schritt: {job}")

    known = {p.key: p for p in spec.params}
    for key in values:
        if key not in known:
            raise ValueError(f"Unbekannter Parameter für {job}: {key}")

    positional: list[str] = []
    options: list[str] = []
    for param in spec.params:
        # Bewusst ohne Rückfall auf param.default: was nicht übergeben wurde,
        # landet auch nicht im argv. Den Default kennt argparse im Skript
        # ohnehin, und zwei Quellen für denselben Wert driften auseinander.
        # `default` dient nur dem Frontend zum Vorbelegen des Feldes.
        raw = values.get(param.key)

        # Ein Schalter trägt keinen Wert: gesetzt heißt, der Name steht im argv.
        if param.kind == "flag":
            if raw in (True, "true", "True", "1", "on", "yes"):
                options.append(param.name)
            continue

        # Ein leeres Formularfeld ist keine Eingabe, sondern eine ausgelassene.
        if raw is None or raw == "":
            if param.required:
                raise ValueError(f"{spec.title}: {param.label} wird gebraucht.")
            continue
        value = str(_coerce(param, raw))
        if param.positional:
            positional.append(value)
        else:
            options += [param.name, value]

    script = config.PROJECT_ROOT / "scripts" / f"{spec.script}.py"
    return [config.PYTHON, "-u", str(script), *positional, *options]


def describe() -> list[dict]:
    """Der Katalog als JSON für das Frontend, das daraus seine Formulare baut."""
    return [
        {
            "job": job,
            "title": spec.title,
            "what": spec.what,
            "params": [
                {
                    "key": p.key,
                    "label": p.label,
                    "kind": p.kind,
                    "default": p.default,
                    "choices": list(p.choices),
                    "required": p.required,
                    "help": p.help,
                }
                for p in spec.params
            ],
        }
        for job, spec in JOBS.items()
    ]
