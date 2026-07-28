import { describe, expect, it } from "vitest"
import { applyLabel, removeRange, spanAt } from "./span-editor"

const spans = [
  { start: 0, end: 2, label: "BRAND" },
  { start: 4, end: 6, label: "PRICE" },
]

describe("applyLabel", () => {
  it("fügt einen Span ein und hält die Liste nach start sortiert", () => {
    expect(applyLabel(spans, 2, 4, "PRODUCT")).toEqual([
      { start: 0, end: 2, label: "BRAND" },
      { start: 2, end: 4, label: "PRODUCT" },
      { start: 4, end: 6, label: "PRICE" },
    ])
  })

  it("verdrängt überlappende Spans - der neue gewinnt", () => {
    expect(applyLabel(spans, 1, 5, "PRODUCT")).toEqual([
      { start: 1, end: 5, label: "PRODUCT" },
    ])
  })

  it("ersetzt einen Span bei identischem Bereich", () => {
    expect(applyLabel(spans, 0, 2, "PRODUCT")).toEqual([
      { start: 0, end: 2, label: "PRODUCT" },
      { start: 4, end: 6, label: "PRICE" },
    ])
  })

  it("lässt direkt angrenzende Spans stehen", () => {
    const result = applyLabel([{ start: 0, end: 2, label: "BRAND" }], 2, 3, "PRICE")
    expect(result).toHaveLength(2)
  })

  it("mutiert die Eingabe nicht", () => {
    const original = [...spans]
    applyLabel(spans, 1, 5, "PRODUCT")
    expect(spans).toEqual(original)
  })
})

describe("removeRange", () => {
  it("entfernt jeden Span, der den Bereich schneidet", () => {
    expect(removeRange(spans, 1, 2)).toEqual([{ start: 4, end: 6, label: "PRICE" }])
  })

  it("lässt alles stehen, wenn nichts überlappt", () => {
    expect(removeRange(spans, 2, 4)).toEqual(spans)
  })
})

describe("spanAt", () => {
  it("findet den Span, der den Index enthält", () => {
    expect(spanAt(spans, 5)).toEqual({ start: 4, end: 6, label: "PRICE" })
  })

  it("gibt null für ein Wort ohne Label", () => {
    expect(spanAt(spans, 3)).toBeNull()
  })

  it("behandelt end als exklusiv", () => {
    expect(spanAt(spans, 2)).toBeNull()
  })
})
