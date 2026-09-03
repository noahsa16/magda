import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { UploadPanel } from "./upload-panel"

function setup(overrides: Partial<Parameters<typeof UploadPanel>[0]> = {}) {
  const onStartFile = vi.fn()
  const onStartUrl = vi.fn()
  const onVariantChange = vi.fn()
  render(
    <UploadPanel
      variant="gbert"
      onVariantChange={onVariantChange}
      onStartFile={onStartFile}
      onStartUrl={onStartUrl}
      busy={false}
      {...overrides}
    />,
  )
  return { onStartFile, onStartUrl, onVariantChange }
}

function pdfFile(name = "prospekt.pdf") {
  return new File(["%PDF-1.7"], name, { type: "application/pdf" })
}

describe("UploadPanel", () => {
  it("der Start-Button ist ohne Eingabe deaktiviert", () => {
    setup()
    expect(screen.getByRole("button", { name: /verarbeiten/i })).toBeDisabled()
  })

  it("eine ausgewählte Datei aktiviert den Start-Button und startet mit ihr", async () => {
    const { onStartFile } = setup()
    const user = userEvent.setup()
    const input = screen.getByLabelText("PDF auswählen").querySelector("input")!

    await user.upload(input, pdfFile())

    expect(screen.getByText("prospekt.pdf")).toBeInTheDocument()
    const button = screen.getByRole("button", { name: /verarbeiten/i })
    expect(button).toBeEnabled()

    await user.click(button)
    expect(onStartFile).toHaveBeenCalledWith(expect.objectContaining({ name: "prospekt.pdf" }))
  })

  it("eine eingegebene URL startet den Import statt eines Uploads", async () => {
    const { onStartUrl, onStartFile } = setup()
    const user = userEvent.setup()

    await user.type(screen.getByLabelText("Penny-Katalog-URL"), "https://x/?catalogId=1")
    await user.click(screen.getByRole("button", { name: /verarbeiten/i }))

    expect(onStartUrl).toHaveBeenCalledWith("https://x/?catalogId=1")
    expect(onStartFile).not.toHaveBeenCalled()
  })

  it("Datei und URL schliessen sich gegenseitig aus", async () => {
    const user = userEvent.setup()
    setup()
    const input = screen.getByLabelText("PDF auswählen").querySelector("input")!

    await user.upload(input, pdfFile())
    expect(screen.getByText("prospekt.pdf")).toBeInTheDocument()

    await user.type(screen.getByLabelText("Penny-Katalog-URL"), "https://x/?catalogId=1")
    // Die Datei-Anzeige verschwindet, sobald eine URL eingetippt wird.
    expect(screen.queryByText("prospekt.pdf")).not.toBeInTheDocument()
  })

  it("waehlt gbert und layoutxlm ueber Klick auf die Modellkarten", async () => {
    const { onVariantChange } = setup()
    const user = userEvent.setup()

    await user.click(screen.getByRole("button", { name: /layoutxlm/i }))
    expect(onVariantChange).toHaveBeenCalledWith("layoutxlm")
  })

  it("busy deaktiviert den Start-Button auch mit gueltiger Eingabe", async () => {
    const user = userEvent.setup()
    setup({ busy: true })

    await user.type(screen.getByLabelText("Penny-Katalog-URL"), "https://x/?catalogId=1")
    expect(screen.getByRole("button", { name: /verarbeiten/i })).toBeDisabled()
  })
})
