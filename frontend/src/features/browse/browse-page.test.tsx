import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { createMemoryRouter, RouterProvider } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import type { LabelSource } from "@/lib/types"
import { BrowsePage } from "./browse-page"

const SOURCES: LabelSource[] = [
  { kind: "model", id: "qwen3.5-397b-a17b", name: "qwen3.5-397b-a17b", pages: 196, done: 196 },
  { kind: "model", id: "mistral-medium-3.5-128b", name: "mistral-medium-3.5-128b", pages: 196, done: 196 },
  { kind: "gold", id: "Noah", name: "Noah", pages: 3, done: 3 },
  {
    kind: "gold",
    id: "sonnet-5 (vorannotiert, ungeprueft)",
    name: "sonnet-5 (vorannotiert, ungeprueft)",
    pages: 40,
    done: 0,
  },
]

function setup(route = "/labels") {
  vi.spyOn(api, "sources").mockResolvedValue(SOURCES)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter([{ path: "/labels", element: <BrowsePage /> }], {
    initialEntries: [route],
  })
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe("BrowsePage — Ordnerebenen", () => {
  it("trennt Modell-Labels von Handannotation", async () => {
    setup()
    expect(await screen.findByText("Modell-Labels")).toBeInTheDocument()
    expect(screen.getByText("Handannotation")).toBeInTheDocument()
    // Auf der obersten Ebene stehen die Überordner, nicht schon die Läufe.
    expect(screen.queryByText("qwen3.5-397b-a17b")).not.toBeInTheDocument()
  })

  it("zählt Handannotation nach geprüften Seiten, nicht nach vorhandenen", async () => {
    setup()
    // 3 von Noah geprüft, 40 von Sonnet vorannotiert und ungeprüft.
    expect(await screen.findByText("3 von 43 geprüft")).toBeInTheDocument()
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
    await user.click(await screen.findByText("Handannotation"))
    // Der Klammerzusatz ist Beiwerk, der Name davor die Beschriftung.
    expect(await screen.findByText("sonnet-5")).toBeInTheDocument()
    expect(screen.getByText("ungeprüft")).toBeInTheDocument()
    // Geprüfte Handarbeit trägt das Kennzeichen nicht.
    expect(screen.getAllByText("ungeprüft")).toHaveLength(1)
  })
})
