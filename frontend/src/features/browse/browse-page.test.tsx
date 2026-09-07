import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
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

const TASK = {
  title: "Testkatalog 1364390 von Hand annotieren",
  created: "2026-09-03",
  for: ["Kjell", "Bogdan"],
  why: "",
  pages: ["1364390_p1", "1364390_p2", "1364390_p3"],
}

function setup(route = "/labels", audits: { label: string; total: number; judged: number }[] = []) {
  vi.spyOn(api, "sources").mockResolvedValue(SOURCES)
  vi.spyOn(api, "annotationTask").mockResolvedValue(TASK)
  vi.spyOn(api, "gold").mockResolvedValue([
    { page_id: "1364390_p1", catalog: "1364390", status: "done", annotator: "Kjell", num_spans: 4, stale: false },
    { page_id: "1364390_p2", catalog: "1364390", status: "untouched", annotator: "", num_spans: 0, stale: false },
    { page_id: "1364390_p3", catalog: "1364390", status: "untouched", annotator: "", num_spans: 0, stale: false },
  ])
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
      { path: "/annotate", element: <div>Annotator</div> },
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


describe("BrowsePage — Annotationsaufgabe", () => {
  it("zeigt die Aufgabe als ersten Ordner der Handannotation", async () => {
    // Die Aufgabenseiten haben noch keine Gold-Datei, also keinen Annotator.
    // In den Urheber-Ordnern ("Noah 3 von 3") kam die Aufgabe deshalb gar
    // nicht vor – der Einstieg für Kjell und Bogdan fehlte.
    const user = userEvent.setup()
    setup()
    await user.click(await screen.findByRole("button", { name: /Handannotation öffnen/ }))
    expect(await screen.findByText(TASK.title)).toBeInTheDocument()
    expect(screen.getByText("1 von 3 Seiten fertig")).toBeInTheDocument()
    expect(screen.getByText("für Kjell und Bogdan")).toBeInTheDocument()
  })

  it("öffnet die Aufgabe im ungefilterten Annotator", async () => {
    // `annotator=` ohne Wert: BrowsePage warf den Leerstring als "nicht
    // gesetzt" weg und zeigte die Quellenübersicht statt des Annotators.
    const user = userEvent.setup()
    setup()
    await user.click(await screen.findByRole("button", { name: /Handannotation öffnen/ }))
    await user.click(await screen.findByText(TASK.title))
    // AnnotatePage selbst lädt hier nicht (Fetch ist nicht gemockt); es
    // reicht, dass die Ordnerebene weg ist und der Annotator übernimmt.
    await waitFor(() => expect(screen.queryByText("Handannotation")).not.toBeInTheDocument())
    expect(screen.queryByText("Modell-Labels")).not.toBeInTheDocument()
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
