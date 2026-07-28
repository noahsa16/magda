import { describe, expect, it } from "vitest"
import { groupGoldByCatalog, groupPagesByCatalog } from "./catalogs"
import type { CatalogStatus, GoldSummary, PageSummary } from "./types"

const status: CatalogStatus[] = [
  { id: "111", raw: 2, words: 2, images: 2, labeled: 1, downloaded: "2026-07-23" },
  { id: "222", raw: 1, words: 1, images: 1, labeled: 0, downloaded: null },
]

const gold = (page_id: string, s: GoldSummary["status"], stale = false): GoldSummary => ({
  page_id, catalog: page_id.split("_")[0], status: s, annotator: "", num_spans: 0, stale,
})

const page = (page_id: string, labeled: boolean): PageSummary => ({
  page_id, catalog: page_id.split("_")[0], labeled,
})

describe("groupGoldByCatalog", () => {
  it("zählt fertige Seiten je Katalog", () => {
    const tiles = groupGoldByCatalog(
      [gold("111_p1", "done"), gold("111_p2", "in_progress"), gold("222_p1", "done")],
      status,
    )
    expect(tiles).toEqual([
      { id: "111", pages: 2, done: 1, downloaded: "2026-07-23", stale: 0, broken: 0 },
      { id: "222", pages: 1, done: 1, downloaded: null, stale: 0, broken: 0 },
    ])
  })

  it("zählt eine veraltete Seite nicht als fertig", () => {
    // Dieselbe Regel wie doneCount in annotate-page.tsx: bei geänderter
    // Wortliste zeigen die Span-Indizes auf andere Wörter.
    const tiles = groupGoldByCatalog([gold("111_p1", "done", true)], status)
    expect(tiles[0].done).toBe(0)
    expect(tiles[0].stale).toBe(1)
  })

  it("zählt kaputte Gold-Dateien getrennt", () => {
    const tiles = groupGoldByCatalog([gold("111_p1", "broken")], status)
    expect(tiles[0].broken).toBe(1)
    expect(tiles[0].done).toBe(0)
  })

  it("sortiert nach Katalog-ID", () => {
    const tiles = groupGoldByCatalog([gold("222_p1", "done"), gold("111_p1", "done")], status)
    expect(tiles.map((t) => t.id)).toEqual(["111", "222"])
  })

  it("kommt ohne Statuseintrag aus", () => {
    const tiles = groupGoldByCatalog([gold("999_p1", "done")], status)
    expect(tiles).toEqual([
      { id: "999", pages: 1, done: 1, downloaded: null, stale: 0, broken: 0 },
    ])
  })

  it("liefert für keine Seiten eine leere Liste", () => {
    expect(groupGoldByCatalog([], status)).toEqual([])
  })
})

describe("groupPagesByCatalog", () => {
  it("zählt gelabelte Seiten je Katalog", () => {
    const tiles = groupPagesByCatalog(
      [page("111_p1", true), page("111_p2", false), page("222_p1", false)],
      status,
    )
    expect(tiles).toEqual([
      { id: "111", pages: 2, done: 1, downloaded: "2026-07-23", stale: 0, broken: 0 },
      { id: "222", pages: 1, done: 0, downloaded: null, stale: 0, broken: 0 },
    ])
  })
})
