import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { entityColor } from "@/lib/entities"

/**
 * Wie oft kommt welcher Entity-Typ in den LLM-Labels vor?
 *
 * Gezählt werden Entities, nicht Wörter. Lauter QUANTITY und kein PRODUCT wäre
 * ein Warnsignal für die Label-Qualität – das sieht man hier vor dem Training,
 * nicht erst an schlechten Metriken danach.
 */
export function LabelDistribution() {
  const { data } = useQuery({ queryKey: ["labelDistribution"], queryFn: () => api.labelDistribution() })
  const schema = useQuery({ queryKey: ["schema"], queryFn: api.schema })

  if (!data || data.total === 0) {
    return (
      <section className="space-y-2">
        <h2 className="text-xl font-bold tracking-tight">Labelverteilung</h2>
        <p className="text-sm text-muted-foreground">
          Noch keine gelabelten Seiten. Schritt 03 auf der Pipeline-Seite starten.
        </p>
      </section>
    )
  }

  const types = schema.data?.entity_types ?? Object.keys(data.counts)
  const rows = types
    .map((type) => ({ type, count: data.counts[type] ?? 0 }))
    .sort((a, b) => b.count - a.count)
  const max = Math.max(...rows.map((r) => r.count), 1)

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold tracking-tight">Labelverteilung</h2>
        <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
          {data.total} Entities auf {data.pages} Seiten
        </p>
      </div>
      <ul className="space-y-1.5">
        {rows.map(({ type, count }) => (
          <li key={type} className="flex items-center gap-3">
            <span className="w-24 shrink-0 font-mono text-[11px]">{type}</span>
            <span className="h-3 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
              <span
                className="block h-full rounded-full"
                style={{
                  width: `${(count / max) * 100}%`,
                  backgroundColor: entityColor(types, type),
                }}
              />
            </span>
            <span className="w-12 shrink-0 text-right font-mono text-xs tabular-nums">{count}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
