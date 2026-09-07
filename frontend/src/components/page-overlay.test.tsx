import { fireEvent, render } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { PageOverlay, wordsInBox } from "./page-overlay"

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

describe("wordsInBox", () => {
  it("trifft jede Box, die das Rechteck schneidet, auch in Gegenrichtung gezogen", () => {
    // Von rechts unten nach links oben gezogen; die Preisbox ragt nur mit
    // ihrem linken Rand hinein und zählt trotzdem.
    expect(wordsInBox(words, { x0: 215, y0: 330, x1: 60, y1: 300 })).toEqual([0, 1])
    expect(wordsInBox(words, { x0: 60, y0: 300, x1: 100, y1: 330 })).toEqual([0])
    expect(wordsInBox(words, { x0: 0, y0: 0, x1: 50, y1: 50 })).toEqual([])
  })
})

describe("PageOverlay — Rechteck aufziehen", () => {
  function setup() {
    const onBoxSelect = vi.fn()
    const onWordClick = vi.fn()
    const { container } = render(
      <PageOverlay imageUrl="/img.png" width={100} height={100}
        words={words} entityTypes={TYPES} onBoxSelect={onBoxSelect} onWordClick={onWordClick} />,
    )
    const svg = container.querySelector("svg")!
    // jsdom misst nichts: das SVG wird als 200×200 px angenommen, also
    // 2 px je PDF-Punkt.
    svg.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 200, height: 200, right: 200, bottom: 200, x: 0, y: 0, toJSON() {} })
    const capture = vi.fn()
    svg.setPointerCapture = capture
    return { svg, onBoxSelect, onWordClick, container, capture }
  }

  it("meldet die Wörter im aufgezogenen Rechteck und verschluckt den Klick danach", () => {
    // Das Wort 0 liegt bei x 72–199, y 310–325 PDF-Punkten – weit ausserhalb
    // eines 100er-viewBox, deshalb eigene Wörter im sichtbaren Bereich.
    const { svg, onBoxSelect, onWordClick, container } = setup()
    fireEvent.pointerDown(svg, { button: 0, clientX: 20, clientY: 20 })
    fireEvent.pointerMove(svg, { clientX: 180, clientY: 180 })
    fireEvent.pointerUp(svg, { clientX: 180, clientY: 180 })

    expect(onBoxSelect).toHaveBeenCalledWith([])
    // Der click, mit dem der Browser das Loslassen quittiert, darf nicht
    // als Einzelklick durchgehen – er nähme das Wort gleich wieder heraus.
    fireEvent.click(container.querySelectorAll("rect")[0])
    expect(onWordClick).not.toHaveBeenCalled()
    fireEvent.click(container.querySelectorAll("rect")[0])
    expect(onWordClick).toHaveBeenCalledTimes(1)
  })

  it("wertet eine Bewegung unter der Schwelle als Klick", () => {
    const { svg, onBoxSelect, onWordClick, container, capture } = setup()
    fireEvent.pointerDown(svg, { button: 0, clientX: 20, clientY: 20 })
    fireEvent.pointerMove(svg, { clientX: 22, clientY: 21 })
    fireEvent.pointerUp(svg, { clientX: 22, clientY: 21 })
    fireEvent.click(container.querySelectorAll("rect")[0])

    expect(onBoxSelect).not.toHaveBeenCalled()
    expect(onWordClick).toHaveBeenCalledTimes(1)
    // jsdom stellt click ohnehin der Box zu; im Browser täte es das mit
    // gefangenem Zeiger nicht mehr. Deshalb wird die Ursache geprüft, nicht
    // die Wirkung: unter der Schwelle wird der Zeiger nie gefangen.
    expect(capture).not.toHaveBeenCalled()
  })

  it("fängt den Zeiger erst, wenn wirklich gezogen wird", () => {
    const { svg, capture } = setup()
    fireEvent.pointerDown(svg, { button: 0, clientX: 20, clientY: 20 })
    fireEvent.pointerMove(svg, { clientX: 60, clientY: 60 })
    expect(capture).toHaveBeenCalledTimes(1)
  })
})
