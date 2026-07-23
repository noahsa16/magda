import { Link } from "react-router-dom"
import type { ModelStatus } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Verlauf der Dev-F1 über die Epochen als Miniaturkurve. */
function Sparkline({ history }: { history: ModelStatus["history"] }) {
  if (history.length < 2) return null
  const values = history.map((h) => h.f1)
  const max = Math.max(...values, 0.01)
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * 100},${28 - (v / max) * 26}`)
    .join(" ")
  return (
    <svg viewBox="0 0 100 28" preserveAspectRatio="none" className="mt-3 h-10 w-full border-b border-border">
      <polyline
        points={points}
        fill="none"
        stroke="var(--riso-blue)"
        strokeWidth={2}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

export function ModelStatusCard({
  status, active = false,
}: { status: ModelStatus | undefined; active?: boolean }) {
  if (!status) return null

  const progress =
    status.steps && status.max_steps ? Math.round((status.steps / status.max_steps) * 100) : null

  return (
    <div
      className={cn(
        "rounded-lg border-2 bg-card p-4",
        active ? "plate-pink border-foreground" : "border-border",
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
          {status.variant}
          {active && <span className="text-primary"> · rechnet hier</span>}
        </p>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest",
            status.trained
              ? "bg-[var(--riso-blue)] text-white"
              : "border border-border text-muted-foreground",
          )}
        >
          {status.trained ? "einsatzbereit" : "nicht trainiert"}
        </span>
      </div>

      {!status.trained && (
        <p className="mt-2 text-sm text-muted-foreground">
          Für die Extraktion braucht es einen Checkpoint unter{" "}
          <code className="font-mono text-xs">checkpoints/{status.variant}/best</code>. Das Training
          startest du auf der <Link to="/" className="underline underline-offset-2">Übersicht</Link>.
        </p>
      )}

      {status.trained && (
        <>
          <div className="mt-3 grid grid-cols-3 gap-3">
            <div>
              <p className="text-2xl font-extrabold tabular-nums">
                {status.best_f1 != null ? status.best_f1.toFixed(3) : "–"}
              </p>
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                bestes Dev-F1
              </p>
            </div>
            <div>
              <p className="text-2xl font-extrabold tabular-nums">
                {status.epoch != null ? status.epoch.toFixed(0) : "–"}
              </p>
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                Epochen
              </p>
            </div>
            <div>
              <p className="text-2xl font-extrabold tabular-nums">{status.steps ?? "–"}</p>
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                Schritte{progress != null && ` · ${progress}%`}
              </p>
            </div>
          </div>
          <Sparkline history={status.history} />
          <p className="mt-2 text-[11px] text-muted-foreground">
            Dev-F1 über {status.history.length} Auswertungen. Die belastbare Zahl steht in der{" "}
            <Link to="/evaluation" className="underline underline-offset-2">Evaluation</Link> –
            sie misst auf dem Test-Split.
          </p>
        </>
      )}
    </div>
  )
}
