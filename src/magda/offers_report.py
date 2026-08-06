"""Ehrliche Messung des Angebots-Clusterings per Ablation.

`_match_badges` betritt den geometrischen Zweig nur, wenn kein Block
arithmetisch (Menge x Grundpreis) gepasst hat - die Arithmetik hinterher an
den geometrisch zugeordneten Faellen zu pruefen liefert also garantiert
"falsch", denn fuer die ist sie per Konstruktion schon gescheitert. Gemessen
wird deshalb per Ablation: der arithmetische Weg wird abgeschaltet
(`cluster_page(page, arithmetic=False, trace=...)`), die Geometrie ordnet
allein zu, und die Arithmetik urteilt anschliessend unbeteiligt, ob sie
denselben Block gewaehlt haette.

Details und Begruendung: docs/superpowers/specs/2026-08-06-offers-messung-und-regressionstests-design.md

Reine Auswertung, keine I/O-Politik - das Lesen der Seiten und das
Schreiben des Reports gehoert in `cli/offers_report.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from magda.offers import BadgeMatch, Offer, PRICE_TYPES, _expected_prices, _price_matches, _price_value, cluster_page


@dataclass
class PageVerdict:
    """Zaehlwerte einer einzelnen Seite - vor der Aggregation ueber den Split."""

    page_id: str
    confirmed: int = 0
    contradicted: int = 0
    unjudgeable: int = 0
    offers_total: int = 0
    offers_with_product_and_price: int = 0
    fragments: int = 0
    blocks_without_matching_pairing: int = 0


@dataclass
class Report:
    """Aggregat ueber einen Split (Train+Dev oder Test, siehe `--splits`)."""

    pages: int = 0
    pages_skipped: int = 0
    confirmed: int = 0
    contradicted: int = 0
    unjudgeable: int = 0
    offers_total: int = 0
    offers_with_product_and_price: int = 0
    fragments: int = 0
    blocks_without_matching_pairing: int = 0

    @property
    def judged(self) -> int:
        return self.confirmed + self.contradicted

    @property
    def confirmation_rate(self) -> float | None:
        """`confirmed / judged`, oder None ohne beurteilbare Zuordnung.

        None statt 0.0 oder 1.0: ein leerer Report ist kein Befund, weder ein
        guter noch ein schlechter, und soll nicht wie einer aussehen.
        """
        if self.judged == 0:
            return None
        return self.confirmed / self.judged

    def to_dict(self) -> dict:
        return {
            "pages": self.pages,
            "pages_skipped": self.pages_skipped,
            "confirmed": self.confirmed,
            "contradicted": self.contradicted,
            "unjudgeable": self.unjudgeable,
            "confirmation_rate": self.confirmation_rate,
            "offers_total": self.offers_total,
            "offers_with_product_and_price": self.offers_with_product_and_price,
            "fragments": self.fragments,
            "blocks_without_matching_pairing": self.blocks_without_matching_pairing,
        }


def _has_product_and_price(offer: Offer) -> bool:
    types = {e.type for e in offer.entities}
    has_product = "PRODUCT" in types or "BRAND" in types
    has_price = bool(types & PRICE_TYPES)
    return has_product and has_price


def _pairing_mismatch(offer: Offer, page: dict) -> bool:
    """True, wenn der Block Menge *und* Grundpreis hat, aber kein Preis dazu passt.

    Der Fall aus CLAUDE.md (1351497_p20): `900 g | 750 ml | 313,5 g` bei
    Preis 4.49, aber nur 0,75 x 5,99 trifft ihn - drei zusammengeworfene
    Nachbarprodukte statt Varianten. Menge x Grundpreis prueft sich selbst;
    das braucht keine Handannotation.
    """
    types = {e.type for e in offer.entities}
    if "QUANTITY" not in types or "UNIT_PRICE" not in types:
        return False
    expected = _expected_prices(offer, page)
    if not expected:
        return False
    values = [
        v for v in (_price_value(e.text) for e in offer.entities if e.type in PRICE_TYPES)
        if v is not None
    ]
    if not values:
        return False
    return not any(_price_matches(v, expected) for v in values)


def judge_page(page: dict) -> PageVerdict:
    """Fuehrt die Ablation fuer eine Seite aus und urteilt je geometrischer Zuordnung.

    Zwei getrennte `cluster_page`-Durchlaeufe: `arithmetic=True` liefert den
    Ist-Zustand fuer die nicht-zirkulaeren Zaehler (offers_total, Fragmente,
    Blocks ohne passende Paarung), `arithmetic=False` mit `trace` liefert die
    Ablation, gegen die die Arithmetik als Richter urteilt.
    """
    verdict = PageVerdict(page_id=page.get("page_id") or "unknown")

    offers = cluster_page(page, arithmetic=True)
    verdict.offers_total = len(offers)
    for offer in offers:
        if _has_product_and_price(offer):
            verdict.offers_with_product_and_price += 1
        else:
            verdict.fragments += 1
        if _pairing_mismatch(offer, page):
            verdict.blocks_without_matching_pairing += 1

    trace: list[BadgeMatch] = []
    cluster_page(page, arithmetic=False, trace=trace)
    for match in trace:
        if match.path != "geometric":
            continue
        if match.confirmed is True:
            verdict.confirmed += 1
        elif match.confirmed is False:
            verdict.contradicted += 1
        else:
            verdict.unjudgeable += 1

    return verdict


def collect(pages: list[dict]) -> Report:
    """Aggregiert `judge_page` ueber Seiten.

    Seiten ohne Wortliste werden uebersprungen und gezaehlt statt
    stillschweigend weggelassen - sonst sieht ein unvollstaendiger
    Labelordner aus wie ein vollstaendig gemessener.
    """
    report = Report()
    for page in pages:
        if not page.get("words"):
            report.pages_skipped += 1
            continue
        verdict = judge_page(page)
        report.pages += 1
        report.confirmed += verdict.confirmed
        report.contradicted += verdict.contradicted
        report.unjudgeable += verdict.unjudgeable
        report.offers_total += verdict.offers_total
        report.offers_with_product_and_price += verdict.offers_with_product_and_price
        report.fragments += verdict.fragments
        report.blocks_without_matching_pairing += verdict.blocks_without_matching_pairing
    return report
