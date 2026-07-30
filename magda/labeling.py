"""Schritt 2 der Pipeline: automatisches Labeln der Wörter per LLM.

Das LLM bekommt das Seitenbild plus die nummerierte Wortliste und soll
Spans über Wortindizes zurückgeben (start/end/label). Spans statt
Wort-für-Wort-Labels, weil LLMs bei "gib mir exakt N Labels" gern die
Länge verfehlen – Spans lassen sich dagegen sauber validieren und
notfalls einzeln verwerfen (passiert in labels.spans_to_bio).
"""

import base64
import json
import re
import time

from openai import OpenAI

from magda.labels import spans_to_bio

# Jede Regel unten steht für einen gemessenen Fehler, nicht für eine Vermutung.
# Grundlage ist der Vergleich der Mistral-Labels gegen die drei handannotierten
# Gold-Seiten (scripts/08_compare_labels.py, micro-F1 0.306):
#
#   UNIT_PRICE   0 von 18 richtig – die Klammer landete durchweg in QUANTITY
#   QUANTITY     0 von 18 richtig – "je" wurde in den Span gezogen
#   PRODUCT   19 Spans verfehlt   – "oder", "Versch. Sorten", "je …" mit drin
#   BRAND     12 Spans verfehlt   – die Marke verschluckte den Produktnamen
#   PRICE/OLD_PRICE 0.85/0.81     – funktioniert, bleibt wie es ist
#
# Der schwerwiegendste Befund war, dass die alte Fassung dem Modell an zwei
# Stellen das Gegenteil des Goldstandards beibrachte: Sie erklärte "je 200 g"
# zum QUANTITY-Span und zeigte im Beispiel UNIT_PRICE als Teil der Preiszeile.
# Ein Prompt, der gegen die eigene Referenz arbeitet, ist nicht ungenau,
# sondern falsch.
#
# Aufbau und Ton sind an den Extractor-Prompt aus dem Vorgängerprojekt
# angelehnt (notebooks/pdf_extractor(op).py): benannte Erkennungsmerkmale
# statt vager Anweisungen, kontrastive Richtig/Falsch-Paare, und eine
# ausdrückliche Liste dessen, was NICHT gelabelt wird.
_PROMPT = """\
Du siehst eine Seite aus einem deutschen Supermarkt-Prospekt (Penny) sowie die
Liste aller Wörter auf der Seite, jeweils mit Index.

Markiere Entitäten als Spans über die Wortindizes. Erlaubte Labels:

PRODUCT     Produktbezeichnung inkl. Sortenangabe, ohne Menge und Preis
BRAND       Markenname
PRICE       Aktionspreis (der Preis, den man zahlt)
OLD_PRICE   Durchgestrichener oder höherer Vergleichspreis
QUANTITY    Füllmenge: Zahl + Einheit
UNIT_PRICE  Grundpreis in runden Klammern
DISCOUNT    Rabattangabe, z.B. "-33%"
VALID       Gültigkeitszeitraum

═══════════════════════════════════════════════════════════════════════
REGEL 1 — Der Grundpreis ist IMMER ein eigener Span (häufigster Fehler)
═══════════════════════════════════════════════════════════════════════
Alles in runden Klammern der Form "(1 kg = 11.98)" oder "(1 l = 0.70)" ist
UNIT_PRICE. Der Span beginnt beim Wort mit der öffnenden Klammer und endet
beim Wort mit der schließenden Klammer.

  Richtig: QUANTITY="500 g"   UNIT_PRICE="(1 kg = 11.98)"
  Falsch:  QUANTITY="500 g (1 kg = 11.98)"      <- Klammer gehört nicht dazu
  Falsch:  QUANTITY="(1 kg = 11.98)"            <- das ist kein QUANTITY
  Falsch:  PRICE="0.88 (1 l = 0.70)"            <- zwei getrennte Angaben

═══════════════════════════════════════════════════════════════════════
REGEL 2 — QUANTITY ist nur Zahl und Einheit, sonst nichts
═══════════════════════════════════════════════════════════════════════
"je", "ca.", "Versch. Sorten", "Stück", "zzgl.", "Pfand" gehören NICHT in
den QUANTITY-Span - dort steht nur die Füllmenge.

  Richtig: "500 g" · "1,25 l" · "6 x 1,5 l" · "500-g-Schale"
  Falsch:  "je 500 g" · "je 1,25 l" · "Sorten, je 150 g"

═══════════════════════════════════════════════════════════════════════
REGEL 3 — BRAND ist nur der Markenname, nicht das Produkt
═══════════════════════════════════════════════════════════════════════
Ein Angebot beginnt meist mit der Marke in GROSSBUCHSTABEN, danach folgt der
Produktname in normaler Schreibweise. Der BRAND-Span endet beim ersten Wort,
das nicht mehr durchgehend groß geschrieben ist.

  Richtig: BRAND="MÜHLENHOF"  PRODUCT="Frische Hähnchen- Brustfilets"
  Richtig: BRAND="MAGICO KAFFEE"  PRODUCT="Löslicher Kaffee Classic,"
  Richtig: BRAND="ORTO MIO"   PRODUCT="Antipasticreme,"
  Falsch:  BRAND="MÜHLENHOF Frische Hähnchen- Brustfilets"
  Falsch:  BRAND="LENOR Waschmittel*"
  Falsch:  BRAND="MARATHON Isotonischer"

Im Korpus belegte Marken (die Liste ist nicht vollständig, sie zeigt die Form):
MÜHLENHOF, MILPRIMA, BÄCKERKRÖNUNG, MAGICO, MARATHON, PARADISO, GREENLAND,
BRAVO, ORTO MIO, SIMPLY SUNNY, NAMDONG, SAN FABIO, KNORR, FERRERO,
DR. OETKER, JACOBS, LENOR, ZEWA, BARILLA, KROMBACHER, GÉRAMONT.

═══════════════════════════════════════════════════════════════════════
REGEL 4 — Ein Preis-Span ist genau EIN Wort: die Zahl
═══════════════════════════════════════════════════════════════════════
Preise stehen paarweise beieinander. Jede Zahl wird ein eigener Span über
genau ein Wort. Nie zwei Preise in einem Span, nie ein Wort dazu.

Wörter, die neben einem Preis stehen und NICHT in den Span gehören:
"UVP", "statt", "Aktion", "je", "nur", "ab", "Einzelpreis".

  Richtig: OLD_PRICE="10.49"                 (für den Text "UVP 10.49")
  Falsch:  OLD_PRICE="UVP 10.49"             <- "UVP" ist kein Preis
  Falsch:  PRICE="Aktion"                    <- das ist eine Überschrift
  Falsch:  PRICE="0.88 0.77"                 <- zwei Preise, zwei Spans

Welcher der beiden ist PRICE? Vergleiche die ZAHLENWERTE: die kleinere Zahl
ist PRICE, die größere OLD_PRICE. Das gilt immer, auch wenn die größere Zahl
zuerst steht oder größer gedruckt ist. Rechne nach, bevor du antwortest.

  "5.99  6.99"  ->  PRICE="5.99"   OLD_PRICE="6.99"      (5.99 < 6.99)
  "1.49  1.59"  ->  PRICE="1.49"   OLD_PRICE="1.59"      (1.49 < 1.59)
  "3.49  2.29"  ->  OLD_PRICE="3.49"  PRICE="2.29"       (2.29 < 3.49)

Steht nur ein Preis ohne Partner, ist er PRICE.

═══════════════════════════════════════════════════════════════════════
REGEL 5 — PRODUCT: Name mit Sorte, aber ohne Menge, Preis und "oder"
═══════════════════════════════════════════════════════════════════════
Der PRODUCT-Span umfasst den Produktnamen einschließlich der Sortenangabe.
Dazu zählt auch "Versch. Sorten". Er endet vor der Mengenangabe.

  Richtig: PRODUCT="Löslicher Kaffee Classic,"      QUANTITY="200 g"
  Richtig: PRODUCT="Käsescheiben Natur,"            QUANTITY="150 g"
  Richtig: PRODUCT="Burger Buns* Versch. Sorten,"   QUANTITY="300 g"
  Falsch:  PRODUCT="Käsescheiben Natur, je 150 g (1 kg = 15.27)"
  Falsch:  PRODUCT="Löslicher Kaffee"               <- Sorte fehlt

NICHT zum Produktnamen gehören Handelsklasse und Werbetext:

  Richtig: PRODUCT="Heidelbeeren"    Falsch: PRODUCT="Heidelbeeren Kl. I,"
  Richtig: PRODUCT="Pasta*"          Falsch: PRODUCT="Pasta* Zu 100% aus Hartweizen"

Merkregel: Sorte beantwortet "welche Variante?" und gehört dazu. Handelsklasse
und Werbetext beantworten "wie gut / wie beworben?" und bleiben draußen.

Ein PRODUCT-Span enthält NIEMALS ein Wort, das zu QUANTITY, UNIT_PRICE,
PRICE oder OLD_PRICE gehört. Diese Angaben haben eigene Labels. Enthält
dein Span eine Zahl mit Einheit oder eine runde Klammer, ist er zu lang.

"oder" trennt zwei Angebote. KEIN Span enthält jemals das Wort "oder":
der laufende Span endet davor, nach "oder" beginnt ein neuer Span für das
zweite Produkt. "oder" selbst bleibt ohne Label.

  Richtig: PRODUCT="Waschmittel* Aprilfrisch,"  und ein zweiter Span
           PRODUCT="All in 1 Color Pods* Amethyst Blütentraum,"
  Falsch:  ein einziger Span von "Waschmittel*" über "oder" hinweg

═══════════════════════════════════════════════════════════════════════
REGEL 6 — Was NIE ein Label bekommt
═══════════════════════════════════════════════════════════════════════
"je", "oder", "statt", "ca.", "UVP", "KAUFEN", "ENTSPRICHT", "NEU", "TOP",
"zzgl. 0.25 Pfand", "Nur mit App", "mit PENNY App", "ohne PENNY App",
"Aktion", "Haltungsform 2", "Kl. I", "Zu 100% aus Hartweizen", "im Kühlregal
erhältlich", Fußnotenziffern, Sternchen, Aufzählungspunkte, einzelne
Buchstaben aus Grafiken.

"Versch. Sorten" ist die Ausnahme: als Teil eines PRODUCT-Spans gehört es
dazu (Regel 5), allein oder in einer Mengenangabe nicht.

Ebenso der Druckvermerk am rechten Seitenrand in der Form "25_02-09-10" —
das ist eine Druckkennung, kein Inhalt des Prospekts.

Lieber ein Wort ohne Label lassen als ein falsches vergeben.

═══════════════════════════════════════════════════════════════════════
REGEL 7 — Angebote ohne Produkttext
═══════════════════════════════════════════════════════════════════════
Manche Angebote bestehen nur aus einem Produktfoto und einem Preis; der
Produktname steht nirgends im Text. Dann labelst du NUR den Preis. Erfinde
keinen PRODUCT-Span aus benachbarten Wörtern — du darfst ausschließlich auf
Wörter zeigen, die in der Liste stehen.

═══════════════════════════════════════════════════════════════════════
REGEL 8 — Zusammengehörendes und Getrenntes
═══════════════════════════════════════════════════════════════════════
Am Zeilenumbruch getrennte Wörter ("Orangen-" + "Nektar", "Hähnchen-" +
"Brustfilets") gehören in EINEN Span, der beide Wörter umfasst.

Ein Preis, der mittig unter mehreren Produkten steht, gilt für alle — er
bekommt trotzdem nur einen einzigen PRICE-Span an seiner Textstelle.
Erkennungsmerkmale für so eine Gruppe: "oder", "Versch. Sorten", "je".

═══════════════════════════════════════════════════════════════════════
REGEL 9 — Den Gültigkeitszeitraum zuerst suchen
═══════════════════════════════════════════════════════════════════════
Suche VOR allem anderen die Seite nach einem Zeitraum ab (meist oben oder in
einem Banner, Form "Mo, 20.7. – Sa, 25.7." oder "Do, 23.7. bis Sa, 25.7.").
Er kommt höchstens einmal pro Seite vor und wird sonst leicht übersehen.
Der VALID-Span umfasst die ganze Angabe mit Wochentagen und Daten.

═══════════════════════════════════════════════════════════════════════

Vollständiges Beispiel. Für die Wortliste

  0:MARATHON 1:Isotonischer 2:Fitnessdrink 3:Citrus, 4:zzgl. 5:0.25
  6:Pfand, 7:je 8:0,5 9:l 10:(1 11:l 12:= 13:0.78) 14:1.49 15:1.59

lautet die Antwort:

[{{"start": 0, "end": 1, "label": "BRAND"}},
 {{"start": 1, "end": 4, "label": "PRODUCT"}},
 {{"start": 8, "end": 10, "label": "QUANTITY"}},
 {{"start": 10, "end": 14, "label": "UNIT_PRICE"}},
 {{"start": 14, "end": 15, "label": "PRICE"}},
 {{"start": 15, "end": 16, "label": "OLD_PRICE"}}]

Beachte: 4-7 ("zzgl. 0.25 Pfand, je") bleiben ohne Label, die Klammer 10-14
ist ein eigener Span, und QUANTITY beginnt bei 8, nicht bei 7.

Nutze das Bild, um zu erkennen, welche Angaben zu welchem Angebot gehören:
Preis, Produkt und Menge stehen räumlich beieinander, und der durchgestrichene
Preis ist nur im Bild als solcher erkennbar.

Antworte ausschließlich mit einem JSON-Array dieser Form. "end" ist exklusiv.
Spans dürfen sich nicht überlappen. Wörter ohne Entität lässt du weg.
Kein Markdown, keine Erklärungen, kein Vorspann.

Wortliste:
{word_list}
"""


