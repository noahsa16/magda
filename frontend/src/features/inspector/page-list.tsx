import { useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
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

  return (
    <div className="flex h-full flex-col gap-2">
      <Input
        placeholder="Seite suchen…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <ScrollArea className="h-[70vh]">
        {byCatalog.map(([catalog, catalogPages]) => (
          <div key={catalog} className="mb-3">
            <p className="px-2 py-1 font-mono text-xs text-muted-foreground">{catalog}</p>
            <ul>
              {catalogPages.map((p) => (
                <li key={p.page_id}>
                  <button
                    type="button"
                    className={cn(
                      "flex w-full items-center justify-between rounded px-2 py-1 text-left text-sm hover:bg-accent",
                      selected === p.page_id && "bg-accent font-medium",
                    )}
                    onClick={() => onSelect(p.page_id)}
                  >
                    <span className="font-mono">{p.page_id}</span>
                    <Badge variant={p.labeled ? "default" : "outline"}>
                      {p.labeled ? "gelabelt" : "offen"}
                    </Badge>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </ScrollArea>
    </div>
  )
}
