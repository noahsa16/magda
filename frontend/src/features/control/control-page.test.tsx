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
    job: "download", title: "Prospekte laden", what: "Holt einen Katalog.",
    params: [
      { key: "url", label: "Katalog-URL", kind: "str", default: null, choices: [], required: true, help: "" },
      { key: "max_pages", label: "Seiten höchstens", kind: "int", default: 40, choices: [], required: false, help: "" },
    ],
  },
  { job: "extract", title: "Wörter extrahieren", what: "PyMuPDF liest.", params: [] },
  { job: "label", title: "LLM-Labeling", what: "Ein Vision-Modell markiert Spans.", params: [] },
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

/** Öffnet einen Schritt über seine Kachel. */
async function oeffne(titel: string | RegExp) {
  fireEvent.click(await screen.findByRole("button", { name: titel }))
}

describe("ControlPage", () => {
  it("zeigt die Schritte als Kacheln, nicht als offene Formulare", async () => {
    // Zehn Formulare untereinander waren zwei Bildschirmhöhen, in denen nichts
    // hervorstach. Erst der Klick auf einen Schritt zeigt seine Parameter.
    mockFetch(base())
    renderWithProviders(<ControlPage />)

    expect(await screen.findByRole("button", { name: /Wörter extrahieren/ })).toBeInTheDocument()
    expect(screen.queryByLabelText(/Katalog-URL/)).not.toBeInTheDocument()
  })

  it("öffnet beim Klick das Formular des Schritts", async () => {
    mockFetch(base())
    renderWithProviders(<ControlPage />)
    await oeffne(/Prospekte laden/)

    expect(await screen.findByLabelText(/Katalog-URL/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Seiten höchstens/)).toHaveValue("40")
    expect(screen.getByText("$ magda download")).toBeInTheDocument()
  })

  it("führt über die Brotkrumen zurück zur Übersicht", async () => {
    mockFetch(base())
    renderWithProviders(<ControlPage />)
    await oeffne(/Prospekte laden/)
    await screen.findByLabelText(/Katalog-URL/)

    fireEvent.click(screen.getByRole("button", { name: "Alle Schritte" }))

    expect(screen.queryByLabelText(/Katalog-URL/)).not.toBeInTheDocument()
    expect(await screen.findByRole("button", { name: /LLM-Labeling/ })).toBeInTheDocument()
  })

  it("schickt die eingegebenen Werte beim Start", async () => {
    mockFetch(base())
    renderWithProviders(<ControlPage />)
    await oeffne(/Prospekte laden/)

    fireEvent.change(await screen.findByLabelText(/Katalog-URL/), {
      target: { value: "https://x/?catalogId=42" },
    })
    fireEvent.click(screen.getByRole("button", { name: /starten/i }))

    await waitFor(() => {
      const call = vi
        .mocked(fetch)
        .mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "POST")
      expect(call).toBeDefined()
      expect(JSON.parse((call?.[1] as RequestInit).body as string)).toEqual({
        job: "download",
        args: { url: "https://x/?catalogId=42", max_pages: "40" },
      })
    })
  })

  it("zeigt den laufenden Schritt ohne Zutun", async () => {
    // Wer einen Lauf gestartet hat und die Seite neu lädt, will sehen, was
    // läuft – nicht erst wieder danach suchen.
    mockFetch(base({
      "/api/run": { ...IDLE_RUN, running: true, job: "label", lines: ["Seite 1"] },
    }))
    renderWithProviders(<ControlPage />)

    expect(await screen.findByText("$ magda label")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Stoppen/ })).toBeInTheDocument()
  })

  it("zeigt die Historie mit Exit-Code", async () => {
    mockFetch(base({
      "/api/runs": [{
        run_id: "20260729-142201_download", job: "download",
        title: "Prospekte laden", args: {}, command: ["python", "-m", "magda", "download"],
        started: "2026-07-29T14:22:01", finished: "2026-07-29T14:22:03",
        exit_code: 2, duration: 2.0,
      }],
    }))
    renderWithProviders(<ControlPage />)
    await oeffne(/Prospekte laden/)

    // Die Historie liegt hinter dem Reiter "Läufe" – Live und Vergangenheit
    // teilen sich eine Spalte, weil man immer nur eins davon ansieht.
    // userEvent statt fireEvent: Radix-Tabs reagieren auf Pointer-Ereignisse.
    await userEvent.click(await screen.findByRole("tab", { name: /Läufe/ }))
    expect(await screen.findByText(/Abbruch \(2\)/)).toBeInTheDocument()
  })

  it("hebt Fehlerzeilen in der Ausgabe hervor", async () => {
    mockFetch(base({
      "/api/run": {
        ...IDLE_RUN, running: true, job: "extract",
        lines: ["### Extraktion", "Traceback (most recent call last):"],
      },
    }))
    renderWithProviders(<ControlPage />)

    const fehler = await screen.findByText(/Traceback/)
    expect(fehler.className).toMatch(/riso-pink/)
  })

  it("trennt Pipeline-Schritte von Auswertungswerkzeugen", async () => {
    mockFetch(base())
    renderWithProviders(<ControlPage />)

    await screen.findByRole("button", { name: /Wörter extrahieren/ })
    // Der Fortschrittszähler läuft über die Pipeline, nicht über alles:
    // ein Flair-Vergleich ist kein Schritt, den man abhaken muss.
    expect(screen.getByText("0 / 6 erledigt")).toBeInTheDocument()
  })
})
