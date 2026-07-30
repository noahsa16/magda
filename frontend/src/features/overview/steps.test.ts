import { describe, expect, it } from "vitest"
import type { EvalReport } from "@/lib/types"
import { stepProgress, stepStates } from "./steps"

const empty = { raw: 0, words: 0, images: 0, labeled: 0, excluded: 0, pending: 0, gold_done: 0, gold_in_progress: 0, labeled_by_model: {} }
const report = { variant: "layoutxlm", split: "test", num_pages: 4, created: "", report: {} } as EvalReport

describe("stepStates", () => {
  it("gibt ohne Daten nur den Download frei", () => {
    const s = stepStates(empty, [])
    expect(s["01_download_flyers"]).toBe("ready")
    expect(s["02_extract_words"]).toBe("blocked")
    expect(s["04_train"]).toBe("blocked")
  })

  it("markiert vollständige Schritte als erledigt", () => {
    const s = stepStates({ raw: 40, words: 40, images: 40, labeled: 40, excluded: 0, pending: 0, gold_done: 0, gold_in_progress: 0, labeled_by_model: {} }, [])
    expect(s["01_download_flyers"]).toBe("done")
    expect(s["02_extract_words"]).toBe("done")
    expect(s["03_label_words"]).toBe("done")
  })

  it("zählt aussortierte Duplikate als erledigt, nicht als Rückstand", () => {
    // Der reale Fall: 327 Seiten geladen, 196 verschieden, 131 Duplikate.
    // Gegen raw gerechnet stand der Schritt ewig auf "ready".
    const s = stepStates(
      { raw: 327, words: 196, images: 196, labeled: 196, excluded: 131, pending: 0, gold_done: 0, gold_in_progress: 0, labeled_by_model: {} },
      [],
    )
    expect(s["02_extract_words"]).toBe("done")
  })

  it("hält teilweise gelabelte Seiten startbar statt erledigt", () => {
    const s = stepStates({ raw: 40, words: 40, images: 40, labeled: 37, excluded: 0, pending: 0, gold_done: 0, gold_in_progress: 0, labeled_by_model: {} }, [])
    expect(s["03_label_words"]).toBe("ready")
    // Trainieren geht schon mit unvollständigen Labels.
    expect(s["04_train"]).toBe("ready")
  })

  it("bleibt bei nur einer Variante offen – der Vergleich fehlt noch", () => {
    const full = { raw: 40, words: 40, images: 40, labeled: 40, excluded: 0, pending: 0, gold_done: 0, gold_in_progress: 0, labeled_by_model: {} }
    const s = stepStates(full, [report], ["gbert"])
    expect(s["04_train"]).toBe("ready")
    expect(s["05_evaluate"]).toBe("ready")
  })

  it("ist erst mit beiden Varianten erledigt", () => {
    const full = { raw: 40, words: 40, images: 40, labeled: 40, excluded: 0, pending: 0, gold_done: 0, gold_in_progress: 0, labeled_by_model: {} }
    const s = stepStates(
      full,
      [report, { ...report, variant: "gbert" } as EvalReport],
      ["layoutxlm", "gbert"],
    )
    expect(s["04_train"]).toBe("done")
    expect(s["05_evaluate"]).toBe("done")
  })
})

describe("stepProgress", () => {
  it("zeigt Anteile für die datenverarbeitenden Schritte", () => {
    const totals = { raw: 40, words: 40, images: 40, labeled: 37, excluded: 0, pending: 0, gold_done: 0, gold_in_progress: 0, labeled_by_model: {} }
    expect(stepProgress("02_extract_words", totals)).toBe("40 / 40 Seiten")
    expect(stepProgress("03_label_words", totals)).toBe("37 / 40 Seiten")
    expect(stepProgress("04_train", totals)).toBeNull()
  })

  it("rechnet den Nenner gegen die Duplikate", () => {
    const totals = { raw: 327, words: 196, images: 196, labeled: 196, excluded: 131, pending: 0, gold_done: 0, gold_in_progress: 0, labeled_by_model: {} }
    expect(stepProgress("02_extract_words", totals)).toBe("196 / 196 Seiten · 131 Duplikate")
  })
})
