import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render } from "@testing-library/react"
import type { ReactElement } from "react"
import { MemoryRouter } from "react-router-dom"
import { TooltipProvider } from "@/components/ui/tooltip"
import { vi } from "vitest"

export function renderWithProviders(ui: ReactElement, opts: { route?: string } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    // Spiegelt den echten Baum: das App-Layout stellt den Tooltip-Provider
    // bereit. Ohne ihn wirft Radix beim ersten Tooltip und der Test sieht eine
    // leere Seite statt der Komponente.
    <QueryClientProvider client={qc}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[opts.route ?? "/"]}>{ui}</MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  )
}

/** Mockt fetch: URL-Präfix -> JSON-Antwort. Unbekannte URLs geben 404. */
export function mockFetch(routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString()
      for (const [prefix, data] of Object.entries(routes)) {
        if (url.startsWith(prefix)) {
          // Ein PUT beantwortet die API mit dem gespeicherten Datensatz. Der
          // Stub spiegelt den Body in die Route zurück, sonst antwortet er auf
          // jedes Speichern mit dem Ausgangszustand - und wer die Antwort in
          // seinen Cache legt, dreht damit die eigene Eingabe zurück.
          const isRecord = data !== null && typeof data === "object" && !Array.isArray(data)
          const body =
            init?.method === "PUT" && isRecord && typeof init.body === "string"
              ? { ...(data as object), ...JSON.parse(init.body) }
              : data
          return new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        }
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 })
    }),
  )
}
