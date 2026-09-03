import { fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import type { DemoResult } from "@/lib/types"
import { DemoPage } from "./demo-page"

const IDLE_RUN = {
  running: false, job: null, args: {}, run_id: null, lines: [], exit_code: null, elapsed: null,
}

const UPLOAD_ID = "0123456789abcdef0123456789abcdef"

function pdfFile(name = "prospekt.pdf") {
  return new File(["%PDF-1.7"], name, { type: "application/pdf" })
}

function offer(overrides: Partial<DemoResult["offers"][number]> = {}) {
  return {
    page_index: 0,
    bbox: [0, 0, 30, 10] as [number, number, number, number],
    product: "Butter", brand: "Landliebe", price: "1.29", old_price: null,
    quantity: null, unit_price: null, app_price: null, discount: null, valid: null,
    variants: [], confidence: 0.9, arithmetic: "confirmed" as const,
    entity_word_ranges: [{ type: "PRODUCT", start: 0, end: 1 }],
    ...overrides,
  }
}

function demoResult(overrides: Partial<DemoResult> = {}): DemoResult {
  const offers = overrides.offers ?? [offer()]
  return {
    doc_id: "abc123",
    models: { variant: "gbert", checkpoint: "fake/best", pairs_checkpoint: "fake/pairs.pt", pair_threshold: 0.68 },
    timing: { extract: 0.1, ner: 0.2, grouping: 0.05 },
    pages_without_text: [],
    pages: [
      {
        page_index: 0, width: 100, height: 100, png_base64: null,
        words: [{ text: "Butter", bbox: [0, 0, 10, 10] }, { text: "1.29", bbox: [20, 0, 30, 10] }],
        entities: [],
        offers,
      },
    ],
    offers,
    ...overrides,
  }
}

afterEach(() => vi.unstubAllGlobals())

describe("DemoPage", () => {
  it("zeigt die Eingabekarte ohne Ergebnis", async () => {
    mockFetch({ "/api/run": IDLE_RUN })
    renderWithProviders(<DemoPage />)

    expect(await screen.findByLabelText("PDF auswählen")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /verarbeiten/i })).toBeDisabled()
  })

  it("startet Upload und Job mit der gewählten Variante", async () => {
    mockFetch({
      "/api/run": IDLE_RUN,
      "/api/demo/upload": { upload_id: UPLOAD_ID, pages: 1, bytes: 123 },
    })
    renderWithProviders(<DemoPage />)
    const user = userEvent.setup()

    const input = screen.getByLabelText("PDF auswählen").querySelector("input")!
    await user.upload(input, pdfFile())
    await user.click(screen.getByRole("button", { name: /layoutxlm/i }))
    await user.click(screen.getByRole("button", { name: /verarbeiten/i }))

    await waitFor(() => {
      const call = vi
        .mocked(fetch)
        .mock.calls.find(([url, init]) => {
          const u = url.toString()
          return u.startsWith("/api/run") && (init as RequestInit | undefined)?.method === "POST"
        })
      expect(call).toBeDefined()
      const body = JSON.parse((call?.[1] as RequestInit).body as string)
      expect(body).toEqual({
        job: "extract-pdf",
        args: { upload_id: UPLOAD_ID, variant: "layoutxlm" },
      })
    })
  })

  it("zeigt den Seitenfortschritt, waehrend der Job laeuft", async () => {
    mockFetch({
      "/api/run": {
        ...IDLE_RUN, running: true, job: "extract-pdf",
        args: { upload_id: UPLOAD_ID, variant: "gbert" },
        lines: ["Lade Modelle (gbert) ...", "  Seite 1/3: 0.31s"],
      },
      "/api/demo/upload": { upload_id: UPLOAD_ID, pages: 3, bytes: 999 },
    })
    renderWithProviders(<DemoPage />)
    const user = userEvent.setup()

    const input = screen.getByLabelText("PDF auswählen").querySelector("input")!
    await user.upload(input, pdfFile())
    await user.click(screen.getByRole("button", { name: /verarbeiten/i }))

    expect(await screen.findByText("Seite 1 von 3, 0.31 s")).toBeInTheDocument()
  })

  it("zeigt das Ergebnis, sobald der Job fertig ist", async () => {
    mockFetch({
      "/api/run": {
        ...IDLE_RUN, job: "extract-pdf", exit_code: 0,
        args: { upload_id: UPLOAD_ID, variant: "gbert" },
        lines: ["  Seite 1/1: 0.10s"],
      },
      "/api/demo/upload": { upload_id: UPLOAD_ID, pages: 1, bytes: 999 },
      [`/api/demo/${UPLOAD_ID}`]: demoResult(),
    })
    renderWithProviders(<DemoPage />)
    const user = userEvent.setup()

    const input = screen.getByLabelText("PDF auswählen").querySelector("input")!
    await user.upload(input, pdfFile())
    await user.click(screen.getByRole("button", { name: /verarbeiten/i }))

    expect(await screen.findByText("Butter")).toBeInTheDocument()
    expect(screen.getByText("Landliebe")).toBeInTheDocument()
    expect(screen.getByText("1 Angebote")).toBeInTheDocument()
    // Export-Links zeigen auf den Export-Endpunkt mit dem passenden Format.
    expect(screen.getByRole("link", { name: /CSV/ })).toHaveAttribute(
      "href", `/api/demo/${UPLOAD_ID}/export?format=csv`,
    )
  })

  it("filtert die Angebote ueber das Suchfeld", async () => {
    const offers = [
      offer({ product: "Butter", brand: "Landliebe" }),
      offer({ product: "Milch", brand: "Weihenstephan", entity_word_ranges: [{ type: "PRODUCT", start: 5, end: 6 }] }),
    ]
    mockFetch({
      "/api/run": {
        ...IDLE_RUN, job: "extract-pdf", exit_code: 0,
        args: { upload_id: UPLOAD_ID, variant: "gbert" }, lines: [],
      },
      "/api/demo/upload": { upload_id: UPLOAD_ID, pages: 1, bytes: 999 },
      [`/api/demo/${UPLOAD_ID}`]: demoResult({
        offers,
        pages: [{ page_index: 0, width: 100, height: 100, png_base64: null, words: [], entities: [], offers }],
      }),
    })
    renderWithProviders(<DemoPage />)
    const user = userEvent.setup()

    const input = screen.getByLabelText("PDF auswählen").querySelector("input")!
    await user.upload(input, pdfFile())
    await user.click(screen.getByRole("button", { name: /verarbeiten/i }))
    await screen.findByText("Butter")
    expect(screen.getByText("Milch")).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("Angebote durchsuchen"), { target: { value: "milch" } })

    expect(screen.queryByText("Butter")).not.toBeInTheDocument()
    expect(screen.getByText("Milch")).toBeInTheDocument()
  })

  it("zeigt eine klare Meldung fuer ein PDF ohne Textlayer", async () => {
    mockFetch({
      "/api/run": {
        ...IDLE_RUN, job: "extract-pdf", exit_code: 0,
        args: { upload_id: UPLOAD_ID, variant: "gbert" }, lines: [],
      },
      "/api/demo/upload": { upload_id: UPLOAD_ID, pages: 1, bytes: 999 },
      [`/api/demo/${UPLOAD_ID}`]: demoResult({
        offers: [],
        pages_without_text: [`${UPLOAD_ID.slice(0, 12)}_p1`],
        pages: [{ page_index: 0, width: 100, height: 100, png_base64: null, words: [], entities: [], offers: [] }],
      }),
    })
    renderWithProviders(<DemoPage />)
    const user = userEvent.setup()

    const input = screen.getByLabelText("PDF auswählen").querySelector("input")!
    await user.upload(input, pdfFile())
    await user.click(screen.getByRole("button", { name: /verarbeiten/i }))

    expect(await screen.findByText("PDF ohne Textlayer")).toBeInTheDocument()
    expect(screen.getByText("Keine Angebote gefunden – das PDF enthält keine erkennbaren Angebote.")).toBeInTheDocument()
  })
})
