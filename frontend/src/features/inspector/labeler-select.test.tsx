import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { LabelerSelect } from "./labeler-select"

function renderWith(labelers: { model: string; pages: number }[]) {
  vi.spyOn(api, "labelers").mockResolvedValue(labelers)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <LabelerSelect value={undefined} onChange={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe("LabelerSelect", () => {
  it("bleibt unsichtbar, solange nur ein Modell gelabelt hat", async () => {
    const { container } = renderWith([{ model: "mistral-medium-3.5-128b", pages: 196 }])
    // Kurz warten, damit die Query wirklich aufgelöst ist – sonst prüft der
    // Test nur den Ladezustand und wäre auch bei zwei Modellen grün.
    await waitFor(() => expect(api.labelers).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it("zeigt die Auswahl, sobald es etwas zu vergleichen gibt", async () => {
    renderWith([
      { model: "mistral-medium-3.5-128b", pages: 196 },
      { model: "qwen3.6-27b", pages: 196 },
    ])
    expect(await screen.findByText("Labels von")).toBeInTheDocument()
    expect(screen.getByRole("combobox")).toHaveTextContent("mistral-medium-3.5-128b")
  })
})
