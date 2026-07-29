import { Check } from "lucide-react"
import { Link } from "react-router-dom"
import type { PipelineStatus } from "@/lib/types"
import { cn } from "@/lib/utils"
import { STEPS, type StepState, stepProgress } from "./steps"

/**
 * Die Pipeline als Zustandsbild – ohne Knöpfe. Ausgeführt wird in der
 * Steuerzentrale; hier steht nur, wie weit die Daten sind.
 *
 * Die Ziffer im Kreis ist die Position in der Liste, nicht die Dateinummer:
 * Schritt 06 ist noch frei, der Flair-Arm heißt 07. Maßgeblich ist der
 * Skriptname darunter.
 */
export function PipelineDiagram({
  states,
  totals,
}: {
  states: Record<string, StepState>
  totals: PipelineStatus["totals"]
}) {
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold tracking-tight">Pipeline</h2>
        <Link
          to="/control"
          className="font-mono text-[11px] uppercase tracking-widest text-primary underline-offset-4 hover:underline"
        >
          In der Steuerzentrale ausführen →
        </Link>
      </div>

      <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {STEPS.map((step, i) => {
          const state = states[step.job] ?? "blocked"
          const progress = stepProgress(step.job, totals)
          return (
            <li
              key={step.job}
              className={cn(
                "flex items-start gap-3 rounded-lg border-2 p-3",
                state === "done" && "border-[var(--riso-blue)] bg-card",
                state === "ready" && "border-foreground bg-card",
                state === "blocked" && "border-border text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "flex size-8 shrink-0 items-center justify-center rounded-full border-2 font-mono text-xs font-bold",
                  state === "done" && "border-[var(--riso-blue)] bg-[var(--riso-blue)] text-white",
                  state === "ready" && "border-foreground",
                  state === "blocked" && "border-border",
                )}
              >
                {state === "done" ? <Check className="size-4" /> : `0${i + 1}`}
              </span>
              <div className="min-w-0">
                <h3 className="text-sm font-semibold">{step.title}</h3>
                <code className="block font-mono text-[11px] text-muted-foreground">
                  scripts/{step.job}.py
                </code>
                {progress && (
                  <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                    {progress}
                  </span>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
