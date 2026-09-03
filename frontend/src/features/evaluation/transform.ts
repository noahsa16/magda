import type {
  EntityMetrics, EvalReport, ProtocolKey, SchemeCounts, SchemeKey, SignificanceReport,
} from "@/lib/types"

export type MetricKey = "f1-score" | "precision" | "recall"

export interface Row {
  entity: string
  /** Metrik je Variante – offen, weil die Zahl der Arme im Backend steht. */
  values: Record<string, number | undefined>
  support?: number
  /** Differenz des gewählten Vergleichspaars, `b - a`. */
  delta?: number
}

/**
 * Anzeigereihenfolge der Arme: die Ablationskette, nicht das Alphabet.
 *
 *     xlmr  ──+Layout──▶  lilt  ──+Vision──▶  layoutxlm
 *
 * Jeder Schritt fügt genau eine Zutat hinzu, und die Tabelle liest sich nur
 * so herum. Alphabetisch stünde `layoutxlm` vor `lilt` vor `xlmr`, also genau
 * rückwärts. `gbert` steht vorn als text-only Baseline mit deutschem Encoder;
 * es ist kein Glied der Kette, sondern die Projektreferenz.
 *
 * Bewusst keine vollständige Liste gültiger Arme – die steht in
 * `config.VARIANTS` im Backend. Was hier fehlt, wird hinten angehängt statt
 * verschluckt: ein neuer Arm soll sichtbar sein, bevor jemand diese Zeile
 * nachträgt.
 */
export const VARIANT_ORDER = ["gbert", "xlmr", "lilt", "layoutxlm"]

export const VARIANT_LABELS: Record<string, string> = {
  gbert: "GBERT",
  xlmr: "XLM-R",
  lilt: "LiLT",
  layoutxlm: "LayoutXLM",
}

export function variantLabel(variant: string): string {
  return VARIANT_LABELS[variant] ?? variant
}

/**
 * Reports, die nur einen Teil der Labels messen – nicht vergleichbar.
 *
 * `flair_llm_test.json` traegt `variant` und `report` und kommt deshalb durch
 * die Formpruefung von `/api/evaluation`. Sein micro-F1 gilt aber nur fuer
 * BRAND (0.281 ueber 24 Instanzen), weil `flair/ner-german-large` von unseren
 * acht Labels nur dieses eine kennt. Als Spalte neben den vier Armen gelesen
 * waere das ein katastrophal schlechtes Modell statt einer Antwort auf eine
 * andere Frage.
 *
 * Die alte, fest zweispaltige Seite hat das aus Versehen verdeckt. Eine Seite,
 * die alle gefundenen Arme zeigt, muss es ausdruecklich tun.
 */
export function restrictedArms(
  reports: EvalReport[],
): { variant: string; labels: string[] }[] {
  return reports
    .filter((r) => r.restricted_to?.length)
    .map((r) => ({ variant: r.variant, labels: r.restricted_to as string[] }))
}

/**
 * Reports genau eines Splits – der Testsplit, wenn es ihn gibt.
 *
 * `data/eval/` ist ein Archiv: dort liegen Reports mehrerer Splits und
 * mehrerer Läufe nebeneinander. Belegter Fall (25.08.2026): drei Dateien mit
 * `variant: "gbert"` – der Testlauf über 116 Seiten sowie zwei Dev-Reports
 * über je 21 Seiten aus einem früheren Split. `perEntityRows` schreibt alle
 * in dieselbe Spalte, und welcher gewinnt, entschied die Reihenfolge der
 * Dateinamen.
 *
 * Der Testsplit hat Vorrang, weil er die berichtete Zahl trägt. Kommt eine
 * Variante darin trotzdem doppelt vor (zwei Läufe, gleicher Split), gewinnt
 * der jüngere – nachvollziehbar statt alphabetisch.
 */
export function reportsOfOneSplit(reports: EvalReport[]): EvalReport[] {
  if (reports.length === 0) return []
  const splits = new Map<string, number>()
  for (const r of reports) splits.set(r.split, (splits.get(r.split) ?? 0) + 1)
  const gewaehlt = splits.has("test")
    ? "test"
    : [...splits.entries()].sort((a, b) => b[1] - a[1])[0][0]

  const neuester = new Map<string, EvalReport>()
  for (const r of reports.filter((r) => r.split === gewaehlt)) {
    const bisher = neuester.get(r.variant)
    if (!bisher || r.created > bisher.created) neuester.set(r.variant, r)
  }
  return [...neuester.values()]
}

