import { describe, expect, it } from "vitest"
import { groupEntities } from "./bio"

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
