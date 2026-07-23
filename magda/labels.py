"""Entity-Schema für Angebots-Extraktion.

Stand: Entwurf aus dem Proposal. Das endgültige Label-Set legen wir fest,
sobald wir die ersten gelabelten Seiten gesichtet haben (Datenphase).
"""

# Reihenfolge ist fix, weil daraus die Label-IDs abgeleitet werden.
# Nachträglich also nur hinten anfügen, sonst passen alte Checkpoints nicht mehr.
ENTITY_TYPES = [
    "PRODUCT",    # Produktbezeichnung, z.B. "Rinderhackfleisch"
    "BRAND",      # Marke, z.B. "Coca-Cola"
    "PRICE",      # Aktionspreis, z.B. "1.99"
    "OLD_PRICE",  # durchgestrichener Originalpreis
    "QUANTITY",   # Menge/Gewicht, z.B. "500 g" oder "6 x 1,5 l"
    "DISCOUNT",   # Rabattangabe, z.B. "-33%"
    "VALID",      # Gültigkeitszeitraum, z.B. "Mo, 9.3. bis Sa, 14.3."
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
