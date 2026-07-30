import { useQuery } from "@tanstack/react-query"
import { Check, X } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

/** Ein abgebrochener Lauf hat gar keinen Exit-Code – das ist kein Erfolg. */
function outcome(exitCode: number | null): { ok: boolean; text: string } {
  if (exitCode === 0) return { ok: true, text: "fertig" }
  if (exitCode == null) return { ok: false, text: "abgebrochen" }
  return { ok: false, text: `Abbruch (${exitCode})` }
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "–"
  if (seconds < 60) return `${seconds.toFixed(0)}s`
  return `${Math.floor(seconds / 60)}m ${String(Math.round(seconds % 60)).padStart(2, "0")}s`
}

export function RunHistory() {
  const [openId, setOpenId] = useState<string | null>(null)
  const { data } = useQuery({ queryKey: ["runs"], queryFn: api.runs })
  // Der Log wird erst beim Aufklappen geholt – ein Trainingslauf hat
  // zehntausende Zeilen, die niemand ungefragt übertragen will.
  const detail = useQuery({
    queryKey: ["runDetail", openId],
    queryFn: () => api.runDetail(openId as string),
    enabled: openId != null,
  })

  const runs = data ?? []

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold tracking-tight">Läufe</h2>
      {runs.length === 0 && (
        <p className="text-sm text-muted-foreground">Noch kein Lauf aufgezeichnet.</p>
      )}
      {runs.length > 0 && (
        <ol className="divide-y divide-border overflow-hidden rounded-lg border-2 border-foreground bg-card">
          {runs.map((run) => {
            const result = outcome(run.exit_code)
            const args = Object.entries(run.args ?? {})
            return (
              <li key={run.run_id} className="p-3 text-sm">
                <button
                  type="button"
                  onClick={() => setOpenId(openId === run.run_id ? null : run.run_id)}
                  className="flex w-full items-baseline gap-2 text-left"
                >
                  {result.ok ? (
                    <Check className="size-4 shrink-0 translate-y-0.5 text-[var(--riso-blue)]" />
                  ) : (
                    <X className="size-4 shrink-0 translate-y-0.5 text-destructive" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="font-mono text-xs">{run.job}</span>
                    <span
                      className={cn(
                        "ml-2 text-xs",
                        result.ok ? "text-muted-foreground" : "text-destructive",
                      )}
                    >
                      {result.text}
                    </span>
                    {args.length > 0 && (
                      <span className="block truncate font-mono text-[11px] text-muted-foreground">
                        {args.map(([k, v]) => `${k}=${v}`).join(" ")}
                      </span>
                    )}
                  </span>
                  <span className="shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">
                    {run.started.slice(11, 16)} · {formatDuration(run.duration)}
                  </span>
                </button>

                {openId === run.run_id && (
                  <div className="mt-2 space-y-2">
                    <p className="break-all rounded bg-muted p-2 font-mono text-[11px]">
                      {detail.data?.command.join(" ") ?? "…"}
                    </p>
                    <pre className="max-h-72 overflow-auto rounded bg-foreground p-3 font-mono text-[11px] text-background">
                      {detail.isPending ? "Lade…" : detail.data?.log || "(keine Ausgabe)"}
                    </pre>
                    <Button variant="outline" size="sm" onClick={() => setOpenId(null)}>
                      Schließen
                    </Button>
                  </div>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
