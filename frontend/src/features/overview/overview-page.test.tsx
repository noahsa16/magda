import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { OverviewPage } from "./overview-page"

const IDLE_RUN = { running: false, job: null, lines: [], exit_code: null, elapsed: null }

describe("OverviewPage", () => {
  it("zeigt die Pipeline-Schritte mit Skriptnamen", async () => {
    mockFetch({
      "/api/status": { catalogs: [], totals: { raw: 0, words: 0, images: 0, labeled: 0 } },
      "/api/evaluation": [],
      "/api/run": IDLE_RUN,
    })
    renderWithProviders(<OverviewPage />)
    expect(await screen.findByText(/01_download_flyers/)).toBeInTheDocument()
    expect(screen.getByText(/05_evaluate/)).toBeInTheDocument()
  })

  it("zeigt Kennzahlen und Kataloge", async () => {
    mockFetch({
      "/api/status": {
        catalogs: [{ id: "462828", raw: 10, words: 8, images: 8, labeled: 4 }],
        totals: { raw: 10, words: 8, images: 8, labeled: 4 },
      },
      "/api/evaluation": [],
      "/api/run": IDLE_RUN,
    })
    renderWithProviders(<OverviewPage />)
    expect(await screen.findByText("462828")).toBeInTheDocument()
    expect(screen.getAllByText("Gelabelt").length).toBeGreaterThanOrEqual(1)
    // findAll: die Kennzahlen zählen animiert hoch und erreichen den Endwert
    // erst nach ein paar Frames.
    expect((await screen.findAllByText("4")).length).toBeGreaterThanOrEqual(1)
  })
})
