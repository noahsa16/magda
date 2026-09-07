import { ArrowRight, ClipboardList } from "lucide-react"
import { useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import type { AnnotationTask } from "@/lib/types"

interface TaskRow {
  page_id: string
  status: string
  source?: string
  stale: boolean
}

interface TaskBannerProps {
  task: AnnotationTask
  /** Gold-Zeilen des jeweiligen Werkzeugs (Spans oder Angebote). */
  rows: TaskRow[]
  /** "Spans" im Annotator, "Angebote" im Gruppierer. */
  unit: string
  onOpen: (pageId: string) => void
}

/** Fortschritt der abgesprochenen Aufgabe, in der Reihenfolge der Aufgabe.
 *
 * Eigene Rechnung statt `groupGoldByCatalog`: die Aufgabe geht quer über
 * Kataloge, und die Kachelzählung kennt die Seitenliste nicht. Veraltete
 * Seiten zählen wie überall nicht als fertig. */
export function taskProgress(task: AnnotationTask, rows: TaskRow[]) {
  const byId = new Map(rows.map((r) => [r.page_id, r]))
  const isDone = (id: string) => {
    const row = byId.get(id)
    return row?.status === "done" && !row.stale && (!row.source || row.source === "gold")
  }
  const done = task.pages.filter(isDone).length
  const next = task.pages.find((id) => !isDone(id)) ?? null
  return { done, next }
}

export function TaskBanner({ task, rows, unit, onOpen }: TaskBannerProps) {
  const { done, next } = useMemo(() => taskProgress(task, rows), [task, rows])
  if (task.pages.length === 0) return null
  const total = task.pages.length
  const catalogs = [...new Set(task.pages.map((p) => p.split("_p")[0]))]

  return (
    <section
      aria-label="Annotationsaufgabe"
      className="plate space-y-3 rounded-xl border-2 border-[var(--riso-blue)] bg-card p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-[var(--riso-blue)]">
            <ClipboardList className="size-3.5" />
            Aufgabe{task.for.length > 0 && ` für ${task.for.join(" und ")}`}
          </p>
          <h2 className="text-lg font-bold tracking-tight">{task.title}</h2>
          <p className="max-w-3xl text-sm text-muted-foreground">{task.why}</p>
          <p className="font-mono text-[11px] text-muted-foreground">
            {total} Seiten · Katalog {catalogs.join(", ")}
            {task.created && ` · abgesprochen ${task.created}`}
          </p>
        </div>
        {next && (
          <Button size="sm" onClick={() => onOpen(next)}>
            Nächste offene Seite
            <ArrowRight className="size-4" />
          </Button>
        )}
      </div>
      <div className="flex items-center gap-3">
        <Progress value={(done / total) * 100} />
        <span className="shrink-0 font-mono text-[11px] tabular-nums">
          {done}/{total} {unit} fertig
        </span>
      </div>
    </section>
  )
}
