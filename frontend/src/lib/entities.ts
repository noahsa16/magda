// Farbenblind-taugliche Palette (Okabe-Ito + Erweiterung). Zuordnung läuft
// über die Position im Schema aus /api/schema – neue Entity-Typen (hinten
// angefügt, wie labels.py vorschreibt) bekommen automatisch die nächste Farbe.
const PALETTE = [
  "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2",
  "#D55E00", "#CC79A7", "#8C510A", "#5AB4AC", "#762A83",
]

const FALLBACK = "#999999"

export function entityColor(entityTypes: string[], type: string): string {
  const idx = entityTypes.indexOf(type)
  return idx === -1 ? FALLBACK : PALETTE[idx % PALETTE.length]
}
