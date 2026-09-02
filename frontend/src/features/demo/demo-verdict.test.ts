import { describe, expect, it } from "vitest"
import type { DemoOffer } from "@/lib/types"
import { filterOffers, sortOffers, verdictMeta } from "./demo-verdict"

function offer(overrides: Partial<DemoOffer> = {}): DemoOffer {
  return {
    page_index: 0,
    bbox: [0, 0, 10, 10],
    product: "Butter",
    brand: "Landliebe",
    price: "1.29",
    old_price: null,
    quantity: null,
    unit_price: null,
    app_price: null,
    discount: null,
    valid: null,
    variants: [],
    confidence: 0.9,
    arithmetic: "unverifiable",
    entity_word_ranges: [{ type: "PRODUCT", start: 3, end: 4 }],
    ...overrides,
  }
}

describe("verdictMeta", () => {
  it("kennt alle vier Urteile aus offers_verify.judge_offers", () => {
    expect(verdictMeta("confirmed").label).toBe("bestätigt")
    expect(verdictMeta("contradicted").label).toBe("widerlegt")
    expect(verdictMeta("unresolved").label).toBe("unaufgelöst")
    expect(verdictMeta("unverifiable").label).toBe("unprüfbar")
  })

  it("jedes Urteil traegt einen Satz Erklaerung", () => {
    for (const verdict of ["confirmed", "contradicted", "unresolved", "unverifiable"] as const) {
      expect(verdictMeta(verdict).hint.length).toBeGreaterThan(10)
    }
  })
})

describe("filterOffers", () => {
  const offers = [
    offer({ product: "Butter", brand: "Landliebe" }),
    offer({ product: "Milch", brand: "Weihenstephan" }),
    offer({ product: "Kaffee", brand: null }),
  ]

  it("ohne Suchbegriff bleiben alle Angebote", () => {
    expect(filterOffers(offers, "")).toHaveLength(3)
  })

  it("filtert ueber Produkt", () => {
    expect(filterOffers(offers, "milch").map((o) => o.product)).toEqual(["Milch"])
  })

  it("filtert ueber Marke, case-insensitiv", () => {
    expect(filterOffers(offers, "LANDLIEBE").map((o) => o.product)).toEqual(["Butter"])
  })

  it("ein Angebot ohne Marke bleibt beim Marken-Filter aussen vor, crasht aber nicht", () => {
    expect(filterOffers(offers, "xyz")).toHaveLength(0)
  })
})

describe("sortOffers", () => {
  it("sortiert nach Seite, dann nach Wortindex innerhalb der Seite", () => {
    const unsorted = [
      offer({ page_index: 1, entity_word_ranges: [{ type: "PRODUCT", start: 5, end: 6 }] }),
      offer({ page_index: 0, entity_word_ranges: [{ type: "PRODUCT", start: 20, end: 21 }] }),
      offer({ page_index: 0, entity_word_ranges: [{ type: "PRODUCT", start: 3, end: 4 }] }),
    ]

    const sorted = sortOffers(unsorted)

    expect(sorted.map((o) => [o.page_index, o.entity_word_ranges[0].start])).toEqual([
      [0, 3],
      [0, 20],
      [1, 5],
    ])
  })

  it("laesst die urspruengliche Liste unveraendert", () => {
    const original = [offer({ page_index: 1 }), offer({ page_index: 0 })]
    sortOffers(original)
    expect(original[0].page_index).toBe(1)
  })
})
