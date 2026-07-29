import type { CatalogStatus } from "./types"

/**
 * Bündelt Regionalausgaben zu Prospektwochen.
 *
 * Penny vergibt je Woche 44 Katalog-IDs auf einem Gitter mit Schrittweite 3;
 * ein Block ist rund 130 IDs breit, zwischen zwei Wochen liegen Tausende. Eine
 * Lücke über 500 trennt also zuverlässig zwei Wochen – ohne dass wir ein Datum
 * bräuchten, das die Quelle gar nicht mitliefert.
 *
 * Ohne diese Bündelung zeigt die Übersicht 54 Zeilen für zwei Prospekte.
 */
const WEEK_GAP = 500

/**
 * Zerlegt alles mit einer Katalog-ID in Blöcke einer Prospektwoche,
 * neueste zuerst. Grundlage für die Wochenliste *und* für die Kachelraster.
 */
export function chunkByWeek<T extends { id: string }>(items: T[]): T[][] {
  const sorted = [...items].sort((a, b) => Number(a.id) - Number(b.id))
  const blocks: T[][] = []
  for (const item of sorted) {
    const current = blocks[blocks.length - 1]
    const previous = current?.[current.length - 1]
    if (previous && Number(item.id) - Number(previous.id) <= WEEK_GAP) {
      current.push(item)
    } else {
      blocks.push([item])
    }
  }
  return blocks.reverse()
}

export interface CatalogWeek {
  /** Kleinste Katalog-ID des Blocks – stabil und als Schlüssel brauchbar. */
  id: string
  catalogs: CatalogStatus[]
  raw: number
  words: number
  labeled: number
  /** Als Duplikat aussortiert – zählt zum Fortschritt, nicht zum Rückstand. */
  excluded: number
  /** Ladedatum der ersten Ausgabe, als grobe Einordnung. */
  downloaded: string | null
  /** Bundesländer, die in diesem Block vorkommen. */
  regions: string[]
}

export function groupByWeek(catalogs: CatalogStatus[]): CatalogWeek[] {
  return chunkByWeek(catalogs)
    .map((block) => ({
      id: block[0].id,
      catalogs: block,
      raw: block.reduce((sum, c) => sum + c.raw, 0),
      words: block.reduce((sum, c) => sum + c.words, 0),
      labeled: block.reduce((sum, c) => sum + c.labeled, 0),
      excluded: block.reduce((sum, c) => sum + (c.excluded ?? 0), 0),
      downloaded: block.find((c) => c.downloaded)?.downloaded ?? null,
      // Defensiv: eine API-Antwort ohne region darf die Übersicht nicht in
      // eine weiße Seite verwandeln.
      regions: [
        ...new Set(block.map((c) => (c.region ?? "").split(" · ")[0]).filter(Boolean)),
      ].sort(),
    }))
}
