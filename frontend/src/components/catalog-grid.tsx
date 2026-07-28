import { AlertTriangle } from "lucide-react"
import type { ReactNode } from "react"
import { Progress } from "@/components/ui/progress"
import type { CatalogTile } from "@/lib/types"

interface CatalogGridProps {
  tiles: CatalogTile[]
  /** Beschriftung der Kennzahl: "fertig" im Annotator, "gelabelt" im Inspektor. */
  unit: string
  onSelect: (id: string) => void
  emptyHint?: ReactNode
}

/** Ladedatum als TT.MM., der Rest ist bei Wochenprospekten Rauschen. */
function shortDate(iso: string): string {
  const [, month, day] = iso.split("-")
  return `${day}.${month}.`
}

export function CatalogGrid({ tiles, unit, onSelect, emptyHint }: CatalogGridProps) {
  if (tiles.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border-2 border-dashed border-foreground/30 px-6 text-center">
        <p className="text-muted-foreground">{emptyHint}</p>
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {tiles.map((tile) => {
        const invalid = tile.stale + tile.broken
        const pct = tile.pages > 0 ? (tile.done / tile.pages) * 100 : 0
        return (
          <button
            key={tile.id}
            type="button"
            onClick={() => onSelect(tile.id)}
            className="plate space-y-2 rounded-lg border-2 border-foreground bg-card p-4 text-left transition-colors hover:bg-accent"
          >
            <p className="font-mono text-lg font-bold tracking-tight">{tile.id}</p>
            <p className="font-mono text-[11px] text-muted-foreground">
              {tile.pages} Seiten
              {tile.downloaded && ` · geladen ${shortDate(tile.downloaded)}`}
            </p>
            <div className="flex items-center gap-2">
              <Progress value={pct} />
              <span className="shrink-0 font-mono text-[11px] tabular-nums">
                {tile.done}/{tile.pages} {unit}
              </span>
            </div>
            {invalid > 0 && (
              <p className="flex items-center gap-1 font-mono text-[11px] text-destructive">
                <AlertTriangle className="size-3" />
                {invalid} ungültig
              </p>
            )}
          </button>
        )
      })}
    </div>
  )
}
