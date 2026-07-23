import { describe, expect, it } from "vitest"
import { nextStep } from "./next-step"

describe("nextStep", () => {
  it("empfiehlt Download bei leerem Datenverzeichnis", () => {
    expect(nextStep({ raw: 0, words: 0, images: 0, labeled: 0 })).toContain("01_download")
  })
  it("empfiehlt Extraktion, wenn PDFs ohne Words existieren", () => {
    expect(nextStep({ raw: 5, words: 3, images: 3, labeled: 0 })).toContain("02_extract")
  })
  it("empfiehlt Labeling, wenn Words ohne Labels existieren", () => {
    expect(nextStep({ raw: 5, words: 5, images: 5, labeled: 2 })).toContain("03_label")
  })
  it("gibt null zurueck, wenn alles verarbeitet ist", () => {
    expect(nextStep({ raw: 5, words: 5, images: 5, labeled: 5 })).toBeNull()
  })
})
