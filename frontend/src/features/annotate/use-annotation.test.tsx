import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { useAnnotation } from "./use-annotation"

const GOLD_A = {
  page_id: "462828_p1", words_hash: "hashA", status: "untouched",
  annotator: "", updated: null, spans: [], stale: false,
}
const GOLD_B = {
  page_id: "462828_p2", words_hash: "hashB", status: "untouched",
  annotator: "", updated: null, spans: [], stale: false,
}

interface PendingPut {
  url: string
  body: { words_hash: string; status: string; annotator: string; spans: unknown[] }
  /** Löst den PUT auf, wann immer der Test es will - so lässt sich die
   * Reihenfolge zweier überlappender Flushes gezielt steuern. */
  resolve: (status: number, body: unknown) => void
}

/** Eigener fetch-Mock statt des bestehenden mockFetch-Helfers: Der deckt nur
 * sofort auflösende Erfolgsfälle ab. Hier müssen PUTs kontrolliert und in
 * einer bestimmten Reihenfolge auflösen, auch mit Fehlerantworten. */
function stubFetch(getRoutes: Record<string, unknown>) {
  const puts: PendingPut[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString()
      if (init?.method === "PUT") {
        return new Promise<Response>((resolvePromise) => {
          puts.push({
            url,
            body: JSON.parse(init.body as string),
            resolve: (status, body) =>
              resolvePromise(
                new Response(JSON.stringify(body), {
                  status,
                  headers: { "Content-Type": "application/json" },
                }),
              ),
          })
        })
      }
      for (const [prefix, data] of Object.entries(getRoutes)) {
        if (url.startsWith(prefix)) {
          return Promise.resolve(
            new Response(JSON.stringify(data), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }),
          )
        }
      }
      return Promise.resolve(new Response(JSON.stringify({ detail: "not found" }), { status: 404 }))
    }),
  )
  return puts
}

function renderAnnotation(initialPageId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return renderHook(
    ({ pageId }: { pageId: string | null }) => useAnnotation(pageId, "noah"),
    {
      initialProps: { pageId: initialPageId as string | null },
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={qc}>{children}</QueryClientProvider>
      ),
    },
  )
}

afterEach(() => vi.unstubAllGlobals())

describe("useAnnotation", () => {
  it("verliert die neuere Änderung nicht, wenn der ältere Flush später aufloest", async () => {
    const puts = stubFetch({ "/api/gold/462828_p1": GOLD_A })
    const { result } = renderAnnotation("462828_p1")
    await waitFor(() => expect(result.current.isPending).toBe(false))

    act(() => result.current.setSpans([{ start: 0, end: 1, label: "PRODUCT" }]))
    await waitFor(() => expect(puts).toHaveLength(1))

    // Zweite Bearbeitung, während der erste Save noch aussteht (nicht
    // aufgelöst) - schedule() überschreibt pendingRef mit dieser Änderung.
    act(() =>
      result.current.setSpans([
        { start: 0, end: 1, label: "PRODUCT" },
        { start: 1, end: 2, label: "BRAND" },
      ]),
    )

    // Der ältere Save löst zuerst auf.
    puts[0].resolve(200, { ...GOLD_A, spans: puts[0].body.spans })

    // Ohne den Fix (Referenzvergleich vor dem Nullen von pendingRef) würde
    // dieser Save pendingRef.current nullen, bevor der zweite Timer feuert -
    // die zweite Änderung ginge dann nie ab.
    await waitFor(() => expect(puts).toHaveLength(2), { timeout: 1000 })
    expect(puts[1].body.spans).toHaveLength(2)

    puts[1].resolve(200, { ...GOLD_A, spans: puts[1].body.spans })
    await waitFor(() => expect(result.current.saveState).toBe("saved"))
  })

  it("sichert beim Seitenwechsel die alte Seite, die neue behält ihre eigene Bearbeitung", async () => {
    const puts = stubFetch({
      "/api/gold/462828_p1": GOLD_A,
      "/api/gold/462828_p2": GOLD_B,
    })
    const { result, rerender } = renderAnnotation("462828_p1")
    await waitFor(() => expect(result.current.isPending).toBe(false))

    act(() => result.current.setSpans([{ start: 0, end: 1, label: "PRODUCT" }]))
    // Timer für Seite A steht noch aus (300 ms) - der Seitenwechsel passiert
    // bewusst währenddessen.

    rerender({ pageId: "462828_p2" })
    await waitFor(() => expect(result.current.isPending).toBe(false))

    // Sofortige Bearbeitung auf der neuen Seite, bevor der alte Timer
    // gefeuert hat - schedule() erkennt die andere Seite und erzwingt ein
    // sofortiges Sichern von A.
    act(() => result.current.setSpans([{ start: 0, end: 1, label: "BRAND" }]))

    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0].url).toContain("462828_p1")
    expect(puts[0].body.spans).toEqual([{ start: 0, end: 1, label: "PRODUCT" }])

    puts[0].resolve(200, { ...GOLD_A, spans: puts[0].body.spans })

    // Bs Bearbeitung im Speicher bleibt unberührt vom Save der alten Seite.
    expect(result.current.spans).toEqual([{ start: 0, end: 1, label: "BRAND" }])

    await waitFor(() => expect(puts).toHaveLength(2), { timeout: 1000 })
    expect(puts[1].url).toContain("462828_p2")
    expect(puts[1].body.spans).toEqual([{ start: 0, end: 1, label: "BRAND" }])

    puts[1].resolve(200, { ...GOLD_B, spans: puts[1].body.spans })
    await waitFor(() => expect(result.current.saveState).toBe("saved"))
  })

  it("markiert nach fehlgeschlagenem Flush einer verlassenen Seite nicht die neue Seite", async () => {
    const puts = stubFetch({
      "/api/gold/462828_p1": GOLD_A,
      "/api/gold/462828_p2": GOLD_B,
    })
    const { result, rerender } = renderAnnotation("462828_p1")
    await waitFor(() => expect(result.current.isPending).toBe(false))

    act(() => result.current.setSpans([{ start: 0, end: 1, label: "PRODUCT" }]))

    rerender({ pageId: "462828_p2" })
    await waitFor(() => expect(result.current.isPending).toBe(false))

    act(() => result.current.setSpans([{ start: 0, end: 1, label: "BRAND" }]))
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0].url).toContain("462828_p1")

    // Der erzwungene Save der verlassenen Seite A schlägt fehl - ein
    // allgemeiner Serverfehler, kein Wortlisten-Konflikt. Genügt laut Review
    // für den Befund, nicht nur der 409-Fall.
    puts[0].resolve(500, { detail: "Serverfehler" })

    // Absichtlich deutlich vor Bs eigenem 300-ms-Timer geprüft: Reicht As
    // catch-Block Zeit zum Laufen, aber lange bevor Bs eigener (erfolgreicher)
    // Save den Speicherzustand ohnehin wieder auf "saved" setzen würde -
    // sonst würde dieser die Fehlanzeige überdecken und die Prüfung nichts
    // mehr beweisen.
    await new Promise((r) => setTimeout(r, 20))
    expect(result.current.saveState).not.toBe("error")
    expect(result.current.conflict).toBe(false)

    await waitFor(() => expect(puts).toHaveLength(2), { timeout: 1000 })
    puts[1].resolve(200, { ...GOLD_B, spans: puts[1].body.spans })
    await waitFor(() => expect(result.current.saveState).toBe("saved"))
  })
})
