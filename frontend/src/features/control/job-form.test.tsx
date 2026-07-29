import { fireEvent, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { JobDef } from "@/lib/types"
import { renderWithProviders } from "@/test/utils"
import { JobForm, defaultValues, missingRequired } from "./job-form"

const DOWNLOAD: JobDef = {
  job: "01_download_flyers",
  title: "Prospekte laden",
  what: "Holt einen Penny-Katalog.",
  params: [
    { key: "url", label: "Katalog-URL", kind: "str", default: null, choices: [], required: true, help: "mit catalogId" },
    { key: "max_pages", label: "Seiten höchstens", kind: "int", default: 40, choices: [], required: false, help: "" },
  ],
}

const TRAIN: JobDef = {
  job: "04_train",
  title: "Training",
  what: "Token-Klassifikation.",
  params: [
    { key: "variant", label: "Variante", kind: "choice", default: null, choices: ["gbert", "layoutxlm"], required: true, help: "" },
  ],
}

describe("defaultValues", () => {
  it("uebernimmt die Defaults aus dem Katalog", () => {
    expect(defaultValues(DOWNLOAD)).toEqual({ url: "", max_pages: "40" })
  })
})

describe("missingRequired", () => {
  it("meldet leere Pflichtfelder", () => {
    expect(missingRequired(DOWNLOAD, { url: "", max_pages: "40" })).toEqual(["Katalog-URL"])
    expect(missingRequired(DOWNLOAD, { url: "https://x", max_pages: "40" })).toEqual([])
  })
})

describe("JobForm", () => {
  it("rendert ein Feld je Parameter", () => {
    renderWithProviders(
      <JobForm job={DOWNLOAD} values={defaultValues(DOWNLOAD)} onChange={vi.fn()} onStart={vi.fn()} disabled={false} />,
    )
    expect(screen.getByLabelText(/Katalog-URL/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Seiten höchstens/)).toHaveValue("40")
  })

  it("sperrt den Start bei leerem Pflichtfeld", () => {
    renderWithProviders(
      <JobForm job={DOWNLOAD} values={{ url: "", max_pages: "40" }} onChange={vi.fn()} onStart={vi.fn()} disabled={false} />,
    )
    expect(screen.getByRole("button", { name: /starten/i })).toBeDisabled()
    expect(screen.getByText(/Fehlt noch: Katalog-URL/)).toBeInTheDocument()
  })

  it("startet mit den eingegebenen Werten", () => {
    const onStart = vi.fn()
    renderWithProviders(
      <JobForm job={DOWNLOAD} values={{ url: "https://x", max_pages: "12" }} onChange={vi.fn()} onStart={onStart} disabled={false} />,
    )
    fireEvent.click(screen.getByRole("button", { name: /starten/i }))
    expect(onStart).toHaveBeenCalledWith({ url: "https://x", max_pages: "12" })
  })

  it("zeigt choice-Parameter als Auswahl", () => {
    renderWithProviders(
      <JobForm job={TRAIN} values={{ variant: "gbert" }} onChange={vi.fn()} onStart={vi.fn()} disabled={false} />,
    )
    const select = screen.getByLabelText(/Variante/)
    expect(select).toHaveValue("gbert")
    expect(screen.getByRole("option", { name: "layoutxlm" })).toBeInTheDocument()
  })

  it("zeigt Schritte ohne Parameter als reinen Knopf", () => {
    const plain: JobDef = { job: "02_extract_words", title: "Wörter", what: "PyMuPDF liest.", params: [] }
    renderWithProviders(
      <JobForm job={plain} values={{}} onChange={vi.fn()} onStart={vi.fn()} disabled={false} />,
    )
    expect(screen.getByRole("button", { name: /starten/i })).toBeEnabled()
  })
})
