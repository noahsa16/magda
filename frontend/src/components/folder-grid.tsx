import { cn } from "@/lib/utils"

export type FolderTone = "model" | "gold" | "unchecked" | "group"

export interface FolderItem {
  id: string
  label: string
  sublabel?: string
  badge?: string
  tone: FolderTone
}

/**
 * Ordnersymbol im Stil des Finders: hinterer Reiter, vorderes Blatt.
 *
 * Als SVG statt als Icon aus lucide – dort liegen nur Umrisse, und was die
 * Form auf einen Blick erkennbar macht, ist die Füllung in zwei Tönen.
 */
function FolderIcon({ tone }: { tone: FolderTone }) {
  const [back, front] = {
    group: ["#2563eb", "#3b82f6"],
    model: ["#3b82f6", "#60a5fa"],
    gold: ["#d97706", "#f59e0b"],
    unchecked: ["#64748b", "#94a3b8"],
  }[tone]

  return (
    <svg viewBox="0 0 64 52" className="h-[72px] w-[88px] shrink-0 drop-shadow-sm" aria-hidden="true">
      <path
        d="M2 8a4 4 0 0 1 4-4h17l6 6h29a4 4 0 0 1 4 4v30a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4Z"
        fill={back}
      />
      <path d="M2 18h60v24a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4Z" fill={front} />
    </svg>
  )
}

/**
 * Ein Raster aus Ordnern, durch das man sich klickt wie über einen Schreibtisch.
 *
 * Ersetzt die vorherige Auswahlliste in der Kopfzeile. Mit mehreren
 * Labeling-Modellen und zwei Sorten Handannotation ist "wessen Labels?" die
 * erste Entscheidung und keine nachträgliche Einstellung – ein Ordner sagt
 * das ohne Beschriftung.
 */
export function FolderGrid({
  items,
  onOpen,
  emptyHint,
}: {
  items: FolderItem[]
  onOpen: (id: string) => void
  emptyHint?: React.ReactNode
}) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border-2 border-dashed border-foreground/30 p-8 text-center text-sm text-muted-foreground">
        {emptyHint ?? "Hier liegt noch nichts."}
      </div>
    )
  }

  return (
    <div className="grid gap-1 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onDoubleClick={() => onOpen(item.id)}
          onClick={() => onOpen(item.id)}
          title={item.label}
          className={cn(
            "flex flex-col items-center gap-1 rounded-xl border-2 border-transparent px-2 py-3",
            "transition-colors hover:border-foreground hover:bg-accent",
            "focus-visible:border-foreground focus-visible:outline-none",
          )}
        >
          <FolderIcon tone={item.tone} />
          <span className="line-clamp-2 max-w-full text-center text-[13px] font-semibold leading-tight">
            {item.label}
          </span>
          {item.sublabel && (
            <span className="text-center font-mono text-[10px] leading-tight text-muted-foreground">
              {item.sublabel}
            </span>
          )}
          {item.badge && (
            <span className="rounded-full border border-border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
              {item.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
