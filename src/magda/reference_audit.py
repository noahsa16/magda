"""Regelbasierte Hinweise auf Referenzprobleme, ohne Labels zu korrigieren.

Die Auswahl liest weder Vorhersagen noch Modellnamen. Hinweise sind keine
menschlichen Urteile: auch ein konsistenter Text kann je nach Kontext einen
anderen Typ haben. Ohne Entscheidung am Bild bleiben sie unbestätigte Hinweise.
"""

import json
import re
from collections import Counter, defaultdict

from magda import config, gold, offers_gold, provenance
from magda.labels import ENTITY_TYPES, validate_spans

NUMERIC_TYPES = {"PRICE", "OLD_PRICE", "APP_PRICE", "UNIT_PRICE", "QUANTITY", "DISCOUNT"}


def audit_reference(page_ids):
    issues, inventory, occurrences = [], [], defaultdict(list)
    for page_id in page_ids:
        page = json.loads((config.WORDS_DIR / f"{page_id}.json").read_text())
        paths = {"spans": config.GOLD_DIR / f"{page_id}.json",
                 "groups": config.GOLD_DIR / "offers" / f"{page_id}.json"}
        records = {key: json.loads(path.read_text()) for key, path in paths.items()}
        words = page["words"]
        spans, groups = records["spans"].get("spans", []), records["groups"].get("groups", [])
        span_errors = validate_spans(spans, len(words))
        group_errors = offers_gold.validate_groups(groups, len(words))

        def add(code, detail, **location):
            issue = {"page_id": page_id, "code": code, "detail": detail, **location}
            issue["id"] = provenance.digest(issue)[:16]
            issue["status"] = "unadjudicated"
            issues.append(issue)

        for kind, record in records.items():
            if record.get("status") != "done" or record.get("words_hash") != gold.words_hash(words):
                add("invalid_status_or_hash", f"{kind}: Abschluss oder Wortbindung ungültig.")
        for error in span_errors + group_errors:
            add("invalid_structure", error)
        inventory.append({
            "page_id": page_id, "words": len(words), "spans": len(spans), "groups": len(groups),
            "labels": dict(Counter(s.get("label") for s in spans)),
            "hashes": {kind: provenance.file_digest(path) for kind, path in paths.items()},
            "words_sha256": provenance.file_digest(config.WORDS_DIR / f"{page_id}.json"),
            "image_sha256": (provenance.file_digest(config.IMAGES_DIR / f"{page_id}.png")
                             if (config.IMAGES_DIR / f"{page_id}.png").is_file() else None),
            "provenance": {kind: {"annotator": record.get("annotator"),
                                   "provenance": record.get("provenance")}
                           for kind, record in records.items()},
        })
        if span_errors or group_errors:
            continue
        assigned = {index: group_id for group_id, group in enumerate(groups) for index in group}
        for span in spans:
            start, end, label = (span[key] for key in ("start", "end", "label"))
            text = " ".join(w["text"] for w in words[start:end])
            location = {"start": start, "end": end, "label": label, "text": text}
            if label in NUMERIC_TYPES and not re.search(r"\d", text):
                add("numeric_without_digit", "Numerisches Label enthält keine Ziffer.", **location)
            if label == "QUANTITY" and re.match(r"(?i)^je\s", text):
                add("quantity_prefix", "Nach bestehender Konvention gehört 'je' nicht zur Menge.", **location)
            if label == "QUANTITY" and re.search(r"(?i)entspricht|kaufen|sparen", text):
                add("quantity_campaign_text", "Mengenangabe enthält Aktions- oder Preistext.", **location)
            if label == "OLD_PRICE":
                context = " ".join(w["text"] for w in words[max(0, start - 4):start]).casefold()
                if context.endswith("ohne penny app"):
                    add("regular_price_marked_old", "Preis direkt nach 'ohne PENNY App': PRICE-Regel prüfen.", **location)
            if label != "VALID":
                membership = {assigned.get(index) for index in range(start, end)}
                if None in membership:
                    add("entity_not_fully_grouped", "Entity ist keinem Angebot vollständig zugeordnet.", **location)
                if len(membership - {None}) > 1:
                    add("entity_crosses_groups", "Entity überlappt mehrere Angebotsgruppen.", **location)
            normalized = re.sub(r"\s+", " ", text.casefold()).strip()
            if label in {"PRODUCT", "BRAND", "QUANTITY", "UNIT_PRICE"} and len(normalized) >= 4:
                occurrences[normalized].append({"page_id": page_id, **location})
        for group_id, group in enumerate(groups):
            members = [s for s in spans if set(range(s["start"], s["end"])) & set(group)]
            types = {s["label"] for s in members}
            if "PRODUCT" in types and "PRICE" not in types:
                add("product_group_without_regular_price",
                    "Produktgruppe hat keinen PRICE-Span und fällt aus offer-price-v2 heraus.",
                    group=group_id, labels=sorted(types))
            if "PRICE" in types and not types & {"PRODUCT", "BRAND"}:
                add("price_group_without_name", "Preisgruppe hat keinen auswertbaren Angebotsnamen.", group=group_id)
    conflicts = [
        {"text": text, "occurrences": rows, "labels": sorted({r["label"] for r in rows})}
        for text, rows in sorted(occurrences.items()) if len({r["label"] for r in rows}) > 1
    ]
    return {
        "protocol": "reference-audit-v1", "automatic_corrections": False,
        "pages": inventory, "issues": issues, "text_label_conflicts": conflicts,
        "issue_counts": dict(Counter(i["code"] for i in issues)),
        "annotation_types": ENTITY_TYPES,
        "reference_sha256": provenance.digest(inventory),
        "interpretation": "Prüfhinweise, keine gemessene Referenzfehlerrate. Kontext kann Unterschiede erklären.",
    }
