import { describe, expect, it } from "vitest"
import { groupOf, removeGroup, startGroup, toggleRange } from "./grouping-editor"

/** Ein Wort in ein Angebot legen ist ein Klick; die Regeln dahinter sind
 * dieselben wie in der API: höchstens ein Angebot je Wort, keine leeren
 * Angebote. Was hier durchrutscht, quittiert der Server mit 422 – und der
 * Annotator sieht nur, dass nichts gespeichert wurde. */

describe("groupOf", () => {
  it("findet das Angebot eines Wortes", () => {
    expect(groupOf([[0, 1], [5]], 5)).toBe(1)
  })

  it("meldet -1 für ein Wort ohne Angebot", () => {
    expect(groupOf([[0, 1]], 9)).toBe(-1)
  })
})

describe("toggleRange", () => {
  it("legt ohne aktives Angebot ein neues an", () => {
    const { groups, active } = toggleRange([], -1, 3, 5)

    expect(groups).toEqual([[3, 4]])
    expect(active).toBe(0)
  })

  it("hängt an das aktive Angebot an, statt ein zweites zu öffnen", () => {
    const { groups } = toggleRange([[3, 4]], 0, 7, 8)

    expect(groups).toEqual([[3, 4, 7]])
  })

  it("nimmt denselben Klick wieder zurück", () => {
    const { groups } = toggleRange([[3, 4, 7]], 0, 7, 8)

    expect(groups).toEqual([[3, 4]])
  })

  it("löst ein Wort aus einem fremden Angebot heraus", () => {
    // Ein Wort kann nur einem Angebot gehören. Den Klick wirkungslos zu
    // lassen, versteckte den Grund - hier wechselt es sichtbar die Seite.
    const { groups } = toggleRange([[0, 1], [5]], 1, 1, 2)

    expect(groups).toEqual([[0], [1, 5]])
  })

  it("hält die Wörter eines Angebots sortiert", () => {
    const { groups } = toggleRange([[7]], 0, 2, 3)

    expect(groups).toEqual([[2, 7]])
  })

  it("lässt kein leeres Angebot zurück", () => {
    const { groups } = toggleRange([[0], [5]], 0, 0, 1)

    expect(groups).toEqual([[5]])
  })

  it("lässt nach dem Leerklicken des aktiven Angebots keines aktiv", () => {
    // Still auf den Nachbarn zu rutschen, erweiterte den nächsten Klick um ein
    // fremdes Angebot - der Annotator sähe die Ursache nicht.
    const { groups, active } = toggleRange([[0], [5], [9]], 0, 0, 1)

    expect(groups).toEqual([[5], [9]])
    expect(active).toBe(-1)
  })

  it("zieht den aktiven Index nach, wenn ein vorderes Angebot wegfällt", () => {
    // Wort 0 wechselt aus dem ersten Angebot ins aktive dritte; das erste
    // bleibt leer zurück und faellt weg. Ohne Nachfuehrung zeigte `active`
    // danach auf das falsche Angebot.
    const { groups, active } = toggleRange([[0], [5], [9]], 2, 0, 1)

    expect(groups).toEqual([[5], [0, 9]])
    expect(active).toBe(1)
  })
})

describe("startGroup", () => {
  it("schaltet auf ein neues Angebot, ohne eines zu erzeugen", () => {
    const { groups, active } = startGroup([[0, 1]])

    expect(groups).toEqual([[0, 1]])
    expect(active).toBe(1)
  })

  it("nimmt das nächste Wort in das neue Angebot auf", () => {
    const gestartet = startGroup([[0, 1]])

    const { groups } = toggleRange(gestartet.groups, gestartet.active, 5, 6)

    expect(groups).toEqual([[0, 1], [5]])
  })
})

describe("removeGroup", () => {
  it("löst ein Angebot auf und gibt seine Wörter frei", () => {
    const { groups, active } = removeGroup([[0, 1], [5]], 0)

    expect(groups).toEqual([[5]])
    expect(active).toBe(-1)
  })

  it("lässt einen Index ausserhalb der Liste unberührt", () => {
    expect(removeGroup([[0]], 7).groups).toEqual([[0]])
  })
})
