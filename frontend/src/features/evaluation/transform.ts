import type {
  EntityMetrics, EvalReport, ProtocolKey, SchemeCounts, SchemeKey, SignificanceReport,
} from "@/lib/types"

export type MetricKey = "f1-score" | "precision" | "recall"

export interface Row {
  entity: string
  gbert?: number
  layoutxlm?: number
  support?: number
  delta?: number
}

// seqeval mischt avg-Zeilen unter die Entity-Typen – die gehören nicht ins
// per-Entity-Diagramm.
const AVG_KEYS = new Set(["micro avg", "macro avg", "weighted avg"])

/**
 * Der Report eines Protokolls, mit Rückfall auf das Primärprotokoll.
 *
 * `report_no_windows` und `report_truncated` fehlen in älteren Dateien. Ohne
 * Rückfall zeigte die Seite dann eine leere Tabelle, und das sieht aus wie
 * "gemessen und nichts gefunden" statt "gar nicht gemessen".
 */
export function reportOf(r: EvalReport, protocol: ProtocolKey): Record<string, EntityMetrics> {
  if (protocol === "report") return r.report ?? {}
  return r[protocol] ?? r.report ?? {}
}

export function hasProtocol(reports: EvalReport[], protocol: ProtocolKey): boolean {
  if (protocol === "report") return true
  return reports.some((r) => r[protocol] != null)
}

export function perEntityRows(
  reports: EvalReport[],
  metric: MetricKey,
  protocol: ProtocolKey = "report",
): Row[] {
  const rows = new Map<string, Row>()
  for (const r of reports) {
    // Zweite Verteidigungslinie: die API filtert formfremde Dateien aus
    // data/eval/ heraus, aber eine weiße Seite mit Stacktrace ist ein zu
    // hoher Preis dafür, dass sich nie jemand vertut.
    for (const [entity, m] of Object.entries(reportOf(r, protocol))) {
      if (AVG_KEYS.has(entity)) continue
      const row = rows.get(entity) ?? { entity, gbert: undefined, layoutxlm: undefined }
      row[r.variant] = m[metric]
      // Support ist über beide Varianten gleich – sie messen gegen dieselbe
      // Referenz. Wer zuerst kommt, setzt ihn.
      row.support ??= m.support
      rows.set(entity, row)
    }
  }
  for (const row of rows.values()) {
    row.delta =
      row.gbert != null && row.layoutxlm != null ? row.layoutxlm - row.gbert : undefined
  }
  return [...rows.values()]
}

export function overallF1(
  reports: EvalReport[],
  variant: string,
  protocol: ProtocolKey = "report",
): number | null {
  const report = reports.find((r) => r.variant === variant)
  if (!report) return null
  return reportOf(report, protocol)["micro avg"]?.["f1-score"] ?? null
}

/** Sortiert Zeilen nach einer Spalte; fehlende Werte fallen immer ans Ende. */
export function sortRows(rows: Row[], key: keyof Row, descending: boolean): Row[] {
  return [...rows].sort((a, b) => {
    const x = a[key]
    const y = b[key]
    if (x == null && y == null) return 0
    if (x == null) return 1
    if (y == null) return -1
    if (typeof x === "string" || typeof y === "string") {
      return descending ? String(y).localeCompare(String(x)) : String(x).localeCompare(String(y))
    }
    return descending ? y - x : x - y
  })
}

export interface SchemeRow {
  scheme: SchemeKey
  gbert?: SchemeCounts
  layoutxlm?: SchemeCounts
}

export const SCHEMES: SchemeKey[] = ["strict", "exact", "partial", "type"]

export function schemeRows(reports: EvalReport[]): SchemeRow[] {
  const rows: SchemeRow[] = SCHEMES.map((scheme) => ({ scheme }))
  for (const r of reports) {
    for (const row of rows) {
      row[r.variant] = r.matching_schemes?.[row.scheme]
    }
  }
  return rows.filter((row) => row.gbert || row.layoutxlm)
}

/**
 * Die MUC-Kategorien als Anteile – die Zusammensetzung eines F1, nicht seine Höhe.
 *
 * Bezugsgröße ist alles, was schiefgehen konnte: die Referenzspans plus die
 * erfundenen. Ein Modell mit vielen `missing` hat ein Recall-Problem, eines mit
 * vielen `spurious` ein Precision-Problem, und das sind verschiedene nächste
 * Schritte. Der Punktschätzer allein unterscheidet die beiden Fälle nicht.
 */
export function errorComposition(counts: SchemeCounts) {
  const total =
    counts.correct + counts.incorrect + counts.partial + counts.missing + counts.spurious
  if (total === 0) return null
  return {
    total,
    parts: [
      { key: "correct", label: "korrekt", value: counts.correct },
      { key: "partial", label: "teilweise", value: counts.partial },
      { key: "incorrect", label: "falscher Typ", value: counts.incorrect },
      { key: "missing", label: "übersehen", value: counts.missing },
      { key: "spurious", label: "erfunden", value: counts.spurious },
    ].filter((p) => p.value > 0),
  }
}

/** Der Bootstrap-Vergleich, der zu genau diesen beiden Varianten gehört. */
export function significanceFor(
  results: SignificanceReport[] | undefined,
  a: string,
  b: string,
): SignificanceReport | null {
  return (
    results?.find((r) => {
      const models = Object.keys(r.per_model ?? {})
      return models.includes(a) && models.includes(b)
    }) ?? null
  )
}
