import type { EvalReport, InferenceResult, PageDetail, PageSummary, PipelineStatus } from "./types"

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
  inference: (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return fetchJson<InferenceResult>("/api/inference", { method: "POST", body: form })
  },
}
