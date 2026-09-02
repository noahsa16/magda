import type { DemoOffer } from "@/lib/types"
import { cn } from "@/lib/utils"

// Dieselbe Okabe-Ito-Basis wie lib/entities.ts, aber eine eigene Palette:
// Angebote sind keine Entity-Typen, und dieselbe Funktion für beide würde
// suggerieren, dass Angebot Nr. 3 etwas mit Entity-Typ Nr. 3 zu tun hat.
const PALETTE = [
  "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2",
  "#D55E00", "#CC79A7", "#8C510A", "#5AB4AC", "#762A83",
]

function offerColor(index: number): string {
  return PALETTE[index % PALETTE.length]
}

interface OfferOverlayProps {
  imageUrl: string
  width: number // PDF-Punkte - das SVG-viewBox übernimmt die Skalierung aufs Bild
  height: number
  offers: DemoOffer[]
  activeIndex: number | null
  onSelect: (index: number) => void
}

/** Angebots-Boxen auf dem Seitenbild - eine Box je Angebot (nicht je Wort,
 * anders als `PageOverlay` im Annotator), farbig nach Position in `offers`. */
export function OfferOverlay({
  imageUrl, width, height, offers, activeIndex, onSelect,
}: OfferOverlayProps) {
  return (
    <div className="relative overflow-hidden rounded-lg border-2 border-foreground bg-card">
      <img src={imageUrl} alt="Prospektseite" className="block w-full" />
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
      >
        {offers.map((offer, index) => {
          const [x0, y0, x1, y1] = offer.bbox
          const active = index === activeIndex
          const color = offerColor(index)
          return (
            <rect
              key={index}
              data-testid={`offer-box-${index}`}
              x={x0} y={y0} width={x1 - x0} height={y1 - y0}
              rx={2}
              fill={color}
              fillOpacity={active ? 0.28 : 0.1}
              stroke={color}
              strokeWidth={active ? 3 : 1.2}
              style={{ cursor: "pointer", pointerEvents: "all" }}
              onClick={() => onSelect(index)}
            >
              <title>Angebot {index + 1}: {offer.product ?? "ohne Produktname"}</title>
            </rect>
          )
        })}
      </svg>
      {offers.length === 0 && (
        <p
          className={cn(
            "absolute inset-x-0 bottom-0 bg-foreground/80 px-3 py-1.5",
            "text-center text-xs text-background",
          )}
        >
          Keine Angebote auf dieser Seite.
        </p>
      )}
    </div>
  )
}
