import { useMutation, useQuery } from "@tanstack/react-query"
import { ChevronLeft, ChevronRight, Download } from "lucide-react"
import { useMemo, useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import type { DemoOffer } from "@/lib/types"
import { Console } from "@/features/control/console"
import { useRun } from "@/features/control/use-run"
import { filterOffers, sortOffers } from "./demo-verdict"
import { OfferCard } from "./offer-card"
import { OfferOverlay } from "./offer-overlay"
import { parseProgress } from "./parse-progress"
import { UploadPanel } from "./upload-panel"

type Variant = "gbert" | "layoutxlm"

interface OfferEntry {
  offer: DemoOffer
  pageIndex: number
  indexOnPage: number
}

export function DemoPage() {
  const [variant, setVariant] = useState<Variant>("gbert")
  const [uploadId, setUploadId] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [pageIndex, setPageIndex] = useState(0)
  const [activeOffer, setActiveOffer] = useState<number | null>(null)
  const [logOpen, setLogOpen] = useState(false)

  const run = useRun()

  const start = useMutation({
    mutationFn: (source: { kind: "file"; file: File } | { kind: "url"; url: string }) =>
      source.kind === "file" ? api.demoUpload(source.file) : api.demoFromUrl(source.url),
    onSuccess: (upload) => {
      setUploadId(upload.upload_id)
      setPageIndex(0)
      setActiveOffer(null)
      run.start("extract-pdf", { upload_id: upload.upload_id, variant })
    },
  })

  // Derselbe Runner-Stream wie der Pipeline-Tab (`/api/run`, `useRun`) - hier
  // nur gefiltert auf den Job, den diese Seite selbst gestartet hat. Ein
  // fremder, zufällig laufender Job (z.B. aus dem Pipeline-Tab) soll die
  // Demo nicht in einen falschen Zustand versetzen.
  const isThisJob = run.status?.job === "extract-pdf" && run.status.args.upload_id === uploadId
  const jobRunning = isThisJob && run.running
  const jobDone = isThisJob && !run.running && run.status?.exit_code === 0
  const jobFailed = isThisJob && !run.running && run.status?.exit_code != null && run.status.exit_code !== 0

  const resultQuery = useQuery({
    queryKey: ["demo-result", uploadId],
    queryFn: () => api.demoResult(uploadId!),
    enabled: uploadId != null && jobDone,
  })

  const progress = parseProgress(run.status?.lines ?? [])
  const result = resultQuery.data

  const allEntries = useMemo<OfferEntry[]>(
    () =>
      result?.pages.flatMap((p) =>
        p.offers.map((offer, indexOnPage) => ({ offer, pageIndex: p.page_index, indexOnPage })),
      ) ?? [],
    [result],
  )
  // sortOffers/filterOffers arbeiten auf DemoOffer[] und sind eigenständig
  // getestet (demo-verdict.test.ts) - hier nur an die Entries zurückgebunden,
  // über Objektidentität, damit Seite und Index je Angebot erhalten bleiben.
  const orderedEntries = useMemo(() => {
    const offers = allEntries.map((e) => e.offer)
    const matched = new Set(filterOffers(offers, search))
    return sortOffers(offers)
      .filter((offer) => matched.has(offer))
      .map((offer) => allEntries.find((e) => e.offer === offer)!)
  }, [allEntries, search])

  const page = result?.pages[pageIndex]
  const pageOffers = page?.offers ?? []

  function reset() {
    start.reset()
    setUploadId(null)
    setSearch("")
    setPageIndex(0)
    setActiveOffer(null)
  }

  function goToOffer(entry: OfferEntry) {
    setPageIndex(entry.pageIndex)
    setActiveOffer(entry.indexOnPage)
  }

  return (
    <div className="flex min-w-0 flex-col gap-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold tracking-tight">Demo</h1>
        <p className="text-sm text-muted-foreground">
          Ein fremdes Prospekt-PDF direkt zu Angeboten – ohne data/, für einen einzelnen Katalog.
        </p>
      </header>

      {!result && (
        <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,28rem)_minmax(0,1fr)]">
          <UploadPanel
            variant={variant}
            onVariantChange={setVariant}
            onStartFile={(file) => start.mutate({ kind: "file", file })}
            onStartUrl={(url) => start.mutate({ kind: "url", url })}
            busy={start.isPending || jobRunning}
          />

          <div className="min-w-0 space-y-3">
            {start.isError && (
              <Alert variant="destructive">
                <AlertTitle>Konnte nicht starten</AlertTitle>
                <AlertDescription>{(start.error as Error).message}</AlertDescription>
              </Alert>
            )}
            {run.startError && (
              <Alert variant="destructive">
                <AlertTitle>Start abgelehnt</AlertTitle>
                <AlertDescription>{run.startError}</AlertDescription>
              </Alert>
            )}
            {jobFailed && (
              <Alert variant="destructive">
                <AlertTitle>Verarbeitung fehlgeschlagen</AlertTitle>
                <AlertDescription>
                  magda extract-pdf ist mit Exit-Code {run.status?.exit_code} abgebrochen – Ausgabe unten.
                </AlertDescription>
              </Alert>
            )}
            {resultQuery.isError && (
              <Alert variant="destructive">
                <AlertTitle>Ergebnis nicht lesbar</AlertTitle>
                <AlertDescription>{(resultQuery.error as Error).message}</AlertDescription>
              </Alert>
            )}

            {(start.isPending || jobRunning) && (
              <div className="space-y-2 rounded-xl border-2 border-foreground bg-card p-4">
                <p className="font-mono text-sm">
                  {start.isPending
                    ? "Lädt hoch …"
                    : progress
                      ? `Seite ${progress.page} von ${progress.total}, ${progress.seconds.toFixed(2)} s`
                      : "Verarbeitet …"}
                </p>
                <Progress value={progress ? (progress.page / progress.total) * 100 : undefined} />
              </div>
            )}

            {resultQuery.isPending && jobDone && <Skeleton className="h-40 w-full" />}

            {(jobRunning || jobDone || jobFailed) && (
              <Collapsible open={logOpen} onOpenChange={setLogOpen}>
                <CollapsibleTrigger asChild>
                  <Button variant="outline" size="sm">
                    {logOpen ? "Ausgabe verbergen" : "Ausgabe zeigen"}
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="mt-2">
                  <Console lines={run.status?.lines ?? []} running={run.running} />
                </CollapsibleContent>
              </Collapsible>
            )}
          </div>
        </div>
      )}

      {result && page && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Button variant="outline" size="sm" onClick={reset}>
              Neues PDF
            </Button>
            <div className="flex flex-wrap items-center gap-3">
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Produkt oder Marke suchen …"
                className="h-8 w-56"
                aria-label="Angebote durchsuchen"
              />
              <div className="flex gap-1">
                {(["csv", "json", "sqlite"] as const).map((format) => (
                  <Button key={format} asChild variant="outline" size="sm">
                    <a href={api.demoExportUrl(uploadId!, format)}>
                      <Download className="size-3.5" /> {format.toUpperCase()}
                    </a>
                  </Button>
                ))}
              </div>
            </div>
          </div>

          {result.pages_without_text.length > 0 && (
            <Alert>
              <AlertTitle>PDF ohne Textlayer</AlertTitle>
              <AlertDescription>
                {result.pages_without_text.length} von {result.pages.length} Seiten haben keinen
                Textlayer – die Pipeline braucht einen, ein reines Bild-PDF bleibt dort leer.
              </AlertDescription>
            </Alert>
          )}

          <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="min-w-0 space-y-3">
              <div className="flex items-center justify-between">
                <Button
                  size="sm" variant="outline" disabled={pageIndex <= 0}
                  onClick={() => {
                    setPageIndex((i) => i - 1)
                    setActiveOffer(null)
                  }}
                >
                  <ChevronLeft className="size-4" /> Seite
                </Button>
                <p className="font-mono text-xs text-muted-foreground">
                  Seite {pageIndex + 1} / {result.pages.length}
                </p>
                <Button
                  size="sm" variant="outline" disabled={pageIndex >= result.pages.length - 1}
                  onClick={() => {
                    setPageIndex((i) => i + 1)
                    setActiveOffer(null)
                  }}
                >
                  Seite <ChevronRight className="size-4" />
                </Button>
              </div>
              <OfferOverlay
                imageUrl={api.demoPageImageUrl(uploadId!, pageIndex + 1)}
                width={page.width}
                height={page.height}
                offers={pageOffers}
                activeIndex={activeOffer}
                onSelect={setActiveOffer}
              />
            </div>

            <div className="min-w-0 space-y-2">
              <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                {orderedEntries.length} Angebote
              </p>
              {orderedEntries.length === 0 && allEntries.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  Keine Angebote gefunden – das PDF enthält keine erkennbaren Angebote.
                </p>
              )}
              {orderedEntries.length === 0 && allEntries.length > 0 && (
                <p className="text-sm text-muted-foreground">Keine Treffer für „{search}“.</p>
              )}
              <div className="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
                {orderedEntries.map((entry, index) => (
                  <OfferCard
                    key={`${entry.pageIndex}-${entry.indexOnPage}`}
                    offer={entry.offer}
                    index={index}
                    active={entry.pageIndex === pageIndex && entry.indexOnPage === activeOffer}
                    onSelect={() => goToOffer(entry)}
                    onHoverChange={(hovering) => {
                      if (entry.pageIndex === pageIndex) {
                        setActiveOffer(hovering ? entry.indexOnPage : null)
                      }
                    }}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
