import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render } from "@testing-library/react"
import type { ReactElement } from "react"
import { MemoryRouter } from "react-router-dom"
import { vi } from "vitest"

export function renderWithProviders(ui: ReactElement, opts: { route?: string } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[opts.route ?? "/"]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

/** Mockt fetch: URL-Präfix -> JSON-Antwort. Unbekannte URLs geben 404. */
export function mockFetch(routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = input.toString()
      for (const [prefix, data] of Object.entries(routes)) {
        if (url.startsWith(prefix)) {
          return new Response(JSON.stringify(data), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        }
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 })
    }),
  )
}
