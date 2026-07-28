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

  it("entfernt das Label des angeklickten Spans mit 0", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText(/2 Wörter/)

    const boxes = document.querySelectorAll("svg rect")
    await user.click(boxes[0])
    await user.keyboard("1")
    await waitFor(() => expect(screen.getByText(/^1 Spans/)).toBeInTheDocument())

    // Klick auf ein gelabeltes Wort wählt den ganzen Span.
    await user.click(boxes[0])
    await user.keyboard("0")

    await waitFor(() => expect(screen.getByText(/^0 Spans/)).toBeInTheDocument())
  })

  it("markiert die Seite mit f als fertig", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText(/2 Wörter/)

    await user.keyboard("f")

    expect(await screen.findByRole("button", { name: /^Fertig/ })).toBeInTheDocument()
  })

  it("ignoriert Tastenkürzel mit gedrücktem Modifier", async () => {
    // Cmd+1 wechselt den Browser-Tab, Cmd+F öffnet die Suche. Beides sind
    // beiläufige Griffe und dürfen nicht in die Gold-Datei schreiben.
    const user = userEvent.setup()
    setup()
    await screen.findByText(/2 Wörter/)

    const boxes = document.querySelectorAll("svg rect")
    await user.click(boxes[0])
    await user.keyboard("{Meta>}1{/Meta}")
    await user.keyboard("{Control>}f{/Control}")

    expect(screen.getByText(/^0 Spans/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Als fertig markieren/ })).toBeInTheDocument()
  })

  it("löst mit f keinen Konflikt aus, solange die Annotation lädt", async () => {
    // Der Keydown-Listener hängt ab dem ersten Render. Vor dem Laden ist noch
    // kein words_hash da - ein Speicherversuch quittiert der Server dann mit
    // 409 und die Oberfläche sperrt eine völlig intakte Seite.
    const user = userEvent.setup()
    const puts: string[] = []
    const routes: Record<string, unknown> = {
      "/api/schema": { entity_types: ["PRODUCT", "BRAND"] },
      "/api/pages/462828_p1": PAGE,
      "/api/pages": [{ page_id: "462828_p1", catalog: "462828", labeled: false }],
      "/api/gold": [],
    }
    const json = (data: unknown, status: number) =>
      new Response(JSON.stringify(data), {
        status, headers: { "Content-Type": "application/json" },
      })

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = input.toString()
        if (init?.method === "PUT") {
          puts.push(url)
          return Promise.resolve(
            json({ detail: "Die Wortliste dieser Seite hat sich geändert." }, 409),
          )
        }
        // Die Annotation dieser Seite lädt für die Dauer des Tests nie.
        if (url.startsWith("/api/gold/462828_p1")) return new Promise<Response>(() => {})
        for (const [prefix, data] of Object.entries(routes)) {
          if (url.startsWith(prefix)) return Promise.resolve(json(data, 200))
        }
        return Promise.resolve(json({ detail: "not found" }, 404))
      }),
    )
    renderWithProviders(<AnnotatePage />, { route: "/annotate?page=462828_p1" })
    await screen.findByText("0 / 1 Seiten fertig")

    await user.keyboard("f")
    await new Promise((r) => setTimeout(r, 400))

    expect(puts).toEqual([])
    expect(screen.queryByText("Wortliste hat sich geändert")).not.toBeInTheDocument()
  })
})
