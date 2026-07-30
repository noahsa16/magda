"""Entity-Schema für Angebots-Extraktion.

Stand: Entwurf aus dem Proposal. Das endgültige Label-Set legen wir fest,
sobald wir die ersten gelabelten Seiten gesichtet haben (Datenphase).
"""

# Reihenfolge ist fix, weil daraus die Label-IDs abgeleitet werden.
# Nachträglich also nur hinten anfügen, sonst passen alte Checkpoints nicht mehr.
ENTITY_TYPES = [
    "PRODUCT",     # Produktbezeichnung, z.B. "Rinderhackfleisch"
    "BRAND",       # Marke, z.B. "Coca-Cola"
    "PRICE",       # Aktionspreis, z.B. "1.99"
    "OLD_PRICE",   # durchgestrichener Originalpreis
    "QUANTITY",    # Menge/Gewicht, z.B. "500 g" oder "6 x 1,5 l"
    "DISCOUNT",    # Rabattangabe, z.B. "-33%"
    "VALID",       # Gültigkeitszeitraum, z.B. "Mo, 9.3. bis Sa, 14.3."
    # Ab hier nachträglich ergänzt – nur anhängen, nie einschieben, sonst
    # verschieben sich die Label-IDs und alte Checkpoints passen nicht mehr.
    "UNIT_PRICE",  # Grundpreis, z.B. "(1 kg = 24.95)"
    # Penny bewirbt viele Angebote mit einem zweiten, niedrigeren Preis, den
    # nur App-Nutzer zahlen ("mit PENNY App 1.59"). Ohne eigenes Label ist er
    # nicht unterzubringen: Als PRICE stünden zwei Aktionspreise nebeneinander,
    # als OLD_PRICE wäre der günstigste Preis der Seite als Streichpreis
    # markiert. Beides haben die Annotatoren unabhängig voneinander als
    # Problem gemeldet, jeweils anders gelöst.
    "APP_PRICE",   # nur mit PENNY App, z.B. "mit PENNY App 1.59"
]

# BIO-Schema: "O" + je ein B-/I-Tag pro Entity-Typ
LABELS = ["O"]
for _t in ENTITY_TYPES:
    LABELS.append(f"B-{_t}")
    LABELS.append(f"I-{_t}")

label2id = {label: i for i, label in enumerate(LABELS)}
id2label = {i: label for label, i in label2id.items()}


def spans_to_bio(num_words: int, spans: list[dict]) -> list[str]:
    """Wandelt Wort-Spans in eine BIO-Tagfolge um.

    spans: Liste von {"start": int, "end": int, "label": str}, wobei start/end
    Wortindizes sind (end exklusiv, wie bei range()). Ungültige Spans werden
    verworfen statt einen Abbruch zu provozieren – die kommen vom LLM und
    sind gelegentlich Murks. Bei Überlappungen gewinnt der zuerst genannte Span.
    """
    tags = ["O"] * num_words

    for span in spans:
        start, end, entity = span.get("start"), span.get("end"), span.get("label")
        if entity not in ENTITY_TYPES:
            continue
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < 0 or end > num_words or start >= end:
            continue
        # Überlappung mit bereits vergebenem Span? Dann überspringen.
        if any(tags[i] != "O" for i in range(start, end)):
            continue

        tags[start] = f"B-{entity}"
        for i in range(start + 1, end):
            tags[i] = f"I-{entity}"

    return tags


def bio_to_spans(tags: list[str]) -> list[dict]:
    """Umkehrung von spans_to_bio: BIO-Tagfolge zurück in Spans.

    Gebraucht überall dort, wo gespeicherte Labels nachbearbeitet oder
    verglichen werden – auf der Platte stehen Tags, gearbeitet wird mit
    Spans. Ein I-Tag ohne vorangehendes B-Tag beginnt einen eigenen Span,
    statt still zu verschwinden: kaputte Tagfolgen sollen sichtbar bleiben.
    """
    spans: list[dict] = []
    for i, tag in enumerate(tags):
        if tag == "O":
            continue
        entity = tag[2:]
        previous = spans[-1] if spans else None
        continues = (
            tag.startswith("I-")
            and previous is not None
            and previous["label"] == entity
            and previous["end"] == i
        )
        if continues:
            previous["end"] = i + 1
        else:
            spans.append({"start": i, "end": i + 1, "label": entity})
    return spans


def validate_spans(spans: list[dict], num_words: int) -> list[str]:
    """Prüft handannotierte Spans und sammelt alle Fehler ein.

    Gibt Meldungen zurück statt zu werfen, damit die API dem Frontend in einer
    Antwort sagen kann, was alles nicht stimmt. Anders als spans_to_bio() wird
    hier nichts stillschweigend verworfen: Bei Handarbeit ist ein ungültiger
    Span ein Fehler, kein Rauschen.
    """
    errors = []
    occupied: set[int] = set()

    for span in spans:
        start, end, entity = span.get("start"), span.get("end"), span.get("label")

        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"Span {start}-{end}: start und end müssen Zahlen sein.")
            continue
        if start < 0 or end > num_words or start >= end:
            errors.append(
                f"Span {start}-{end} liegt außerhalb von 0-{num_words} oder ist leer."
            )
            continue
        if entity not in ENTITY_TYPES:
            errors.append(f"Span {start}-{end}: unbekanntes Label {entity!r}.")
            continue

        overlap = occupied & set(range(start, end))
        if overlap:
            errors.append(f"Span {start}-{end} überlappen mit einem anderen Span.")
            continue
        occupied |= set(range(start, end))

    return errors
