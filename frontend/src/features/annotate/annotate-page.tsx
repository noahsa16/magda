import { useQuery } from "@tanstack/react-query"
import { Check, ChevronLeft, ChevronRight } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { PageOverlay } from "@/components/page-overlay"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { spansToTags } from "@/lib/bio"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { PageList } from "@/features/inspector/page-list"
import { LabelLegend } from "./label-legend"
import { applyLabel, removeRange, spanAt } from "./span-editor"
import { useAnnotation } from "./use-annotation"

const SAVE_LABEL = {
  saved: "gespeichert",
  saving: "speichert…",
  error: "nicht gespeichert",
} as const

export function AnnotatePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selected = searchParams.get("page")
  const [annotator, setAnnotator] = useState(
    () => localStorage.getItem("magda.annotator") ?? "",
  )
  // Auswahl über Wortindizes; anchor = erster Klick, focus = Shift-Klick.
  const [sel, setSel] = useState<{ anchor: number; focus: number } | null>(null)

  const schema = useQuery({ queryKey: ["schema"], queryFn: api.schema })
  const pages = useQuery({ queryKey: ["pages"], queryFn: api.pages })
  const gold = useQuery({ queryKey: ["gold"], queryFn: api.gold })
  const page = useQuery({
    queryKey: ["page", selected],
    queryFn: () => api.page(selected!),
    enabled: selected !== null,
  })

  const ann = useAnnotation(selected, annotator)
  const entityTypes = schema.data?.entity_types ?? []
  const ids = useMemo(() => (pages.data ?? []).map((p) => p.page_id), [pages.data])
  const idx = selected ? ids.indexOf(selected) : -1

  useEffect(() => {
    localStorage.setItem("magda.annotator", annotator)
  }, [annotator])

  function goto(i: number) {
    if (i < 0 || i >= ids.length) return
    setSel(null)
    setSearchParams({ page: ids[i] })
  }

  const range = sel ? { start: Math.min(sel.anchor, sel.focus), end: Math.max(sel.anchor, sel.focus) + 1 } : null

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return
      if (e.key === "ArrowLeft") return goto(idx - 1)
      if (e.key === "ArrowRight") return goto(idx + 1)
      if (ann.conflict) return
      if (e.key === "f") return ann.setStatus(ann.status === "done" ? "in_progress" : "done")
      if (!range) return
      if (e.key === "0" || e.key === "Delete" || e.key === "Backspace") {
        ann.setSpans(removeRange(ann.spans, range.start, range.end))
        return setSel(null)
      }
      const n = Number(e.key)
      if (n >= 1 && n <= entityTypes.length) {
        ann.setSpans(applyLabel(ann.spans, range.start, range.end, entityTypes[n - 1]))
        setSel(null)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  /** Klick auf ein gelabeltes Wort wählt den ganzen Span, sonst das Wort. */
  function onWordClick(i: number, shift: boolean) {
    if (shift && sel) return setSel({ ...sel, focus: i })
    const existing = spanAt(ann.spans, i)
    setSel(existing ? { anchor: existing.start, focus: existing.end - 1 } : { anchor: i, focus: i })
  }

  if (pages.isPending || schema.isPending) return <Skeleton className="h-40 w-full" />

  const data = page.data
  const goldRows = gold.data ?? []
  // Eine Seite mit veralteter Wortliste ist keine fertige Seite mehr, auch
  // wenn in der Datei "done" steht.
  const doneCount = goldRows.filter((g) => g.status === "done" && !g.stale).length
  const invalidCount = goldRows.filter((g) => g.status === "broken" || g.stale).length
  const tags = data ? spansToTags(ann.spans, data.words.length) : undefined

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="text-3xl font-extrabold tracking-tight">Annotieren</h1>
          <p className="font-mono text-xs text-muted-foreground">
            {idx >= 0 ? `${idx + 1} / ${ids.length}` : `${ids.length} Seiten`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            value={annotator}
            onChange={(e) => setAnnotator(e.target.value)}
            placeholder="Dein Name"
            className="h-8 w-36"
            aria-label="Annotator"
          />
          <span
            className={cn(
              "font-mono text-[11px] uppercase tracking-widest",
              ann.saveState === "error" ? "text-destructive" : "text-muted-foreground",
            )}
          >
            {SAVE_LABEL[ann.saveState]}
          </span>
          {ann.saveState === "error" && (
            <Button variant="outline" size="sm" onClick={ann.retry}>
              Erneut
            </Button>
          )}
          <Button variant="outline" size="sm" aria-label="Vorherige Seite"
            disabled={idx <= 0} onClick={() => goto(idx - 1)}>
            <ChevronLeft className="size-4" />
          </Button>
          <Button variant="outline" size="sm" aria-label="Nächste Seite"
            disabled={idx >= ids.length - 1} onClick={() => goto(idx + 1)}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      <div className="grid min-w-0 gap-5 lg:grid-cols-[240px_minmax(0,1fr)_260px]">
        <PageList
          pages={pages.data ?? []}
          selected={selected}
          onSelect={(id) => { setSel(null); setSearchParams({ page: id }) }}
          goldStatus={gold.data}
        />

        <div className="min-w-0 space-y-3">
          {!selected && (
            <div className="flex h-96 items-center justify-center rounded-lg border-2 border-dashed border-foreground/30">
              <p className="text-muted-foreground">Seite links auswählen</p>
            </div>
          )}

          {ann.conflict && (
            <Alert variant="destructive">
              <AlertTitle>Wortliste hat sich geändert</AlertTitle>
              <AlertDescription>
                Diese Annotation passt nicht mehr zu den Wortindizes aus Schritt 02
                und wird nicht gespeichert. Die Seite muss neu annotiert werden.
              </AlertDescription>
            </Alert>
          )}

          {selected && (page.isPending || ann.isPending) && (
            <Skeleton className="aspect-[595/842] w-full" />
          )}

          {selected && data && !page.isPending && (
            <>
              <div className="flex items-center justify-between gap-3 rounded-lg border-2 border-foreground bg-card px-4 py-2.5">
                <p className="font-mono text-sm tabular-nums">
                  {ann.spans.length} Spans · {data.words.length} Wörter
                </p>
                <Button
                  size="sm"
                  variant={ann.status === "done" ? "default" : "outline"}
                  disabled={ann.conflict}
                  onClick={() => ann.setStatus(ann.status === "done" ? "in_progress" : "done")}
                >
                  <Check className="size-4" />
                  {ann.status === "done" ? "Fertig" : "Als fertig markieren"}
                </Button>
              </div>

              <PageOverlay
                imageUrl={api.pageImageUrl(selected)}
                width={data.width}
                height={data.height}
                words={data.words}
                tags={tags}
                entityTypes={entityTypes}
                highlight={range}
                onWordClick={(i, e) => onWordClick(i, e.shiftKey)}
              />
            </>
          )}
        </div>

        <div className="lg:sticky lg:top-24 lg:self-start">
          <LabelLegend
            entityTypes={entityTypes}
            done={doneCount}
            total={ids.length}
            invalid={invalidCount}
          />
        </div>
      </div>
    </div>
  )
}
