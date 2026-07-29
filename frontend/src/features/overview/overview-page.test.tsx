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
    "/api/labels/distribution": { pages: 0, counts: {}, total: 0 },
    ...extra,
  }
}

describe("OverviewPage", () => {
  it("zeigt jeden Pipeline-Schritt im Fortschrittsstreifen", async () => {
    mockFetch(base())
    renderWithProviders(<OverviewPage />)

    // Der Skriptname hängt im Tooltip; sichtbar ist der Titel des Schritts.
    expect(await screen.findByText("Prospekte laden")).toBeInTheDocument()
    expect(screen.getByText("Evaluation")).toBeInTheDocument()
  })

  it("fuehrt nichts aus, sondern verlinkt auf die Pipeline-Seite", async () => {
    mockFetch(base())
    renderWithProviders(<OverviewPage />)

    await screen.findByText("Prospekte laden")
    expect(screen.queryByRole("button", { name: /starten/i })).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Ausführen/ })).toHaveAttribute("href", "/pipeline")
  })

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

  it("zeigt Kataloge und die Label-Verteilung", async () => {
    mockFetch(base({
      "/api/status": {
        catalogs: [{
          id: "462828", raw: 10, words: 8, images: 8, labeled: 4,
          downloaded: "2026-07-23", region: "Niedersachsen · 81 Märkte", region_confirmed: true,
        }],
        totals: { ...EMPTY_TOTALS, raw: 10, words: 8, images: 8, labeled: 4 },
      },
      "/api/labels/distribution": {
        pages: 4, counts: { PRODUCT: 120, PRICE: 89, BRAND: 0 }, total: 209,
      },
    }))
    renderWithProviders(<OverviewPage />)

    expect(await screen.findByText("462828")).toBeInTheDocument()  // Prospektwoche
    expect(await screen.findByText("PRODUCT")).toBeInTheDocument()
    expect(screen.getByText("120")).toBeInTheDocument()
  })
})