def _strip_code_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()


def _extract_json_array(text: str) -> str:
    """Schneidet das JSON-Array aus einer Antwort mit Beiwerk heraus.

    Trotz "kein Markdown, keine Erklärungen" im Prompt liefert das Modell
    regelmäßig Prosa drumherum – beobachtet wurden Einleitungssätze, eine
    angehängte Zusammenfassung und (einmal) beides auf Koreanisch. Statt
    daran zu scheitern, nehmen wir schlicht alles zwischen der ersten '['
    und der dazu passenden schließenden ']'.
    """
    text = _strip_code_fences(text)
    start = text.find("[")
    if start == -1:
        raise ValueError(f"Kein JSON-Array in der Antwort: {text[:150]}")

    # Klammern zählen, statt rfind(']') zu nehmen: hinter dem Array kann noch
    # Fließtext mit weiteren Klammern stehen.
    depth = 0
    for i, char in enumerate(text[start:], start=start):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise ValueError(f"JSON-Array nicht geschlossen (abgeschnitten?): {text[:150]}")


# Die Qwen-Modelle denken vor der Antwort, und diese Token zählen gegen
# max_tokens. Gemessen am 30.07.2026: qwen3.5-397b lieferte auf allen drei
# Gold-Seiten 0 Zeichen, weil das ganze Budget fürs Nachdenken draufging –
# "finish_reason=length" bei leerem Text. Mit abgeschaltetem Reasoning
# braucht dasselbe Modell 10 statt 200 Token für dieselbe Antwort.
#
# Mistral lehnt den Schalter mit HTTP 400 ab ("chat_template is not supported
# for Mistral"). Statt eine Liste zu pflegen, welches Modell ihn verträgt –
# der GWDG-Katalog ändert sich –, probieren wir ihn einmal aus und merken uns
# die Absage für den Rest des Laufs.
_NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}
_rejects_thinking_flag: set[str] = set()


