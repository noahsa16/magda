import { entityColor } from "@/lib/entities"
import { cn } from "@/lib/utils"

interface TypeDistributionProps {
  counts: Map<string, number>
  entityTypes: string[]
  visibleTypes: Set<string> | null
  onToggleType: (type: string) => void
}

/**
 * Anteil je Entity-Typ als ein durchgehender Balken plus Legende. Zeigt auf
 * einen Blick, ob das LLM eine Seite ausgewogen gelabelt hat – lauter
 * QUANTITY und kein PRODUCT ist ein Warnsignal.
 */
export function TypeDistribution({
  counts, entityTypes, visibleTypes, onToggleType,
}: TypeDistributionProps) {
  const total = [...counts.values()].reduce((a, b) => a + b, 0)

  return (
    <div className="space-y-2">
      <div className="flex h-2.5 w-full overflow-hidden rounded-full border border-foreground bg-muted">
        {total > 0 &&
          entityTypes.map((type) => {
            const share = (counts.get(type) ?? 0) / total
            if (share === 0) return null
            return (
              <div
                key={type}
                style={{ width: `${share * 100}%`, backgroundColor: entityColor(entityTypes, type) }}
                title={`${type}: ${counts.get(type)}`}
              />
            )
          })}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {entityTypes.map((type) => {
          const active = !visibleTypes || visibleTypes.has(type)
          const count = counts.get(type) ?? 0
          return (
            <button
              key={type}
              type="button"
              onClick={() => onToggleType(type)}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[11px] font-medium transition-all",
                active
                  ? "border-transparent text-white"
                  : "border-border text-muted-foreground opacity-50 hover:opacity-100",
                count === 0 && "opacity-40",
              )}
              style={active ? { backgroundColor: entityColor(entityTypes, type) } : undefined}
              title={active ? `${type} ausblenden` : `${type} einblenden`}
            >
              {type}
              <span className={cn("tabular-nums", active && "text-white/80")}>{count}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
