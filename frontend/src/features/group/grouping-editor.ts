/** Wörter zu Angeboten gruppieren – reine Funktionen, ohne React.
 *
 * Gespeichert wird eine Liste von Wortindex-Listen. Ein Wort gehört zu
 * höchstens einem Angebot; die API lehnt alles andere mit 422 ab, also darf
 * dieser Editor es gar nicht erst erzeugen.
 *
 * Leere Angebote werden fallen gelassen. Sonst sammelt eine Sitzung Löcher an,
 * die im Report als `ref_groups_without_entities` auftauchen und dort wie ein
 * Labelfehler aussehen.
 */

export type Groups = number[][]

/** In welchem Angebot steht dieses Wort? -1, wenn in keinem. */
export function groupOf(groups: Groups, word: number): number {
  return groups.findIndex((group) => group.includes(word))
}

interface ToggleResult {
  groups: Groups
  active: number
}

/** Ein neues, leeres Angebot anlegen und aktiv schalten.
 *
 * Es wird erst beim ersten Wort sichtbar – `compact` wirft leere Angebote
 * beim Speichern weg, `active` zeigt solange auf die künftige Position.
 */
export function startGroup(groups: Groups): ToggleResult {
  return { groups, active: groups.length }
}

/**
 * Die Wörter [start, end) dem aktiven Angebot zuschlagen – oder freigeben.
 *
 * Liegt eines davon schon in irgendeinem Angebot, werden alle freigegeben,
 * auch aus einem fremden. Bis zum 07.09.2026 wanderte ein Wort aus einem
 * fremden Angebot stattdessen ins aktive: damit liess sich ein Fehlgriff
 * in einem früheren Angebot gar nicht mehr abwählen, jeder Klick zog ihn
 * nur weiter. Verschieben kostet jetzt zwei Klicks (freigeben, zuordnen),
 * dafür tut ein Klick auf ein gefärbtes Wort immer dasselbe.
 */
export function toggleRange(
  groups: Groups,
  active: number,
  start: number,
  end: number,
): ToggleResult {
  const words = Array.from({ length: end - start }, (_, i) => start + i)
  const assigned = words.some((w) => groupOf(groups, w) >= 0)

  if (assigned) {
    return compact(groups.map((group) => group.filter((w) => !words.includes(w))), active)
  }

  const target = active >= 0 ? active : groups.length
  const next = groups.map((group) => [...group])
  while (next.length <= target) next.push([])
  next[target] = [...next[target], ...words].sort((a, b) => a - b)
  return compact(next, target)
}

/**
 * Wörter dem aktiven Angebot zuschlagen, ohne etwas zurückzunehmen.
 *
 * Für die Rechteckauswahl: sie trifft auch Wörter, die schon im aktiven
 * Angebot liegen, und die dürfen dabei nicht herausfallen – sonst nähme ein
 * zweites, grösseres Rechteck die Hälfte des ersten wieder weg. Was in
 * einem fremden Angebot lag, wechselt wie beim Klick.
 */
export function assignWords(groups: Groups, active: number, words: number[]): ToggleResult {
  if (words.length === 0) return { groups, active }
  const stripped = groups.map((group) => group.filter((w) => !words.includes(w)))
  const target = active >= 0 ? active : stripped.length
  while (stripped.length <= target) stripped.push([])
  stripped[target] = [...new Set([...stripped[target], ...words])].sort((a, b) => a - b)
  return compact(stripped, target)
}

/** Ein ganzes Angebot auflösen. Seine Wörter gehören danach zu keinem. */
export function removeGroup(groups: Groups, index: number): ToggleResult {
  if (index < 0 || index >= groups.length) return { groups, active: -1 }
  return compact(groups.filter((_, i) => i !== index), -1)
}

/** Leere Angebote entfernen und den aktiven Index mitziehen.
 *
 * Der Index verschiebt sich beim Aufräumen – ohne diese Nachführung zeigt
 * `active` nach dem Wegfall eines vorderen Angebots auf das falsche.
 *
 * Fällt das aktive Angebot selbst weg (letztes Wort herausgeklickt), ist
 * danach keines aktiv. Der nächste Klick beginnt ein neues – das ist
 * vorhersehbarer, als still auf den Nachbarn zu rutschen und dessen Inhalt zu
 * erweitern.
 */
function compact(groups: Groups, active: number): ToggleResult {
  const kept: Groups = []
  let nextActive = -1
  groups.forEach((group, i) => {
    if (group.length === 0) return
    if (i === active) nextActive = kept.length
    kept.push(group)
  })
  return { groups: kept, active: nextActive }
}
