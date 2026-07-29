import { useQuery } from "@tanstack/react-query"
import { Loader2, Square } from "lucide-react"
import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { stepStates } from "../overview/steps"
import { CatalogManager } from "./catalog-manager"
import { Console } from "./console"
import { JobForm, defaultValues } from "./job-form"
import { RunHistory } from "./run-history"
import { useRun } from "./use-run"

export function ControlPage() {
  const jobsQ = useQuery({ queryKey: ["jobs"], queryFn: api.jobs })
  const statusQ = useQuery({ queryKey: ["status"], queryFn: api.status })
  const evalQ = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation })
  const modelQ = useQuery({ queryKey: ["model"], queryFn: api.model })
  const run = useRun()

  // Ein Wertesatz je Schritt. Was hier nicht steht, kommt aus dem Katalog –
  // so überlebt eine Eingabe den Wechsel zwischen den Schritten.
  const [values, setValues] = useState<Record<string, Record<string, string>>>({})

  if (jobsQ.isPending) return <Skeleton className="h-96 w-full" />
  if (jobsQ.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Backend nicht erreichbar</AlertTitle>
        <AlertDescription>
          {jobsQ.error.message} — läuft <code>uvicorn magda.api:app --reload</code>?
        </AlertDescription>
      </Alert>
    )
  }

  const jobs = jobsQ.data
  const totals = statusQ.data?.totals
  const trained = (modelQ.data ?? []).filter((m) => m.trained).map((m) => m.variant)
  const states = totals ? stepStates(totals, evalQ.data ?? [], trained) : {}

  const valuesFor = (jobName: string) => {
    const job = jobs.find((j) => j.job === jobName)
    return values[jobName] ?? (job ? defaultValues(job) : {})
  }

  const setValue = (jobName: string, key: string, value: string) =>
    setValues((prev) => ({ ...prev, [jobName]: { ...valuesFor(jobName), [key]: value } }))

  const useCatalogUrl = (url: string) =>
    setValues((prev) => ({
      ...prev,
      "01_download_flyers": { ...valuesFor("01_download_flyers"), url },
    }))

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold tracking-tight">Steuerzentrale</h1>
        <p className="max-w-3xl text-muted-foreground">
          Jeder Schritt liest vom Vorgänger über die Platte. Parameter, laufender Job und
          vergangene Läufe stehen hier; die Übersicht zeigt nur den Stand.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div className="space-y-4">
          {jobs.map((job) => {
            const state = states[job.job]
            const isRunning = run.running && run.status?.job === job.job
            return (
              <section
                key={job.job}
                className={cn(
                  "space-y-3 rounded-lg border-2 border-foreground bg-card p-4 transition-colors",
                  isRunning && "bg-primary/10",
                )}
              >
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <h2 className="font-semibold">{job.title}</h2>
                  <code className="font-mono text-[11px] text-muted-foreground">
                    scripts/{job.job}.py
                  </code>
                  {state === "done" && (
                    <span className="font-mono text-[11px] text-[var(--riso-blue)]">
                      · erledigt
                    </span>
                  )}
                  {state === "blocked" && (
                    <span className="font-mono text-[11px] text-muted-foreground">
                      · Vorgänger fehlt
                    </span>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">{job.what}</p>

                {isRunning ? (
                  <Button variant="outline" size="sm" onClick={run.stop}>
                    <Square className="size-3.5" /> Stoppen
                  </Button>
                ) : (
                  <JobForm
                    job={job}
                    values={valuesFor(job.job)}
                    onChange={(key, value) => setValue(job.job, key, value)}
                    onStart={(v) => run.start(job.job, v)}
                    disabled={run.busy}
                  />
                )}
              </section>
            )
          })}

          <CatalogManager onUse={useCatalogUrl} />
        </div>

        <div className="space-y-6">
          <section className="space-y-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-lg font-bold tracking-tight">Live</h2>
              <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                {run.status?.job ?? "kein Lauf"}
                {run.status?.elapsed != null && ` · ${run.status.elapsed}s`}
                {run.running && <Loader2 className="ml-1 inline size-3 animate-spin" />}
              </p>
            </div>
            {run.startError && <p className="text-sm text-destructive">{run.startError}</p>}
            <Console lines={run.status?.lines ?? []} running={run.running} />
          </section>

          <RunHistory />
        </div>
      </div>
    </div>
  )
}
