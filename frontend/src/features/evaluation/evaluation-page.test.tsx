import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import type { EvalReport, SchemeCounts, SignificanceReport } from "@/lib/types"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { EvaluationPage } from "./evaluation-page"

const metrics = (f1: number, support = 500) => ({
  precision: f1, recall: f1, "f1-score": f1, support,
})

const scheme = (f1: number): SchemeCounts => ({
  precision: f1, recall: f1, f1,
  correct: 90, incorrect: 5, partial: 0, missing: 5, spurious: 10, possible: 100, actual: 105,
})

const EVAL: EvalReport[] = [
  {
    variant: "gbert", split: "test", num_pages: 100, created: "2026-08-02T21:00:00",
    protocol: "windowed", window_stride: 128, words_without_prediction_unwindowed: 1476,
    report: { PRODUCT: metrics(0.824, 1003), "micro avg": metrics(0.8938, 5080) },
    report_no_windows: { PRODUCT: metrics(0.8), "micro avg": metrics(0.8754, 5080) },
    matching_scheme_source: "SemEval-2013 Task 9.1 (MUC-5-Zaehlweise)",
    matching_schemes: {
      strict: scheme(0.894), exact: scheme(0.909), partial: scheme(0.926), type: scheme(0.925),
    },
  },
  {
    variant: "layoutxlm", split: "test", num_pages: 100, created: "2026-08-02T21:00:00",
    report: { PRODUCT: metrics(0.841, 1003), "micro avg": metrics(0.8952, 5080) },
    matching_schemes: {
      strict: scheme(0.895), exact: scheme(0.921), partial: scheme(0.935), type: scheme(0.923),
    },
  },
]

/** Alle vier Arme, wie nach einem vollstaendigen Pod-Lauf. */
const VIER: EvalReport[] = [
  ...EVAL,
  {
    variant: "xlmr", split: "test", num_pages: 100, created: "2026-08-25T10:00:00",
    report: { PRODUCT: metrics(0.80, 1003), "micro avg": metrics(0.881, 5080) },
  },
  {
    variant: "lilt", split: "test", num_pages: 100, created: "2026-08-25T10:00:00",
    report: { PRODUCT: metrics(0.83, 1003), "micro avg": metrics(0.890, 5080) },
  },
]

const SIGNIFICANCE = [{
  created: "2026-08-02T23:36:07", labels_from: "sonnet-5", pages: 100, clusters: 43,
  cluster_threshold: 0.7,
  per_model: {
    gbert: { f1: 0.8938, ci95: [0.8484, 0.9306], clusters: 43, pages: 100, resamples: 10000 },
    layoutxlm: { f1: 0.8952, ci95: [0.8418, 0.9366], clusters: 43, pages: 100, resamples: 10000 },
  },
  paired: {
    difference: -0.0014, ci95: [-0.0164, 0.0108], p_value: 0.8431,
    significant: false, clusters: 43,
  },
}] as unknown as SignificanceReport[]

describe("EvaluationPage mit vier Armen", () => {
  it("zeigt jeden ausgewerteten Arm mit seiner Zutat", async () => {
    // Vier Kacheln statt zwei - und jede nennt, was der Arm sieht. Ohne das
    // ist die Reihe vier Zahlen ohne die Frage, die sie beantworten.
    mockFetch({ "/api/evaluation": VIER, "/api/significance": SIGNIFICANCE })
    renderWithProviders(<EvaluationPage />)

    expect(await screen.findByText("nur Text · deutscher Encoder")).toBeInTheDocument()
    expect(screen.getByText("nur Text · XLM-R")).toBeInTheDocument()
    expect(screen.getByText("Text + Layout")).toBeInTheDocument()
    expect(screen.getByText("Text + Layout + Bild")).toBeInTheDocument()
  })

  it("ordnet die Spalten entlang der Kette, nicht nach Eingangsreihenfolge", async () => {
    // In VIER stehen layoutxlm und xlmr vor lilt. Die Tabelle muss trotzdem
    // gbert, XLM-R, LiLT, LayoutXLM zeigen - sonst liest sich die Kette
    // rueckwaerts und die Δ-Spalte daneben ergibt keinen Sinn.
    mockFetch({ "/api/evaluation": VIER, "/api/significance": SIGNIFICANCE })
    renderWithProviders(<EvaluationPage />)

    // Die letzte Tabelle der Seite ist die pro Entity. Die Schema-Tabelle
    // darueber kennt nur zwei Arme - Schemata stehen erst in Reports ab der
    // Umstellung, und genau deshalb darf sie hier nicht mitgezaehlt werden.
    const tabellen = await screen.findAllByRole("table")
    const heads = within(tabellen[tabellen.length - 1])
      .getAllByRole("columnheader")
      .map((h) => h.textContent)

    expect(heads.filter((h) => h?.includes("F1") && !h?.includes("Δ"))).toEqual([
      "GBERT F1", "XLM-R F1", "LiLT F1", "LayoutXLM F1",
    ])
  })

  it("wechselt mit dem Vergleichspaar auch die Δ-Spalte", async () => {
    // Der Sinn der Kette: "was bringt Layout" ist XLM-R gegen LiLT, und diese
    // Frage soll die Seite stellen koennen, ohne dass jemand Code aendert.
    mockFetch({ "/api/evaluation": VIER, "/api/significance": SIGNIFICANCE })
    renderWithProviders(<EvaluationPage />)

    await userEvent.click(
      await screen.findByRole("button", { name: /XLM-R → LiLT/ }),
    )

    expect(
      await screen.findByRole("columnheader", { name: /Δ XLM-R→LiLT/ }),
    ).toBeInTheDocument()
    // 0.83 (lilt) - 0.80 (xlmr) auf PRODUCT
    expect(screen.getByText("+0.030")).toBeInTheDocument()
  })
})

