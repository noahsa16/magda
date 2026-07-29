import { describe, expect, it } from "vitest"
import type { CatalogStatus } from "./types"
import { chunkByWeek, groupByWeek } from "./weeks"

/** Penny vergibt je Woche 44 IDs im Dreierabstand; zwischen Wochen liegen Tausende. */
function katalog(id: string, over: Partial<CatalogStatus> = {}): CatalogStatus {
  return {
    id, raw: 10, words: 10, images: 10, labeled: 0,
    downloaded: "2026-07-29", region: "Bayern · 12 Märkte", region_confirmed: true, ...over,
  }
}

describe("chunkByWeek", () => {
  it("trennt zwei Prospektwochen", () => {
    const blocks = chunkByWeek([
      katalog("1342812"), katalog("1342815"), katalog("1342941"),
      katalog("1347375"), katalog("1347378"),
    ])

    expect(blocks).toHaveLength(2)
    // Neueste Woche zuerst – man interessiert sich für den aktuellen Prospekt.
    expect(blocks[0].map((c) => c.id)).toEqual(["1347375", "1347378"])
    expect(blocks[1].map((c) => c.id)).toEqual(["1342812", "1342815", "1342941"])
  })

  it("haelt eine Woche zusammen, auch bei Luecken im Gitter", () => {
    // Nach dem Entdoppeln fehlen die meisten Regionen einer alten Woche.
    const blocks = chunkByWeek([katalog("1342812"), katalog("1342941")])

    expect(blocks).toHaveLength(1)
  })

  it("kommt mit einer einzigen Woche aus", () => {
    expect(chunkByWeek([katalog("1347375")])).toEqual([[katalog("1347375")]])
    expect(chunkByWeek([])).toEqual([])
  })
})

describe("groupByWeek", () => {
  it("summiert die Kennzahlen je Woche", () => {
    const wochen = groupByWeek([
      katalog("1347375", { raw: 40, labeled: 10 }),
      katalog("1347378", { raw: 2, labeled: 1, region: "Berlin · 73 Märkte" }),
    ])

    expect(wochen).toHaveLength(1)
    expect(wochen[0].raw).toBe(42)
    expect(wochen[0].labeled).toBe(11)
    expect(wochen[0].regions).toEqual(["Bayern", "Berlin"])
  })

  it("ueberlebt eine Antwort ohne Region", () => {
    const ohne = { ...katalog("1347375"), region: undefined as unknown as string }

    expect(groupByWeek([ohne])[0].regions).toEqual([])
  })
})
