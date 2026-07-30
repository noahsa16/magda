import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

interface Crumb {
  label: string
  /** Fehlt bei der aktuellen Ebene - die ist kein Ziel. */
  onClick?: () => void
}

export function Crumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Pfad" className="flex items-center gap-1 font-mono text-xs">
      {items.map((item, i) => (
        <span key={item.label} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="size-3 text-muted-foreground" />}
          {item.onClick ? (
            <button
              type="button"
              onClick={item.onClick}
              className="text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              {item.label}
            </button>
          ) : (
            <span className={cn("font-semibold")}>{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}
