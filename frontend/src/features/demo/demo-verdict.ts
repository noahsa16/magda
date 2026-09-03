import type { ArithmeticVerdict, DemoOffer } from "@/lib/types"

/**
 * Anzeige-Metadaten je arithmetischem Urteil (magda.offers_verify.judge_offers).
 *
 * Reine Funktionen, damit Ampelfarbe und Tooltip-Text ohne DOM testbar sind -
 * die Komponente, die das rendert, macht damit nur noch Markup.
 */
export interface VerdictMeta {
  label: string
  /** Tailwind-Klassen für Hintergrund und Text der Badge. */
  tone: string
  /** Ein Satz Erklärung für den Tooltip. */
  hint: string
}

const VERDICTS: Record<ArithmeticVerdict, VerdictMeta> = {
  confirmed: {
    label: "bestätigt",
    tone: "bg-green-600/15 text-green-700 dark:text-green-400",
    hint: "Menge × Grundpreis geht in diesem Angebot auf.",
  },
  contradicted: {
    label: "widerlegt",
    tone: "bg-destructive/15 text-destructive",
    hint: "Die Rechnung geht stattdessen in einem anderen Angebot der Seite auf – die Zuordnung ist verdächtig.",
  },
  unresolved: {
    label: "unaufgelöst",
    tone: "bg-[color:var(--riso-yellow)]/25 text-foreground",
    hint: "Ein Grundpreis liegt vor, aber die Rechnung geht auf der ganzen Seite nirgends auf.",
  },
  unverifiable: {
    label: "unprüfbar",
    tone: "bg-muted text-muted-foreground",
    hint: "Kein Grundpreis vorhanden (oft Non-Food) – die Zuordnung lässt sich nicht nachrechnen.",
  },
}

export function verdictMeta(verdict: ArithmeticVerdict): VerdictMeta {
  return VERDICTS[verdict] ?? VERDICTS.unverifiable
}

/** Angebote nach Produkt oder Marke filtern - Suchfeld über der Kartenliste. */
export function filterOffers(offers: DemoOffer[], query: string): DemoOffer[] {
  const q = query.trim().toLowerCase()
  if (!q) return offers
  return offers.filter((o) =>
    (o.product ?? "").toLowerCase().includes(q) || (o.brand ?? "").toLowerCase().includes(q),
  )
}

/** Sortierung Seite → Lesereihenfolge (Wortindex des ersten Entity-Bereichs). */
export function sortOffers(offers: DemoOffer[]): DemoOffer[] {
  return [...offers].sort((a, b) => {
    if (a.page_index !== b.page_index) return a.page_index - b.page_index
    const startOf = (o: DemoOffer) =>
      o.entity_word_ranges.length > 0 ? Math.min(...o.entity_word_ranges.map((r) => r.start)) : 0
    return startOf(a) - startOf(b)
  })
}
