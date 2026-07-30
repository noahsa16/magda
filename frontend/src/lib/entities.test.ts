import { describe, expect, it } from "vitest"
import { entityColor } from "./entities"

const TYPES = ["PRODUCT", "BRAND", "PRICE"]

describe("entityColor", () => {
  it("vergibt Farben stabil nach Position im Schema", () => {
    expect(entityColor(TYPES, "PRODUCT")).toBe(entityColor(TYPES, "PRODUCT"))
    expect(entityColor(TYPES, "PRODUCT")).not.toBe(entityColor(TYPES, "BRAND"))
  })

  it("faellt bei unbekannten Typen auf Grau zurueck", () => {
    expect(entityColor(TYPES, "UNBEKANNT")).toBe("#999999")
  })
})
