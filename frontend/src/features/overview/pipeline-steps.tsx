import { Check } from "lucide-react"
import { Fragment } from "react"
import { cn } from "@/lib/utils"

export interface PipelineStep {
  title: string
  done: boolean
}

/**
 * Horizontaler Stepper über die fünf Pipeline-Schritte. Die Nummerierung ist
 * hier keine Deko: die Schritte 01–05 entsprechen exakt den Skripten in
 * scripts/ und laufen zwingend in dieser Reihenfolge.
 */
export function PipelineSteps({ steps }: { steps: PipelineStep[] }) {
  const current = steps.findIndex((s) => !s.done)
  return (
    <ol className="flex items-start overflow-x-auto rounded-xl border bg-card px-4 py-4 shadow-sm">
      {steps.map((step, i) => (
        <Fragment key={step.title}>
          {i > 0 && (
            <div
              aria-hidden
              className={cn("mt-4 h-px min-w-6 flex-1", steps[i - 1].done ? "bg-primary/40" : "bg-border")}
            />
          )}
          <li className="flex shrink-0 flex-col items-center gap-1.5 px-2">
            <span
              className={cn(
                "flex size-8 items-center justify-center rounded-full border font-mono text-xs transition-colors",
                step.done && "border-primary bg-primary text-primary-foreground",
                !step.done && i === current && "border-primary text-primary ring-4 ring-primary/15",
                !step.done && i !== current && "border-border text-muted-foreground",
              )}
            >
              {step.done ? <Check className="size-4" /> : `0${i + 1}`}
            </span>
            <span
              className={cn(
                "text-xs",
                i === current ? "font-medium text-foreground" : "text-muted-foreground",
              )}
            >
              {step.title}
            </span>
          </li>
        </Fragment>
      ))}
    </ol>
  )
}
