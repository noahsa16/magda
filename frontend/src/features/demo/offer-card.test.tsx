import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { renderWithProviders } from "@/test/utils"
import type { DemoOffer } from "@/lib/types"
import { OfferCard } from "./offer-card"

function offer(overrides: Partial<DemoOffer> = {}): DemoOffer {
  return {
    page_index: 0,
    bbox: [0, 0, 10, 10],
    product: "Butter",
    brand: "Landliebe",
    price: "1.29",
    old_price: null,
    quantity: null,
    unit_price: null,
    app_price: null,
    discount: null,
    valid: null,
    variants: [],
    confidence: 0.8,
    arithmetic: "confirmed",
    entity_word_ranges: [{ type: "PRODUCT", start: 0, end: 1 }],
    ...overrides,
  }
}

describe("OfferCard", () => {
  it("zeigt Produkt fett, Marke und Preis", () => {
    renderWithProviders(
      <OfferCard offer={offer()} index={0} active={false} onSelect={() => {}} />,
    )

    expect(screen.getByText("Butter")).toBeInTheDocument()
    expect(screen.getByText("Landliebe")).toBeInTheDocument()
    expect(screen.getByText("1.29 €")).toBeInTheDocument()
  })

  it("zeigt den Streichpreis durchgestrichen neben dem Preis", () => {
    renderWithProviders(
      <OfferCard
        offer={offer({ old_price: "2.49" })}
        index={0}
        active={false}
        onSelect={() => {}}
      />,
    )

    const old = screen.getByText("2.49 €")
    expect(old.className).toContain("line-through")
  })

  it("zeigt den App-Preis als eigenes Badge", () => {
    renderWithProviders(
      <OfferCard
        offer={offer({ app_price: "0.99" })}
        index={0}
        active={false}
        onSelect={() => {}}
      />,
    )

    expect(screen.getByText("App 0.99 €")).toBeInTheDocument()
  })

  it("zeigt keine Tabelle bei genau einer Variante", () => {
    renderWithProviders(
      <OfferCard
        offer={offer({ variants: [{ position: 0, quantity: "200 g", price: "1.29", old_price: null, unit_price: null, app_price: null }] })}
        index={0}
        active={false}
        onSelect={() => {}}
      />,
    )
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
  })

  it("zeigt eine Tabelle ab zwei Varianten", () => {
    renderWithProviders(
      <OfferCard
        offer={offer({
          variants: [
            { position: 0, quantity: "200 g", price: "1.29", old_price: null, unit_price: null, app_price: null },
            { position: 1, quantity: "400 g", price: "2.29", old_price: null, unit_price: null, app_price: null },
          ],
        })}
        index={0}
        active={false}
        onSelect={() => {}}
      />,
    )
    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.getByText("400 g")).toBeInTheDocument()
  })

  it("ruft onSelect bei Klick auf", async () => {
    const onSelect = vi.fn()
    renderWithProviders(
      <OfferCard offer={offer()} index={0} active={false} onSelect={onSelect} />,
    )

    await userEvent.click(screen.getByRole("button"))
    expect(onSelect).toHaveBeenCalledOnce()
  })

  it("zeigt das arithmetische Urteil als Badge mit Tooltip-Text im DOM", () => {
    renderWithProviders(
      <OfferCard offer={offer({ arithmetic: "contradicted" })} index={0} active={false} onSelect={() => {}} />,
    )

    expect(screen.getByText("widerlegt")).toBeInTheDocument()
  })

  it("ohne Produktnamen bricht die Karte nicht ab", () => {
    renderWithProviders(
      <OfferCard offer={offer({ product: null, brand: null })} index={0} active={false} onSelect={() => {}} />,
    )

    expect(screen.getByText("(ohne Produktname)")).toBeInTheDocument()
  })
})
