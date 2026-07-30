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
    // Ungültige Spans verwerfen statt das Array zu erweitern.
    // Das verhindert, dass das Frontend Tags mit falscher Länge
    // an groupEntities() übergibt – z.B. wenn die Wortliste schrumpft.
    if (span.start < 0 || span.end > wordCount || span.start >= span.end) {
      continue
    }
    // Bei Überlappung gewinnt der zuerst genannte Span – dieselbe Regel wie in
    // labels.spans_to_bio(). Über die Oberfläche entstehen keine Überlappungen,
    // über eine von Hand gemergte Datei in gold/ aber schon: Liefen beide
    // Seiten auseinander, sähe der Annotator etwas anderes, als später ins
    // Training ginge – ohne dass es irgendwo auffiele.
    if (tags.slice(span.start, span.end).some((tag) => tag !== "O")) {
      continue
    }
    tags[span.start] = `B-${span.label}`
    for (let i = span.start + 1; i < span.end; i++) tags[i] = `I-${span.label}`
  }
  return tags
}
