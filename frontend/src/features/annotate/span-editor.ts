// Reine Auswahl-Logik des Annotators, bewusst ohne React: Das ist der Teil,
// bei dem sich Fehler still in die Gold-Daten schreiben würden.

import type { Span } from "@/lib/types"

function overlaps(span: Span, start: number, end: number): boolean {
  return span.start < end && start < span.end
}

/** Entfernt jeden Span, der [start, end) schneidet. */
export function removeRange(spans: Span[], start: number, end: number): Span[] {
  return spans.filter((s) => !overlaps(s, start, end))
}

/** Setzt einen Span. Überlappende weichen - eine Regel ohne Sonderfälle. */
export function applyLabel(spans: Span[], start: number, end: number, label: string): Span[] {
  return [...removeRange(spans, start, end), { start, end, label }].sort(
    (a, b) => a.start - b.start,
  )
}

/** Der Span, der einen Wortindex enthält - für Klick auf ein gelabeltes Wort. */
export function spanAt(spans: Span[], index: number): Span | null {
  return spans.find((s) => index >= s.start && index < s.end) ?? null
}
