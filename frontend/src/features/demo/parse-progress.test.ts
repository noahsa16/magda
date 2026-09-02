import { describe, expect, it } from "vitest"
import { parseProgress } from "./parse-progress"

describe("parseProgress", () => {
  it("liest die letzte passende Zeile", () => {
    const lines = [
      "Lade Modelle (gbert) ...",
      "Modelle geladen in 2.1s.",
      "  Seite 1/12: 0.31s",
      "  Seite 2/12: 0.28s",
    ]

    expect(parseProgress(lines)).toEqual({ page: 2, total: 12, seconds: 0.28 })
  })

  it("ignoriert Zeilen ohne das Fortschrittsformat", () => {
    expect(parseProgress(["irgendwas", "noch was"])).toBeNull()
  })

  it("ohne Zeilen gibt es keinen Fortschritt", () => {
    expect(parseProgress([])).toBeNull()
  })
})
