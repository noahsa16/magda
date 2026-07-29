import type { EvalReport, PipelineStatus } from "@/lib/types"

export interface StepDef {
  job: string
  title: string
  what: string
  variants: string[]
}

/** Die fünf Skripte in scripts/ – die Nummerierung ist die Ausführungsreihenfolge. */
export const STEPS: StepDef[] = [
  {
    job: "01_download_flyers",
    title: "Prospekte laden",
    what: "Holt aktuelle Penny-Kataloge und legt jede Seite einzeln als PDF in data/raw ab.",
    variants: [],
  },
  {
    job: "02_extract_words",
    title: "Wörter extrahieren",
    what: "PyMuPDF liest Text und Koordinaten aus dem PDF-Textlayer und rendert je ein PNG.",
    variants: [],
  },
  {
    job: "03_label_words",
    title: "LLM-Labeling",
    what: "Ein Vision-Modell markiert Spans auf dem Seitenbild, daraus werden BIO-Tags.",
    variants: [],
  },
  {
    job: "04_train",
    title: "Training",
    what: "Token-Klassifikation auf den gelabelten Seiten – einmal mit, einmal ohne Layout.",
    variants: ["layoutxlm", "gbert"],
  },
  {
    job: "05_evaluate",
    title: "Evaluation",
    what: "Entity-Level-F1 auf dem eingefrorenen Test-Split, als Report nach data/eval.",
    variants: ["layoutxlm", "gbert"],
  },
  {
    job: "07_flair_baseline",
    title: "Flair-Vergleichsarm",
    what: "Fertiges deutsches NER-Modell ohne Anpassung – misst nur BRAND.",
    variants: [],
  },
]

export type StepState = "done" | "ready" | "blocked"

/**
 * Ein Schritt ist erledigt, wenn sein Output vollständig vorliegt, und
 * startbar, sobald sein Vorgänger Daten geliefert hat. Trainieren ohne
 * gelabelte Seiten ergibt keinen Lauf, den man abbrechen müsste – der Knopf
 * bleibt gesperrt.
 *
 * Training und Evaluation gelten erst mit *beiden* Varianten als erledigt:
 * ein einzelnes Modell beantwortet die Forschungsfrage nicht, die lebt vom
 * Vergleich.
 */
export function stepStates(
  totals: PipelineStatus["totals"],
  reports: EvalReport[],
  trainedVariants: string[] = [],
): Record<string, StepState> {
  const VARIANTS = ["layoutxlm", "gbert"]
  const bothTrained = VARIANTS.every((v) => trainedVariants.includes(v))
  const evaluated = new Set<string>(reports.map((r) => r.variant))
  const bothEvaluated = VARIANTS.every((v) => evaluated.has(v))
  return {
    "01_download_flyers": totals.raw > 0 ? "done" : "ready",
    "02_extract_words":
      totals.raw > 0 && totals.words >= totals.raw ? "done" : totals.raw > 0 ? "ready" : "blocked",
    "03_label_words":
      totals.words > 0 && totals.labeled >= totals.words
        ? "done"
        : totals.words > 0
          ? "ready"
          : "blocked",
    "04_train": bothTrained ? "done" : totals.labeled > 0 ? "ready" : "blocked",
    "05_evaluate": bothEvaluated ? "done" : totals.labeled > 0 ? "ready" : "blocked",
    // Kein "done": der Arm hat keine Varianten, an denen sich Vollständigkeit
    // ablesen ließe, und er wird gegen Gold erneut gefahren, sobald Gold wächst.
    "07_flair_baseline": totals.labeled > 0 ? "ready" : "blocked",
  }
}

/** Welche Varianten eines Schritts liegen schon vor? Markiert die Knöpfe. */
export function doneVariants(
  job: string,
  reports: EvalReport[],
  trainedVariants: string[],
): Set<string> {
  if (job === "04_train") return new Set<string>(trainedVariants)
  if (job === "05_evaluate") return new Set<string>(reports.map((r) => r.variant))
  return new Set<string>()
}

/** Fortschrittstext pro Schritt, z. B. "37 / 40 Seiten". */
export function stepProgress(job: string, totals: PipelineStatus["totals"]): string | null {
  if (job === "01_download_flyers") return `${totals.raw} Seiten`
  if (job === "02_extract_words") return `${totals.words} / ${totals.raw} Seiten`
  if (job === "03_label_words") return `${totals.labeled} / ${totals.words} Seiten`
  return null
}
