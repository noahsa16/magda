import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { renderWithProviders } from "@/test/utils"
import { CatalogGrid } from "./catalog-grid"
import type { CatalogTile } from "@/lib/types"

const tile = (over: Partial<CatalogTile> = {}): CatalogTile => ({
  id: "1342881", pages: 40, done: 18, downloaded: "2026-07-23", stale: 0, broken: 0,
  region: "Bayern · 153 Märkte", region_confirmed: true, ...over,
})

describe("CatalogGrid", () => {
  it("zeigt Kennzahlen und Beschriftung je Kachel", () => {
    renderWithProviders(<CatalogGrid tiles={[tile()]} unit="fertig" onSelect={() => {}} />)
    expect(screen.getByText("1342881")).toBeInTheDocument()
    expect(screen.getByText(/40 Seiten/)).toBeInTheDocument()
    expect(screen.getByText("18/40 fertig")).toBeInTheDocument()
  })

  it("meldet die Auswahl mit der Katalog-ID", async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    renderWithProviders(<CatalogGrid tiles={[tile()]} unit="fertig" onSelect={onSelect} />)
    await user.click(screen.getByRole("button", { name: /1342881/ }))
    expect(onSelect).toHaveBeenCalledWith("1342881")
  })

  it("weist auf veraltete und kaputte Seiten hin", () => {
    renderWithProviders(
      <CatalogGrid tiles={[tile({ stale: 3, broken: 1 })]} unit="fertig" onSelect={() => {}} />,
    )
    expect(screen.getByText(/4 ungültig/)).toBeInTheDocument()
  })

  it("verschweigt den Hinweis, wenn nichts ungültig ist", () => {
    renderWithProviders(<CatalogGrid tiles={[tile()]} unit="fertig" onSelect={() => {}} />)
    expect(screen.queryByText(/ungültig/)).not.toBeInTheDocument()
  })

  it("lässt das Ladedatum weg, wenn es fehlt", () => {
    renderWithProviders(
      <CatalogGrid tiles={[tile({ downloaded: null })]} unit="fertig" onSelect={() => {}} />,
    )
    expect(screen.getByText("40 Seiten")).toBeInTheDocument()
  })

  it("zeigt den Leerzustand ohne Kacheln", () => {
    renderWithProviders(
      <CatalogGrid tiles={[]} unit="fertig" onSelect={() => {}} emptyHint="Nichts da" />,
    )
    expect(screen.getByText("Nichts da")).toBeInTheDocument()
  })
})
