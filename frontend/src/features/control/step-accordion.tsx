import { Check, Circle, Loader2, Lock, Square } from "lucide-react"
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import type { JobDef } from "@/lib/types"
import { cn } from "@/lib/utils"
import type { StepState } from "../overview/steps"
import { JobForm } from "./job-form"

interface StepAccordionProps {
  jobs: JobDef[]
  states: Record<string, StepState>
  open: string | undefined
  onOpenChange: (value: string) => void
  runningJob: string | null
  valuesFor: (job: string) => Record<string, string>
  onChange: (job: string, key: string, value: string) => void
  onStart: (job: string, values: Record<string, string>) => void
  onStop: () => void
  busy: boolean
  progress: (job: string) => string | null
}

/** Zustandspunkt links – die einzige Stelle, an der Farbe etwas bedeutet. */
function StateDot({ state, running }: { state: StepState | undefined; running: boolean }) {
  if (running) return <Loader2 className="size-4 animate-spin text-primary" />
  if (state === "done") return <Check className="size-4 text-[var(--riso-blue)]" />
  if (state === "blocked") return <Lock className="size-4 text-muted-foreground/50" />
  return <Circle className="size-4 text-foreground" />
}

/**
 * Ein Schritt je Zeile, aufgeklappt nur der, an dem man gerade arbeitet.
 *
 * Vorher standen alle acht Schritte gleichzeitig mit ihren Formularen
 * untereinander – rund zwei Bildschirmhöhen, in denen nichts hervorstach.
 * Eine Pipeline hat aber immer genau einen nächsten Schritt; den zeigt die
 * Seite offen, der Rest bleibt eine Zeile mit Zustand und Fortschritt.
 */
export function StepAccordion({
  jobs, states, open, onOpenChange, runningJob, valuesFor,
  onChange, onStart, onStop, busy, progress,
}: StepAccordionProps) {
  return (
    <Accordion
      type="single"
      collapsible
      value={open}
      onValueChange={onOpenChange}
      className="overflow-hidden rounded-xl border-2 border-foreground bg-card"
    >
      {jobs.map((job, index) => {
        const state = states[job.job]
        const running = runningJob === job.job
        const progressText = progress(job.job)
        return (
          <AccordionItem
            key={job.job}
            value={job.job}
            className={cn(
              "border-b border-border last:border-b-0",
              running && "bg-primary/5",
            )}
          >
            <AccordionTrigger className="gap-3 px-4 py-3 hover:no-underline">
              <div className="flex min-w-0 flex-1 items-center gap-3 text-left">
                <span className="flex size-7 shrink-0 items-center justify-center">
                  <StateDot state={state} running={running} />
                </span>
                <span className="w-6 shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">
                  {String(index).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1">
                  <span className={cn("font-semibold", state === "blocked" && "text-muted-foreground")}>
                    {job.title}
                  </span>
                  {progressText && (
                    <span className="ml-2 font-mono text-[11px] text-muted-foreground tabular-nums">
                      {progressText}
                    </span>
                  )}
                </span>
                {running && (
                  <span className="shrink-0 font-mono text-[11px] uppercase tracking-widest text-primary">
                    läuft
                  </span>
                )}
              </div>
            </AccordionTrigger>

            <AccordionContent className="space-y-3 px-4 pb-4">
              <p className="max-w-2xl text-sm text-muted-foreground">{job.what}</p>
              {running ? (
                <Button variant="outline" size="sm" onClick={onStop}>
                  <Square className="size-3.5" /> Stoppen
                </Button>
              ) : (
                <JobForm
                  job={job}
                  values={valuesFor(job.job)}
                  onChange={(key, value) => onChange(job.job, key, value)}
                  onStart={(values) => onStart(job.job, values)}
                  disabled={busy}
                />
              )}
              <p className="font-mono text-[11px] text-muted-foreground">scripts/{job.job}.py</p>
            </AccordionContent>
          </AccordionItem>
        )
      })}
    </Accordion>
  )
}
