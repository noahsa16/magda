import { describe, expect, it } from "vitest"
import type { EvalReport, SchemeCounts, SignificanceReport } from "@/lib/types"
import {
  errorComposition, hasProtocol, overallF1, perEntityRows, reportOf,
  schemeRows, significanceFor, sortRows, variantPairs, variantsOf,
} from "./transform"

const metrics = (f1: number, support = 10) => ({
  precision: f1, recall: f1, "f1-score": f1, support,
})

const REPORTS: EvalReport[] = [
  {
    variant: "gbert", split: "test", num_pages: 10, created: "2026-07-23T12:00:00",
    report: { PRODUCT: metrics(0.7), PRICE: metrics(0.8, 200), "micro avg": metrics(0.75) },
    report_no_windows: { PRODUCT: metrics(0.6), "micro avg": metrics(0.65) },
  },
  {
    variant: "layoutxlm", split: "test", num_pages: 10, created: "2026-07-23T12:00:00",
    report: { PRODUCT: metrics(0.85), "micro avg": metrics(0.85) },
  },
]

/** Alle vier Arme, wie sie nach einem vollstaendigen Pod-Lauf vorliegen. */
const VIER: EvalReport[] = [
  ...REPORTS,
  {
    variant: "lilt", split: "test", num_pages: 10, created: "2026-08-25T12:00:00",
    report: { PRODUCT: metrics(0.82), "micro avg": metrics(0.82) },
  },
  {
    variant: "xlmr", split: "test", num_pages: 10, created: "2026-08-25T12:00:00",
    report: { PRODUCT: metrics(0.78), "micro avg": metrics(0.78) },
  },
]

describe("variantsOf", () => {
  it("ordnet die Arme entlang der Ablationskette, nicht alphabetisch", () => {
    // xlmr -> lilt -> layoutxlm ist die Kette, in der jeder Schritt genau eine
    // Zutat hinzufuegt. Alphabetisch stuende layoutxlm vor lilt vor xlmr und
    // die Tabelle laese sich rueckwaerts.
    expect(variantsOf(VIER)).toEqual(["gbert", "xlmr", "lilt", "layoutxlm"])
  })

  it("nennt nur Arme, die wirklich ausgewertet sind", () => {
    expect(variantsOf(REPORTS)).toEqual(["gbert", "layoutxlm"])
  })

  it("haengt unbekannte Arme hinten an, statt sie zu verschlucken", () => {
    // Ein neuer Arm soll auf der Seite auftauchen, auch bevor jemand die
    // Anzeigereihenfolge nachtraegt - sonst misst man ihn und sieht ihn nicht.
    const mit = [...REPORTS, { ...REPORTS[0], variant: "lilt-v2" }]
    expect(variantsOf(mit)).toEqual(["gbert", "layoutxlm", "lilt-v2"])
  })
})

describe("perEntityRows", () => {
  it("legt alle Varianten pro Entity nebeneinander, avg-Zeilen fliegen raus", () => {
    const rows = perEntityRows(VIER, "f1-score", "report", ["gbert", "layoutxlm"])
    expect(rows[0].entity).toBe("PRODUCT")
    expect(rows[0].values).toEqual({ gbert: 0.7, layoutxlm: 0.85, lilt: 0.82, xlmr: 0.78 })
    expect(rows[0].support).toBe(10)
    expect(rows[0].delta).toBeCloseTo(0.15)
  })

  it("misst Δ gegen das gewaehlte Paar, nicht gegen feste Spalten", () => {
    // Der Sinn der Kette: "was bringt Layout" ist xlmr gegen lilt, und diese
    // Frage darf die Seite stellen koennen, ohne dass jemand Code aendert.
    const rows = perEntityRows(VIER, "f1-score", "report", ["xlmr", "lilt"])
    expect(rows[0].delta).toBeCloseTo(0.04)
  })

  it("lässt Δ weg, wenn eine der beiden Varianten fehlt", () => {
    // Sonst stünde dort +0.800 und läse sich wie ein gemessener Vorsprung.
    const rows = perEntityRows([REPORTS[0]], "f1-score", "report", ["gbert", "layoutxlm"])
    expect(rows.every((r) => r.delta === undefined)).toBe(true)
  })
})

