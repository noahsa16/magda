import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { OverviewPage } from "./overview-page"

describe("OverviewPage", () => {
  it("zeigt den Empty State mit Download-Kommando", async () => {
    mockFetch({
      "/api/status": { catalogs: [], totals: { raw: 0, words: 0, images: 0, labeled: 0 } },
    })
    renderWithProviders(<OverviewPage />)
    expect(await screen.findByText(/01_download_flyers/)).toBeInTheDocument()
  })

  it("zeigt Kennzahlen und Kataloge", async () => {
    mockFetch({
      "/api/status": {
        catalogs: [{ id: "462828", raw: 10, words: 8, images: 8, labeled: 4 }],
        totals: { raw: 10, words: 8, images: 8, labeled: 4 },
      },
    })
    renderWithProviders(<OverviewPage />)
    expect(await screen.findByText("462828")).toBeInTheDocument()
    // Nicht an die Card-DOM-Struktur koppeln – "Gelabelt" steht in Karte UND Tabellenkopf.
    expect(screen.getAllByText("Gelabelt").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("4").length).toBeGreaterThanOrEqual(1)
  })
})
