import { describe, expect, it } from "vitest"
import type { EvalReport } from "@/lib/types"
import { stepProgress, stepStates } from "./steps"

const empty = { raw: 0, words: 0, images: 0, labeled: 0 }
const report = { variant: "layoutxlm", split: "test", num_pages: 4, created: "", report: {} } as EvalReport

describe("stepStates", () => {
  it("gibt ohne Daten nur den Download frei", () => {
    const s = stepStates(empty, [])
    expect(s["01_download_flyers"]).toBe("ready")
    expect(s["02_extract_words"]).toBe("blocked")
    expect(s["04_train"]).toBe("blocked")
  })

  it("markiert vollständige Schritte als erledigt", () => {
    const s = stepStates({ raw: 40, words: 40, images: 40, labeled: 40 }, [])
    expect(s["01_download_flyers"]).toBe("done")
    expect(s["02_extract_words"]).toBe("done")
    expect(s["03_label_words"]).toBe("done")
  })

  it("hält teilweise gelabelte Seiten startbar statt erledigt", () => {
    const s = stepStates({ raw: 40, words: 40, images: 40, labeled: 37 }, [])
    expect(s["03_label_words"]).toBe("ready")
    // Trainieren geht schon mit unvollständigen Labels.
    expect(s["04_train"]).toBe("ready")
  })

  it("bleibt bei nur einer Variante offen – der Vergleich fehlt noch", () => {
    const full = { raw: 40, words: 40, images: 40, labeled: 40 }
    const s = stepStates(full, [report], ["gbert"])
    expect(s["04_train"]).toBe("ready")
    expect(s["05_evaluate"]).toBe("ready")
  })

  it("ist erst mit beiden Varianten erledigt", () => {
    const full = { raw: 40, words: 40, images: 40, labeled: 40 }
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
    const totals = { raw: 40, words: 40, images: 40, labeled: 37 }
    expect(stepProgress("02_extract_words", totals)).toBe("40 / 40 Seiten")
    expect(stepProgress("03_label_words", totals)).toBe("37 / 40 Seiten")
    expect(stepProgress("04_train", totals)).toBeNull()
  })
})
