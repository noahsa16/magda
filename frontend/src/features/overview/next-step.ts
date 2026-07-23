import type { PipelineStatus } from "@/lib/types"

// Welcher Pipeline-Schritt ist als Nächstes dran? null = alles verarbeitet.
export function nextStep(totals: PipelineStatus["totals"]): string | null {
  if (totals.raw === 0) return "python scripts/01_download_flyers.py"
  if (totals.words < totals.raw) return "python scripts/02_extract_words.py"
  if (totals.labeled < totals.words) return "python scripts/03_label_words.py"
  return null
}
