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
  /** Ladedatum als YYYY-MM-DD; null, wenn data/raw/<id> fehlt. */
  downloaded: string | null
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

export interface ModelStatus {
  variant: "layoutxlm" | "gbert"
  trained: boolean
  epoch: number | null
  steps: number | null
  max_steps: number | null
  best_f1: number | null
  history: { epoch: number; f1: number }[]
}

/** Zustand des laufenden Pipeline-Schritts (magda/runner.py). */
export interface RunStatus {
  running: boolean
  job: string | null
  lines: string[]
  exit_code: number | null
  elapsed: number | null
}

/** Wort-Span einer Gold-Annotation. end ist exklusiv, wie bei range(). */
export interface Span {
  start: number
  end: number
  label: string
}

export interface GoldAnnotation {
  page_id: string
  words_hash: string
  status: "untouched" | "in_progress" | "done"
  annotator: string
  updated: string | null
  spans: Span[]
  /** Serverseitig: passt words_hash noch zur aktuellen Wortliste? */
  stale: boolean
}

export interface GoldSummary {
  page_id: string
  catalog: string
  /** "broken": Die Gold-Datei ist nicht lesbar (z.B. Merge-Konfliktmarker). */
  status: "untouched" | "in_progress" | "done" | "broken"
  annotator: string
  num_spans: number
  /** Serverseitig: passt words_hash noch zur aktuellen Wortliste? */
  stale: boolean
}

/** Eine Kachel in der Prospekt-Übersicht. Gleiche Form für beide Werkzeuge. */
export interface CatalogTile {
  id: string
  pages: number
  /** Annotator: Gold fertig. Inspektor: vom LLM gelabelt. */
  done: number
  downloaded: string | null
  /** Nur im Annotator > 0: Wortliste hat sich seit dem Annotieren geändert. */
  stale: number
  /** Nur im Annotator > 0: Gold-Datei nicht lesbar. */
  broken: number
}
