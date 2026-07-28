import { useMemo, useState } from "react"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import type { GoldSummary, PageSummary } from "@/lib/types"

interface PageListProps {
  pages: PageSummary[]
  selected: string | null
  onSelect: (id: string) => void
  /** Wenn gesetzt, zeigt der Punkt den Gold-Status statt "gelabelt". */
  goldStatus?: GoldSummary[]
}

/** Punktfarbe und Titel einer Seite im Gold-Modus. Ungültige Seiten (kaputte
 * Datei, veraltete Wortliste) bekommen einen eigenen Zustand: Sie als "fertig"
 * zu zeigen wäre genau die stille Falschanzeige, gegen die der Hash existiert. */
function goldDot(gold: GoldSummary | undefined): { className: string; title: string } {
  if (gold?.status === "broken") return { className: "bg-destructive", title: "Datei unlesbar" }
  if (gold?.stale) return { className: "bg-destructive", title: "Wortliste geändert" }
  if (gold?.status === "done") return { className: "bg-[var(--riso-blue)]", title: "fertig" }
  if (gold?.status === "in_progress") return { className: "bg-primary", title: "in Arbeit" }
  return { className: "border border-muted-foreground", title: "unberührt" }
}

export function PageList({ pages, selected, onSelect, goldStatus }: PageListProps) {
  const [query, setQuery] = useState("")
  const [filterOn, setFilterOn] = useState(false)

  const goldById = useMemo(
    () => new Map((goldStatus ?? []).map((g) => [g.page_id, g])),
    [goldStatus],
  )

  // Der Knopf filtert nach derselben Bedeutung, die der Punkt daneben zeigt:
  // im Gold-Modus nach "noch nicht fertig", sonst nach "vom LLM gelabelt".
  const matchesFilter = (p: PageSummary) =>
    goldStatus ? goldById.get(p.page_id)?.status !== "done" : p.labeled

  const byCatalog = useMemo(() => {
    const filtered = pages.filter(
      (p) => p.page_id.includes(query) && (!filterOn || matchesFilter(p)),
    )
    const groups = new Map<string, PageSummary[]>()
    for (const p of filtered) {
      groups.set(p.catalog, [...(groups.get(p.catalog) ?? []), p])
    }
    return [...groups.entries()]
  }, [pages, query, filterOn, goldById, goldStatus])

  const matchCount = pages.filter(matchesFilter).length

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <Input
        placeholder="Seite suchen…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="h-8"
      />
      <button
        type="button"
        onClick={() => setFilterOn((v) => !v)}
        className={cn(
          "self-start rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest transition-colors",
          filterOn
            ? "border-transparent bg-primary text-primary-foreground"
            : "border-border text-muted-foreground hover:text-foreground",
        )}
      >
        {matchCount} von {pages.length} {goldStatus ? "offen" : "gelabelt"}
      </button>

      <div className="min-h-0 overflow-y-auto" style={{ maxHeight: "70vh" }}>
        {byCatalog.map(([catalog, catalogPages]) => (
          <div key={catalog} className="mb-3">
            <p className="sticky top-0 z-10 bg-background/95 px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground backdrop-blur">
              Katalog {catalog}
            </p>
            <ul className="space-y-0.5">
              {catalogPages.map((p) => (
                <li key={p.page_id}>
                  <button
                    type="button"
                    className={cn(
                      "flex w-full min-w-0 items-center justify-between gap-2 rounded-md border px-2 py-1 text-left text-sm transition-colors",
                      selected === p.page_id
                        ? "border-foreground bg-accent font-semibold"
                        : "border-transparent hover:bg-accent",
                    )}
                    onClick={() => onSelect(p.page_id)}
                  >
                    <span className="min-w-0 truncate font-mono text-[13px]">
                      {p.page_id.split("_")[1] ?? p.page_id}
                    </span>
                    {goldStatus ? (
                      <span
                        className={cn("size-2 shrink-0 rounded-full", goldDot(goldById.get(p.page_id)).className)}
                        title={goldDot(goldById.get(p.page_id)).title}
                      />
                    ) : (
                      <span
                        className={cn(
                          "size-2 shrink-0 rounded-full",
                          p.labeled ? "bg-[var(--riso-blue)]" : "border border-muted-foreground",
                        )}
                        title={p.labeled ? "gelabelt" : "offen"}
                      />
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
