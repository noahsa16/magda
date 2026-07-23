import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Check, Loader2, Play, Square } from "lucide-react"
import { useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import type { EvalReport, ModelStatus, PipelineStatus } from "@/lib/types"
import { cn } from "@/lib/utils"
import { STEPS, doneVariants, stepProgress, stepStates } from "./steps"

function Console({ lines, running }: { lines: string[]; running: boolean }) {
  const endRef = useRef<HTMLDivElement>(null)

  // Immer die letzte Zeile zeigen – bei einem Lauf über tausende Seiten ist
  // das Ende die einzige interessante Stelle.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" })
  }, [lines.length])

  return (
    <div className="max-h-64 overflow-y-auto rounded-md bg-foreground p-4 font-mono text-xs leading-relaxed text-background">
      {lines.length === 0 && (
        <p className="text-background/50">
          {running ? "Warte auf Ausgabe…" : "Noch keine Ausgabe."}
        </p>
      )}
      {lines.map((line, i) => (
        <div key={i} className="whitespace-pre-wrap break-all">
          {line}
        </div>
      ))}
      {running && <span className="inline-block animate-pulse text-primary">▊</span>}
      <div ref={endRef} />
    </div>
  )
}

export function PipelineRunner({
  totals, reports, models,
}: { totals: PipelineStatus["totals"]; reports: EvalReport[]; models: ModelStatus[] }) {
  const qc = useQueryClient()

  // Solange etwas läuft, alle 1,5 s nachfragen; danach schlafen lassen.
  // refetchIntervalInBackground: ein Trainingslauf dauert Minuten, in denen
  // der Tab im Hintergrund liegt – ohne das Flag pausiert das Polling und die
  // Konsole steht still.
  const run = useQuery({
    queryKey: ["run"],
    queryFn: api.run,
    refetchInterval: (q) => (q.state.data?.running ? 1500 : false),
    refetchIntervalInBackground: true,
  })

  const start = useMutation({
    mutationFn: ({ job, variant }: { job: string; variant?: string }) =>
      api.startRun(job, variant),
    onSuccess: (data) => qc.setQueryData(["run"], data),
  })
  const stop = useMutation({
    mutationFn: api.stopRun,
    onSuccess: (data) => qc.setQueryData(["run"], data),
  })

  // Nach dem Lauf die Zähler neu laden – der Schritt hat Dateien geschrieben.
  const running = run.data?.running ?? false
  useEffect(() => {
    if (!running) {
      qc.invalidateQueries({ queryKey: ["status"] })
      qc.invalidateQueries({ queryKey: ["evaluation"] })
      qc.invalidateQueries({ queryKey: ["model"] })
    }
  }, [running, qc])

  const trainedVariants = models.filter((m) => m.trained).map((m) => m.variant)
  const states = stepStates(totals, reports, trainedVariants)
  const busy = running || start.isPending

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold tracking-tight">Pipeline</h2>
        <p className="text-sm text-muted-foreground">
          Jeder Schritt liest vom Vorgänger über die Platte und lässt sich hier starten.
        </p>
      </div>

      <ol className="divide-y-2 divide-foreground overflow-hidden rounded-lg border-2 border-foreground bg-card">
        {STEPS.map((step, i) => {
          const state = states[step.job]
          const isRunning = running && run.data?.job?.startsWith(step.job)
          const progress = stepProgress(step.job, totals)
          return (
            <li
              key={step.job}
              className={cn(
                "flex flex-wrap items-center gap-x-4 gap-y-3 p-4 transition-colors",
                isRunning && "bg-primary/10",
              )}
            >
              <span
                className={cn(
                  "flex size-10 shrink-0 items-center justify-center rounded-full border-2 font-mono text-sm font-bold",
                  state === "done" && "border-[var(--riso-blue)] bg-[var(--riso-blue)] text-white",
                  state === "ready" && "border-foreground",
                  state === "blocked" && "border-border text-muted-foreground",
                  isRunning && "border-primary bg-primary text-primary-foreground",
                )}
              >
                {isRunning ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : state === "done" ? (
                  <Check className="size-5" />
                ) : (
                  `0${i + 1}`
                )}
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <h3 className="font-semibold">{step.title}</h3>
                  <code className="font-mono text-[11px] text-muted-foreground">
                    scripts/{step.job}.py
                  </code>
                  {progress && (
                    <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                      · {progress}
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-sm text-muted-foreground">{step.what}</p>
              </div>

              <div className="flex shrink-0 gap-2">
                {isRunning ? (
                  <Button variant="outline" size="sm" onClick={() => stop.mutate()}>
                    <Square className="size-3.5" /> Stoppen
                  </Button>
                ) : step.variants.length > 0 ? (
                  step.variants.map((v) => {
                    const done = doneVariants(step.job, reports, trainedVariants).has(v)
                    return (
                      <Button
                        key={v}
                        variant="outline"
                        size="sm"
                        disabled={busy || state === "blocked"}
                        onClick={() => start.mutate({ job: step.job, variant: v })}
                        title={done ? `${v} liegt vor – erneut laufen lassen` : `${v} starten`}
                      >
                        {done ? (
                          <Check className="size-3.5 text-[var(--riso-blue)]" />
                        ) : (
                          <Play className="size-3.5" />
                        )}
                        {v}
                      </Button>
                    )
                  })
                ) : (
                  <Button
                    variant={state === "ready" ? "default" : "outline"}
                    size="sm"
                    disabled={busy || state === "blocked"}
                    onClick={() => start.mutate({ job: step.job })}
                  >
                    <Play className="size-3.5" /> Starten
                  </Button>
                )}
              </div>
            </li>
          )
        })}
      </ol>

      {start.isError && (
        <p className="text-sm text-destructive">{start.error.message}</p>
      )}

      {run.data && (run.data.lines.length > 0 || running) && (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              {run.data.job ?? "Ausgabe"}
              {run.data.elapsed != null && ` · ${run.data.elapsed}s`}
              {!running && run.data.exit_code != null && (
                <span className={run.data.exit_code === 0 ? "text-[var(--riso-blue)]" : "text-destructive"}>
                  {" "}· {run.data.exit_code === 0 ? "fertig" : `Abbruch (${run.data.exit_code})`}
                </span>
              )}
            </p>
          </div>
          <Console lines={run.data.lines} running={running} />
        </div>
      )}
    </section>
  )
}
