import { describe, expect, it } from "vitest"
import { assignWords, groupOf, removeGroup, startGroup, toggleRange } from "./grouping-editor"

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

  it("gibt ein Wort aus einem fremden Angebot frei, statt es herüberzuholen", () => {
    // Belegter Fall (07.09.2026): Ein Fehlgriff in einem früheren Angebot
    // liess sich nicht abwählen, weil jeder Klick ihn ins aktive zog.
    const { groups, active } = toggleRange([[0, 1], [5]], 1, 1, 2)

    expect(groups).toEqual([[0], [5]])
    expect(active).toBe(1)
  })

  it("gibt eine halb zugeordnete Entity ganz frei, statt den Rest zuzuordnen", () => {
    const { groups } = toggleRange([[0]], 1, 0, 2)

    expect(groups).toEqual([])
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
    // Wort 0 wird aus dem ersten Angebot freigegeben, während das dritte
    // aktiv ist; das erste bleibt leer zurück und fällt weg. Ohne
    // Nachführung zeigte `active` danach auf das falsche Angebot.
    const { groups, active } = toggleRange([[0], [5], [9]], 2, 0, 1)

    expect(groups).toEqual([[5], [9]])
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

describe("assignWords", () => {
  it("nimmt schon zugeordnete Wörter nicht wieder heraus", () => {
    // Der Unterschied zu toggleRange: ein zweites, grösseres Rechteck über
    // dasselbe Angebot darf nichts zurücknehmen.
    const { groups, active } = assignWords([[3, 4]], 0, [3, 4, 7])

    expect(groups).toEqual([[3, 4, 7]])
    expect(active).toBe(0)
  })

  it("legt ohne aktives Angebot ein neues an", () => {
    expect(assignWords([[0]], -1, [5, 6]).groups).toEqual([[0], [5, 6]])
  })

  it("holt Wörter aus einem fremden Angebot herüber", () => {
    expect(assignWords([[0, 1], [5]], 1, [1]).groups).toEqual([[0], [1, 5]])
  })

  it("ändert bei leerer Auswahl nichts", () => {
    expect(assignWords([[0]], -1, [])).toEqual({ groups: [[0]], active: -1 })
  })
})
