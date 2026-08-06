import { useQuery } from "@tanstack/react-query"
import { Check, ChevronLeft, ChevronRight, Plus, Trash2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { CatalogGrid } from "@/components/catalog-grid"
import { Crumbs } from "@/components/crumbs"
import { PageOverlay } from "@/components/page-overlay"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { groupEntities } from "@/lib/bio"
import { groupGoldByCatalog } from "@/lib/catalogs"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { PageList } from "@/features/inspector/page-list"
import { groupOf, removeGroup, startGroup, toggleRange } from "./grouping-editor"
import { useOfferGrouping } from "./use-offer-grouping"

const SAVE_LABEL = {
  saved: "gespeichert",
  saving: "speichert…",
  error: "nicht gespeichert",
} as const

const EMPTY_HINT = (
  <>Noch keine Prospekte extrahiert. Auf der Übersicht <code>magda extract</code> starten.</>
)

/** Angebotsnamen fürs Einfärben. `PageOverlay` färbt über die Position in
 * dieser Liste – so bekommt jedes Angebot eine eigene Farbe, ohne dass das
 * Overlay etwas von Gruppierung wissen muss. */
function offerNames(count: number): string[] {
  return Array.from({ length: count }, (_, i) => `Angebot ${i + 1}`)
}

export function GroupPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selected = searchParams.get("page")
  const catalog = searchParams.get("catalog") ?? selected?.split("_p")[0] ?? null
  const [annotator, setAnnotator] = useState(
    () => localStorage.getItem("magda.annotator") ?? "",
  )
  // Welches Angebot nimmt den nächsten Klick auf? -1 = das nächste Wort
  // eröffnet ein neues.
  const [active, setActive] = useState(-1)
  // Erster Klick einer Shift-Auswahl.
  const [anchor, setAnchor] = useState<number | null>(null)

  const pages = useQuery({ queryKey: ["pages"], queryFn: () => api.pages() })
  const summaries = useQuery({ queryKey: ["offer-gold"], queryFn: api.offerGold })
  const status = useQuery({ queryKey: ["status"], queryFn: api.status })
  const page = useQuery({
    queryKey: ["page", selected],
    queryFn: () => api.page(selected!),
    enabled: selected !== null,
  })

  const grouping = useOfferGrouping(selected, annotator)

  const catalogPages = useMemo(
    () => (pages.data ?? []).filter((p) => p.catalog === catalog),
    [pages.data, catalog],
  )
  const ids = useMemo(() => catalogPages.map((p) => p.page_id), [catalogPages])
  const idx = selected ? ids.indexOf(selected) : -1

  // PageList und die Kachelübersicht erwarten die Form von /api/gold.
  // num_offers statt num_spans ist der einzige Unterschied - umbenennen statt
  // eine zweite Liste und eine zweite Kachelfunktion bauen.
  const goldLike = useMemo(
    () => (summaries.data ?? []).map((s) => ({ ...s, num_spans: s.num_offers })),
    [summaries.data],
  )
  const goldRows = useMemo(
    () => goldLike.filter((g) => g.catalog === catalog),
    [goldLike, catalog],
  )
  const tiles = useMemo(
    () => groupGoldByCatalog(goldLike, status.data?.catalogs ?? []),
    [goldLike, status.data],
  )

  useEffect(() => {
    localStorage.setItem("magda.annotator", annotator)
  }, [annotator])

  const data = page.data
  const entities = useMemo(
    () => (data?.tags ? groupEntities(data.words, data.tags) : []),
    [data],
  )

  function goto(i: number) {
    if (i < 0 || i >= ids.length) return
    setActive(-1)
    setAnchor(null)
    setSearchParams({ catalog: catalog!, page: ids[i] })
  }

  function apply(start: number, end: number) {
    const next = toggleRange(grouping.groups, active, start, end)
    grouping.setGroups(next.groups)
    setActive(next.active)
  }

  /** Klick auf ein gelabeltes Wort nimmt den ganzen Span mit.
   *
   * Wortweise wäre die Referenz genauso ausdrucksstark, aber ein Angebot hat
   * schnell zwölf Wörter - bei 40 Seiten ist das der Unterschied zwischen
   * einem Nachmittag und einer Woche.
   */
  function onWordClick(i: number, shift: boolean) {
    if (shift && anchor !== null) {
      apply(Math.min(anchor, i), Math.max(anchor, i) + 1)
      setAnchor(null)
      return
    }
    setAnchor(i)
    const entity = entities.find((e) => i >= e.start && i < e.end)
    apply(entity ? entity.start : i, entity ? entity.end : i + 1)
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === "ArrowLeft") return goto(idx - 1)
      if (e.key === "ArrowRight") return goto(idx + 1)
      if (grouping.conflict) return
      if (e.key === "n") {
        const next = startGroup(grouping.groups)
        return setActive(next.active)
      }
      if (e.key === "f") {
        return grouping.setStatus(grouping.status === "done" ? "in_progress" : "done")
      }
      if ((e.key === "Delete" || e.key === "Backspace") && active >= 0) {
        const next = removeGroup(grouping.groups, active)
        grouping.setGroups(next.groups)
        setActive(next.active)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  if (pages.isPending || summaries.isPending) return <Skeleton className="h-40 w-full" />

  if (catalog === null) {
    return (
      <div className="flex min-w-0 flex-col gap-4">
        <div className="flex items-baseline gap-3">
          <h1 className="text-3xl font-extrabold tracking-tight">Gruppieren</h1>
          <p className="text-sm text-muted-foreground">
            Welche Entities ein Angebot bilden – die Referenz, gegen die das
            Clustering gemessen wird.
          </p>
        </div>
        <CatalogGrid
          tiles={tiles}
          unit="fertig"
          onSelect={(id) => setSearchParams({ catalog: id })}
          emptyHint={EMPTY_HINT}
        />
      </div>
    )
  }

  const names = offerNames(grouping.groups.length)
  const tags = data
    ? data.words.map((_, i) => {
        const g = groupOf(grouping.groups, i)
        return g === -1 ? "O" : `B-${names[g]}`
      })
    : undefined
  const doneCount = goldRows.filter((g) => g.status === "done" && !g.stale).length

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <Crumbs
            items={[
              { label: "Prospekte", onClick: () => setSearchParams({}) },
              selected
                ? { label: catalog, onClick: () => setSearchParams({ catalog }) }
                : { label: catalog },
              ...(selected ? [{ label: selected.split("_").pop()! }] : []),
            ]}
          />
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
              grouping.saveState === "error" ? "text-destructive" : "text-muted-foreground",
            )}
          >
            {SAVE_LABEL[grouping.saveState]}
          </span>
          {grouping.saveState === "error" && (
            <Button variant="outline" size="sm" onClick={grouping.retry}>
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
          pages={catalogPages}
          selected={selected}
          onSelect={(id) => {
            setActive(-1)
            setAnchor(null)
            setSearchParams({ catalog, page: id })
          }}
          goldStatus={goldRows}
        />

        <div className="min-w-0 space-y-3">
          {!selected && (
            <div className="flex h-96 items-center justify-center rounded-lg border-2 border-dashed border-foreground/30">
              <p className="text-muted-foreground">Seite links auswählen</p>
            </div>
          )}

          {grouping.conflict && (
            <Alert variant="destructive">
              <AlertTitle>Wortliste hat sich geändert</AlertTitle>
              <AlertDescription>
                Diese Gruppierung passt nicht mehr zu den Wortindizes aus Schritt 02
                und wird nicht gespeichert. Die Seite muss neu gruppiert werden.
              </AlertDescription>
            </Alert>
          )}

          {selected && (page.isPending || grouping.isPending) && (
            <Skeleton className="aspect-[595/842] w-full" />
          )}

          {selected && data && !page.isPending && !grouping.isPending && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border-2 border-foreground bg-card px-4 py-2.5">
                <p className="font-mono text-sm tabular-nums">
                  {grouping.groups.length} Angebote ·{" "}
                  {active >= 0 ? `Angebot ${active + 1} aktiv` : "neues Angebot"}
                </p>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline"
                    onClick={() => setActive(startGroup(grouping.groups).active)}>
                    <Plus className="size-4" />
                    Neues Angebot
                  </Button>
                  <Button size="sm" variant="outline" disabled={active < 0}
                    onClick={() => {
                      const next = removeGroup(grouping.groups, active)
                      grouping.setGroups(next.groups)
                      setActive(next.active)
                    }}>
                    <Trash2 className="size-4" />
                    Auflösen
                  </Button>
                  <Button
                    size="sm"
                    variant={grouping.status === "done" ? "default" : "outline"}
                    disabled={grouping.conflict}
                    onClick={() =>
                      grouping.setStatus(grouping.status === "done" ? "in_progress" : "done")
                    }
                  >
                    <Check className="size-4" />
                    {grouping.status === "done" ? "Fertig" : "Als fertig markieren"}
                  </Button>
                </div>
              </div>

              <PageOverlay
                imageUrl={api.pageImageUrl(selected)}
                width={data.width}
                height={data.height}
                words={data.words}
                tags={tags}
                entityTypes={names}
                onWordClick={(i, e) => onWordClick(i, e.shiftKey)}
              />
            </>
          )}
        </div>

        <div className="lg:sticky lg:top-24 lg:self-start space-y-3 rounded-lg border-2 border-foreground bg-card p-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Gruppieren
          </h2>
          <ul className="space-y-1.5 text-sm">
            <li><kbd className="font-mono">Klick</kbd> Entity dem aktiven Angebot zuschlagen</li>
            <li><kbd className="font-mono">Shift+Klick</kbd> bis hierhin</li>
            <li><kbd className="font-mono">n</kbd> neues Angebot beginnen</li>
            <li><kbd className="font-mono">⌫</kbd> aktives Angebot auflösen</li>
            <li><kbd className="font-mono">f</kbd> Seite als fertig markieren</li>
            <li><kbd className="font-mono">← →</kbd> Seite wechseln</li>
          </ul>
          <p className="border-t-2 border-foreground/10 pt-3 text-xs text-muted-foreground">
            Ein erneuter Klick nimmt die Zuordnung zurück. Was zu keinem Angebot
            gehört – Kleingedrucktes, Seitenkopf – bleibt ungefärbt und zählt
            in keiner Messung mit.
          </p>
          <p className="font-mono text-xs tabular-nums text-muted-foreground">
            {doneCount} / {ids.length} Seiten fertig
          </p>
        </div>
      </div>
    </div>
  )
}
