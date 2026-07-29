import { Check } from "lucide-react"
import { Link } from "react-router-dom"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { PipelineStatus } from "@/lib/types"
import { cn } from "@/lib/utils"
import { STEPS, type StepState, stepProgress } from "./steps"

/**
 * Die Pipeline als schmaler Fortschrittsstreifen – ohne Knöpfe.
 *
 * Vorher waren das sieben große Kacheln, die eine halbe Bildschirmhöhe
 * einnahmen, um eine Zahl je Schritt zu zeigen. Der Streifen sagt dasselbe in
 * einer Zeile; Einzelheiten hängen im Tooltip, ausgeführt wird auf der
 * Pipeline-Seite.
 */
export function PipelineDiagram({
  states,
  totals,
}: {
  states: Record<string, StepState>
  totals: PipelineStatus["totals"]
}) {
  const erledigt = STEPS.filter((s) => states[s.job] === "done").length

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-bold tracking-tight">
          Pipeline
          <span className="ml-2 font-mono text-[11px] font-normal text-muted-foreground tabular-nums">
            {erledigt}/{STEPS.length}
          </span>
        </h2>
        <Link
          to="/pipeline"
          className="font-mono text-[11px] uppercase tracking-widest text-primary underline-offset-4 hover:underline"
        >
          Ausführen →
        </Link>
      </div>

      <ol className="flex flex-wrap items-stretch gap-1.5">
        {STEPS.map((step, i) => {
          const state = states[step.job] ?? "blocked"
          const fortschritt = stepProgress(step.job, totals)
          return (
            <li key={step.job} className="min-w-0 flex-1 basis-28">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link
                    to="/pipeline"
                    className={cn(
                      "flex h-full flex-col gap-1 rounded-lg border-2 px-2.5 py-2 transition-colors",
                      state === "done" &&
                        "border-[var(--riso-blue)] bg-[var(--riso-blue)]/10 hover:bg-[var(--riso-blue)]/20",
                      state === "ready" && "border-foreground bg-card hover:bg-accent",
                      state === "blocked" && "border-border text-muted-foreground",
                    )}
                  >
                    <span className="flex items-center gap-1.5">
                      <span className="font-mono text-[10px] tabular-nums">
                        {String(i).padStart(2, "0")}
                      </span>
                      {state === "done" && (
                        <Check className="size-3 text-[var(--riso-blue)]" />
                      )}
                    </span>
                    <span className="truncate text-xs font-semibold">{step.title}</span>
                    <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
                      {fortschritt ?? " "}
                    </span>
                  </Link>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  <p className="font-mono text-[11px]">scripts/{step.job}.py</p>
                  <p>{step.what}</p>
                </TooltipContent>
              </Tooltip>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
