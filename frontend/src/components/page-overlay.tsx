import { useMemo, useState } from "react"
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
  /** Scan-Reveal: Scanlinie + gestaffeltes Einblenden der Boxen (Demo). */
  animate?: boolean
}

interface Hover {
  text: string
  tag: string
  xPct: number
  yPct: number
}

export function PageOverlay({
  imageUrl, width, height, words, tags, entityTypes, visibleTypes, highlight, animate = false,
}: PageOverlayProps) {
  const [hover, setHover] = useState<Hover | null>(null)

  // Reveal-Reihenfolge folgt der Leserichtung: Boxen nach y-Position sortiert,
  // damit die Staffelung mit der Scanlinie von oben nach unten läuft.
  const revealRank = useMemo(() => {
    if (!animate) return null
    const entityIndices = words
      .map((_, i) => i)
      .filter((i) => (tags?.[i] ?? "O") !== "O")
      .sort((a, b) => words[a].bbox[1] - words[b].bbox[1])
    const rank = new Map<number, number>()
    entityIndices.forEach((wordIdx, order) => rank.set(wordIdx, order))
    return rank
  }, [animate, words, tags])

  return (
    <div className="relative overflow-hidden rounded-lg border shadow-sm">
      <img src={imageUrl} alt="Prospektseite" className="block w-full" />
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
          const rank = type != null ? revealRank?.get(i) : undefined
          return (
            <rect
              key={i}
              x={x0} y={y0} width={x1 - x0} height={y1 - y0}
              rx={1.5}
              className={rank != null ? "box-reveal" : undefined}
              style={
                rank != null
                  ? { "--reveal-delay": `${0.45 + rank * 0.028}s` } as React.CSSProperties
                  : { transition: "fill-opacity 150ms, stroke-width 150ms" }
              }
              fill={type ? entityColor(entityTypes, type) : "none"}
              fillOpacity={highlighted ? 0.6 : 0.35}
              stroke={type ? entityColor(entityTypes, type) : "#9ca3af"}
              strokeOpacity={type ? 1 : 0.4}
              strokeWidth={highlighted ? 2.5 : 0.8}
              onMouseEnter={() =>
                setHover({ text: word.text, tag, xPct: (x0 / width) * 100, yPct: (y1 / height) * 100 })
              }
              onMouseLeave={() => setHover(null)}
            />
          )
        })}
      </svg>
      {animate && (
        <div
          className="scanline pointer-events-none absolute inset-x-0 h-0.5"
          style={{
            background: "linear-gradient(90deg, transparent, #0072B2 20%, #56B4E9 50%, #0072B2 80%, transparent)",
            boxShadow: "0 0 12px 2px rgba(0, 114, 178, 0.45)",
          }}
        />
      )}
      {hover && (
        <div
          className="pointer-events-none absolute z-10 max-w-[80%] -translate-y-1 truncate rounded bg-foreground px-2 py-1 font-mono text-xs text-background shadow-md"
          style={{
            left: `min(${hover.xPct}%, 70%)`,
            top: `${hover.yPct}%`,
          }}
        >
          {hover.text} · {hover.tag}
        </div>
      )}
    </div>
  )
}
