import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import type { GoldSummary, PageSummary } from "@/lib/types"
import { PageList } from "./page-list"

const PAGES: PageSummary[] = [
  { page_id: "462828_p1", catalog: "462828", labeled: true },
  { page_id: "462828_p2", catalog: "462828", labeled: false },
]

const gold = (rows: Partial<GoldSummary>[]): GoldSummary[] =>
  rows.map((r, i) => ({
    page_id: PAGES[i].page_id, catalog: "462828", status: "untouched",
    annotator: "", num_spans: 0, stale: false, ...r,
  }))

describe("PageList", () => {
  it("filtert im Inspektor unverändert nach gelabelten Seiten", async () => {
    const user = userEvent.setup()
    render(<PageList pages={PAGES} selected={null} onSelect={vi.fn()} />)

    const button = screen.getByRole("button", { name: "1 von 2 gelabelt" })
    await user.click(button)

    expect(screen.getByText("p1")).toBeInTheDocument()
    expect(screen.queryByText("p2")).not.toBeInTheDocument()
  })

  it("filtert im Gold-Modus nach noch nicht fertigen Seiten", async () => {
    const user = userEvent.setup()
    render(
      <PageList
        pages={PAGES}
        selected={null}
        onSelect={vi.fn()}
        goldStatus={gold([{ status: "done" }, { status: "in_progress" }])}
      />,
    )

    // Der Punkt daneben zeigt den Gold-Status - der Knopf muss dasselbe meinen.
    const button = screen.getByRole("button", { name: "1 von 2 offen" })
    await user.click(button)

    expect(screen.queryByText("p1")).not.toBeInTheDocument()
    expect(screen.getByText("p2")).toBeInTheDocument()
  })

  it("hebt Seiten mit veralteter Wortliste und kaputter Datei hervor", () => {
    render(
      <PageList
        pages={PAGES}
        selected={null}
        onSelect={vi.fn()}
        goldStatus={gold([{ status: "done", stale: true }, { status: "broken" }])}
      />,
    )

    expect(screen.getByTitle("Wortliste geändert")).toBeInTheDocument()
    expect(screen.getByTitle("Datei unlesbar")).toBeInTheDocument()
  })
})
