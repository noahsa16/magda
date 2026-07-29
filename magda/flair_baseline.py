"""Vergleichsarm: fertiges deutsches NER-Modell ohne jede Anpassung.

Beziffert, was man geschenkt bekommt – und damit, was die Domänenanpassung
wert ist. Ohne diesen Arm bleibt „unsere Anpassung war nötig" eine Behauptung.

flair/ner-german-large ist auf CoNLL-03 German trainiert und kennt PER, LOC,
ORG und MISC. Von den acht Projekt-Labels ist damit genau eines erreichbar:
BRAND über ORG. MISC bleibt bewusst ungemappt – es sammelt Nationalitäten,
Ereignisse und Werktitel und trifft Produktnamen nur zufällig; die Zahl wäre
nicht interpretierbar.

Nebenbei ist das Modell die Arbeit, die das Proposal als Komplexitätsreferenz
für den Kurs nennt (Akbik et al. 2018) – hier wird sie nicht nur zitiert.

Der Import von flair passiert absichtlich erst in _make_sentence() und
load_tagger(): die Mapping-Logik muss ohne die optionale Abhängigkeit testbar
bleiben.
"""

from magda.labels import spans_to_bio

FLAIR_MODEL = "flair/ner-german-large"

TAG_MAPPING = {"ORG": "BRAND"}
REPORTED_LABELS = frozenset(TAG_MAPPING.values())


def restrict_to(tags: list[str], keep: frozenset[str]) -> list[str]:
    """Setzt alle Entity-Typen außer den genannten auf "O".

    Wird auf beide Seiten angewandt: Ein Modell, das PRICE gar nicht vorhersagen
    kann, darf dafür weder bestraft noch belohnt werden. Ohne die Einschränkung
    der Referenz zählte jeder Preis darin als Falsch-Negativ, und die Zahl
    beschriebe nicht mehr die BRAND-Leistung, sondern das Label-Set.
    """
    return [tag if tag != "O" and tag[2:] in keep else "O" for tag in tags]


def spans_to_project_tags(num_words: int, flair_spans: list[tuple[int, int, str]]) -> list[str]:
    """Übersetzt Flair-Spans in BIO-Tags des Projekt-Schemas.

    flair_spans sind (start, end, label) mit Wortindizes, end exklusiv. Nicht
    gemappte Flair-Label fallen hier raus. Die BIO-Erzeugung übernimmt
    spans_to_bio() – inklusive Grenzprüfung und Überlappungsregel, die dort
    schon für die LLM-Spans getestet ist.
    """
    spans = [
        {"start": start, "end": end, "label": TAG_MAPPING[label]}
        for start, end, label in flair_spans
        if label in TAG_MAPPING
    ]
    return spans_to_bio(num_words, spans)


def check_tagset(labels: set[str]) -> None:
    """Prüft am geladenen Modell, ob die gemappten Label überhaupt existieren.

    Modellkataloge ändern sich, und ein umbenanntes Label fällt sonst nicht auf:
    Das Mapping liefe leer durch, der Report stünde auf 0.000, und niemand
    wüsste, ob das Modell schlecht ist oder das Mapping tot.
    """
    missing = set(TAG_MAPPING) - labels
    if missing:
        raise RuntimeError(
            f"Modell kennt {sorted(missing)} nicht (gefunden: {sorted(labels)}). "
            "Das Mapping wäre leer und der Report 0.000 ohne erkennbaren Grund."
        )


def _tagger_labels(tagger) -> set[str]:
    """Entity-Typen des Modells, unabhängig vom Tagging-Schema.

    flair legt im label_dictionary je nach Modell "S-ORG"/"B-ORG" oder schlicht
    "ORG" ab, ältere Fassungen zudem als bytes.
    """
    labels = set()
    for item in tagger.label_dictionary.get_items():
        if isinstance(item, bytes):
            item = item.decode("utf-8")
        labels.add(item.split("-", 1)[1] if "-" in item else item)
    return labels


def _make_sentence(words: list[str]):
    """Eine Seite als vorsegmentierte flair-Sentence.

    Die Wortliste aus Schritt 02 wird als fertige Token übergeben, flairs
    eigener Tokenizer bleibt aus. Damit sitzt jede Vorhersage auf genau einem
    Wortindex – kein Rückmapping über Zeichen-Offsets, das "(1 kg = 24.95)"
    anders zerlegen würde als unsere Wortliste.

    Der eigentliche Grund ist aber die Vergleichbarkeit: So sieht Flair exakt
    dieselbe Eingabe wie GBERT. Bei abweichender Tokenisierung stünden am Ende
    zwei Zahlen nebeneinander, die nicht dasselbe messen.
    """
    from flair.data import Sentence

    return Sentence(words)


def load_tagger(model_name: str = FLAIR_MODEL):
    """Lädt das Modell und prüft sein Tagset, statt es zu glauben."""
    try:
        from flair.models import SequenceTagger
    except ImportError as exc:
        raise RuntimeError(
            "flair ist nicht installiert: pip install -r requirements-flair.txt"
        ) from exc

    tagger = SequenceTagger.load(model_name)
    check_tagset(_tagger_labels(tagger))
    return tagger


def predict_pages(pages: list[dict], tagger) -> list[list[str]]:
    """Taggt Seiten und gibt ein Projekt-BIO-Tag je Wort zurück."""
    all_tags = []
    for page in pages:
        words = [w["text"] for w in page["words"]]
        if not words:
            all_tags.append([])
            continue

        sentence = _make_sentence(words)
        tagger.predict(sentence)

        spans = []
        for span in sentence.get_spans("ner"):
            # flair zählt Token ab 1 und meint das Ende inklusiv.
            start = span.tokens[0].idx - 1
            end = span.tokens[-1].idx
            spans.append((start, end, span.get_label("ner").value))

        all_tags.append(restrict_to(spans_to_project_tags(len(words), spans), REPORTED_LABELS))
    return all_tags