describe("Protokolle", () => {
  it("liest das gewählte Protokoll", () => {
    expect(overallF1(REPORTS, "gbert", "report_no_windows")).toBe(0.65)
    expect(overallF1(REPORTS, "gbert", "report")).toBe(0.75)
  })

  it("fällt auf das Primärprotokoll zurück, wenn ein Report es nicht kennt", () => {
    // Ältere Dateien in data/eval/ haben nur `report`. Eine leere Tabelle
    // sähe aus wie "gemessen und nichts gefunden" statt "gar nicht gemessen".
    expect(overallF1(REPORTS, "layoutxlm", "report_no_windows")).toBe(0.85)
    expect(reportOf(REPORTS[1], "report_truncated")).toBe(REPORTS[1].report)
  })

  it("meldet ein Protokoll nur als vorhanden, wenn es wirklich dasteht", () => {
    expect(hasProtocol(REPORTS, "report_no_windows")).toBe(true)
    expect(hasProtocol(REPORTS, "report_truncated")).toBe(false)
    expect(hasProtocol([], "report")).toBe(true)
  })
})

describe("overallF1", () => {
  it("liest micro avg", () => {
    expect(overallF1(REPORTS, "layoutxlm")).toBe(0.85)
  })
  it("null ohne Report der Variante", () => {
    expect(overallF1([], "gbert")).toBeNull()
  })
})

describe("sortRows", () => {
  const rows = [
    { entity: "B", values: { gbert: 0.5 }, support: 300 },
    { entity: "A", values: { gbert: 0.9 }, support: 100 },
    { entity: "C", values: {}, support: 200 },
  ]

  it("sortiert absteigend nach Zahl", () => {
    expect(sortRows(rows, "support", true).map((r) => r.entity)).toEqual(["B", "C", "A"])
  })

  it("schiebt fehlende Werte immer ans Ende, egal in welche Richtung", () => {
    // Sonst führt ein nicht ausgewertetes Label die Tabelle an.
    expect(sortRows(rows, "gbert", true).map((r) => r.entity)).toEqual(["A", "B", "C"])
    expect(sortRows(rows, "gbert", false).map((r) => r.entity)).toEqual(["B", "A", "C"])
  })

  it("sortiert Namen alphabetisch", () => {
    expect(sortRows(rows, "entity", false).map((r) => r.entity)).toEqual(["A", "B", "C"])
  })
})

describe("errorComposition", () => {
  const counts: SchemeCounts = {
    precision: 0.8, recall: 0.9, f1: 0.85,
    correct: 80, incorrect: 5, partial: 0, missing: 10, spurious: 5,
    possible: 95, actual: 90,
  }

  it("lässt leere Kategorien weg", () => {
    const composition = errorComposition(counts)
    expect(composition?.total).toBe(100)
    expect(composition?.parts.map((p) => p.key)).toEqual([
      "correct", "incorrect", "missing", "spurious",
    ])
  })

  it("null statt Division durch null", () => {
    expect(errorComposition({ ...counts, correct: 0, incorrect: 0, missing: 0, spurious: 0 }))
      .toBeNull()
  })
})

describe("schemeRows", () => {
  const scheme = (f1: number): SchemeCounts => ({
    precision: f1, recall: f1, f1,
    correct: 1, incorrect: 0, partial: 0, missing: 0, spurious: 0, possible: 1, actual: 1,
  })

  it("stellt beide Varianten je Schema nebeneinander", () => {
    const rows = schemeRows([
      { ...REPORTS[0], matching_schemes: { strict: scheme(0.8), exact: scheme(0.85), partial: scheme(0.9), type: scheme(0.88) } },
      { ...REPORTS[1], matching_schemes: { strict: scheme(0.7), exact: scheme(0.75), partial: scheme(0.8), type: scheme(0.78) } },
    ])
    expect(rows.map((r) => r.scheme)).toEqual(["strict", "exact", "partial", "type"])
    expect(rows[0].counts.gbert?.f1).toBe(0.8)
    expect(rows[0].counts.layoutxlm?.f1).toBe(0.7)
  })

  it("gibt nichts zurück, wenn kein Report Schemata trägt", () => {
    // Reports von vor der Umstellung – der Block darf dann gar nicht erscheinen.
    expect(schemeRows(REPORTS)).toEqual([])
  })
})

