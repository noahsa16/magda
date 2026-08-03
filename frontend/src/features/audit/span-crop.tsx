import type { AuditCandidate } from "@/lib/types"

/** Wieviel vom Umfeld mitgezeigt wird, als Vielfaches der Span-Breite. */
const MARGIN_X = 3.2
const MARGIN_Y = 4.5

/**
 * Der Seitenausschnitt um einen Span.
 *
 * Das ist das eigentliche Werkzeug dieser Seite: Ob ein Preis ein App-Preis
 * ist, steht bei Penny nicht im Text, sondern im blauen Kasten drumherum – und
 * der ist Grafik. Wer nur den Wortlaut liest, urteilt über dieselbe
 * Information, die schon dem Textmodell fehlt.
 *
 * Zugeschnitten wird per CSS statt serverseitig: Das Seitenbild liegt ohnehin
 * unter /api/pages/{id}/image, und der Browser hat es nach dem ersten
 * Kandidaten derselben Seite im Cache.
 */
export function SpanCrop({ candidate, height = 150 }: { candidate: AuditCandidate; height?: number }) {
  const [x0, y0, x1, y1] = candidate.bbox
  const spanWidth = Math.max(x1 - x0, 8)
  const spanHeight = Math.max(y1 - y0, 8)

  const cropWidth = spanWidth * MARGIN_X
  const cropHeight = spanHeight * MARGIN_Y
  const cropLeft = x0 - (cropWidth - spanWidth) / 2
  const cropTop = y0 - (cropHeight - spanHeight) / 2

  // Der Zoom ergibt sich aus der Zielhöhe; die Breite folgt dem Seitenverhältnis
  // des Ausschnitts, damit nichts verzerrt.
  const zoom = height / cropHeight
  const width = cropWidth * zoom

  return (
    <div
      className="relative shrink-0 overflow-hidden rounded-md border bg-muted"
      style={{ width, height }}
    >
      <img
        src={`/api/pages/${candidate.page_id}/image`}
        alt={`Ausschnitt um ${candidate.text}`}
        className="max-w-none absolute"
        style={{
          width: candidate.page_width * zoom,
          height: candidate.page_height * zoom,
          left: -cropLeft * zoom,
          top: -cropTop * zoom,
        }}
      />
      {/* Der Rahmen markiert, über welches Wort geurteilt wird – im Ausschnitt
          stehen fast immer mehrere Preise nebeneinander. */}
      <div
        className="absolute rounded-sm ring-2 ring-red-500/90"
        style={{
          left: (x0 - cropLeft) * zoom,
          top: (y0 - cropTop) * zoom,
          width: spanWidth * zoom,
          height: spanHeight * zoom,
        }}
      />
    </div>
  )
}
