import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { InspectorPage } from "./inspector-page"

const SCHEMA = { entity_types: ["PRODUCT", "BRAND", "PRICE", "OLD_PRICE", "QUANTITY", "DISCOUNT", "VALID"] }
const PAGE = {
  page_id: "462828_p3",
  width: 595.28,
  height: 841.89,
  words: [
    { text: "Rinderhackfleisch", bbox: [72.4, 310.2, 198.6, 324.8] },
    { text: "3.99", bbox: [210.5, 305.0, 265.3, 348.1] },
  ],
  tags: ["B-PRODUCT", "B-PRICE"],
}

describe("InspectorPage", () => {
  it("zeigt den Empty State ohne Seiten", async () => {
    mockFetch({ "/api/schema": SCHEMA, "/api/pages": [] })
    renderWithProviders(<InspectorPage />)
    expect(await screen.findByText(/02_extract_words/)).toBeInTheDocument()
  })

  it("zeigt nach Seitenauswahl die gruppierten Entities", async () => {
    // Achtung: mockFetch matcht per Präfix – die Detail-URL MUSS vor /api/pages stehen.
    mockFetch({
      "/api/schema": SCHEMA,
      "/api/pages/462828_p3": PAGE,
      "/api/pages": [{ page_id: "462828_p3", catalog: "462828", labeled: true }],
    })
    renderWithProviders(<InspectorPage />)
    await userEvent.click(await screen.findByText("462828_p3"))
    expect(await screen.findByText("Rinderhackfleisch")).toBeInTheDocument()
    expect(screen.getByText("3.99")).toBeInTheDocument()
  })
})
