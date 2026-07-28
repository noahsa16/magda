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

/** Reihenfolge über die *abgeschlossenen* Speicherungen: Jeder Flush bekommt
 * eine monoton steigende Nummer, pro Seite steht hier die höchste, deren
 * Antwort schon übernommen wurde. Eine Prüfung nur gegen noch offene
 * Änderungen reicht dafür grundsätzlich nicht - zwei PUTs derselben Seite
 * können in umgekehrter Reihenfolge antworten, und die verspätete ältere
 * fände nichts Offenes mehr vor.
 *
 * Bewusst außerhalb des Hooks: Der Unmount-Cleanup sichert noch, seine Antwort
 * trifft also erst ein, wenn längst eine neue Hook-Instanz läuft. An Refs
 * gebunden wäre die Ordnung genau in dem Fall verloren, für den sie existiert.
 * Der Zähler steigt global, deshalb bleibt jede spätere Speicherung auch über
 * Instanzgrenzen hinweg die jüngere. */
let saveSeq = 0
const appliedSeq = new Map<string, number>()

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
  // Zu welcher Seite der Hash gehört. Ohne das lässt sich "noch kein Hash
  // geladen" nicht von "Hash der vorigen Seite" unterscheiden - beides sieht
  // im Hash selbst gleich harmlos aus und führt zu einem falschen 409.
  const hashPageIdRef = useRef<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingRef = useRef<Pending | null>(null)
  // Seite, zu der der lokale Zustand gehört. Solange sie nicht die angezeigte
  // ist, sind spans/status die der Vorseite und dürfen nicht gerendert werden.
  const [loadedPageId, setLoadedPageId] = useState<string | null>(null)

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
    hashRef.current = query.data.words_hash
    hashPageIdRef.current = pageId
    setLoadedPageId(pageId)

    // Steht für diese Seite noch eine ungesicherte Änderung aus, ist sie neuer
    // als alles, was der Server sagen kann - etwa wenn ein Refetch nach dem
    // Speichern antwortet oder man zu einer Seite mit fehlgeschlagenem Save
    // zurückkehrt. Sie zurückholen statt sie überschreiben zu lassen.
    const pending = pendingRef.current
    if (pending && pending.pageId === pageId) {
      setSpansState(pending.spans)
      setStatusState(pending.status)
      return
    }

    setSpansState(query.data.spans)
    setStatusState(query.data.status)
    setSaveState("saved")
    // Der Server hat den gespeicherten Hash gegen die aktuelle Wortliste
    // geprüft. Ohne das wüssten wir es erst beim ersten Speicherversuch.
    setConflict(query.data.stale)
  }, [query.data, pageId])

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
    const seq = ++saveSeq
    // Ist zu dieser Seite bereits eine neuere Antwort verarbeitet worden? Dann
    // ist diese hier überholt und darf weder Cache noch Anzeige anfassen.
    const outdated = () => (appliedSeq.get(pending.pageId) ?? 0) > seq
    if (mountedRef.current && isCurrentPage()) setSaveState("saving")
    try {
      const saved = await api.saveGold(pending.pageId, {
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
      // Ein Refetch dieser Seite, der vor diesem Speichern losgelaufen ist,
      // trägt den Stand von davor und gewinnt bei React Query gegen unser
      // setQueryData, weil er später eintrifft. Abbrechen statt zusehen.
      await queryClient.cancelQueries({ queryKey: ["gold", pending.pageId], exact: true })
      // Den Cache dieser Seite mit dem Gespeicherten füllen. Ohne das bleibt
      // ["gold", pageId] für immer auf dem Stand der Erstladung: Wer die Seite
      // später wieder aufschlägt, sieht kurz eine leere Seite und verliert
      // seine Arbeit, sobald er in diesem Fenster ein Label setzt.
      // Übersprungen, wenn für dieselbe Seite etwas Neueres aussteht oder
      // bereits angekommen ist - dann ist diese Antwort schon veraltet.
      const superseded = pendingRef.current?.pageId === pending.pageId || outdated()
      if (!superseded) {
        appliedSeq.set(pending.pageId, seq)
        queryClient.setQueryData(["gold", pending.pageId], saved)
      }
      // Exaktes Match trifft nur die Übersichts-Query ["gold"], nicht
      // ["gold", pageId] der gerade offenen Seite - die wird oben gezielt
      // gesetzt. Ein Refetch stattdessen würde eine zwischen Flush-Ende und
      // Refetch-Antwort weiterlaufende Bearbeitung überschreiben.
      queryClient.invalidateQueries({ queryKey: ["gold"], exact: true })
      if (isLatest && mountedRef.current && isCurrentPage()) setSaveState("saved")
    } catch (err) {
      // Eine neuere Antwort derselben Seite ist bereits übernommen: Ihr Stand
      // liegt auf dem Server, dieser ältere Versuch ist bedeutungslos. Ohne
      // die Prüfung bliebe eine rote Fehlanzeige stehen, die der
      // Wiederholen-Knopf nicht mehr auflösen kann - pendingRef ist leer.
      if (outdated()) return
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
      // Ohne geladenen Hash *dieser* Seite gibt es nichts zu speichern: Beim
      // Erstladen ist er leer, direkt nach einem Seitenwechsel noch der der
      // vorigen Seite. Beides quittiert der Server mit einem 409, der wie ein
      // echter Konflikt aussieht und die Seite grundlos sperrt.
      if (hashPageIdRef.current !== pageId) return
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
    // Auch dann "lädt noch", wenn die Query bereits aus dem Cache antwortet,
    // der lokale Zustand aber noch der Vorseite gehört (die Übernahme läuft
    // erst im Effekt). Sonst rendert der Aufrufer einmal die Spans der einen
    // Seite über den Wörtern der anderen.
    isPending: pageId !== null && (query.isPending || loadedPageId !== pageId),
    setSpans, setStatus, retry: flush,
  }
}
