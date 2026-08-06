"""Kann eine flache BIO-Folge ein Angebot ausdruecken? Die Zahl dazu.

Das Gruppieren laesst sich nicht ueber `ENTITY_TYPES` loesen: BIO-Tags koennen
sagen "dieses Wort ist ein Preis", aber nicht "dieser Preis gehoert zu jenem
Produkt". Der naheliegende Ausweg ist eine **zweite, parallele Tag-Folge**
(`B-OFFER`/`I-OFFER`) ueber die ganze Kachel. Ein Span kann aber nur
zusammenfassen, was benachbart ist - faellt ein Angebot in zwei Laeufe, kann
eine flache Folge es nicht als eines ausdruecken.

Diese Vorbedingung war bisher behauptet, nicht nachrechenbar: "92,7 % der
visuellen Wortgruppen sind genau ein zusammenhaengender Lauf" stand in
CLAUDE.md ohne das Skript, das sie erzeugt. Dieses Modul ist das Skript.

Gemessen wird ueber die *gelabelten* Woerter. Fuellwoerter zwischen zwei
Entities desselben Angebots ("zzgl", "je") stoeren einen Span nicht - er
ueberdeckt sie einfach mit. Die Entity eines *fremden* Angebots dazwischen
zerreisst ihn dagegen, und genau das ist die Grenze eines flachen Schemas.

Die Zahl haengt an der Gruppierung, die man hineinreicht. Heute ist das die
Heuristik; sobald `gold/offers/` gefuellt ist, gehoert sie an die Referenz -
die Aussage "so viel Prozent sind darstellbar" ist nur so gut wie die
Gruppierung, ueber die sie gerechnet wurde.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from magda.offers import BADGE_TYPES, Offer, cluster_page


@dataclass
class Report:
    offers: int = 0
    contiguous: int = 0
    pages: int = 0
    by_runs: dict[int, int] = field(default_factory=dict)
    # Dieselbe Rechnung ohne PRICE/APP_PRICE/OLD_PRICE/DISCOUNT. Der
    # Unterschied ist der eigentliche Befund: Pennys Preis steht in einem
    # gelben Kasten, im Textlayer weit weg vom Produktnamen.
    offers_without_badges: int = 0
    contiguous_without_badges: int = 0
    by_runs_without_badges: dict[int, int] = field(default_factory=dict)

    @property
    def share(self) -> float | None:
        """None statt 0.0, wenn nichts zu messen war - "alles falsch" waere etwas anderes."""
        return None if self.offers == 0 else self.contiguous / self.offers

    @property
    def share_without_badges(self) -> float | None:
        if self.offers_without_badges == 0:
            return None
        return self.contiguous_without_badges / self.offers_without_badges

    def to_dict(self) -> dict:
        return {
            "pages": self.pages,
            "offers": self.offers,
            "contiguous": self.contiguous,
            "share": self.share,
            "by_runs": {str(k): v for k, v in sorted(self.by_runs.items())},
            "offers_without_badges": self.offers_without_badges,
            "contiguous_without_badges": self.contiguous_without_badges,
            "share_without_badges": self.share_without_badges,
            "by_runs_without_badges": {
                str(k): v for k, v in sorted(self.by_runs_without_badges.items())
            },
        }


def run_counts(page: dict, offers: list[Offer]) -> list[int]:
    """In wie viele Laeufe zerfaellt jedes Angebot? 1 heisst: als Span darstellbar.

    Gezaehlt wird ueber die Entities in Wortreihenfolge. Zwei Entities
    desselben Angebots hintereinander bilden einen Lauf, auch wenn ungelabelte
    Woerter dazwischenstehen; eine fremde Entity dazwischen beginnt einen neuen.
    """
    owner: list[tuple[int, int]] = []
    for offer_index, offer in enumerate(offers):
        for entity in offer.entities:
            owner.append((entity.start, offer_index))
    owner.sort()

    runs = Counter()
    previous = None
    for _, offer_index in owner:
        if offer_index != previous:
            runs[offer_index] += 1
        previous = offer_index
    return [runs[i] for i in range(len(offers))]


def _without_badges(offers: list[Offer]) -> list[Offer]:
    """Dieselben Angebote ohne ihre Preis-Badges, leere fallen weg.

    Nicht ueber `_make_offer`, weil ein Angebot ohne jede
    Beschreibungs-Entity sonst an der leeren Box-Vereinigung stirbt - hier
    interessieren ohnehin nur die Wortpositionen.
    """
    stripped = []
    for offer in offers:
        members = [e for e in offer.entities if e.type not in BADGE_TYPES]
        if members:
            stripped.append(Offer(id=offer.id, page_id=offer.page_id,
                                  bbox=offer.bbox, entities=members))
    return stripped


def collect(pages: list[dict], grouping=cluster_page) -> Report:
    """Summiert ueber Seiten. `grouping` ist austauschbar wie in offers_gold."""
    report = Report()
    for page in pages:
        offers = grouping(page)
        if not offers:
            continue
        report.pages += 1
        for count in run_counts(page, offers):
            report.offers += 1
            report.by_runs[count] = report.by_runs.get(count, 0) + 1
            if count == 1:
                report.contiguous += 1
        for count in run_counts(page, _without_badges(offers)):
            report.offers_without_badges += 1
            report.by_runs_without_badges[count] = report.by_runs_without_badges.get(count, 0) + 1
            if count == 1:
                report.contiguous_without_badges += 1
    return report
