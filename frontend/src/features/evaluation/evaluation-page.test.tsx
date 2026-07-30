import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { mockFetch, renderWithProviders } from "@/test/utils"
import { EvaluationPage } from "./evaluation-page"

describe("EvaluationPage", () => {
  it("erklärt im Empty State, was hier entsteht, statt nur ein Kommando zu zeigen", async () => {
    mockFetch({ "/api/evaluation": [] })
    renderWithProviders(<EvaluationPage />)
    expect(await screen.findByText(/Forschungsfrage/)).toBeInTheDocument()
    expect(screen.getByText(/seqeval/)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Training/ })).toHaveAttribute("href", "/")
  })
})
