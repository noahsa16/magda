import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { DemoPage } from "./demo-page"

describe("DemoPage", () => {
  it("zeigt Upload-Aufforderung und deaktivierten Button ohne Datei", async () => {
    mockFetch({ "/api/schema": { entity_types: ["PRODUCT"] } })
    renderWithProviders(<DemoPage />)
    expect(await screen.findByText(/PDF/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Extrahieren/ })).toBeDisabled()
  })
})
