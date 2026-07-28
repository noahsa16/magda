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

const STATUS = {
  catalogs: [{ id: "462828", raw: 1, words: 1, images: 1, labeled: 0, downloaded: "2026-07-20" }],
  totals: { raw: 1, words: 1, images: 1, labeled: 0 },
}

function setup({ route, ...overrides }: Record<string, unknown> & { route?: string } = {}) {
  mockFetch({
    "/api/schema": { entity_types: ["PRODUCT", "BRAND"] },
    "/api/status": STATUS,
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
  return renderWithProviders(<AnnotatePage />, {
    route: (route as string | undefined) ?? "/annotate?catalog=462828&page=462828_p1",
  })
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
      // /api/gold listet jede Seite aus data/words/, auch die unberührten -
      // eine leere Liste bei vorhandenen Seiten gibt es serverseitig nicht.
      "/api/gold": [{
        page_id: "462828_p1", catalog: "462828", status: "untouched",
        annotator: "", num_spans: 0, stale: false,
      }],
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

describe("AnnotatePage — Ebenen", () => {
  it("zeigt ohne Parameter die Prospekt-Übersicht", async () => {
    setup({ route: "/annotate" })
    expect(await screen.findByText("462828")).toBeInTheDocument()
    expect(screen.queryByLabelText("Annotator")).not.toBeInTheDocument()
  })

  it("öffnet per Klick auf eine Kachel die Seitenliste", async () => {
    const user = userEvent.setup()
    setup({ route: "/annotate" })
    await user.click(await screen.findByRole("button", { name: /462828/ }))
    expect(await screen.findByLabelText("Annotator")).toBeInTheDocument()
  })

  it("führt über den Brotkrumen zurück zur Übersicht", async () => {
    const user = userEvent.setup()
    setup({ route: "/annotate?catalog=462828" })
    await user.click(await screen.findByRole("button", { name: "Prospekte" }))
    expect(await screen.findByText(/Seiten/)).toBeInTheDocument()
    expect(screen.queryByLabelText("Annotator")).not.toBeInTheDocument()
  })

  it("zeigt bei unbekanntem Katalog die Übersicht mit Hinweis", async () => {
    setup({ route: "/annotate?catalog=gibtsnicht" })
    expect(await screen.findByText(/nicht gefunden/i)).toBeInTheDocument()
  })

  it("zeigt den Hinweis auch, wenn es noch gar keine Prospekte gibt", async () => {
    // Ohne Kacheln darf ein veralteter Lesezeichen-Link nicht in der
    // Seitenansicht mit leerer Liste landen.
    setup({
      route: "/annotate?catalog=gibtsnicht",
      "/api/pages": [],
      "/api/gold": [],
      "/api/status": { catalogs: [], totals: { raw: 0, words: 0, images: 0, labeled: 0 } },
    })
    expect(await screen.findByText(/nicht gefunden/i)).toBeInTheDocument()
    expect(screen.queryByLabelText("Annotator")).not.toBeInTheDocument()
  })

  it("zeigt den Leerzustand nicht, solange die Gold-Übersicht lädt", async () => {
    // Die Kacheln kommen aus /api/gold. Löst /api/pages zuerst auf, forderte
    // die Übersicht sonst zum Neu-Extrahieren auf, während gold noch unterwegs war.
    const json = (data: unknown) =>
      new Response(JSON.stringify(data), {
        status: 200, headers: { "Content-Type": "application/json" },
      })
    const routes: Record<string, unknown> = {
      "/api/schema": { entity_types: ["PRODUCT", "BRAND"] },
      "/api/pages": [{ page_id: "462828_p1", catalog: "462828", labeled: false }],
      "/api/status": STATUS,
    }
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = input.toString()
        // Die Gold-Übersicht lädt für die Dauer des Tests nie.
        if (url.startsWith("/api/gold")) return new Promise<Response>(() => {})
        for (const [prefix, data] of Object.entries(routes)) {
          if (url.startsWith(prefix)) return Promise.resolve(json(data))
        }
        return Promise.resolve(json({ detail: "not found" }))
      }),
    )
    const { container } = renderWithProviders(<AnnotatePage />, { route: "/annotate" })

    await new Promise((r) => setTimeout(r, 100))

    expect(screen.queryByText(/Noch keine Prospekte extrahiert/)).not.toBeInTheDocument()
    expect(container.querySelector('[data-slot="skeleton"]')).toBeInTheDocument()
  })

  it("zeigt das Ladedatum des Prospekts auf der Kachel", async () => {
    setup({ route: "/annotate" })
    expect(await screen.findByText(/geladen 20\.07\./)).toBeInTheDocument()
  })

  it("blättert nicht über die Grenze des offenen Prospekts hinaus", async () => {
    setup({
      route: "/annotate?catalog=462828&page=462828_p1",
      "/api/pages": [
        { page_id: "462828_p1", catalog: "462828", labeled: false },
        { page_id: "999999_p1", catalog: "999999", labeled: false },
      ],
      "/api/gold": [
        {
          page_id: "462828_p1", catalog: "462828", status: "untouched",
          annotator: "", num_spans: 0, stale: false,
        },
        {
          page_id: "999999_p1", catalog: "999999", status: "untouched",
          annotator: "", num_spans: 0, stale: false,
        },
      ],
      "/api/status": {
        catalogs: [
          { id: "462828", raw: 1, words: 1, images: 1, labeled: 0, downloaded: "2026-07-20" },
          { id: "999999", raw: 1, words: 1, images: 1, labeled: 0, downloaded: "2026-07-21" },
        ],
        totals: { raw: 2, words: 2, images: 2, labeled: 0 },
      },
    })
    expect(await screen.findByText("1 / 1")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Nächste Seite/ })).toBeDisabled()
  })
})
