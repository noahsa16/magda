import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { EvaluationPage } from "./evaluation-page"

describe("EvaluationPage", () => {
  it("zeigt den Empty State mit Evaluate-Kommando", async () => {
    mockFetch({ "/api/evaluation": [] })
    renderWithProviders(<EvaluationPage />)
    // Beide Varianten-Kommandos (gbert + layoutxlm) matchen den Regex.
    expect(await screen.findAllByText(/05_evaluate/)).toHaveLength(2)
  })
})
