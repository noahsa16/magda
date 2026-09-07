import { useMemo, useRef, useState } from "react"
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
  /** Boxen komplett ausblenden – zeigt die Seite, wie sie gedruckt wurde. */
  showBoxes?: boolean
  /** Auch Wörter ohne Entity dünn umranden (zeigt, was die Extraktion gefunden hat). */
  showPlainWords?: boolean
  /** Klick auf eine Box, z. B. um sie in der Liste auszuwählen. */
  onWordClick?: (index: number, event: React.MouseEvent) => void
  /** Rechteck aufziehen: bekommt die Indizes aller Wörter, deren Box das
   * Rechteck schneidet. Ein blosser Klick (unter DRAG_THRESHOLD) löst es
   * nicht aus, der geht weiter an onWordClick. */
  onBoxSelect?: (indices: number[]) => void
  /** Scan-Reveal: Scanlinie + gestaffeltes Einblenden der Boxen (Demo). */
  animate?: boolean
}

/** Ab wie vielen Bildschirmpixeln eine Bewegung ein Aufziehen ist und kein
 * verwackelter Klick. */
const DRAG_THRESHOLD = 4

interface Box {
  x0: number
  y0: number
  x1: number
  y1: number
}

/** Welche Wörter schneidet das Rechteck? Für die Gruppierung reicht
 * Schneiden statt Einschliessen: wer ein Angebot einrahmt, trifft den Rand
 * einer Box selten exakt. */
export function wordsInBox(words: Word[], box: Box): number[] {
  const x0 = Math.min(box.x0, box.x1), x1 = Math.max(box.x0, box.x1)
  const y0 = Math.min(box.y0, box.y1), y1 = Math.max(box.y0, box.y1)
  return words
    .map((w, i) => (w.bbox[0] < x1 && w.bbox[2] > x0 && w.bbox[1] < y1 && w.bbox[3] > y0 ? i : -1))
    .filter((i) => i >= 0)
}

interface Hover {
  text: string
  tag: string
  xPct: number
  yPct: number
}

