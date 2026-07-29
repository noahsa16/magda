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
  totals: {
    raw: number
    words: number
    images: number
    labeled: number
    /** Gold zählt quer über Kataloge, deshalb nur in den Summen. */
    gold_done: number
    gold_in_progress: number
  }
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

/** Ein Parameter eines Pipeline-Schritts, wie ihn /api/jobs beschreibt. */
export interface JobParam {
  key: string
  label: string
  kind: "str" | "int" | "float" | "choice"
  /** Nur zum Vorbelegen des Feldes – nicht gesetzte Werte landen nicht im argv. */
  default: string | number | null
  choices: string[]
  required: boolean
  help: string
}

export interface JobDef {
  job: string
  title: string
  what: string
  params: JobParam[]
}

/** Zustand des laufenden Pipeline-Schritts (magda/runner.py). */
export interface RunStatus {
  running: boolean
  job: string | null
  args: Record<string, string>
  run_id: string | null
  lines: string[]
  exit_code: number | null
  elapsed: number | null
}

/** Ein Eintrag der Lauf-Historie (magda/runs.py). */
export interface RunRecord {
  run_id: string
  job: string
  title?: string
  args: Record<string, string>
  command: string[]
  started: string
  finished: string | null
  exit_code: number | null
  duration: number | null
}

export interface RunDetail extends RunRecord {
  log: string
}

/** Ein Katalog im Verzeichnis (catalogs.json). */
export interface CatalogEntry {
  id: string
  url: string
  title: string
  version: string
  pages: number | null
  added: string
  added_by: string
  note: string
  /** Serverseitig: wie viele Seiten liegen lokal unter data/raw/<id>? */
  local_pages: number
}

export interface CatalogRegistry {
  entries: CatalogEntry[]
  /** Gesetzt, wenn catalogs.json nicht lesbar ist (z.B. Merge-Konflikt). */
  error: string | null
}

export interface ProbeResult {
  catalog_id: string
  version: string
  title: string | null
  /** false: getcatalog.do ist abgelaufen, die Version ist geraten. */
  meta_found: boolean
  page_1_status: number
  page_1_bytes: number
}

export interface LabelDistribution {
  pages: number
  counts: Record<string, number>
  total: number
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
