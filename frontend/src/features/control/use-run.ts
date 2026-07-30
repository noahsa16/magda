import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { api } from "@/lib/api"

/** Alles, was ein abgeschlossener Schritt geschrieben haben könnte. */
const INVALIDATE_AFTER_RUN = [
  "status", "evaluation", "model", "runs", "catalogs", "labelDistribution",
]

/**
 * Start, Stopp und Zustand des laufenden Schritts.
 *
 * refetchIntervalInBackground: ein Trainingslauf dauert Minuten, in denen der
 * Tab im Hintergrund liegt – ohne das Flag pausiert das Polling und die Konsole
 * steht still.
 */
export function useRun() {
  const qc = useQueryClient()

  const status = useQuery({
    queryKey: ["run"],
    queryFn: api.run,
    refetchInterval: (q) => (q.state.data?.running ? 1500 : false),
    refetchIntervalInBackground: true,
  })

  const start = useMutation({
    mutationFn: ({ job, args }: { job: string; args: Record<string, string> }) =>
      api.startRun(job, args),
    onSuccess: (data) => qc.setQueryData(["run"], data),
  })

  const stop = useMutation({
    mutationFn: api.stopRun,
    onSuccess: (data) => qc.setQueryData(["run"], data),
  })

  const running = status.data?.running ?? false
  useEffect(() => {
    if (!running) {
      for (const key of INVALIDATE_AFTER_RUN) {
        qc.invalidateQueries({ queryKey: [key] })
      }
    }
  }, [running, qc])

  return {
    status: status.data,
    running,
    busy: running || start.isPending,
    start: (job: string, args: Record<string, string>) => start.mutate({ job, args }),
    stop: () => stop.mutate(),
    startError: start.error?.message ?? null,
  }
}
