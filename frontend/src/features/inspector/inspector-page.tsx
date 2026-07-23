import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { EntityList } from "@/components/entity-list"
import { PageOverlay } from "@/components/page-overlay"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { groupEntities } from "@/lib/bio"
import { api } from "@/lib/api"
import { PageList } from "./page-list"

export function InspectorPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selected = searchParams.get("page")
  // null = alle Typen sichtbar; Set = explizite Auswahl.
  const [visibleTypes, setVisibleTypes] = useState<Set<string> | null>(null)
  const [highlight, setHighlight] = useState<{ start: number; end: number } | null>(null)

  const schema = useQuery({ queryKey: ["schema"], queryFn: api.schema })
  const pages = useQuery({ queryKey: ["pages"], queryFn: api.pages })
  const page = useQuery({
    queryKey: ["page", selected],
    queryFn: () => api.page(selected!),
    enabled: selected !== null,
  })

  const entityTypes = schema.data?.entity_types ?? []

  function toggleType(type: string) {
    setVisibleTypes((prev) => {
      const next = new Set(prev ?? entityTypes)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next.size === entityTypes.length ? null : next
    })
  }

  if (pages.isPending || schema.isPending) return <Skeleton className="h-40 w-full" />

  if (pages.data?.length === 0) {
    return (
      <Alert>
        <AlertTitle>Noch keine Seiten extrahiert</AlertTitle>
        <AlertDescription>
          <code>python scripts/02_extract_words.py</code> aus dem Projektroot laufen lassen
          (davor <code>01_download_flyers.py</code>, falls data/raw/ leer ist).
        </AlertDescription>
      </Alert>
    )
  }

  const entityCount =
    page.data?.tags ? groupEntities(page.data.words, page.data.tags).length : null

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Label-Inspektor</h1>
        {selected && page.data && (
          <p className="font-mono text-sm text-muted-foreground">
            {selected} · {page.data.words.length} Wörter
            {entityCount != null && <> · {entityCount} Entities</>}
          </p>
        )}
      </div>

      <div className="grid min-w-0 gap-4 lg:grid-cols-[220px_minmax(0,1fr)_280px]">
        <div className="min-w-0">
          <PageList
            pages={pages.data ?? []}
            selected={selected}
            onSelect={(id) => {
              setHighlight(null)
              setSearchParams({ page: id })
            }}
          />
        </div>

        <div className="min-w-0">
          {!selected && (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
              <p className="text-muted-foreground">Seite links auswählen.</p>
            </div>
          )}
          {selected && page.isPending && <Skeleton className="aspect-[595/842] w-full" />}
          {selected && page.data && (
            <PageOverlay
              imageUrl={api.pageImageUrl(selected)}
              width={page.data.width}
              height={page.data.height}
              words={page.data.words}
              tags={page.data.tags}
              entityTypes={entityTypes}
              visibleTypes={visibleTypes}
              highlight={highlight}
            />
          )}
        </div>

        <div className="min-w-0 lg:sticky lg:top-6 lg:self-start">
          {selected && page.data && page.data.tags && (
            <EntityList
              words={page.data.words}
              tags={page.data.tags}
              entityTypes={entityTypes}
              visibleTypes={visibleTypes}
              onToggleType={toggleType}
              onSelect={setHighlight}
            />
          )}
          {selected && page.data && !page.data.tags && (
            <Alert>
              <AlertTitle>Noch nicht gelabelt</AlertTitle>
              <AlertDescription>
                <code>python scripts/03_label_words.py</code> erzeugt die Labels.
              </AlertDescription>
            </Alert>
          )}
        </div>
      </div>
    </div>
  )
}
