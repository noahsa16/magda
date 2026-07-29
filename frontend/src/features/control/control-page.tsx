import { useQuery } from "@tanstack/react-query"
import { ChevronDown, Loader2 } from "lucide-react"
import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { stepProgress, stepStates } from "../overview/steps"
import { CatalogManager } from "./catalog-manager"
import { Console } from "./console"
import { defaultValues } from "./job-form"
import { RunHistory } from "./run-history"
import { StepAccordion } from "./step-accordion"
import { useRun } from "./use-run"

export function ControlPage() {
  const jobsQ = useQuery({ queryKey: ["jobs"], queryFn: api.jobs })
  const statusQ = useQuery({ queryKey: ["status"], queryFn: api.status })
  const evalQ = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation })
  const modelQ = useQuery({ queryKey: ["model"], queryFn: api.model })
  const run = useRun()

  const [values, setValues] = useState<Record<string, Record<string, string>>>({})
  const [open, setOpen] = useState<string | undefined>(undefined)
  const [catalogsOpen, setCatalogsOpen] = useState(false)

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

  // Aufgeklappt ist standardmäßig der Schritt, der als Nächstes dran ist.
  const next = jobs.find((j) => states[j.job] === "ready")?.job
  const active = open ?? run.status?.job ?? next

  const done = jobs.filter((j) => states[j.job] === "done").length

  const valuesFor = (jobName: string) => {
    const job = jobs.find((j) => j.job === jobName)
    return values[jobName] ?? (job ? defaultValues(job) : {})
  }
  const setValue = (jobName: string, key: string, value: string) =>
    setValues((prev) => ({ ...prev, [jobName]: { ...valuesFor(jobName), [key]: value } }))

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">Pipeline</h1>
            <p className="text-sm text-muted-foreground">
              Jeder Schritt liest vom Vorgänger über die Platte.
            </p>
          </div>
          <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground tabular-nums">
            {done} / {jobs.length} erledigt
          </p>
        </div>
        <Progress value={(done / jobs.length) * 100} />
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-4">
          <StepAccordion
            jobs={jobs}
            states={states}
            open={active}
            onOpenChange={setOpen}
            runningJob={run.status?.job ?? null}
            valuesFor={valuesFor}
            onChange={setValue}
            onStart={(job, v) => run.start(job, v)}
            onStop={run.stop}
            busy={run.busy}
            progress={(job) => (totals ? stepProgress(job, totals) : null)}
          />

          {run.startError && (
            <Alert variant="destructive">
              <AlertTitle>Start abgelehnt</AlertTitle>
              <AlertDescription>{run.startError}</AlertDescription>
            </Alert>
          )}

          <Collapsible open={catalogsOpen} onOpenChange={setCatalogsOpen}>
            <CollapsibleTrigger className="flex w-full items-center justify-between rounded-xl border-2 border-foreground bg-card px-4 py-3 text-left">
              <span className="font-semibold">Kataloge verwalten</span>
              <ChevronDown
                className={cn("size-4 transition-transform", catalogsOpen && "rotate-180")}
              />
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-4">
              <CatalogManager
                onUse={(url) =>
                  setValues((prev) => ({
                    ...prev,
                    "01_download_flyers": { ...valuesFor("01_download_flyers"), url },
                  }))
                }
              />
            </CollapsibleContent>
          </Collapsible>
        </div>

        {/* Live und Historie teilen sich eine Spalte: man schaut entweder dem
            laufenden Schritt zu oder untersucht einen vergangenen, nie beides. */}
        <Tabs defaultValue="live" className="lg:sticky lg:top-24 lg:self-start">
          <div className="flex items-center justify-between gap-2">
            <TabsList>
              <TabsTrigger value="live">
                Live
                {run.running && <Loader2 className="ml-1.5 size-3 animate-spin" />}
              </TabsTrigger>
              <TabsTrigger value="history">Läufe</TabsTrigger>
            </TabsList>
            {run.status?.elapsed != null && run.running && (
              <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                {run.status.elapsed}s
              </span>
            )}
          </div>
          <TabsContent value="live" className="mt-3">
            <Console lines={run.status?.lines ?? []} running={run.running} />
          </TabsContent>
          <TabsContent value="history" className="mt-3">
            <RunHistory />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
