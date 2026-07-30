import { render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createMemoryRouter, RouterProvider } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { routes } from "./router"

// Die Seiten feuern Queries – für den Shell-Smoke-Test reicht ein leerer Mock.
vi.stubGlobal("fetch", vi.fn(async () => new Response("[]", {
  status: 200, headers: { "Content-Type": "application/json" },
})))

describe("App-Shell", () => {
  it("zeigt die Navigation mit allen fünf Bereichen", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const router = createMemoryRouter(routes, { initialEntries: ["/"] })
    render(
      <QueryClientProvider client={qc}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )
    expect(await screen.findByRole("link", { name: /Übersicht/ })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Pipeline/ })).toHaveAttribute("href", "/pipeline")
    // Inspektor und Annotator liegen seit dem Ordner-Umbau hinter einem
    // gemeinsamen Einstieg: "wessen Labels?" ist die erste Frage.
    expect(screen.getByRole("link", { name: /Daten/ })).toHaveAttribute("href", "/labels")
    expect(screen.getByRole("link", { name: /Ergebnis/ })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Demo/ })).toBeInTheDocument()
  })
})
