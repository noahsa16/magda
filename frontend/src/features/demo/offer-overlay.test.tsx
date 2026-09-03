import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import type { DemoOffer } from "@/lib/types"
import { OfferOverlay } from "./offer-overlay"

function offer(overrides: Partial<DemoOffer> = {}): DemoOffer {
  return {
    page_index: 0,
    bbox: [10, 10, 50, 30],
    product: "Butter",
    brand: null,
    price: "1.29",
    old_price: null,
    quantity: null,
    unit_price: null,
    app_price: null,
    discount: null,
    valid: null,
    variants: [],
    confidence: null,
    arithmetic: "unverifiable",
    entity_word_ranges: [],
    ...overrides,
  }
}

describe("OfferOverlay", () => {
  it("zeichnet genau eine Box je Angebot", () => {
    render(
      <OfferOverlay
        imageUrl="/x.png"
        width={200}
        height={200}
        offers={[offer(), offer({ product: "Milch", bbox: [60, 10, 100, 30] })]}
        activeIndex={null}
        onSelect={() => {}}
      />,
    )

    expect(screen.getByTestId("offer-box-0")).toBeInTheDocument()
    expect(screen.getByTestId("offer-box-1")).toBeInTheDocument()
  })

  it("ruft onSelect mit dem geklickten Index auf", async () => {
    const onSelect = vi.fn()
    render(
      <OfferOverlay
        imageUrl="/x.png"
        width={200}
        height={200}
        offers={[offer(), offer({ product: "Milch" })]}
        activeIndex={null}
        onSelect={onSelect}
      />,
    )

    await userEvent.click(screen.getByTestId("offer-box-1"))
    expect(onSelect).toHaveBeenCalledWith(1)
  })

  it("hebt die aktive Box staerker hervor als die uebrigen", () => {
    render(
      <OfferOverlay
        imageUrl="/x.png"
        width={200}
        height={200}
        offers={[offer(), offer({ product: "Milch" })]}
        activeIndex={1}
        onSelect={() => {}}
      />,
    )

    const active = screen.getByTestId("offer-box-1")
    const inactive = screen.getByTestId("offer-box-0")
    expect(active.getAttribute("fill-opacity")).not.toBe(inactive.getAttribute("fill-opacity"))
  })

  it("zeigt eine Meldung, wenn die Seite keine Angebote hat", () => {
    render(
      <OfferOverlay imageUrl="/x.png" width={200} height={200} offers={[]} activeIndex={null} onSelect={() => {}} />,
    )

    expect(screen.getByText("Keine Angebote auf dieser Seite.")).toBeInTheDocument()
  })
})
