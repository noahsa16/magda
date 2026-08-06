import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import type { Groups } from "./grouping-editor"

export type SaveState = "saved" | "saving" | "error"
export type PageStatus = "untouched" | "in_progress" | "done"

interface Pending {
  pageId: string
  hash: string
  groups: Groups
  status: PageStatus
}

/** Pro Seite eine Speicherkette, aus demselben Grund wie in `use-annotation.ts`:
 * Zwei gleichzeitige PUTs derselben Seite erreichen den Server in beliebiger
 * Reihenfolge, und `os.replace` macht den *letzten* zum Gewinner – der ältere
 * Stand überschreibt still den neueren. Ein Lock im Backend hilft nicht; die
 * Reihenfolge kennt nur der Client.
 *
 * Eigene Map statt der aus `use-annotation.ts`: Das sind verschiedene Dateien
 * (`gold/` gegen `gold/offers/`), die sich nicht gegenseitig ausbremsen
 * müssen. Wer beide Werkzeuge auf derselben Seite offen hat, schreibt in zwei
 * getrennte Dateien.
 */
const chains = new Map<string, Promise<void>>()

/** Gruppierung einer Seite: laden, im Speicher halten, verzögert sichern.
 *
 * Bewusst schlanker als `useAnnotation`: Diese Referenz entsteht in einem
 * Zug je Seite, nicht über Wochen verteilt. Die Invarianten, die dort teuer
 * erkauft wurden, bleiben aber gleich – der ausstehende Stand trägt seine
 * Seite selbst mit, damit ein Seitenwechsel kurz vor dem Timer nicht die
 * Gruppen der einen Seite unter der ID der anderen speichert.
 */
export function useOfferGrouping(pageId: string | null, annotator: string) {
  const queryClient = useQueryClient()
  const [groups, setGroupsState] = useState<Groups>([])
  const [status, setStatusState] = useState<PageStatus>("untouched")
  const [saveState, setSaveState] = useState<SaveState>("saved")
  const [conflict, setConflict] = useState(false)

  const hashRef = useRef("")
  const hashPageIdRef = useRef<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingRef = useRef<Pending | null>(null)
  const [loadedPageId, setLoadedPageId] = useState<string | null>(null)

  const pageIdRef = useRef(pageId)
  pageIdRef.current = pageId

  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  const query = useQuery({
    queryKey: ["offer-gold", pageId],
    queryFn: () => api.offerGoldPage(pageId!),
    enabled: pageId !== null,
  })

  useEffect(() => {
    if (!query.data) return
    hashRef.current = query.data.words_hash
    hashPageIdRef.current = pageId
    setLoadedPageId(pageId)

    // Ein ungesicherter Stand dieser Seite ist neuer als alles, was der Server
    // sagen kann – zurückholen statt überschreiben lassen.
    const pending = pendingRef.current
    if (pending && pending.pageId === pageId) {
      setGroupsState(pending.groups)
      setStatusState(pending.status)
      return
    }

    setGroupsState(query.data.groups)
    setStatusState(query.data.status)
    setSaveState("saved")
    setConflict(query.data.stale)
  }, [query.data, pageId])

  const save = useCallback(
    async (pending: Pending) => {
      const isCurrentPage = () => pending.pageId === pageIdRef.current
      if (mountedRef.current && isCurrentPage()) setSaveState("saving")
      try {
        const saved = await api.saveOfferGold(pending.pageId, {
          words_hash: pending.hash,
          status: pending.status === "done" ? "done" : "in_progress",
          annotator,
          groups: pending.groups,
        })
        const isLatest = pendingRef.current === pending
        if (isLatest) pendingRef.current = null
        await queryClient.cancelQueries({ queryKey: ["offer-gold", pending.pageId], exact: true })
        if (pendingRef.current?.pageId !== pending.pageId) {
          queryClient.setQueryData(["offer-gold", pending.pageId], saved)
        }
        queryClient.invalidateQueries({ queryKey: ["offer-gold"], exact: true })
        if (isLatest && mountedRef.current && isCurrentPage()) setSaveState("saved")
      } catch (err) {
        if (mountedRef.current && isCurrentPage()) {
          if (err instanceof Error && err.message.includes("Wortliste")) setConflict(true)
          setSaveState("error")
        }
      }
    },
    [annotator, queryClient],
  )

  const flush = useCallback(() => {
    const pending = pendingRef.current
    if (!pending) return Promise.resolve()
    const key = pending.pageId
    const run = (chains.get(key) ?? Promise.resolve())
      .then(() => save(pending))
      .catch(() => {})
      .finally(() => {
        if (chains.get(key) === run) chains.delete(key)
      })
    chains.set(key, run)
    return run
  }, [save])

  const flushRef = useRef(flush)
  useEffect(() => {
    flushRef.current = flush
  }, [flush])

  const schedule = useCallback(
    (next: { groups: Groups; status: PageStatus }) => {
      if (!pageId) return
      // Ohne den Hash *dieser* Seite quittiert der Server mit einem 409, der
      // wie ein echter Konflikt aussieht und die Seite grundlos sperrt.
      if (hashPageIdRef.current !== pageId) return
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

  const setGroups = useCallback(
    (next: Groups) => {
      setGroupsState(next)
      const nextStatus: PageStatus = status === "done" ? "done" : "in_progress"
      setStatusState(nextStatus)
      schedule({ groups: next, status: nextStatus })
    },
    [status, schedule],
  )

  const setStatus = useCallback(
    (next: PageStatus) => {
      setStatusState(next)
      schedule({ groups, status: next })
    },
    [groups, schedule],
  )

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      if (pendingRef.current) void flushRef.current()
    },
    [],
  )

  return {
    groups, status, saveState, conflict,
    isPending: pageId !== null && (query.isPending || loadedPageId !== pageId),
    setGroups, setStatus, retry: flush,
  }
}
