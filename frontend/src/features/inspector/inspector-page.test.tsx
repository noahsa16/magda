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
    // Die Überschrift steht auf beiden Ebenen; nur die Seitenliste trennt sie.
    expect(screen.queryByPlaceholderText("Seite suchen…")).not.toBeInTheDocument()
  })

  it("beschriftet die Kennzahl als gelabelt", async () => {
    setup({ route: "/inspector" })
    expect(await screen.findByText(/gelabelt$/)).toBeInTheDocument()
  })

  it("öffnet per Klick auf eine Kachel die Seitenliste", async () => {
    const user = userEvent.setup()
    setup({ route: "/inspector" })
    await user.click(await screen.findByRole("button", { name: /462828/ }))
    expect(await screen.findByPlaceholderText("Seite suchen…")).toBeInTheDocument()
  })

  it("führt über den Brotkrumen zurück zur Übersicht", async () => {
    const user = userEvent.setup()
    setup({ route: "/inspector?catalog=462828" })
    await user.click(await screen.findByRole("button", { name: "Prospekte" }))
    expect(await screen.findByRole("button", { name: /462828/ })).toBeInTheDocument()
    expect(screen.queryByPlaceholderText("Seite suchen…")).not.toBeInTheDocument()
  })

  it("zeigt bei unbekanntem Katalog die Übersicht mit Hinweis", async () => {
    setup({ route: "/inspector?catalog=gibtsnicht" })
    expect(await screen.findByText(/nicht gefunden/i)).toBeInTheDocument()
  })

  it("zeigt den Hinweis auch, wenn es noch gar keine Prospekte gibt", async () => {
    // Ohne Kacheln darf ein veralteter Lesezeichen-Link nicht in der
    // Seitenansicht mit leerer Liste landen.
    setup({
      route: "/inspector?catalog=gibtsnicht",
      "/api/pages": [],
      "/api/status": { catalogs: [], totals: { raw: 0, words: 0, images: 0, labeled: 0 } },
    })
    expect(await screen.findByText(/nicht gefunden/i)).toBeInTheDocument()
    expect(screen.queryByPlaceholderText("Seite suchen…")).not.toBeInTheDocument()
  })

  it("blättert nicht über die Grenze des offenen Prospekts hinaus", async () => {
    setup({
      route: "/inspector?catalog=462828&page=462828_p3",
      "/api/pages": [
        { page_id: "462828_p3", catalog: "462828", labeled: true },
        { page_id: "999999_p1", catalog: "999999", labeled: true },
      ],
      "/api/status": {
        catalogs: [
          { id: "462828", raw: 1, words: 1, images: 1, labeled: 1, downloaded: "2026-07-20" },
          { id: "999999", raw: 1, words: 1, images: 1, labeled: 1, downloaded: "2026-07-21" },
        ],
        totals: { raw: 2, words: 2, images: 2, labeled: 2 },
      },
    })
    expect(await screen.findByText("1 / 1")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Nächste Seite/ })).toBeDisabled()
  })
})
