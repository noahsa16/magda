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
 * Die Wörter [start, end) dem aktiven Angebot zuschlagen.
 *
 * Stehen sie bereits vollständig darin, werden sie entfernt – derselbe Klick
 * nimmt zurück, was er gesetzt hat. Aus einem fremden Angebot werden sie
 * herausgelöst: ein Wort kann nur einem gehören, und die Alternative wäre,
 * den Klick wirkungslos zu lassen und den Grund dafür zu verstecken.
 */
export function toggleRange(
  groups: Groups,
  active: number,
  start: number,
  end: number,
): ToggleResult {
  const words = Array.from({ length: end - start }, (_, i) => start + i)
  const alreadyActive =
    active >= 0 && active < groups.length && words.every((w) => groups[active].includes(w))

  const stripped = groups.map((group) => group.filter((w) => !words.includes(w)))
  if (alreadyActive) return compact(stripped, active)

  const target = active >= 0 ? active : stripped.length
  while (stripped.length <= target) stripped.push([])
  stripped[target] = [...stripped[target], ...words].sort((a, b) => a - b)
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
