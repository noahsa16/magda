import { useMemo } from "react"
import { groupEntities } from "@/lib/bio"
import { entityColor } from "@/lib/entities"
import { cn } from "@/lib/utils"

interface EntityListProps {
  words: { text: string }[]
  tags: string[]
  entityTypes: string[]
  visibleTypes: Set<string> | null // null = alle sichtbar
  onToggleType: (type: string) => void
  onSelect?: (e: { start: number; end: number } | null) => void
  /** Gestaffeltes Einblenden der Einträge (Demo-Ergebnis). */
  animate?: boolean
}

export function EntityList({
  words, tags, entityTypes, visibleTypes, onToggleType, onSelect, animate = false,
}: EntityListProps) {
  const allEntities = useMemo(() => groupEntities(words, tags), [words, tags])
  const entities = allEntities.filter((e) => !visibleTypes || visibleTypes.has(e.type))

  const countByType = useMemo(() => {
    const counts = new Map<string, number>()
    for (const e of allEntities) counts.set(e.type, (counts.get(e.type) ?? 0) + 1)
    return counts
  }, [allEntities])

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        {entityTypes.map((type) => {
          const active = !visibleTypes || visibleTypes.has(type)
          const count = countByType.get(type) ?? 0
          return (
            <button
              key={type}
              type="button"
              onClick={() => onToggleType(type)}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[11px] font-medium transition-colors",
                active ? "border-transparent text-white" : "text-muted-foreground opacity-60 hover:opacity-100",
              )}
              style={active ? { backgroundColor: entityColor(entityTypes, type) } : undefined}
              title={active ? `${type} ausblenden` : `${type} einblenden`}
            >
              {type}
              <span className={cn("tabular-nums", active ? "text-white/80" : "")}>{count}</span>
            </button>
          )
        })}
      </div>

      {entities.length === 0 ? (
        <p className="text-sm text-muted-foreground">Keine Entities auf dieser Seite.</p>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto pr-1" style={{ maxHeight: "70vh" }}>
          <ul className="space-y-0.5">
            {entities.map((e, order) => (
              <li
                key={`${e.start}-${e.end}`}
                className={animate ? "fade-up" : undefined}
                style={animate ? { "--reveal-delay": `${0.5 + order * 0.03}s` } as React.CSSProperties : undefined}
              >
                <button
                  type="button"
                  className="flex w-full min-w-0 items-center justify-between gap-2 rounded-md px-2 py-1 text-left text-sm transition-colors hover:bg-accent"
                  onClick={() => onSelect?.({ start: e.start, end: e.end })}
                  onMouseEnter={() => onSelect?.({ start: e.start, end: e.end })}
                  onMouseLeave={() => onSelect?.(null)}
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
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