describe("EvaluationPage", () => {
  it("erklärt im Empty State, was hier entsteht, statt nur ein Kommando zu zeigen", async () => {
    mockFetch({ "/api/evaluation": [], "/api/significance": [] })
    renderWithProviders(<EvaluationPage />)
    expect(await screen.findByText(/Forschungsfrage/)).toBeInTheDocument()
    expect(screen.getByText(/seqeval/)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Training/ })).toHaveAttribute("href", "/")
  })

  it("nennt zur Differenz das Intervall und den p-Wert", async () => {
    // Der Kern des Projektbefunds: 0.8938 gegen 0.8952 sieht nach einem
    // Unterschied aus, das Intervall überdeckt aber die Null. Ohne diese
    // Angaben behauptet die Seite mehr, als 43 Cluster hergeben.
    mockFetch({ "/api/evaluation": EVAL, "/api/significance": SIGNIFICANCE })
    renderWithProviders(<EvaluationPage />)

    expect(await screen.findByText(/Kein Effekt nachweisbar/)).toBeInTheDocument()
    expect(screen.getByText(/\[-0\.0164, 0\.0108\]/)).toBeInTheDocument()
    expect(screen.getByText(/0\.843/)).toBeInTheDocument()
    expect(screen.getByText(/Duplikat-Cluster/)).toBeInTheDocument()
  })

  it("verlangt magda significance, wenn kein Intervall vorliegt", async () => {
    mockFetch({ "/api/evaluation": EVAL, "/api/significance": [] })
    renderWithProviders(<EvaluationPage />)
    expect(await screen.findByText(/magda significance/)).toBeInTheDocument()
  })

  it("schaltet zwischen den Matching-Schemata um", async () => {
    mockFetch({ "/api/evaluation": EVAL, "/api/significance": SIGNIFICANCE })
    renderWithProviders(<EvaluationPage />)

    expect(await screen.findByText(/Grenze und Typ müssen exakt stimmen/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole("tab", { name: "partial" }))
    expect(await screen.findByText(/Teiltreffer zählen 0\.5/)).toBeInTheDocument()
  })

  it("schaltet die Kennzahlen auf ein anderes Protokoll um", async () => {
    // no-windows misst gegen dieselbe volle Referenz; der Abstand zu windowed
    // ist der Wert der Fenster und keine Rundung.
    mockFetch({ "/api/evaluation": EVAL, "/api/significance": SIGNIFICANCE })
    renderWithProviders(<EvaluationPage />)

    // Auf die Kopfzahl eingegrenzt: 0.894 steht auch in der Schema-Tabelle,
    // und die hängt nicht am Protokoll.
    // Ueber die Zutatenzeile statt ueber "GBERT": der blosse Name steht auch
    // im Tabellenkopf, die Zutat nur auf der Kachel.
    const headline = (await screen.findByText("nur Text · deutscher Encoder"))
      .parentElement as HTMLElement

    expect(within(headline).getByText("0.894")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("tab", { name: "no-windows" }))
    expect(within(headline).getByText("0.875")).toBeInTheDocument()
  })

  it("sortiert die Entity-Tabelle auf Klick um", async () => {
    mockFetch({ "/api/evaluation": EVAL, "/api/significance": SIGNIFICANCE })
    renderWithProviders(<EvaluationPage />)

    const head = await screen.findByRole("columnheader", { name: /Entity/ })
    await userEvent.click(head)
    expect(head.textContent).toMatch(/[↓↑]/)
  })
})
