import { useState } from "react"
import { entityColor } from "@/lib/entities"
import type { Word } from "@/lib/types"

interface PageOverlayProps {
  imageUrl: string
  width: number // PDF-Punkte – das SVG-viewBox übernimmt die Skalierung aufs Bild
  height: number
  words: Word[]
  tags?: string[]
  entityTypes: string[]
  visibleTypes?: Set<string> | null // null/undefined = alle
  highlight?: { start: number; end: number } | null
}

interface Hover {
  text: string
  tag: string
  xPct: number
  yPct: number
}

export function PageOverlay({
  imageUrl, width, height, words, tags, entityTypes, visibleTypes, highlight,
}: PageOverlayProps) {
  const [hover, setHover] = useState<Hover | null>(null)

  return (
    <div className="relative">
      <img src={imageUrl} alt="Prospektseite" className="w-full rounded-md border" />
      {/* viewBox im PDF-Koordinatenraum: der Browser skaliert die Boxen aufs
          Bild, egal mit welcher DPI das PNG gerendert wurde. */}
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
      >
        {words.map((word, i) => {
          const tag = tags?.[i] ?? "O"
          const type = tag === "O" ? null : tag.slice(2)
          if (type && visibleTypes && !visibleTypes.has(type)) return null
          const [x0, y0, x1, y1] = word.bbox
          const highlighted = highlight != null && i >= highlight.start && i < highlight.end
          return (
            <rect
              key={i}
              x={x0} y={y0} width={x1 - x0} height={y1 - y0}
              fill={type ? entityColor(entityTypes, type) : "none"}
              fillOpacity={highlighted ? 0.6 : 0.35}
              stroke={type ? entityColor(entityTypes, type) : "#9ca3af"}
              strokeOpacity={type ? 1 : 0.4}
              strokeWidth={highlighted ? 2 : 0.8}
              onMouseEnter={() =>
                setHover({ text: word.text, tag, xPct: (x0 / width) * 100, yPct: (y1 / height) * 100 })
              }
              onMouseLeave={() => setHover(null)}
            />
          )
        })}
      </svg>
      {hover && (
        <div
          className="pointer-events-none absolute z-10 -translate-y-1 rounded bg-foreground px-2 py-1 font-mono text-xs text-background shadow"
          style={{ left: `${hover.xPct}%`, top: `${hover.yPct}%` }}
        >
          {hover.text} · {hover.tag}
        </div>
      )}
    </div>
  )
}
