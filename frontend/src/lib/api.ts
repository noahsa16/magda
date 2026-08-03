import type {
  Agreement, EvalReport, GoldAnnotation, GoldSummary,
  AuditReport, AuditSummary,
  JobDef, LabelDistribution, Labeler, LabelSource, LabelsVsGold, ModelStatus, PageDetail, PageSummary,
  PipelineStatus,
  RunDetail, RunRecord, RunStatus, Span,
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
  // Ohne model liefert die API die Labels des konfigurierten Modells und
  // markiert eine Seite als gelabelt, sobald irgendein Modell sie bearbeitet
  // hat. Mit model geht es um genau diesen einen Lauf.
  pages: (model?: string) =>
    fetchJson<PageSummary[]>(`/api/pages${model ? `?model=${encodeURIComponent(model)}` : ""}`),
  page: (id: string, model?: string) =>
    fetchJson<PageDetail>(
      `/api/pages/${id}${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),
  labelers: () => fetchJson<Labeler[]>("/api/labelers"),
  sources: () => fetchJson<LabelSource[]>("/api/sources"),
  labelsVsGold: () => fetchJson<LabelsVsGold>("/api/labels/vs-gold"),
  agreement: (a: string, b: string) =>
    fetchJson<Agreement>(
      `/api/labels/agreement?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`,
    ),
  pageImageUrl: (id: string) => `/api/pages/${id}/image`,
  evaluation: () => fetchJson<EvalReport[]>("/api/evaluation"),
  model: () => fetchJson<ModelStatus[]>("/api/model"),
  run: () => fetchJson<RunStatus>("/api/run"),
  startRun: (job: string, args: Record<string, string> = {}) =>
    fetchJson<RunStatus>("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job, args }),
    }),
  stopRun: () => fetchJson<RunStatus>("/api/run/stop", { method: "POST" }),
  jobs: () => fetchJson<JobDef[]>("/api/jobs"),
  runs: () => fetchJson<RunRecord[]>("/api/runs"),
  runDetail: (id: string) => fetchJson<RunDetail>(`/api/runs/${id}`),
  labelDistribution: (model?: string) =>
    fetchJson<LabelDistribution>(
      `/api/labels/distribution${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),
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
  audits: () => fetchJson<{ audits: (AuditSummary & { label: string; labels_from: string })[] }>("/api/audit"),
  audit: (label: string) => fetchJson<AuditReport>(`/api/audit/${label}`),
  saveVerdict: (
    label: string,
    key: string,
    payload: {
      verdict: "correct" | "wrong" | "unsure"
      should_be?: string
      note?: string
      apply_to_duplicates?: boolean
    },
  ) =>
    fetchJson<{ key: string; applied_to: number; summary: AuditSummary }>(
      `/api/audit/${label}/${encodeURIComponent(key)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    ),
}
