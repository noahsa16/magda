import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { AnnotatePage } from "./annotate-page"

const PAGE = {
  page_id: "462828_p1",
  width: 100,
  height: 100,
  words: [
    { text: "MAGICO", bbox: [0, 0, 10, 10] },
    { text: "Kaffee", bbox: [12, 0, 22, 10] },
  ],
}

function setup(overrides: Record<string, unknown> = {}) {
  mockFetch({
    "/api/schema": { entity_types: ["PRODUCT", "BRAND"] },
    "/api/pages/462828_p1": PAGE,
    "/api/pages": [{ page_id: "462828_p1", catalog: "462828", labeled: false }],
    "/api/gold/462828_p1": {
      page_id: "462828_p1", words_hash: "abc", status: "untouched",
      annotator: "", updated: null, spans: [], stale: false,
    },
    "/api/gold": [{
      page_id: "462828_p1", catalog: "462828", status: "untouched",
      annotator: "", num_spans: 0, stale: false,
    }],
    ...overrides,
  })
  return renderWithProviders(<AnnotatePage />, { route: "/annotate?page=462828_p1" })
}

afterEach(() => vi.unstubAllGlobals())

describe("AnnotatePage", () => {
  it("zeigt die Ziffernlegende zu den Entity-Typen", async () => {
    setup()
    expect(await screen.findByText("PRODUCT")).toBeInTheDocument()
    expect(screen.getByText("BRAND")).toBeInTheDocument()
  })

  it("zeigt den Fortschritt über alle Seiten", async () => {
    setup()
    expect(await screen.findByText("0 / 1 Seiten fertig")).toBeInTheDocument()
  })

  it("zählt eine Seite mit veralteter Wortliste nicht als fertig", async () => {
    setup({
      "/api/gold": [{
        page_id: "462828_p1", catalog: "462828", status: "done",
        annotator: "noah", num_spans: 12, stale: true,
      }],
    })
    expect(await screen.findByText("0 / 1 Seiten fertig")).toBeInTheDocument()
    expect(screen.getByText("1 Seite ungültig")).toBeInTheDocument()
  })

  it("meldet den Speicherzustand", async () => {
    setup()
    expect(await screen.findByText("gespeichert")).toBeInTheDocument()
  })

  it("setzt per Zifferntaste ein Label auf das gewählte Wort", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText(/2 Wörter/)

    const boxes = document.querySelectorAll("svg rect")
    await user.click(boxes[0])
    await user.keyboard("1")

    await waitFor(() => expect(screen.getByText(/^1 Spans/)).toBeInTheDocument())
  })
})
