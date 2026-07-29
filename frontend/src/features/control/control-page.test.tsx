import { fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { ControlPage } from "./control-page"

const IDLE_RUN = {
  running: false, job: null, args: {}, run_id: null, lines: [], exit_code: null, elapsed: null,
}

const JOBS = [
  {
    job: "01_download_flyers", title: "Prospekte laden", what: "Holt einen Katalog.",
    params: [
      { key: "url", label: "Katalog-URL", kind: "str", default: null, choices: [], required: true, help: "" },
      { key: "max_pages", label: "Seiten höchstens", kind: "int", default: 40, choices: [], required: false, help: "" },
    ],
  },
  { job: "02_extract_words", title: "Wörter extrahieren", what: "PyMuPDF liest.", params: [] },
]

const TOTALS = {
  raw: 0, words: 0, images: 0, labeled: 0, gold_done: 0, gold_in_progress: 0,
}

function base(extra: Record<string, unknown> = {}) {
  return {
    "/api/jobs": JOBS,
    "/api/runs": [],
    "/api/run": IDLE_RUN,
    "/api/status": { catalogs: [], totals: TOTALS },
    "/api/evaluation": [],
    "/api/model": [],
    "/api/catalogs": { entries: [], error: null },
    ...extra,
  }
}

describe("ControlPage", () => {
  it("zeigt je Schritt ein Formular aus dem Job-Katalog", async () => {
    mockFetch(base())
    renderWithProviders(<ControlPage />)

    expect(await screen.findByLabelText(/Katalog-URL/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Seiten höchstens/)).toHaveValue("40")
  })

  it("schickt die eingegebenen Werte beim Start", async () => {
    mockFetch(base())
    renderWithProviders(<ControlPage />)

    fireEvent.change(await screen.findByLabelText(/Katalog-URL/), {
      target: { value: "https://x/?catalogId=42" },
    })
    fireEvent.click(screen.getAllByRole("button", { name: /starten/i })[0])

    await waitFor(() => {
      const call = vi
        .mocked(fetch)
        .mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "POST")
      expect(call).toBeDefined()
      expect(JSON.parse((call?.[1] as RequestInit).body as string)).toEqual({
        job: "01_download_flyers",
        args: { url: "https://x/?catalogId=42", max_pages: "40" },
      })
    })
  })

  it("zeigt die Historie mit Exit-Code", async () => {
    mockFetch(base({
      "/api/runs": [{
        run_id: "20260729-142201_01_download_flyers", job: "01_download_flyers",
        title: "Prospekte laden", args: {}, command: ["python", "01_download_flyers.py"],
        started: "2026-07-29T14:22:01", finished: "2026-07-29T14:22:03",
        exit_code: 2, duration: 2.0,
      }],
    }))
    renderWithProviders(<ControlPage />)

    // Die Historie liegt hinter dem Reiter "Läufe" – Live und Vergangenheit
    // teilen sich eine Spalte, weil man immer nur eins davon ansieht.
    // userEvent statt fireEvent: Radix-Tabs reagieren auf Pointer-Ereignisse.
    await userEvent.click(await screen.findByRole("tab", { name: /Läufe/ }))
    expect(await screen.findByText(/Abbruch \(2\)/)).toBeInTheDocument()
  })

  it("meldet ein kaputtes Katalog-Verzeichnis, ohne die Seite zu verlieren", async () => {
    mockFetch(base({
      "/api/catalogs": { entries: [], error: "catalogs.json ist nicht lesbar. Merge-Konflikt?" },
    }))
    renderWithProviders(<ControlPage />)

    // Die Katalogverwaltung ist eingeklappt, damit die Seite nicht überläuft.
    fireEvent.click(await screen.findByText("Kataloge verwalten"))
    expect(await screen.findByText(/Merge-Konflikt/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Katalog-URL/)).toBeInTheDocument()
  })
})