export function PageOverlay({
  imageUrl, width, height, words, tags, entityTypes, visibleTypes, highlight,
  showBoxes = true, showPlainWords = true, onWordClick, onBoxSelect, animate = false,
}: PageOverlayProps) {
  const [hover, setHover] = useState<Hover | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  // Aufziehen läuft in PDF-Koordinaten, damit das Rechteck wie die Boxen
  // über das viewBox skaliert. Der Startpunkt in Bildschirmpixeln bleibt für
  // die Klick/Zieh-Unterscheidung daneben liegen.
  const dragStart = useRef<{ clientX: number; clientY: number } | null>(null)
  const [drag, setDrag] = useState<Box | null>(null)
  // Ein abgeschlossenes Aufziehen endet als click-Ereignis auf der Box, auf
  // der die Maus losgelassen wurde. Ohne diese Sperre nähme der Klick das
  // eben gewählte Wort gleich wieder heraus. Die Sperre gilt nur für den
  // laufenden Ereigniszyklus: landet der click woanders (Loslassen über
  // dem Bild statt einer Box), bliebe sie sonst hängen und frässe den
  // nächsten echten Klick.
  const swallowClick = useRef(false)

  function toPage(e: React.PointerEvent): { x: number; y: number } {
    const rect = svgRef.current!.getBoundingClientRect()
    return {
      x: ((e.clientX - rect.left) / rect.width) * width,
      y: ((e.clientY - rect.top) / rect.height) * height,
    }
  }

  function onPointerDown(e: React.PointerEvent) {
    if (!onBoxSelect || e.button !== 0) return
    dragStart.current = { clientX: e.clientX, clientY: e.clientY }
    const { x, y } = toPage(e)
    setDrag({ x0: x, y0: y, x1: x, y1: y })
    // Capture hält das Ziehen auch über den Bildrand hinaus; jsdom kennt
    // die Methode nicht.
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!dragStart.current) return
    const { x, y } = toPage(e)
    setDrag((d) => (d ? { ...d, x1: x, y1: y } : d))
  }

  function onPointerUp(e: React.PointerEvent) {
    const start = dragStart.current
    dragStart.current = null
    if (!start || !drag) return
    const moved = Math.hypot(e.clientX - start.clientX, e.clientY - start.clientY)
    setDrag(null)
    if (moved < DRAG_THRESHOLD) return
    swallowClick.current = true
    setTimeout(() => { swallowClick.current = false }, 0)
    onBoxSelect?.(wordsInBox(words, drag))
  }

  function onClick(i: number, e: React.MouseEvent) {
    if (swallowClick.current) {
      swallowClick.current = false
      return
    }
    onWordClick?.(i, e)
  }

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
    <div className="relative overflow-hidden rounded-lg border-2 border-foreground bg-card">
      <img src={imageUrl} alt="Prospektseite" className="block w-full select-none" draggable={false} />
      {/* viewBox im PDF-Koordinatenraum: der Browser skaliert die Boxen aufs
          Bild, egal mit welcher DPI das PNG gerendert wurde. */}
      <svg
        ref={svgRef}
        className="absolute inset-0 h-full w-full"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        style={onBoxSelect ? { touchAction: "none", cursor: drag ? "crosshair" : undefined } : undefined}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => { dragStart.current = null; setDrag(null) }}
      >
        {showBoxes && words.map((word, i) => {
          const tag = tags?.[i] ?? "O"
          const type = tag === "O" ? null : tag.slice(2)
          if (type && visibleTypes && !visibleTypes.has(type)) return null
          if (!type && !showPlainWords) return null
          const [x0, y0, x1, y1] = word.bbox
          const highlighted = highlight != null && i >= highlight.start && i < highlight.end
          const rank = type != null ? revealRank?.get(i) : undefined
          return (
            <rect
              key={i}
              x={x0} y={y0} width={x1 - x0} height={y1 - y0}
              rx={1.5}
              className={rank != null ? "box-reveal" : undefined}
              style={{
                // SVG liefert Zeigerereignisse standardmäßig nur dort, wo
                // gemalt wird. Ungelabelte Wörter haben fill="none", treffbar
                // wäre also nur ihre 0,8 pt dünne Kontur - im Annotator, wo
                // jedes Wort ungefüllt anfängt, praktisch kein Wort. "all"
                // entkoppelt das Treffen vom Füllzustand, ohne am Aussehen
                // etwas zu ändern.
                pointerEvents: "all",
                cursor: onWordClick ? "pointer" : undefined,
                ...(rank != null
                  ? ({ "--reveal-delay": `${0.45 + rank * 0.028}s` } as React.CSSProperties)
                  : { transition: "fill-opacity 150ms, stroke-width 150ms" }),
              }}
              fill={type ? entityColor(entityTypes, type) : "none"}
              fillOpacity={highlighted ? 0.6 : 0.35}
              stroke={type ? entityColor(entityTypes, type) : "#14203C"}
              strokeOpacity={type ? 1 : 0.25}
              strokeWidth={highlighted ? 2.5 : 0.8}
              onClick={(e) => onClick(i, e)}
              onMouseEnter={() =>
                setHover({ text: word.text, tag, xPct: (x0 / width) * 100, yPct: (y1 / height) * 100 })
              }
              onMouseLeave={() => setHover(null)}
            />
          )
        })}
        {drag && (
          <rect
            data-testid="rubber-band"
            x={Math.min(drag.x0, drag.x1)} y={Math.min(drag.y0, drag.y1)}
            width={Math.abs(drag.x1 - drag.x0)} height={Math.abs(drag.y1 - drag.y0)}
            fill="#2951E8" fillOpacity={0.12} stroke="#2951E8" strokeWidth={1}
            strokeDasharray="3 2" pointerEvents="none"
          />
        )}
      </svg>
      {animate && (
        <div
          className="scanline pointer-events-none absolute inset-x-0 h-0.5"
          style={{
            background: "linear-gradient(90deg, transparent, #E8377D 20%, #2951E8 50%, #E8377D 80%, transparent)",
            boxShadow: "0 0 12px 2px rgba(232, 55, 125, 0.45)",
          }}
        />
      )}
      {hover && (
        <div
          className="pointer-events-none absolute z-10 max-w-[80%] -translate-y-1 truncate rounded bg-foreground px-2 py-1 font-mono text-xs text-background"
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
