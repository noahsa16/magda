import { useQuery } from "@tanstack/react-query"
import { ChevronLeft, ChevronRight, Eye, EyeOff, Scan } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { CatalogGrid } from "@/components/catalog-grid"
import { Crumbs } from "@/components/crumbs"
import { EntityList, type EntityRef } from "@/components/entity-list"
import { PageOverlay } from "@/components/page-overlay"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { groupEntities } from "@/lib/bio"
import { groupPagesByCatalog } from "@/lib/catalogs"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { PageList } from "./page-list"

const EMPTY_HINT = (
  <>Noch keine Seiten extrahiert. Auf der Übersicht <code>02_extract_words</code> starten (davor <code>01_download_flyers</code>, falls data/raw/ leer ist).</>
)

function Metric({ label, value, tone }: { label: string; value: string; tone?: "warn" }) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </p>
      <p className={cn("font-mono text-sm font-semibold tabular-nums", tone === "warn" && "text-destructive")}>
        {value}
      </p>
    </div>
  )
}

export function InspectorPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selected = searchParams.get("page")
  // Die page_id enthält den Katalog bereits (1342881_p3); ein gesetzter
  // ?page= impliziert ihn also. Eigenen Parameter braucht nur der Zustand
  // "Prospekt offen, aber keine Seite gewählt".
  const catalog = searchParams.get("catalog") ?? selected?.split("_p")[0] ?? null
  // null = alle Typen sichtbar; Set = explizite Auswahl.
  const [visibleTypes, setVisibleTypes] = useState<Set<string> | null>(null)
  const [picked, setPicked] = useState<EntityRef | null>(null)
  const [hovered, setHovered] = useState<EntityRef | null>(null)
  const [showBoxes, setShowBoxes] = useState(true)
  const [showPlainWords, setShowPlainWords] = useState(true)

  const schema = useQuery({ queryKey: ["schema"], queryFn: api.schema })
  const pages = useQuery({ queryKey: ["pages"], queryFn: api.pages })
  const page = useQuery({
    queryKey: ["page", selected],
    queryFn: () => api.page(selected!),
    enabled: selected !== null,
  })
  const status = useQuery({ queryKey: ["status"], queryFn: api.status })

  const tiles = useMemo(
    () => groupPagesByCatalog(pages.data ?? [], status.data?.catalogs ?? []),
    [pages.data, status.data],
  )
  const catalogPages = useMemo(
    () => (pages.data ?? []).filter((p) => p.catalog === catalog),
    [pages.data, catalog],
  )

  const entityTypes = schema.data?.entity_types ?? []

  // Blättern folgt der sortierten Seitenliste; -1 = keine Auswahl, dann
  // springt "weiter" auf die erste Seite.
  const ids = useMemo(() => catalogPages.map((p) => p.page_id), [catalogPages])
  const idx = selected ? ids.indexOf(selected) : -1

  function goto(i: number) {
    if (i < 0 || i >= ids.length) return
    setPicked(null)
    setHovered(null)
    setSearchParams({ catalog: catalog!, page: ids[i] })
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return
      if (e.key === "ArrowLeft") goto(idx - 1)
      if (e.key === "ArrowRight") goto(idx + 1)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  function toggleType(type: string) {
    setVisibleTypes((prev) => {
      const next = new Set(prev ?? entityTypes)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next.size === entityTypes.length ? null : next
    })
  }

  /** Klick auf eine Box im Bild wählt das umgebende Entity aus. */
  function selectWord(wordIdx: number) {
    const tags = page.data?.tags
    if (!tags || tags[wordIdx] === "O") return setPicked(null)
    let start = wordIdx
    while (start > 0 && tags[start].startsWith("I-")) start--
    let end = wordIdx + 1
    while (end < tags.length && tags[end].startsWith("I-")) end++
    setPicked({ start, end })
  }

  if (pages.isPending || schema.isPending) return <Skeleton className="h-40 w-full" />

  if (catalog === null) {
    return (
      <div className="flex min-w-0 flex-col gap-4">
        <h1 className="text-3xl font-extrabold tracking-tight">Label-Inspektor</h1>
        <CatalogGrid
          tiles={tiles}
          unit="gelabelt"
          onSelect={(id) => setSearchParams({ catalog: id })}
          emptyHint={EMPTY_HINT}
        />
      </div>
    )
  }

  if (!tiles.some((t) => t.id === catalog)) {
    return (
      <div className="flex min-w-0 flex-col gap-4">
        <h1 className="text-3xl font-extrabold tracking-tight">Label-Inspektor</h1>
        <Alert variant="destructive">
          <AlertTitle>Prospekt nicht gefunden</AlertTitle>
          <AlertDescription>
            Der Katalog <code>{catalog}</code> existiert nicht (mehr). Unten stehen die vorhandenen.
          </AlertDescription>
        </Alert>
        <CatalogGrid
          tiles={tiles}
          unit="gelabelt"
          onSelect={(id) => setSearchParams({ catalog: id })}
          emptyHint={EMPTY_HINT}
        />
      </div>
    )
  }

  const data = page.data
  const entities = data?.tags ? groupEntities(data.words, data.tags) : null
  const tagged = data?.tags ? data.tags.filter((t) => t !== "O").length : 0
  const coverage = data?.tags?.length ? Math.round((tagged / data.tags.length) * 100) : 0

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="text-3xl font-extrabold tracking-tight">Label-Inspektor</h1>
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
          <Button
            variant="outline" size="sm" aria-label="Vorherige Seite (Pfeil links)"
            disabled={idx <= 0} onClick={() => goto(idx - 1)}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Button
            variant="outline" size="sm" aria-label="Nächste Seite (Pfeil rechts)"
            disabled={idx >= ids.length - 1} onClick={() => goto(idx + 1)}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      <div className="grid min-w-0 gap-5 lg:grid-cols-[240px_minmax(0,1fr)_360px]">
        <div className="min-w-0">
          <PageList
            pages={catalogPages}
            selected={selected}
            onSelect={(id) => {
              setPicked(null)
              setHovered(null)
              setSearchParams({ catalog: catalog, page: id })
            }}
          />
        </div>

        <div className="min-w-0 space-y-3">
          {!selected && (
            <div className="flex h-96 flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-foreground/30">
              <Scan className="size-8 text-muted-foreground" />
              <p className="text-muted-foreground">Seite links auswählen</p>
              <p className="font-mono text-xs text-muted-foreground">
                oder mit ← → durch die Seiten blättern
              </p>
            </div>
          )}
          {selected && page.isPending && <Skeleton className="aspect-[595/842] w-full" />}
          {selected && data && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border-2 border-foreground bg-card px-4 py-2.5">
                <div className="flex flex-wrap gap-x-6 gap-y-2">
                  <Metric label="Seite" value={selected} />
                  <Metric label="Wörter" value={String(data.words.length)} />
                  <Metric label="Entities" value={entities ? String(entities.length) : "–"} />
                  <Metric
                    label="Abdeckung"
                    value={data.tags ? `${coverage}%` : "–"}
                    tone={data.tags && coverage === 0 ? "warn" : undefined}
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    variant={showBoxes ? "default" : "outline"} size="sm"
                    onClick={() => setShowBoxes((v) => !v)}
                  >
                    {showBoxes ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
                    Boxen
                  </Button>
                  <Button
                    variant={showPlainWords ? "secondary" : "outline"} size="sm"
                    disabled={!showBoxes}
                    onClick={() => setShowPlainWords((v) => !v)}
                  >
                    Wörter ohne Label
                  </Button>
                </div>
              </div>

              {data.tags && coverage === 0 && (
                <Alert variant="destructive">
                  <AlertTitle>Seite ist gelabelt, aber leer</AlertTitle>
                  <AlertDescription>
                    Alle {data.tags.length} Wörter tragen „O“. Das LLM hat für diese Seite
                    nichts Verwertbares geliefert – ein Fall für die Fehleranalyse.
                  </AlertDescription>
                </Alert>
              )}

              <PageOverlay
                imageUrl={api.pageImageUrl(selected)}
                width={data.width}
                height={data.height}
                words={data.words}
                tags={data.tags}
                entityTypes={entityTypes}
                visibleTypes={visibleTypes}
                highlight={hovered ?? picked}
                showBoxes={showBoxes}
                showPlainWords={showPlainWords}
                onWordClick={selectWord}
              />
            </>
          )}
        </div>

        <div className="min-w-0 lg:sticky lg:top-24 lg:self-start">
          {selected && data?.tags && (
            <EntityList
              words={data.words}
              tags={data.tags}
              entityTypes={entityTypes}
              visibleTypes={visibleTypes}
              onToggleType={toggleType}
              onSelect={setPicked}
              onHover={setHovered}
              selected={picked}
              searchable
              maxHeight="60vh"
            />
          )}
          {selected && data && !data.tags && (
            <Alert>
              <AlertTitle>Noch nicht gelabelt</AlertTitle>
              <AlertDescription>
                Diese Seite hat noch keine Tags. Auf der Übersicht{" "}
                <code>03_label_words</code> starten.
              </AlertDescription>
            </Alert>
          )}
        </div>
      </div>
    </div>
  )
}