def _is_unsupported_param(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 400 and "chat_template" in str(exc)


# Labels, die ohne Zahl nicht existieren können. Gegengeprüft: jeder
# numerische Gold-Span enthält eine Ziffer.
_NUMERIC_LABELS = {"PRICE", "OLD_PRICE", "DISCOUNT", "QUANTITY", "UNIT_PRICE"}


def trim_spans(spans: list[dict], words: list[dict]) -> list[dict]:
    """Kürzt Spans an Grenzen, die keine Entität überschreiten darf.

    Zwei Fälle, beide gemessen: Das Modell zieht zwei Angebote in einen Span,
    wenn "oder" dazwischensteht ("Waschmittel* … oder All in 1 Color Pods* …"),
    und es schluckt den Grundpreis in die Mengenangabe ("g (1 kg = 11.98)").

    Beides ist mechanisch entscheidbar, also wird es hier erzwungen statt nur
    im Prompt erbeten – eine Regel senkt die Fehlerrate, ein Guard setzt sie
    auf null.

    Bewusst hier und nicht in labels.spans_to_bio(): dort laufen auch die
    handannotierten Gold-Spans durch, und die dürfen nicht stillschweigend
    umgeschrieben werden. Was ein Mensch annotiert hat, gilt.
    """
    text = [w["text"] for w in words]
    trimmed = []

    for span in spans:
        start, end = span.get("start"), span.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            trimmed.append(span)  # ungültig – spans_to_bio verwirft es gleich
            continue

        cut = end
        for i in range(start, min(end, len(text))):
            word = text[i]
            if word.lower().strip(",.") == "oder":
                cut = i
                break
            # Öffnende Klammer beginnt den Grundpreis. Für UNIT_PRICE ist sie
            # der Anfang des Spans, für jedes andere Label das Ende.
            if i > start and word.startswith("(") and span.get("label") != "UNIT_PRICE":
                cut = i
                break

        if cut <= start:
            continue

        # Ein Preis, ein Rabatt, eine Menge – ohne Ziffer gibt es das nicht.
        # Das Modell labelt trotz Ausschlussliste im Prompt weiterhin "Aktion"
        # als PRICE und "UVP" als OLD_PRICE, rund zweimal pro Seite. Auch das
        # ist mechanisch entscheidbar, also wird es hier erledigt.
        if span.get("label") in _NUMERIC_LABELS:
            if not any(char.isdigit() for word in text[start:cut] for char in word):
                continue

        trimmed.append({**span, "end": cut})

    return trimmed


def is_retryable(exc: Exception) -> bool:
    """Ist der Fehler ein Schluckauf oder ein echtes Problem?

    Die GWDG lädt Modelle bei Bedarf und antwortet währenddessen mit 503 oder
    schlicht gar nicht. Ohne diese Unterscheidung landet ein Lauf über 196
    Seiten mit lauter "fehlgeschlagen" im Protokoll, obwohl nur das Modell
    kalt war – und ein abgeschnittenes JSON (ValueError) würde umgekehrt
    dreimal wiederholt, ohne dass sich etwas ändert.
    """
    from openai import APIConnectionError, APITimeoutError, RateLimitError

    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True
    status = getattr(exc, "status_code", None)
    if status in {408, 409, 425, 429, 500, 502, 503, 504}:
        return True
    return any(
        marker in str(exc).lower()
        for marker in ("rate limit", "timeout", "timed out", "temporarily unavailable",
                       "service unavailable", "connection reset", "overloaded")
    )


def label_page_with_retry(
    words: list[dict],
    page_png: bytes,
    client: OpenAI,
    model: str,
    max_retries: int = 3,
) -> list[str]:
    """label_page mit Backoff für vorübergehende Fehler.

    Ein Format- oder Parse-Fehler wird nicht wiederholt: das Modell hat
    geantwortet, die Antwort war nur unbrauchbar. Ein zweiter Versuch mit
    identischer Eingabe kostet nur Zeit. Die Seite bleibt ungelabelt und
    kommt beim nächsten Lauf erneut dran – die Skripte sind idempotent.
    """
    last: Exception | None = None
    for attempt in range(max_retries):
        try:
            return label_page(words, page_png, client, model)
        except Exception as exc:
            last = exc
            if not is_retryable(exc) or attempt == max_retries - 1:
                raise
            time.sleep(min(30.0, 2.0 * (2**attempt)))
    raise last  # unerreichbar, aber macht den Rückgabetyp eindeutig


def label_page(
    words: list[dict],
    page_png: bytes,
    client: OpenAI,
    model: str,
) -> list[str]:
    """Labelt eine Seite und gibt die BIO-Tagfolge zurück (ein Tag pro Wort)."""
    word_list = "\n".join(f"{i}: {w['text']}" for i, w in enumerate(words))
    prompt = _PROMPT.format(word_list=word_list)
    b64 = base64.b64encode(page_png).decode("ascii")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }
    ]

    def call(extra_body: dict | None):
        return client.chat.completions.create(
            model=model,
            messages=messages,
            # Nicht 0: bei greedy decoding ist das Modell auf einer Seite in
            # eine Endlosschleife gelaufen (hunderte Wiederholungen von
            # '" a "'), bis das Token-Limit griff. Ein bisschen Temperatur
            # bricht solche Loops. Die Labels werden dadurch nicht mehr exakt
            # reproduzierbar – für einmalig erzeugte Trainingsdaten ist
            # Robustheit hier wichtiger.
            temperature=0.2,
            # Ohne Limit greift das Server-Default und schneidet die Antwort
            # mitten im JSON ab. Gemessen an echten Seiten braucht Mistral rund
            # 25 Zeichen JSON pro Wort, und JSON ist tokendicht (~2 Zeichen pro
            # Token) – also etwa 13 Token pro Wort. Faktor 40 gibt Puffer.
            max_tokens=max(4096, len(words) * 40),
            extra_body=extra_body,
        )

    if model in _rejects_thinking_flag:
        response = call(None)
    else:
        try:
            response = call(_NO_THINKING)
        except Exception as exc:
            if not _is_unsupported_param(exc):
                raise
            _rejects_thinking_flag.add(model)
            response = call(None)

    choice = response.choices[0]
    text = choice.message.content or ""

    # Abgeschnittene Antworten früh und mit klarer Meldung abfangen – sonst
    # kommt nur ein kryptisches "Expecting ',' delimiter" aus json.loads.
    if choice.finish_reason == "length":
        raise ValueError(
            f"Antwort wurde bei {len(text)} Zeichen abgeschnitten "
            f"(max_tokens zu klein für {len(words)} Wörter)"
        )
    if not text.strip():
        raise ValueError("LLM hat eine leere Antwort geliefert")

    spans = json.loads(_extract_json_array(text))
    if not isinstance(spans, list):
        raise ValueError(f"LLM hat kein JSON-Array geliefert: {text[:200]}")

    return spans_to_bio(len(words), trim_spans(spans, words))
