import type { EvalReport } from "@/lib/types"

export type MetricKey = "f1-score" | "precision" | "recall"

export interface Row {
  entity: string
  gbert?: number
  layoutxlm?: number
}

// seqeval mischt avg-Zeilen unter die Entity-Typen – die gehören nicht ins
// per-Entity-Diagramm.
const AVG_KEYS = new Set(["micro avg", "macro avg", "weighted avg"])

export function perEntityRows(reports: EvalReport[], metric: MetricKey): Row[] {
  const rows = new Map<string, Row>()
  for (const r of reports) {
    for (const [entity, m] of Object.entries(r.report)) {
      if (AVG_KEYS.has(entity)) continue
      const row = rows.get(entity) ?? { entity, gbert: undefined, layoutxlm: undefined }
      row[r.variant] = m[metric]
      rows.set(entity, row)
    }
  }
  return [...rows.values()]
}

export function overallF1(reports: EvalReport[], variant: string): number | null {
  const report = reports.find((r) => r.variant === variant)
  return report?.report["micro avg"]?.["f1-score"] ?? null
}
