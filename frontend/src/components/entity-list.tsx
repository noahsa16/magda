import { useMemo, useState } from "react"
import { TypeDistribution } from "@/components/type-distribution"
import { Input } from "@/components/ui/input"
import { groupEntities } from "@/lib/bio"
import { entityColor } from "@/lib/entities"
import { cn } from "@/lib/utils"

export interface EntityRef {
  start: number
  end: number
}

interface EntityListProps {
  words: { text: string }[]
  tags: string[]
  entityTypes: string[]
  visibleTypes: Set<string> | null // null = alle sichtbar
  onToggleType: (type: string) => void
  /** Klick: feste Auswahl. */
  onSelect?: (e: EntityRef | null) => void
  /** Zeigerkontakt: flüchtige Vorschau, überschreibt die Auswahl nicht. */
  onHover?: (e: EntityRef | null) => void
  selected?: EntityRef | null
  /** Suchfeld über den Entities einblenden. */
  searchable?: boolean
  /** Gestaffeltes Einblenden der Einträge (Demo-Ergebnis). */
  animate?: boolean
  maxHeight?: string
}

export function EntityList({
  words, tags, entityTypes, visibleTypes, onToggleType, onSelect, onHover, selected,
  searchable = false, animate = false, maxHeight = "70vh",
}: EntityListProps) {
  const [query, setQuery] = useState("")
  const allEntities = useMemo(() => groupEntities(words, tags), [words, tags])

  const countByType = useMemo(() => {
    const counts = new Map<string, number>()
    for (const e of allEntities) counts.set(e.type, (counts.get(e.type) ?? 0) + 1)
    return counts
  }, [allEntities])

  const needle = query.trim().toLowerCase()
  const entities = allEntities.filter(
    (e) =>
      (!visibleTypes || visibleTypes.has(e.type)) &&
      (needle === "" || e.text.toLowerCase().includes(needle)),
  )

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <TypeDistribution
        counts={countByType}
        entityTypes={entityTypes}
        visibleTypes={visibleTypes}
        onToggleType={onToggleType}
      />

      {searchable && (
        <Input
          placeholder="Entities durchsuchen…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-8"
        />
      )}

      {entities.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {allEntities.length === 0 ? "Keine Entities auf dieser Seite." : "Nichts gefunden."}
        </p>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto pr-1" style={{ maxHeight }}>
          <ul className="space-y-0.5">
            {entities.map((e, order) => {
              const isSelected = selected?.start === e.start && selected?.end === e.end
              return (
                <li
                  key={`${e.start}-${e.end}`}
                  className={animate ? "fade-up" : undefined}
                  style={animate ? { "--reveal-delay": `${0.5 + order * 0.03}s` } as React.CSSProperties : undefined}
                >
                  <button
                    type="button"
                    className={cn(
                      "flex w-full min-w-0 items-center justify-between gap-2 rounded-md border px-2 py-1 text-left text-sm transition-colors",
                      isSelected
                        ? "border-foreground bg-accent font-medium"
                        : "border-transparent hover:bg-accent",
                    )}
                    onClick={() => onSelect?.(isSelected ? null : { start: e.start, end: e.end })}
                    onMouseEnter={() => (onHover ?? onSelect)?.({ start: e.start, end: e.end })}
                    onMouseLeave={() => (onHover ?? onSelect)?.(null)}
                  >
                    <span className="min-w-0 truncate">{e.text}</span>
                    <span
                      className="shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] font-medium text-white"
                      style={{ backgroundColor: entityColor(entityTypes, e.type) }}
                    >
                      {e.type}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
