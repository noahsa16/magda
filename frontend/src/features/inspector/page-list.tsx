import { useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import type { PageSummary } from "@/lib/types"

interface PageListProps {
  pages: PageSummary[]
  selected: string | null
  onSelect: (id: string) => void
}

export function PageList({ pages, selected, onSelect }: PageListProps) {
  const [query, setQuery] = useState("")

  const byCatalog = useMemo(() => {
    const filtered = pages.filter((p) => p.page_id.includes(query))
    const groups = new Map<string, PageSummary[]>()
    for (const p of filtered) {
      groups.set(p.catalog, [...(groups.get(p.catalog) ?? []), p])
    }
    return [...groups.entries()]
  }, [pages, query])

  const labeledCount = pages.filter((p) => p.labeled).length

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <Input
        placeholder="Seite suchen…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <p className="px-1 text-xs text-muted-foreground">
        {labeledCount} von {pages.length} Seiten gelabelt
      </p>
      <div className="min-h-0 overflow-y-auto" style={{ maxHeight: "72vh" }}>
        {byCatalog.map(([catalog, catalogPages]) => (
          <div key={catalog} className="mb-3">
            <p className="sticky top-0 bg-background px-2 py-1 font-mono text-xs text-muted-foreground">
              Katalog {catalog}
            </p>
            <ul className="space-y-0.5">
              {catalogPages.map((p) => (
                <li key={p.page_id}>
                  <button
                    type="button"
                    className={cn(
                      "flex w-full min-w-0 items-center justify-between gap-2 rounded-md px-2 py-1 text-left text-sm transition-colors hover:bg-accent",
                      selected === p.page_id && "bg-accent font-medium",
                    )}
                    onClick={() => onSelect(p.page_id)}
                  >
                    <span className="min-w-0 truncate font-mono text-[13px]">
                      {p.page_id.split("_")[1] ?? p.page_id}
                    </span>
                    <Badge
                      variant={p.labeled ? "default" : "outline"}
                      className="shrink-0 text-[10px]"
                    >
                      {p.labeled ? "gelabelt" : "offen"}
                    </Badge>
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
