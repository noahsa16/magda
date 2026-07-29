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
            <div className="flex items-baseline justify-between gap-2">
              <p className="font-mono text-lg font-bold tracking-tight">{tile.id}</p>
              {tile.pages === 1 && (
                <span
                  className="shrink-0 rounded-full border border-border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground"
                  title="Diese Region unterscheidet sich bundesweit an genau einer Seite"
                >
                  1 Abweichung
                </span>
              )}
            </div>
            {tile.region ? (
              <p className="text-sm font-semibold leading-tight">
                {tile.region}
                {tile.region_confirmed === false && (
                  <span
                    className="ml-1 font-normal text-muted-foreground"
                    title="Aus der Regionsreihenfolge der laufenden Woche übertragen – Penny's Markt-API kennt vergangene Wochen nicht mehr"
                  >
                    (vermutet)
                  </span>
                )}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">Region unbekannt</p>
            )}
            <p className="font-mono text-[11px] text-muted-foreground">
              {tile.pages} {tile.pages === 1 ? "Seite" : "Seiten"}
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
