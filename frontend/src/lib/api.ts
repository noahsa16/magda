import type {
  EvalReport, GoldAnnotation, GoldSummary, InferenceResult, ModelStatus, PageDetail, PageSummary,
  PipelineStatus, RunStatus, Span,
} from "./types"

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    // FastAPI packt Fehlermeldungen in {"detail": ...}
    const body = await res.json().catch(() => null)
    throw new Error(
      typeof body?.detail === "string" ? body.detail : `${res.status} ${res.statusText}`,
    )
  }
  return res.json()
}

export const api = {
  schema: () => fetchJson<{ entity_types: string[] }>("/api/schema"),
  status: () => fetchJson<PipelineStatus>("/api/status"),
  pages: () => fetchJson<PageSummary[]>("/api/pages"),
  page: (id: string) => fetchJson<PageDetail>(`/api/pages/${id}`),
  pageImageUrl: (id: string) => `/api/pages/${id}/image`,
  evaluation: () => fetchJson<EvalReport[]>("/api/evaluation"),
  model: () => fetchJson<ModelStatus[]>("/api/model"),
  inference: (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return fetchJson<InferenceResult>("/api/inference", { method: "POST", body: form })
  },
  run: () => fetchJson<RunStatus>("/api/run"),
  startRun: (job: string, variant?: string) =>
    fetchJson<RunStatus>("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job, variant: variant ?? null }),
    }),
  stopRun: () => fetchJson<RunStatus>("/api/run/stop", { method: "POST" }),
  gold: () => fetchJson<GoldSummary[]>("/api/gold"),
  goldPage: (id: string) => fetchJson<GoldAnnotation>(`/api/gold/${id}`),
  saveGold: (
    id: string,
    payload: { words_hash: string; status: "in_progress" | "done"; annotator: string; spans: Span[] },
  ) =>
    fetchJson<GoldAnnotation>(`/api/gold/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
}
