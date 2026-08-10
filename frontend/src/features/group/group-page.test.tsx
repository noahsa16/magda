import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { GroupPage } from "./group-page"

/** Die Gruppierungsreferenz entsteht hier - falsch geklickt heisst falsch
 * gemessen. Geprüft wird deshalb vor allem das, was der Annotator *nicht*
 * sieht: dass ein Klick die ganze Entity nimmt und nicht nur ein Wort, und
 * dass nach `n` ein zweites Angebot entsteht statt das erste zu wachsen. */

const PAGE = {
  page_id: "462828_p1",
  width: 100,
  height: 100,
  words: [
    { text: "Landliebe", bbox: [0, 0, 10, 10] },
    { text: "Butter", bbox: [12, 0, 22, 10] },
    { text: "2.49", bbox: [40, 0, 50, 10] },
  ],
  // "Landliebe Butter" ist eine Entity über zwei Wörter - ein Klick muss beide
  // nehmen, sonst kostet die Referenz ein Vielfaches an Zeit.
  tags: ["B-PRODUCT", "I-PRODUCT", "B-PRICE"],
}

const STATUS = {
  catalogs: [{ id: "462828", raw: 1, words: 1, images: 1, labeled: 1, downloaded: "2026-07-20" }],
  totals: { raw: 1, words: 1, images: 1, labeled: 1 },
}

function setup(overrides: Record<string, unknown> = {}) {
  mockFetch({
    "/api/schema": { entity_types: ["PRODUCT", "PRICE"] },
    "/api/status": STATUS,
    "/api/pages/462828_p1": PAGE,
    "/api/pages": [{ page_id: "462828_p1", catalog: "462828", labeled: true }],
    "/api/offer-gold/462828_p1": {
      page_id: "462828_p1", words_hash: "abc", status: "untouched",
      annotator: "", updated: null, groups: [], stale: false,
    },
    "/api/offer-gold": [{
      page_id: "462828_p1", catalog: "462828", status: "untouched",
      annotator: "", num_offers: 0, stale: false,
    }],
    ...overrides,
  })
  return renderWithProviders(<GroupPage />, {
    route: "/group?catalog=462828&page=462828_p1",
  })
}

afterEach(() => vi.unstubAllGlobals())

describe("GroupPage", () => {
  it("beginnt ohne Angebote und mit einem neuen als Ziel", async () => {
    setup()
    expect(await screen.findByText("0 Angebote · neues Angebot")).toBeInTheDocument()
  })

  it("nimmt bei einem Klick die ganze Entity, nicht nur das Wort", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText(/0 Angebote/)

    await user.click(document.querySelectorAll("svg rect")[0])

    await waitFor(() => expect(screen.getByText(/1 Angebote/)).toBeInTheDocument())
    // Beide Wörter der Entity tragen jetzt dieselbe Farbe, das dritte nicht.
    const boxes = document.querySelectorAll("svg rect")
    expect(boxes[0].getAttribute("fill")).toBe(boxes[1].getAttribute("fill"))
    expect(boxes[2].getAttribute("fill")).toBe("none")
  })

  it("legt nach n ein zweites Angebot an, statt das erste zu erweitern", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText(/0 Angebote/)

    await user.click(document.querySelectorAll("svg rect")[0])
    await waitFor(() => expect(screen.getByText(/1 Angebote/)).toBeInTheDocument())
    await user.keyboard("n")
    await user.click(document.querySelectorAll("svg rect")[2])

    await waitFor(() => expect(screen.getByText(/2 Angebote/)).toBeInTheDocument())
    const boxes = document.querySelectorAll("svg rect")
    expect(boxes[0].getAttribute("fill")).not.toBe(boxes[2].getAttribute("fill"))
  })

  it("sperrt die Seite bei veralteter Wortliste", async () => {
    setup({
      "/api/offer-gold/462828_p1": {
        page_id: "462828_p1", words_hash: "alt", status: "done",
        annotator: "noah", updated: null, groups: [[0, 1]], stale: true,
      },
    })

    expect(await screen.findByText("Wortliste hat sich geändert")).toBeInTheDocument()
  })

  it("zaehlt eine Seite mit veralteter Wortliste nicht als fertig", async () => {
    setup({
      "/api/offer-gold": [{
        page_id: "462828_p1", catalog: "462828", status: "done",
        annotator: "noah", num_offers: 8, stale: true,
      }],
    })

    expect(await screen.findByText("0 / 1 Seiten fertig")).toBeInTheDocument()
  })
})
