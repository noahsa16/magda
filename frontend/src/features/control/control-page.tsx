import { useQuery } from "@tanstack/react-query"
import { Loader2, Square, X } from "lucide-react"
import { useState } from "react"
import { Crumbs } from "@/components/crumbs"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import { stepProgress, stepStates } from "../overview/steps"
import { AppGrid, PIPELINE, WERKZEUGE, type AppItem } from "./app-grid"
import { Console } from "./console"
import { defaultValues, JobForm } from "./job-form"
import { RunHistory } from "./run-history"
import { useRun } from "./use-run"

export function ControlPage() {
  const jobsQ = useQuery({ queryKey: ["jobs"], queryFn: api.jobs })
  const statusQ = useQuery({ queryKey: ["status"], queryFn: api.status })
  const evalQ = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation })
  const modelQ = useQuery({ queryKey: ["model"], queryFn: api.model })
  const run = useRun()

  const [values, setValues] = useState<Record<string, Record<string, string>>>({})
  const [open, setOpen] = useState<string | null>(null)

  if (jobsQ.isPending) return <Skeleton className="h-96 w-full" />
  if (jobsQ.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Backend nicht erreichbar</AlertTitle>
        <AlertDescription>
          {jobsQ.error.message} — läuft <code>magda serve</code>?
        </AlertDescription>
      </Alert>
    )
  }

  const jobs = jobsQ.data
  const totals = statusQ.data?.totals
  const trained = (modelQ.data ?? []).filter((m) => m.trained).map((m) => m.variant)
  const states = totals ? stepStates(totals, evalQ.data ?? [], trained) : {}

  // Ein laufender Schritt zieht die Ansicht zu sich: man will sehen, was
  // gerade passiert, nicht das Raster.
  const aktiv = run.status?.job ?? open
  const offenerJob = jobs.find((j) => j.job === aktiv)

  const done = PIPELINE.filter((j) => states[j] === "done").length

  const valuesFor = (jobName: string) => {
    const job = jobs.find((j) => j.job === jobName)
    return values[jobName] ?? (job ? defaultValues(job) : {})
  }
  const setValue = (jobName: string, key: string, value: string) =>
    setValues((prev) => ({ ...prev, [jobName]: { ...valuesFor(jobName), [key]: value } }))

  const zuApp = (job: string): AppItem | null => {
    const def = jobs.find((j) => j.job === job)
    if (!def) return null
    return {
      job,
      title: def.title,
      state: states[job],
      running: run.status?.job === job && run.running,
      progress: totals ? stepProgress(job, totals) : null,
    }
  }
  const apps = (namen: string[]) => namen.map(zuApp).filter((a): a is AppItem => a !== null)

  // Schritte, die weder Pipeline noch bekanntes Werkzeug sind – ein neuer
  // Eintrag in jobs.py soll nicht stillschweigend unsichtbar bleiben.
  const bekannt = new Set([...PIPELINE, ...WERKZEUGE])
  const uebrige = jobs.filter((j) => !bekannt.has(j.job)).map((j) => j.job)

  return (
    <div className="flex min-w-0 flex-col gap-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
          <div className="flex flex-wrap items-baseline gap-3">
            <h1 className="text-3xl font-extrabold tracking-tight">Pipeline</h1>
            <Crumbs
              items={
                offenerJob
                  ? [{ label: "Alle Schritte", onClick: () => setOpen(null) }, { label: offenerJob.title }]
                  : [{ label: "Alle Schritte" }]
              }
            />
          </div>
          <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground tabular-nums">
            {done} / {PIPELINE.length} erledigt
          </p>
        </div>
        <Progress value={(done / PIPELINE.length) * 100} />
      </header>

      {offenerJob ? (
        <Fenster
          job={offenerJob}
          state={states[offenerJob.job]}
          run={run}
          values={valuesFor(offenerJob.job)}
          onChange={(key, value) => setValue(offenerJob.job, key, value)}
          onClose={() => setOpen(null)}
        />
      ) : (
        <>
          <section className="space-y-3">
            <AppGrid items={apps([...PIPELINE, ...uebrige])} onOpen={setOpen} />
          </section>

          <section className="space-y-2">
            <h2 className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
              Auswertung
            </h2>
            <AppGrid items={apps(WERKZEUGE)} onOpen={setOpen} klein />
          </section>
        </>
      )}

      {run.startError && (
        <Alert variant="destructive">
          <AlertTitle>Start abgelehnt</AlertTitle>
          <AlertDescription>{run.startError}</AlertDescription>
        </Alert>
      )}
    </div>
  )
}

/** Der geöffnete Schritt: links das Formular, rechts die Ausgabe. */
function Fenster({
  job, state, run, values, onChange, onClose,
}: {
  job: { job: string; title: string; what: string; params: unknown[] }
  state: string | undefined
  run: ReturnType<typeof useRun>
  values: Record<string, string>
  onChange: (key: string, value: string) => void
  onClose: () => void
}) {
  const running = run.status?.job === job.job && run.running
  const jobDef = job as Parameters<typeof JobForm>[0]["job"]

  return (
    <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(26rem,32rem)]">
      <div className="min-w-0 overflow-hidden rounded-xl border-2 border-foreground bg-card">
        <div className="flex items-center justify-between gap-3 border-b-2 border-foreground px-4 py-2.5">
          <span className="font-mono text-[11px] text-muted-foreground">
            $ magda {job.job}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Schließen"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="space-y-4 p-4">
          <p className="max-w-3xl text-sm text-muted-foreground">{job.what}</p>
          {state === "blocked" && !running && (
            <p className="text-sm text-muted-foreground">
              Der vorherige Schritt fehlt noch — startbar ist er trotzdem.
            </p>
          )}
          {running ? (
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={run.stop}>
                <Square className="size-3.5" /> Stoppen
              </Button>
              {run.status?.elapsed != null && (
                <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                  {run.status.elapsed}s
                </span>
              )}
            </div>
          ) : (
            <JobForm
              job={jobDef}
              values={values}
              onChange={onChange}
              onStart={(v) => run.start(job.job, v)}
              disabled={run.busy}
            />
          )}
        </div>
      </div>

      {/* Live und Historie teilen sich eine Spalte: man schaut entweder dem
          laufenden Schritt zu oder untersucht einen vergangenen, nie beides. */}
      <Tabs defaultValue="live" className="min-w-0 xl:sticky xl:top-24 xl:self-start">
        <TabsList>
          <TabsTrigger value="live">
            Live
            {running && <Loader2 className="ml-1.5 size-3 animate-spin" />}
          </TabsTrigger>
          <TabsTrigger value="history">Läufe</TabsTrigger>
        </TabsList>
        <TabsContent value="live" className="mt-3">
          <Console lines={run.status?.lines ?? []} running={run.running} />
        </TabsContent>
        <TabsContent value="history" className="mt-3">
          <RunHistory />
        </TabsContent>
      </Tabs>
    </div>
  )
}