/** Welche Arme wirklich ausgewertet sind, in Kettenreihenfolge. */
export function variantsOf(reports: EvalReport[]): string[] {
  const found = [...new Set(
    reports.filter((r) => !r.restricted_to?.length).map((r) => r.variant),
  )]
  const known = VARIANT_ORDER.filter((v) => found.includes(v))
  const unknown = found.filter((v) => !VARIANT_ORDER.includes(v)).sort()
  return [...known, ...unknown]
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
  pair?: [string, string],
): Row[] {
  const rows = new Map<string, Row>()
  for (const r of reports) {
    // Zweite Verteidigungslinie: die API filtert formfremde Dateien aus
    // data/eval/ heraus, aber eine weiße Seite mit Stacktrace ist ein zu
    // hoher Preis dafür, dass sich nie jemand vertut.
    for (const [entity, m] of Object.entries(reportOf(r, protocol))) {
      if (AVG_KEYS.has(entity)) continue
      const row = rows.get(entity) ?? { entity, values: {} }
      row.values[r.variant] = m[metric]
      // Support ist über alle Varianten gleich – sie messen gegen dieselbe
      // Referenz. Wer zuerst kommt, setzt ihn.
      row.support ??= m.support
      rows.set(entity, row)
    }
  }
  for (const row of rows.values()) {
    const a = pair && row.values[pair[0]]
    const b = pair && row.values[pair[1]]
    // Nur wenn *beide* dastehen: sonst läse sich das fehlende als 0 und die
    // Spalte zeigte einen Vorsprung, der nie gemessen wurde.
    row.delta = a != null && b != null ? b - a : undefined
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

/**
 * Sortiert Zeilen nach einer Spalte; fehlende Werte fallen immer ans Ende.
 *
 * `key` ist entweder ein Feld der Zeile (`entity`, `support`, `delta`) oder der
 * Name einer Variante – deren Werte liegen in `values` und sind nicht mehr als
 * eigene Felder ansprechbar, seit die Zahl der Arme offen ist.
 */
export function sortRows(rows: Row[], key: string, descending: boolean): Row[] {
  const valueOf = (row: Row) =>
    key === "entity" || key === "support" || key === "delta"
      ? row[key]
      : row.values[key]
  return [...rows].sort((a, b) => {
    const x = valueOf(a)
    const y = valueOf(b)
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
  counts: Record<string, SchemeCounts | undefined>
}

export const SCHEMES: SchemeKey[] = ["strict", "exact", "partial", "type"]

export function schemeRows(reports: EvalReport[]): SchemeRow[] {
  const rows: SchemeRow[] = SCHEMES.map((scheme) => ({ scheme, counts: {} }))
  for (const r of reports) {
    for (const row of rows) {
      const counts = r.matching_schemes?.[row.scheme]
      if (counts) row.counts[r.variant] = counts
    }
  }
  return rows.filter((row) => Object.keys(row.counts).length > 0)
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


/**
 * Die Vergleichspaare, die die Seite anbieten soll.
 *
 * Erst die Kettenschritte – benachbarte Arme, zwischen denen genau eine Zutat
 * liegt. Das sind die beantwortbaren Fragen: `xlmr` gegen `lilt` ist "was
 * bringt Layout", `lilt` gegen `layoutxlm` ist "was bringt der visuelle
 * Backbone". Zuletzt der Gesamtvergleich vom ersten zum letzten Arm, weil das
 * die im Bericht stehende Zahl ist – aber nur, wenn er nicht ohnehin schon
 * ein Kettenschritt ist.
 */
export function variantPairs(variants: string[]): [string, string][] {
  if (variants.length < 2) return []
  const pairs: [string, string][] = variants
    .slice(0, -1)
    .map((v, i) => [v, variants[i + 1]] as [string, string])
  const ends: [string, string] = [variants[0], variants[variants.length - 1]]
  const schon = pairs.some(([a, b]) => a === ends[0] && b === ends[1])
  return schon ? pairs : [...pairs, ends]
}
