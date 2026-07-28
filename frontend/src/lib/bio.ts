// BIO-Tagfolge -> zusammenhängende Entities, Gegenstück zu labels.spans_to_bio.
import type { Span } from "./types"

export interface Entity {
  type: string
  text: string
  start: number
  end: number // exklusiv, wie bei range()
}

export function groupEntities(words: { text: string }[], tags: string[]): Entity[] {
  const entities: Entity[] = []
  let current: Entity | null = null

  tags.forEach((tag, i) => {
    if (tag.startsWith("B-")) {
      current = { type: tag.slice(2), text: words[i].text, start: i, end: i + 1 }
      entities.push(current)
    } else if (tag.startsWith("I-") && current?.type === tag.slice(2) && current.end === i) {
      current.text += ` ${words[i].text}`
      current.end = i + 1
    } else {
      // "O" oder verwaistes/abgetrenntes I- beendet die laufende Entity.
      current = null
    }
  })
  return entities
}

/** Spans -> BIO-Tags. Gegenstück zu labels.spans_to_bio() in Python. */
export function spansToTags(spans: Span[], wordCount: number): string[] {
  const tags: string[] = new Array(wordCount).fill("O")
  for (const span of spans) {
    tags[span.start] = `B-${span.label}`
    for (let i = span.start + 1; i < span.end; i++) tags[i] = `I-${span.label}`
  }
  return tags
}
