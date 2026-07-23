// Spiegel der API-Antworten aus magda/api.py.

export interface Word {
  text: string
  bbox: [number, number, number, number] // PDF-Punkte, Ursprung oben links
}

export interface PageSummary {
  page_id: string
  catalog: string
  labeled: boolean
}

export interface PageDetail {
  page_id: string
  width: number
  height: number
  words: Word[]
  tags?: string[]
}

export interface CatalogStatus {
  id: string
  raw: number
  words: number
  images: number
  labeled: number
}

export interface PipelineStatus {
  catalogs: CatalogStatus[]
  totals: { raw: number; words: number; images: number; labeled: number }
}

// seqeval-Report: Entity-Typen plus "micro avg" / "macro avg" / "weighted avg".
export interface EntityMetrics {
  precision: number
  recall: number
  "f1-score": number
  support: number
}

export interface EvalReport {
  variant: "gbert" | "layoutxlm"
  split: string
  num_pages: number
  created: string
  report: Record<string, EntityMetrics>
}

export interface InferenceResult extends PageDetail {
  tags: string[]
  image_b64: string
}
