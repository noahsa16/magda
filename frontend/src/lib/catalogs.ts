// Aggregation für die Prospekt-Übersicht, bewusst ohne React: Das Zählen ist
// der Teil, in dem sich Fehler still in eine Fortschrittsanzeige schreiben.

import type { CatalogStatus, CatalogTile, GoldSummary, PageSummary } from "./types"

function emptyTile(id: string, status: CatalogStatus[]): CatalogTile {
  return {
    id,
    pages: 0,
    done: 0,
    downloaded: status.find((s) => s.id === id)?.downloaded ?? null,
    stale: 0,
    broken: 0,
  }
}

/** Kacheln aus einer Liste von Einträgen, gruppiert über deren Katalog. */
function tilesFrom<T extends { catalog: string }>(
  rows: T[],
  status: CatalogStatus[],
  count: (tile: CatalogTile, row: T) => void,
): CatalogTile[] {
  const byId = new Map<string, CatalogTile>()
  for (const row of rows) {
    let tile = byId.get(row.catalog)
    if (!tile) {
      tile = emptyTile(row.catalog, status)
      byId.set(row.catalog, tile)
    }
    tile.pages += 1
    count(tile, row)
  }
  return [...byId.values()].sort((a, b) => a.id.localeCompare(b.id))
}

export function groupGoldByCatalog(
  summaries: GoldSummary[],
  status: CatalogStatus[],
): CatalogTile[] {
  return tilesFrom(summaries, status, (tile, row) => {
    if (row.status === "broken") tile.broken += 1
    else if (row.stale) tile.stale += 1
    else if (row.status === "done") tile.done += 1
  })
}

export function groupPagesByCatalog(
  pages: PageSummary[],
  status: CatalogStatus[],
): CatalogTile[] {
  return tilesFrom(pages, status, (tile, row) => {
    if (row.labeled) tile.done += 1
  })
}
