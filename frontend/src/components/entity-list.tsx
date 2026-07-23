import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { groupEntities } from "@/lib/bio"
import { entityColor } from "@/lib/entities"

interface EntityListProps {
  words: { text: string }[]
  tags: string[]
  entityTypes: string[]
  visibleTypes: Set<string> | null // null = alle sichtbar
  onToggleType: (type: string) => void
  onSelect?: (e: { start: number; end: number }) => void
}

export function EntityList({
  words, tags, entityTypes, visibleTypes, onToggleType, onSelect,
}: EntityListProps) {
  const entities = groupEntities(words, tags).filter(
    (e) => !visibleTypes || visibleTypes.has(e.type),
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {entityTypes.map((type) => {
          const active = !visibleTypes || visibleTypes.has(type)
          return (
            <button key={type} type="button" onClick={() => onToggleType(type)}>
              <Badge
                variant={active ? "default" : "outline"}
                style={active ? { backgroundColor: entityColor(entityTypes, type) } : undefined}
              >
                {type}
              </Badge>
            </button>
          )
        })}
      </div>

      {entities.length === 0 ? (
        <p className="text-sm text-muted-foreground">Keine Entities auf dieser Seite.</p>
      ) : (
        <ScrollArea className="h-[60vh] pr-3">
          <ul className="space-y-1">
            {entities.map((e) => (
              <li key={`${e.start}-${e.end}`}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left text-sm hover:bg-accent"
                  onClick={() => onSelect?.({ start: e.start, end: e.end })}
                >
                  <span className="truncate">{e.text}</span>
                  <span
                    className="shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] text-white"
                    style={{ backgroundColor: entityColor(entityTypes, e.type) }}
                  >
                    {e.type}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </ScrollArea>
      )}
    </div>
  )
}
