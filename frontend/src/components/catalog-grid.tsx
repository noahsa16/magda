import { AlertTriangle } from "lucide-react"
import type { ReactNode } from "react"
import { Progress } from "@/components/ui/progress"
import type { CatalogTile } from "@/lib/types"
import { chunkByWeek } from "@/lib/weeks"

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

function Tile({
  tile,
  unit,
  onSelect,
}: {
  tile: CatalogTile
  unit: string
  onSelect: (id: string) => void
}) {
  const invalid = tile.stale + tile.broken
  const pct = tile.pages > 0 ? (tile.done / tile.pages) * 100 : 0

  return (
    <button
      type="button"
      onClick={() => onSelect(tile.id)}
      className="plate space-y-2 rounded-xl border-2 border-foreground bg-card p-4 text-left transition-colors hover:bg-accent"
    >
      <div className="flex items-baseline justify-between gap-2">
        <p className="font-mono text-base font-bold tracking-tight">{tile.id}</p>
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
}

export function CatalogGrid({ tiles, unit, onSelect, emptyHint }: CatalogGridProps) {
  if (tiles.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border-2 border-dashed border-foreground/30 px-6 text-center">
        <p className="text-muted-foreground">{emptyHint}</p>
      </div>
    )
  }

  // Nach Prospektwochen bündeln: Dutzende namenloser Kacheln in einem Raster
  // sind unlesbar, mit einer Überschrift je Woche findet man sich zurecht.
  const weeks = chunkByWeek(tiles)

  return (
    <div className="space-y-6">
      {weeks.map((week) => (
        <section key={week[0].id} className="space-y-3">
          {weeks.length > 1 && (
            <div className="flex flex-wrap items-baseline gap-2 border-b-2 border-foreground pb-1.5">
              <h3 className="text-sm font-bold tracking-tight">Prospektwoche {week[0].id}</h3>
              <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                {week.length} Ausgaben · {week.reduce((sum, t) => sum + t.pages, 0)} Seiten
              </span>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {week.map((tile) => (
              <Tile key={tile.id} tile={tile} unit={unit} onSelect={onSelect} />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