describe("significanceFor", () => {
  const report = {
    created: "2026-08-02T23:36:07", labels_from: "sonnet-5", pages: 100, clusters: 43,
    cluster_threshold: 0.7,
    per_model: {
      gbert: { f1: 0.8938, ci95: [0.8484, 0.9306], clusters: 43, pages: 100, resamples: 10000 },
      layoutxlm: { f1: 0.8952, ci95: [0.8418, 0.9366], clusters: 43, pages: 100, resamples: 10000 },
    },
    paired: { difference: -0.0014, ci95: [-0.0164, 0.0108], p_value: 0.8431, significant: false, clusters: 43 },
  } as unknown as SignificanceReport

  it("findet den Vergleich der beiden Varianten", () => {
    expect(significanceFor([report], "gbert", "layoutxlm")).toBe(report)
  })

  it("null statt eines fremden Vergleichs", () => {
    // Ein Lauf gbert-gegen-flair darf nicht als Layout-Vergleich durchgehen.
    expect(significanceFor([report], "gbert", "flair")).toBeNull()
    expect(significanceFor(undefined, "gbert", "layoutxlm")).toBeNull()
  })
})


describe("variantPairs", () => {
  const chain = ["gbert", "xlmr", "lilt", "layoutxlm"]

  it("stellt die Kettenschritte als Paare bereit", () => {
    // Jeder Schritt fuegt genau eine Zutat hinzu, und genau das sind die
    // Fragen, die die Seite beantworten koennen soll: was bringt Layout
    // (xlmr->lilt), was bringt der visuelle Backbone (lilt->layoutxlm).
    expect(variantPairs(chain)).toEqual([
      ["gbert", "xlmr"],
      ["xlmr", "lilt"],
      ["lilt", "layoutxlm"],
      ["gbert", "layoutxlm"],
    ])
  })

  it("haengt die berichtete Hauptzahl nicht doppelt an", () => {
    // Bei zwei Armen ist der Kettenschritt schon der Gesamtvergleich.
    expect(variantPairs(["gbert", "layoutxlm"])).toEqual([["gbert", "layoutxlm"]])
  })

  it("gibt nichts zurueck, solange nur ein Arm ausgewertet ist", () => {
    expect(variantPairs(["gbert"])).toEqual([])
  })
})

describe("sortRows nach Variante", () => {
  // Drei Entities, deren lilt-Reihenfolge der Eingangsreihenfolge widerspricht -
  // sonst waere der Test gruen, ohne je sortiert zu haben.
  const ROWS = [
    { entity: "PRODUCT", values: { gbert: 0.9, lilt: 0.2 }, support: 10 },
    { entity: "PRICE", values: { gbert: 0.1 }, support: 20 },
    { entity: "BRAND", values: { gbert: 0.5, lilt: 0.8 }, support: 30 },
  ]

  it("sortiert nach dem Wert einer Variante, nicht nach einem festen Feld", () => {
    expect(sortRows(ROWS, "lilt", true).map((r) => r.entity)).toEqual([
      "BRAND", "PRODUCT", "PRICE",
    ])
    expect(sortRows(ROWS, "lilt", false).map((r) => r.entity)).toEqual([
      "PRODUCT", "BRAND", "PRICE",
    ])
  })

  it("schiebt Entities ohne Wert dieser Variante immer ans Ende", () => {
    // PRICE hat kein lilt. In beide Sortierrichtungen gehoert es nach hinten,
    // sonst liest sich "nicht gemessen" wie "bester Wert".
    expect(sortRows(ROWS, "lilt", true).at(-1)?.entity).toBe("PRICE")
    expect(sortRows(ROWS, "lilt", false).at(-1)?.entity).toBe("PRICE")
  })
})
