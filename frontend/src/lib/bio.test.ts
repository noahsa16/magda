import { describe, expect, it } from "vitest"
import { groupEntities, spansToTags } from "./bio"

const words = (...texts: string[]) => texts.map((text) => ({ text }))

describe("groupEntities", () => {
  it("gruppiert B-/I-Folgen zu Entities (Beispiel aus EXPLANATION.md)", () => {
    const result = groupEntities(
      words("Rinderhackfleisch", "500", "g", "3.99"),
      ["B-PRODUCT", "B-QUANTITY", "I-QUANTITY", "B-PRICE"],
    )
    expect(result).toEqual([
      { type: "PRODUCT", text: "Rinderhackfleisch", start: 0, end: 1 },
      { type: "QUANTITY", text: "500 g", start: 1, end: 3 },
      { type: "PRICE", text: "3.99", start: 3, end: 4 },
    ])
  })

  it("ignoriert verwaiste I-Tags ohne passendes B-", () => {
    expect(groupEntities(words("a", "b"), ["O", "I-PRICE"])).toEqual([])
  })

  it("trennt bei Lücke oder Typwechsel", () => {
    const result = groupEntities(
      words("a", "b", "c"),
      ["B-PRICE", "O", "I-PRICE"],
    )
    expect(result).toEqual([{ type: "PRICE", text: "a", start: 0, end: 1 }])
  })
})

describe("spansToTags", () => {
  it("erzeugt B-/I-Folgen aus Spans", () => {
    const tags = spansToTags(
      [
        { start: 0, end: 1, label: "BRAND" },
        { start: 1, end: 3, label: "QUANTITY" },
      ],
      4,
    )
    expect(tags).toEqual(["B-BRAND", "B-QUANTITY", "I-QUANTITY", "O"])
  })

  it("füllt eine Seite ohne Spans komplett mit O", () => {
    expect(spansToTags([], 3)).toEqual(["O", "O", "O"])
  })

  it("ist der Rundlauf zu groupEntities", () => {
    const words = [{ text: "MAGICO" }, { text: "je" }, { text: "200" }, { text: "g" }]
    const spans = [
      { start: 0, end: 1, label: "BRAND" },
      { start: 1, end: 4, label: "QUANTITY" },
    ]
    const entities = groupEntities(words, spansToTags(spans, words.length))
    expect(entities.map((e) => ({ start: e.start, end: e.end, label: e.type }))).toEqual(spans)
  })
})
