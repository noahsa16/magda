import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { OverviewPage } from "./overview-page"

const EMPTY_TOTALS = {
  raw: 0, words: 0, images: 0, labeled: 0, gold_done: 0, gold_in_progress: 0,
}

function base(extra: Record<string, unknown> = {}) {
  return {
    "/api/status": { catalogs: [], totals: EMPTY_TOTALS },
    "/api/evaluation": [],
    "/api/model": [],
    "/api/schema": { entity_types: ["PRODUCT", "BRAND", "PRICE"] },
    ...extra,
  }
}

describe("OverviewPage", () => {
  it("zeigt die Zahl handannotierter Seiten als eigene Kennzahl", async () => {
    mockFetch(base({
      "/api/status": {
        catalogs: [],
        totals: { ...EMPTY_TOTALS, raw: 40, words: 40, labeled: 40, gold_done: 7 },
      },
    }))
    renderWithProviders(<OverviewPage />)

    expect(await screen.findByText("Von Hand annotiert")).toBeInTheDocument()
    expect((await screen.findAllByText("7")).length).toBeGreaterThanOrEqual(1)
  })

  it("zeigt je Variante den F1-Wert aus dem Evaluationsreport", async () => {
    mockFetch(base({
      "/api/model": [{ variant: "gbert", trained: true, epoch: 10 }],
      "/api/evaluation": [{
        variant: "gbert",
        report: { "micro avg": { "f1-score": 0.908, precision: 0.889, recall: 0.927, support: 3901 } },
      }],
    }))
    renderWithProviders(<OverviewPage />)

    expect(await screen.findByText("F1 0.908")).toBeInTheDocument()
    expect(screen.getByText(/trainiert, 10 Epochen/)).toBeInTheDocument()
  })

  // Die Übersicht ist bewusst auf Datenstand und Ergebnis reduziert: alles
  // Weitere hat eine eigene Seite und stand hier doppelt.
  it("zeigt weder Pipeline-Schritte noch Label-Verteilung", async () => {
    mockFetch(base())
    renderWithProviders(<OverviewPage />)

    await screen.findByText("Modellstand")
    expect(screen.queryByText("Prospekte laden")).not.toBeInTheDocument()
    expect(screen.queryByText("PRODUCT")).not.toBeInTheDocument()
  })
})
