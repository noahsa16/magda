/**
 * Liest die letzte Fortschrittszeile aus der Konsolenausgabe von
 * `magda extract-pdf` (`_progress` in `cli/extract_pdf.py`): "  Seite 3/12: 0.42s".
 *
 * Eine eigene, reine Funktion statt Regex-Inline im JSX, damit sich das
 * Format ändern lässt, ohne die Anzeigekomponente anzufassen - und damit es
 * ohne Runner-Mock testbar ist.
 */
export interface DemoProgress {
  page: number
  total: number
  seconds: number
}

const LINE = /Seite (\d+)\/(\d+):\s*([\d.]+)s/

export function parseProgress(lines: string[]): DemoProgress | null {
  for (let i = lines.length - 1; i >= 0; i--) {
    const match = LINE.exec(lines[i])
    if (match) {
      return { page: Number(match[1]), total: Number(match[2]), seconds: Number(match[3]) }
    }
  }
  return null
}
