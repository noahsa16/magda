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
    job: "download",
    title: "Prospekte laden",
    what: "Holt aktuelle Penny-Kataloge und legt jede Seite einzeln als PDF in data/raw ab.",
    variants: [],
  },
  {
    job: "extract",
    title: "Wörter extrahieren",
    what: "PyMuPDF liest Text und Koordinaten aus dem PDF-Textlayer und rendert je ein PNG.",
    variants: [],
  },
  {
    job: "label",
    title: "LLM-Labeling",
    what: "Ein Vision-Modell markiert Spans auf dem Seitenbild, daraus werden BIO-Tags.",
    variants: [],
  },
  {
    job: "train",
    title: "Training",
    what: "Token-Klassifikation auf den gelabelten Seiten – einmal mit, einmal ohne Layout.",
    variants: ["layoutxlm", "gbert"],
  },
  {
    job: "eval",
    title: "Evaluation",
    what: "Entity-Level-F1 auf dem eingefrorenen Test-Split, als Report nach data/eval.",
    variants: ["layoutxlm", "gbert"],
  },
  {
    job: "flair",
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
    "download": totals.raw > 0 ? "done" : "ready",
    // Nicht words >= raw: die Entdopplung sortiert Seiten aus, damit bleibt
    // words dauerhaft kleiner als raw und der Schritt sähe nie erledigt aus.
    // Erledigt heißt: keine Seite mehr offen – weder extrahiert noch verworfen.
    "extract":
      totals.raw > 0 && totals.pending === 0 ? "done" : totals.raw > 0 ? "ready" : "blocked",
    "label":
      totals.words > 0 && totals.labeled >= totals.words
        ? "done"
        : totals.words > 0
          ? "ready"
          : "blocked",
    "train": bothTrained ? "done" : totals.labeled > 0 ? "ready" : "blocked",
    "eval": bothEvaluated ? "done" : totals.labeled > 0 ? "ready" : "blocked",
    // Kein "done": der Arm hat keine Varianten, an denen sich Vollständigkeit
    // ablesen ließe, und er wird gegen Gold erneut gefahren, sobald Gold wächst.
    "flair": totals.labeled > 0 ? "ready" : "blocked",
  }
}

/** Welche Varianten eines Schritts liegen schon vor? Markiert die Knöpfe. */
export function doneVariants(
  job: string,
  reports: EvalReport[],
  trainedVariants: string[],
): Set<string> {
  if (job === "train") return new Set<string>(trainedVariants)
  if (job === "eval") return new Set<string>(reports.map((r) => r.variant))
  return new Set<string>()
}

/** Fortschrittstext pro Schritt, z. B. "37 / 40 Seiten". */
export function stepProgress(job: string, totals: PipelineStatus["totals"]): string | null {
  if (job === "download") return `${totals.raw} Seiten`
  if (job === "extract") {
    // Nenner ist, was übrig bleibt, nachdem die Duplikate abgezogen sind.
    // Gegen raw gerechnet stünde hier ewig "196 / 327", und das liest sich wie
    // ein abgebrochener Lauf statt wie eine erfolgreiche Entdopplung.
    const target = totals.raw - totals.excluded
    const dupes = totals.excluded > 0 ? ` · ${totals.excluded} Duplikate` : ""
    return `${totals.words} / ${target} Seiten${dupes}`
  }
  if (job === "label") return `${totals.labeled} / ${totals.words} Seiten`
  return null
}
