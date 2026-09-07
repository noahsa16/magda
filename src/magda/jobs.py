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


import re
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
    # Nur für kind == "pattern": ein voller Regex-Match, den der Wert
    # erfüllen muss. Für Werte, die serverseitig zu einem Pfad werden
    # (upload_id) - eine Auswahlliste wie bei "choice" geht dort nicht,
    # weil die gültigen Werte zur Laufzeit entstehen.
    pattern: str = ""

    @property
    def key(self) -> str:
        """Name in JSON und Formular: "--max-pages" -> "max_pages"."""
        return self.name.lstrip("-").replace("-", "_")

    @property
    def positional(self) -> bool:
        return not self.name.startswith("-")


@dataclass(frozen=True)
class Job:
    title: str
    what: str
    params: tuple[Param, ...] = field(default_factory=tuple)


# Aus der Registry, nicht abgeschrieben: eine zweite Liste derselben Arme
# driftet, und das Frontend böte dann einen an, den `magda train` nicht kennt.
VARIANTS = tuple(config.VARIANTS)

JOBS: dict[str, Job] = {
    "harvest": Job(
        title="Woche ernten",
        what="Holt alle 44 Regionalausgaben einer Woche und behält nur die Seiten, "
             "die es noch nicht gibt. Ohne Angabe die laufende Woche.",
        params=(
            Param("--seed", "str", "Bekannte ID einer älteren Woche",
                  help="leer lassen für die laufende Woche"),
        ),
    ),
    "download": Job(
        title="Prospekte laden",
        what="Holt einen Penny-Katalog und legt jede Seite einzeln als PDF in data/raw ab.",
        params=(
            Param("url", "str", "Katalog-URL", required=True,
                  help="Blätterkatalog-Adresse mit catalogId"),
            Param("--max-pages", "int", "Seiten höchstens", default=40),
        ),
    ),
    "extract": Job(
        title="Wörter extrahieren",
        what="PyMuPDF liest Text und Koordinaten aus dem PDF-Textlayer und rendert je ein PNG.",
        params=(
            Param(
                "--render-missing", "flag", "Nur fehlende Seitenbilder",
                help="Rendert fehlende PNGs nach und lässt data/words/ unangetastet – "
                     "der Weg für einen frischen Klon, in dem die Wortlisten schon aus "
                     "git kommen und der normale Lauf deshalb kein Bild schreibt.",
            ),
        ),
    ),
    "label": Job(
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
    "train": Job(
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
    "eval": Job(
        title="Evaluation",
        what="Entity-Level-F1 auf dem eingefrorenen Test-Split, als Report nach data/eval.",
        params=(
            Param("variant", "choice", "Variante", choices=VARIANTS, required=True),
            Param("--split", "choice", "Split", choices=("dev", "test"), default="test"),
            Param("--labels-from", "str", "Labels von Modell"),
        ),
    ),
    "predict": Job(
        title="Modellvorhersagen exportieren",
        what="Schreibt Wortlabels des gewählten Checkpoints für die anschließende Auswertung.",
        params=(
            Param("variant", "choice", "Modell", choices=VARIANTS, required=True),
            Param("--split", "choice", "Split", choices=("train", "dev", "test"), default="test"),
            Param("--labels-from", "str", "Labelquelle", default=config.CANONICAL_LABELS),
        ),
    ),
    "eval-gold": Job(
        title="Student gegen Handspans",
        what="Entity-F1 aus vorhandenen Vorhersagen. Alle angeforderten Handspans müssen fertig sein.",
        params=(
            Param("variant", "choice", "Modell", choices=VARIANTS, required=True),
            Param("--pages", "choice", "Seitenliste", required=True,
                  choices=("data/eval/test_cluster_pages.txt",), default="data/eval/test_cluster_pages.txt"),
        ),
    ),
    "blackbox-eval": Job(
        title="Blackbox gegen Handreferenz",
        what="Vergleicht Preisvarianten mit fertigen Handspans und Handgruppen. "
             "Vorhandene Blackbox-Antworten wiederverwenden spart einen API-Aufruf.",
        params=(
            Param("--pages", "choice", "Seitenliste", required=True,
                  choices=("data/eval/test_cluster_pages.txt",), default="data/eval/test_cluster_pages.txt"),
            Param("--predictions", "choice", "Eigene Vorhersagen", choices=VARIANTS, default="layoutxlm"),
            Param("--grouper", "choice", "Gruppierung", choices=("pair-model", "heuristic"), default="pair-model"),
            Param("--reference-groups", "choice", "Referenz", choices=("gold",), default="gold"),
            Param("--blackbox-from", "pattern", "Gespeicherter Blackbox-Report",
                  pattern=r"data/eval/blackbox_test_[A-Za-z0-9_.-]+\.json",
                  default="data/eval/blackbox_test_gemma-4-31b-it_pair-model_ref-teacher.json",
                  help="Leer lassen für einen neuen API-Lauf; sonst Modell aus dem Report."),
            Param("--model", "choice", "Blackbox-Modell bei neuem API-Lauf",
                  choices=tuple(config.VISION_MODELS), default=config.CHAT_AI_VISION_MODEL),
            Param("--dry-run", "flag", "Verdrahtung prüfen, keine Kennzahlen berechnen"),
        ),
    ),
    "significance": Job(
        title="Konfidenzintervalle",
        what="Cluster-Bootstrap für GBERT gegen LayoutXLM auf dem Testsplit; liest vorhandene Vorhersagen.",
        params=(
            Param("--labels-from", "str", "Labelquelle", required=True, default=config.CANONICAL_LABELS),
            Param("--resamples", "int", "Bootstrap-Wiederholungen", default=10000),
        ),
    ),
    "dedupe": Job(
        title="Duplikate prüfen",
        what="Findet Seiten, die sich nur in der Druckkennung oder in Kleinigkeiten "
             "unterscheiden. Ohne Häkchen wird nur berichtet, nichts gelöscht.",
        params=(
            Param("--threshold", "float", "Ähnlichkeit ab", default=0.95,
                  help="0.98 streng, 0.90 großzügig"),
            Param("--apply", "flag", "Duplikate entfernen"),
        ),
    ),
    "flair": Job(
        title="Flair-Vergleichsarm",
        what="Fertiges deutsches NER-Modell ohne Anpassung. Misst nur BRAND – "
             "flair/ner-german-large kennt PER/LOC/ORG/MISC, nur ORG hat eine Entsprechung.",
        params=(
            Param("--reference", "choice", "Referenz", choices=("gold", "llm"), default="gold"),
            Param("--split", "choice", "Split", choices=("dev", "test", "all"), default="test"),
            Param("--model", "str", "Modell", default="flair/ner-german-large"),
        ),
    ),
    "gold": Job(
        title="Labels gegen Gold",
        what="Misst jeden Modellordner unter data/labeled/ gegen die handannotierte "
             "Referenz – die Entscheidungsgrundlage für die Modellwahl.",
        params=(
            Param("--per-label", "flag", "Aufschlüsselung je Entity-Typ"),
        ),
    ),
    "agreement": Job(
        title="Modelle gegeneinander",
        what="Wo widersprechen sich zwei Labeling-Modelle? Misst über alle Seiten "
             "statt nur über die annotierten und sortiert nach Annotationsnutzen.",
        params=(
            # Freitext statt choices: die Modellordner entstehen zur Laufzeit,
            # eine feste Liste wäre bei jedem neuen Lauf veraltet. build_command
            # prüft weiterhin Typ und führendes "-"; die Skripte lehnen
            # unbekannte Ordner selbst ab.
            Param("model_a", "str", "Modell A", required=True),
            Param("model_b", "str", "Modell B", required=True),
            Param("--top", "int", "Wie viele Seiten auflisten", default=20),
        ),
    ),
    "extract-pdf": Job(
        title="Demo: PDF verarbeiten",
        what="Verarbeitet ein hochgeladenes oder aus einer Katalog-URL importiertes "
             "PDF direkt zu Angeboten - für die Demo-Seite, ohne data/ zu berühren.",
        params=(
            # kind="pattern" statt "str": upload_id wird in build_command zu
            # einem Pfad unter UPLOADS_DIR - ohne die Musterprüfung wäre eine
            # beliebige Zeichenkette ein potenzieller Pfad.
            Param(
                "upload_id", "pattern", "Upload", required=True,
                pattern=r"[0-9a-f]{32}",
                help="Server-vergebene ID aus /api/demo/upload, kein Dateiname",
            ),
            Param(
                "--variant", "choice", "Modell",
                choices=("gbert", "layoutxlm"), default="gbert",
            ),
        ),
    ),
}


def _coerce(param: Param, raw: object) -> object:
    if param.kind == "pattern":
        text = str(raw)
        if not re.fullmatch(param.pattern, text):
            raise ValueError(f"{param.label}: {text!r} hat nicht das erwartete Format.")
        return text
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

        # upload_id ist keine Eingabe, die als Text im Kommando landet: erst
        # hier, nach der Musterprüfung oben, wird aus der geprüften ID ein
        # Pfad unter UPLOADS_DIR. Der Nutzer gibt so nie selbst einen Pfad
        # ein, auch nicht mittelbar über die ID - genau das war die Vorgabe
        # für den Job "extract-pdf".
        if param.key == "upload_id":
            value = str(config.UPLOADS_DIR / f"{value}.pdf")

        if param.positional:
            positional.append(value)
        else:
            options += [param.name, value]

    if job == "extract-pdf":
        # Ziel-JSON und Seitenbilder liegen fest unter derselben ID - anders
        # als upload_id oben kommt keine dieser drei Angaben vom Nutzer, sie
        # werden hier aus dem schon geprüften Wert abgeleitet.
        upload_id = str(values["upload_id"])
        options += [
            "--out", str(config.UPLOADS_DIR / f"{upload_id}.json"),
            "--images-dir", str(config.UPLOADS_DIR / upload_id),
            "--render-images",
            "--no-embed-images",
        ]

    # `python -m magda` statt des Konsolenbefehls `magda`: config.PYTHON zeigt
    # explizit auf das Projekt-venv, während der PATH davon abhängt, aus welcher
    # Umgebung die API gestartet wurde.
    return [config.PYTHON, "-u", "-m", "magda", job, *positional, *options]


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
