import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { createMemoryRouter, RouterProvider } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import type { LabelSource } from "@/lib/types"
import { BrowsePage } from "./browse-page"

const SOURCES: LabelSource[] = [
  { kind: "model", id: "sonnet-5", name: "sonnet-5", pages: 422, done: 422, status: "canonical" },
  { kind: "model", id: "sonnet-5-app", name: "sonnet-5-app", pages: 296, done: 296, status: "variant" },
  {
    kind: "model",
    id: "qwen3.5-397b-a17b",
    name: "qwen3.5-397b-a17b",
    pages: 196,
    done: 196,
    status: "archive",
  },
  {
    kind: "model",
    id: "mistral-medium-3.5-128b",
    name: "mistral-medium-3.5-128b",
    pages: 196,
    done: 196,
    status: "archive",
  },
  { kind: "offer_groups", id: "claude-sonnet-5", name: "claude-sonnet-5", pages: 195, done: 195 },
  { kind: "gold", id: "Noah", name: "Noah", pages: 3, done: 3 },
  {
    kind: "gold",
    id: "sonnet-5 (vorannotiert, ungeprueft)",
    name: "sonnet-5 (vorannotiert, ungeprueft)",
    pages: 40,
    done: 0,
  },
]

function setup(route = "/labels", audits: { label: string; total: number; judged: number }[] = []) {
  vi.spyOn(api, "sources").mockResolvedValue(SOURCES)
  vi.spyOn(api, "audits").mockResolvedValue({
    audits: audits.map((a) => ({
      labels_from: "sonnet-5",
      labeled: 0, candidate: 0, correct: 0, wrong: 0, unsure: 0,
      ...a,
    })),
  } as Awaited<ReturnType<typeof api.audits>>)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      { path: "/labels", element: <BrowsePage /> },
      { path: "/group", element: <div>Gruppierungsseite</div> },
    ],
    { initialEntries: [route] },
  )
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe("BrowsePage — Ordnerebenen", () => {
  it("zeigt oben nur die Modell-Labels", async () => {
    setup()
    expect(await screen.findByText("Modell-Labels")).toBeInTheDocument()
    // Auf der obersten Ebene steht der Überordner, nicht schon die Läufe.
    expect(screen.queryByText("qwen3.5-397b-a17b")).not.toBeInTheDocument()
  })

  it("blendet die Handannotation aus, ohne sie zu entfernen", async () => {
    // Team-Entscheidung: gelabelt wird maschinell. Die Handannotation bleibt
    // als Werkzeug bestehen – gold/ ist versioniert und `magda gold` misst
    // weiter dagegen –, steht aber nicht mehr im Weg.
    const user = userEvent.setup()
    setup()

    await screen.findByText("Modell-Labels")
    expect(screen.queryByText("Handannotation")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /Handannotation öffnen/ }))
    expect(await screen.findByText("sonnet-5")).toBeInTheDocument()
  })

  it("öffnet die Modell-Läufe erst eine Ebene tiefer", async () => {
    const user = userEvent.setup()
    setup()
    await user.click(await screen.findByText("Modell-Labels"))
    expect(await screen.findByText("qwen3.5-397b-a17b")).toBeInTheDocument()
    expect(screen.getByText("mistral-medium-3.5-128b")).toBeInTheDocument()
  })

  it("markiert ungeprüfte Vorannotation als solche", async () => {
    const user = userEvent.setup()
    setup()
    await user.click(await screen.findByRole("button", { name: /Handannotation öffnen/ }))
    // Der Klammerzusatz ist Beiwerk, der Name davor die Beschriftung.
    expect(await screen.findByText("sonnet-5")).toBeInTheDocument()
    expect(screen.getByText("ungeprüft")).toBeInTheDocument()
    // Geprüfte Handarbeit trägt das Kennzeichen nicht.
    expect(screen.getAllByText("ungeprüft")).toHaveLength(1)
  })
})


describe("BrowsePage — Label-Prüfung", () => {
  it("bietet die Prüfung nur an, wenn etwas vorsortiert ist", async () => {
    setup()
    // Ohne `magda audit` führte der Link auf eine leere Seite mit einer
    // Kommandozeile darauf – das ist keine Einladung, sondern eine Sackgasse.
    expect(await screen.findByText("Modell-Labels")).toBeInTheDocument()
    expect(screen.queryByText(/von Hand prüfen/)).not.toBeInTheDocument()
  })

  it("nennt die offenen Fälle, nicht die Gesamtzahl", async () => {
    setup("/labels", [{ label: "APP_PRICE", total: 374, judged: 74 }])
    // 300 offen, nicht 374 – die Zahl soll sagen, was noch zu tun ist.
    expect(await screen.findByText(/APP_PRICE von Hand prüfen/)).toBeInTheDocument()
    expect(screen.getByText(/300 offen/)).toBeInTheDocument()
  })
})

describe("BrowsePage — Ordnung unter den Quellen", () => {
  it("zeigt die Gruppierung als eigenen Ordner neben den Labels", async () => {
    // Sie war bis hierher ein Kleingedrucktes-Link unter dem Raster. Spans und
    // Gruppen beantworten zwei verschiedene Fragen ("was ist dieses Wort" und
    // "wozu gehört es"); als Fussnote sieht die zweite aus wie ein Nachtrag.
    const user = userEvent.setup()
    setup()

    const kachel = await screen.findByText("Angebots-Gruppierung")
    expect(screen.getByText("195 Seiten")).toBeInTheDocument()

    await user.click(kachel)
    expect(await screen.findByText("Gruppierungsseite")).toBeInTheDocument()
  })

  it("zählt im Überordner nur, womit gearbeitet wird", async () => {
    // Vier Modellordner, davon zwei erledigte Vergleichsarme.
    setup()
    expect(await screen.findByText("2 Läufe")).toBeInTheDocument()
  })

  it("kennzeichnet die kanonische Quelle und das Archiv", async () => {
    // Der eigentliche Anlass: acht gleich aussehende Ordner, und welcher die
    // berichteten Zahlen trägt, stand nirgends.
    const user = userEvent.setup()
    setup()

    await user.click(await screen.findByText("Modell-Labels"))

    await screen.findByText("sonnet-5")
    expect(screen.getByText("kanonisch")).toBeInTheDocument()
    expect(screen.getAllByText("Archiv")).toHaveLength(2)
    // Nicht nur die Beschriftung: der Ordner sieht auch anders aus. Ohne
    // diese Zusicherung liesse sich der Ton wegdrehen, ohne dass etwas
    // rot wird – der Test hielte dann den Text fest und nichts sonst.
    expect(screen.getByTitle("sonnet-5")).toHaveAttribute("data-tone", "model")
    expect(screen.getByTitle("qwen3.5-397b-a17b")).toHaveAttribute("data-tone", "archive")
  })
})
