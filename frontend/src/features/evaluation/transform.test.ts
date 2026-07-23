import { describe, expect, it } from "vitest"
import type { EvalReport } from "@/lib/types"
import { overallF1, perEntityRows } from "./transform"

const metrics = (f1: number) => ({ precision: f1, recall: f1, "f1-score": f1, support: 10 })

const REPORTS: EvalReport[] = [
  {
    variant: "gbert", split: "test", num_pages: 10, created: "2026-07-23T12:00:00",
    report: { PRODUCT: metrics(0.7), PRICE: metrics(0.8), "micro avg": metrics(0.75) },
  },
  {
    variant: "layoutxlm", split: "test", num_pages: 10, created: "2026-07-23T12:00:00",
    report: { PRODUCT: metrics(0.85), "micro avg": metrics(0.85) },
  },
]

describe("perEntityRows", () => {
  it("legt beide Varianten pro Entity nebeneinander, avg-Zeilen fliegen raus", () => {
    const rows = perEntityRows(REPORTS, "f1-score")
    expect(rows).toEqual([
      { entity: "PRODUCT", gbert: 0.7, layoutxlm: 0.85 },
      { entity: "PRICE", gbert: 0.8, layoutxlm: undefined },
    ])
  })
})

describe("overallF1", () => {
  it("liest micro avg", () => {
    expect(overallF1(REPORTS, "layoutxlm")).toBe(0.85)
  })
  it("null ohne Report der Variante", () => {
    expect(overallF1([], "gbert")).toBeNull()
  })
})
