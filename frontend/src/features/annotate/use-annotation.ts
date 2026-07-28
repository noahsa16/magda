import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import type { Span } from "@/lib/types"

export type SaveState = "saved" | "saving" | "error"
export type PageStatus = "untouched" | "in_progress" | "done"

/** Ausstehende Änderung, noch nicht gesichert. Trägt Seite und Hash selbst mit
 * (statt sie beim Flush aus dem Hook-Zustand zu lesen) - sonst würde ein
 * Seitenwechsel während des Wartens auf den Debounce-Timer die Änderung der
 * vorigen Seite mit dem Hash oder unter der ID der neuen Seite abspeichern. */
interface Pending {
  pageId: string
  hash: string
  spans: Span[]
  status: PageStatus
}

/** Annotation einer Seite: laden, im Speicher halten, verzögert sichern.
 *
 * Auto-Speichern darf nicht stillschweigend scheitern - sonst annotiert man
 * zwanzig Minuten ins Leere. Der Fehlerfall bleibt deshalb sichtbar und der
 * ungesicherte Zustand im Speicher, damit ein erneuter Versuch nichts verliert.
 */
export function useAnnotation(pageId: string | null, annotator: string) {
  const queryClient = useQueryClient()
  const [spans, setSpansState] = useState<Span[]>([])
  const [status, setStatusState] = useState<PageStatus>("untouched")
  const [saveState, setSaveState] = useState<SaveState>("saved")
  const [conflict, setConflict] = useState(false)

  const hashRef = useRef<string>("")
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingRef = useRef<Pending | null>(null)

  // Immer die zuletzt angezeigte Seite griffbereit - direkt im Render-Body
  // geschrieben (nicht in einem Effekt), damit sie beim nächsten Aufruf von
  // flush() garantiert aktuell ist, auch wenn flush selbst über einen
  // Seitenwechsel hinweg dieselbe Closure bleibt.
  const pageIdRef = useRef(pageId)
  pageIdRef.current = pageId

  // false ab dem Unmount, damit ein spät auflösender Flush keinen State an
  // einer längst verschwundenen Komponente mehr setzt.
  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  const query = useQuery({
    queryKey: ["gold", pageId],
    queryFn: () => api.goldPage(pageId!),
    enabled: pageId !== null,
  })

  // Serverzustand in den lokalen Zustand übernehmen, wenn die Seite wechselt.
  useEffect(() => {
    if (!query.data) return
    setSpansState(query.data.spans)
    setStatusState(query.data.status)
    hashRef.current = query.data.words_hash
    setSaveState("saved")
    // Der Server hat den gespeicherten Hash gegen die aktuelle Wortliste
    // geprüft. Ohne das wüssten wir es erst beim ersten Speicherversuch.
    setConflict(query.data.stale)
  }, [query.data])

  // Hängt bewusst nicht an pageId: pendingRef trägt die Zielseite selbst mit,
  // damit ein bereits laufender Timer beim Seitenwechsel weiter die richtige
  // Seite sichert, statt auf die neu ausgewählte umzuspringen.
  const flush = useCallback(async () => {
    const pending = pendingRef.current
    if (!pending) return
    // Gehört diese Änderung noch zur gerade angezeigten Seite? Nur dann darf
    // dieser Flush ihren Speicherzustand anzeigen - sonst landet ein Fehler
    // oder ein "gespeichert" einer längst verlassenen Seite auf der falschen.
    const isCurrentPage = () => pending.pageId === pageIdRef.current
    if (mountedRef.current && isCurrentPage()) setSaveState("saving")
    try {
      await api.saveGold(pending.pageId, {
        words_hash: pending.hash,
        // "untouched" ist ein Anzeigezustand, kein speicherbarer.
        status: pending.status === "done" ? "done" : "in_progress",
        annotator,
        spans: pending.spans,
      })
      // Nur wenn seither keine neuere Änderung geplant wurde, darf dieser
      // Flush pendingRef zurücksetzen UND "gespeichert" anzeigen - sonst
      // gälte eine bereits wartende neuere Bearbeitung als gesichert, obwohl
      // ihr eigener Timer noch gar nicht gefeuert hat (zwei überlappende
      // Flushes, deren älterer nach dem neueren aufloest, z. B. durch
      // retry() parallel zu einem Timer).
      const isLatest = pendingRef.current === pending
      if (isLatest) pendingRef.current = null
      // Exaktes Match trifft nur die Übersichts-Query ["gold"], nicht
      // ["gold", pageId] der gerade offenen Seite - sonst würde der davon
      // ausgelöste Refetch eine zwischen Flush-Ende und Refetch-Antwort
      // weiterlaufende Bearbeitung stillschweigend überschreiben.
      queryClient.invalidateQueries({ queryKey: ["gold"], exact: true })
      if (isLatest && mountedRef.current && isCurrentPage()) setSaveState("saved")
    } catch (err) {
      if (mountedRef.current && isCurrentPage()) {
        if (err instanceof Error && err.message.includes("Wortliste")) setConflict(true)
        setSaveState("error")
      }
    }
  }, [annotator, queryClient])

  // Immer die jüngste flush-Fassung griffbereit, damit der Unmount-Cleanup
  // unten (der nur einmal eingerichtet wird) nicht mit veraltetem annotator
  // sichert.
  const flushRef = useRef(flush)
  useEffect(() => {
    flushRef.current = flush
  }, [flush])

  const schedule = useCallback(
    (next: { spans: Span[]; status: PageStatus }) => {
      if (!pageId) return
      // Steht noch eine Änderung für eine andere Seite aus (Seitenwechsel kurz
      // vor Ablauf des Timers), sofort sichern statt sie hier zu überschreiben.
      if (pendingRef.current && pendingRef.current.pageId !== pageId) {
        if (timerRef.current) clearTimeout(timerRef.current)
        void flush()
      }
      pendingRef.current = { pageId, hash: hashRef.current, ...next }
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(flush, 300)
    },
    [pageId, flush],
  )

  const setSpans = useCallback(
    (next: Span[]) => {
      setSpansState(next)
      const nextStatus: PageStatus = status === "done" ? "done" : "in_progress"
      setStatusState(nextStatus)
      schedule({ spans: next, status: nextStatus })
    },
    [status, schedule],
  )

  const setStatus = useCallback(
    (next: PageStatus) => {
      setStatusState(next)
      schedule({ spans, status: next })
    },
    [spans, schedule],
  )

  // Timer beim Verlassen der Komponente aufräumen; steht noch eine Änderung
  // aus, jetzt sichern statt sie beim Schließen der Seite stillschweigend zu
  // verlieren.
  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      if (pendingRef.current) void flushRef.current()
    },
    [],
  )

  return {
    spans, status, saveState, conflict,
    isPending: query.isPending && pageId !== null,
    setSpans, setStatus, retry: flush,
  }
}
