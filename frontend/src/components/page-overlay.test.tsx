import { render } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { PageOverlay } from "./page-overlay"

const TYPES = ["PRODUCT", "BRAND", "PRICE"]
const words = [
  { text: "Rinderhackfleisch", bbox: [72.4, 310.2, 198.6, 324.8] as [number, number, number, number] },
  { text: "3.99", bbox: [210.5, 305.0, 265.3, 348.1] as [number, number, number, number] },
]

describe("PageOverlay", () => {
  it("zeichnet eine Box pro Wort im PDF-Koordinatenraum", () => {
    const { container } = render(
      <PageOverlay imageUrl="/img.png" width={595.28} height={841.89}
        words={words} tags={["B-PRODUCT", "B-PRICE"]} entityTypes={TYPES} />,
    )
    const svg = container.querySelector("svg")!
    expect(svg.getAttribute("viewBox")).toBe("0 0 595.28 841.89")
    expect(container.querySelectorAll("rect")).toHaveLength(2)
  })

  it("blendet gefilterte Typen aus, O-Woerter bleiben dezent sichtbar", () => {
    const { container } = render(
      <PageOverlay imageUrl="/img.png" width={595.28} height={841.89}
        words={words} tags={["B-PRODUCT", "O"]} entityTypes={TYPES}
        visibleTypes={new Set(["PRICE"])} />,
    )
    // PRODUCT ist weggefiltert, das O-Wort wird als dezente Kontur gezeichnet.
    expect(container.querySelectorAll("rect")).toHaveLength(1)
  })

  it("macht auch ungefuellte Boxen auf ganzer Flaeche treffbar", () => {
    const { container } = render(
      <PageOverlay imageUrl="/img.png" width={595.28} height={841.89}
        words={words} entityTypes={TYPES} />,
    )
    // jsdom kennt kein SVG-Hit-Testing, ein Klick traefe hier auch ohne
    // pointer-events. Geprueft wird deshalb die Eigenschaft selbst: ohne sie
    // faengt fill="none" gar keinen Zeiger, und ungelabelte Woerter - im
    // Annotator alle - sind nur auf ihrer duennen Kontur anklickbar.
    for (const rect of container.querySelectorAll("rect")) {
      expect((rect as SVGRectElement).style.pointerEvents).toBe("all")
      expect(rect.getAttribute("fill")).toBe("none")
    }
  })

  it("rendert ohne tags alle Woerter als Kontur", () => {
    const { container } = render(
      <PageOverlay imageUrl="/img.png" width={595.28} height={841.89}
        words={words} entityTypes={TYPES} />,
    )
    expect(container.querySelectorAll("rect")).toHaveLength(2)
  })
})
