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
  /** Welches Modell die Tags erzeugt hat. Fehlt, wenn die Seite ungelabelt ist. */
  model?: string
}

/**
 * Eine Label-Quelle als Ordner – aus /api/sources.
 *
 * "model": ein LLM-Lauf unter data/labeled/<modell>/.
 * "gold": Handannotation aus gold/, gruppiert nach Urheber. Geprüfte Arbeit
 * und ungeprüfte Vorannotation stehen dort nebeneinander, deshalb `done`.
 */
export interface LabelSource {
  kind: "model" | "gold"
  id: string
  name: string
  pages: number
  done: number
}

/** Ein Modell, das gelabelt hat – aus /api/labelers. */
export interface Labeler {
  model: string
  pages: number
}

/** Wie nah liegt ein Labeling-Modell am Goldstandard? Aus /api/labels/vs-gold. */
export interface LabelerScore {
  model: string
  pages_compared: number
  f1: number | null
  precision: number | null
  recall: number | null
  /** F1 je Entity-Typ – zeigt, *wo* ein Modell verliert. */
  per_label: Record<string, number | null>
}

/** Übereinstimmung zweier Labeling-Modelle – aus /api/labels/agreement. */
export interface AgreementPage {
  page_id: string
  words: number
  conflicts: number
  agreement: number
  agreement_on_labeled: number
}

export interface Agreement {
  model_a: string
  model_b: string
  pages_compared: number
  skipped: string[]
  agreement: number
  /** Beide labeln, aber verschieden: {BRAND: {PRODUCT: 12}}. */
  confusion: Record<string, Record<string, number>>
  only_a: Record<string, number>
  only_b: Record<string, number>
  per_label: Record<string, number>
  /** Uneinigste zuerst – das ist die Reihenfolge für die Handannotation. */
  pages: AgreementPage[]
}

export interface LabelsVsGold {
  /** Seiten, gegen die gemessen wurde. Leer = Vergleich noch nicht gefahren. */
  gold_pages: string[]
  results: LabelerScore[]
}

export interface CatalogStatus {
  id: string
  raw: number
  words: number
  images: number
  labeled: number
  /** Als Duplikat aussortiert – steht in data/excluded.json. */
  excluded: number
  /** Weder extrahiert noch aussortiert. Im Normalfall 0. */
  pending: number
  /** Ladedatum als YYYY-MM-DD; null, wenn data/raw/<id> fehlt. */
  downloaded: string | null
  /** "Bayern · 153 Märkte"; leer, wenn die Zuordnung fehlt. */
  region: string
  /** false: aus der Reihenfolge der Vorwoche übertragen, nicht belegt. */
  region_confirmed: boolean | null
}

export interface PipelineStatus {
  catalogs: CatalogStatus[]
  totals: {
    raw: number
    words: number
    images: number
    labeled: number
    excluded: number
    pending: number
    /** Gold zählt quer über Kataloge, deshalb nur in den Summen. */
    gold_done: number
    gold_in_progress: number
    /**
     * Seiten je Labeling-Modell. "labeled" oben zählt jede Seite einmal,
     * egal wie viele Modelle sie bearbeitet haben – hier steht, wer wie viel
     * beigetragen hat.
     */
    labeled_by_model: Record<string, number>
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
  kind: "str" | "int" | "float" | "choice" | "flag"
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
  /** Verkaufsregion, z.B. "Bayern · 153 Märkte". */
  region: string
  region_confirmed: boolean | null
}
