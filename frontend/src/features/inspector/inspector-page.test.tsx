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
const STATUS = {
  catalogs: [{ id: "462828", raw: 1, words: 1, images: 1, labeled: 1, downloaded: "2026-07-20" }],
  totals: { raw: 1, words: 1, images: 1, labeled: 1 },
}

function setup({ route, ...overrides }: Record<string, unknown> & { route?: string } = {}) {
  mockFetch({
    "/api/schema": SCHEMA,
    "/api/pages/462828_p3": PAGE,
    "/api/pages": [{ page_id: "462828_p3", catalog: "462828", labeled: true }],
    "/api/status": STATUS,
    ...overrides,
  })
  return renderWithProviders(<InspectorPage />, {
    route: (route as string | undefined) ?? "/inspector?catalog=462828&page=462828_p3",
  })
}

describe("InspectorPage", () => {
  it("zeigt den Empty State ohne Seiten", async () => {
    setup({
      route: "/inspector",
      "/api/pages": [],
      "/api/status": { catalogs: [], totals: { raw: 0, words: 0, images: 0, labeled: 0 } },
    })
    expect(await screen.findByText(/02_extract_words/)).toBeInTheDocument()
  })

  it("zeigt nach Seitenauswahl die gruppierten Entities", async () => {
    setup({ route: "/inspector?catalog=462828" })
    // Die Liste zeigt nur den Seitenteil ("p3") unter dem Katalog-Gruppenkopf.
    await userEvent.click(await screen.findByText("p3"))
    expect(await screen.findByText("Rinderhackfleisch")).toBeInTheDocument()
    expect(screen.getByText("3.99")).toBeInTheDocument()
  })
})

describe("InspectorPage — Ebenen", () => {
  it("zeigt ohne Parameter die Prospekt-Übersicht", async () => {
    setup({ route: "/inspector" })
    expect(await screen.findByText("462828")).toBeInTheDocument()
  })

  it("beschriftet die Kennzahl als gelabelt", async () => {
    setup({ route: "/inspector" })
    expect(await screen.findByText(/gelabelt$/)).toBeInTheDocument()
  })

  it("öffnet per Klick auf eine Kachel die Seitenliste", async () => {
    const user = userEvent.setup()
    setup({ route: "/inspector" })
    await user.click(await screen.findByRole("button", { name: /462828/ }))
    expect(await screen.findByText("Label-Inspektor")).toBeInTheDocument()
  })
})
