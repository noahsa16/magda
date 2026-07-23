import { useMutation, useQuery } from "@tanstack/react-query"
import { FileText, Loader2, Sparkles, Upload } from "lucide-react"
import { useRef, useState } from "react"
import { EntityList, type EntityRef } from "@/components/entity-list"
import { PageOverlay } from "@/components/page-overlay"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { groupEntities } from "@/lib/bio"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { ModelStatusCard } from "./model-status"

export function DemoPage() {
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [visibleTypes, setVisibleTypes] = useState<Set<string> | null>(null)
  const [highlight, setHighlight] = useState<EntityRef | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const schema = useQuery({ queryKey: ["schema"], queryFn: api.schema })
  const entityTypes = schema.data?.entity_types ?? []
  const model = useQuery({ queryKey: ["model"], queryFn: api.model })
  const layoutxlm = model.data?.find((m) => m.variant === "layoutxlm")

  const inference = useMutation({ mutationFn: api.inference })

  function toggleType(type: string) {
    setVisibleTypes((prev) => {
      const next = new Set(prev ?? entityTypes)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next.size === entityTypes.length ? null : next
    })
  }

  function acceptFile(f: File | undefined | null) {
    if (f && f.name.toLowerCase().endsWith(".pdf")) setFile(f)
  }

  const entityCount = inference.data
    ? groupEntities(inference.data.words, inference.data.tags).length
    : null

  return (
    <div className="mx-auto flex min-w-0 max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight">Live-Demo</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Eine Prospektseite hochladen – das trainierte LayoutXLM extrahiert die Angebote lokal,
          ohne LLM-API.
        </p>
      </div>

      <ModelStatusCard status={layoutxlm} />

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          acceptFile(e.dataTransfer.files?.[0])
        }}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragOver
            ? "border-primary bg-primary/10"
            : "border-foreground/30 bg-card hover:border-primary",
        )}
      >
        {file ? (
          <>
            <FileText className="size-8 text-primary" />
            <span className="font-semibold">{file.name}</span>
            <span className="text-xs text-muted-foreground">Klicken, um eine andere Datei zu wählen</span>
          </>
        ) : (
          <>
            <Upload className="size-8 text-muted-foreground" />
            <span className="font-semibold">Einseitiges Prospekt-PDF hierher ziehen</span>
            <span className="text-xs text-muted-foreground">oder klicken zum Auswählen</span>
          </>
        )}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => acceptFile(e.target.files?.[0])}
      />

      <div className="flex items-center gap-3">
        <Button
          size="lg"
          disabled={!file || inference.isPending}
          onClick={() => file && inference.mutate(file, { onSuccess: () => setHighlight(null) })}
        >
          {inference.isPending ? (
            <>
              <Loader2 className="animate-spin" /> Extrahiere…
            </>
          ) : (
            <>
              <Sparkles /> Extrahieren
            </>
          )}
        </Button>
        {inference.data && entityCount != null && (
          <p className="fade-up text-sm text-muted-foreground" style={{ "--reveal-delay": "1.2s" } as React.CSSProperties}>
            <span className="font-bold text-foreground tabular-nums">{entityCount}</span>{" "}
            Entities in {inference.data.words.length} Wörtern gefunden
          </p>
        )}
      </div>

      {inference.isError && (
        <Alert variant="destructive">
          <AlertTitle>Extraktion fehlgeschlagen</AlertTitle>
          <AlertDescription>{inference.error.message}</AlertDescription>
        </Alert>
      )}

      {inference.data && (
        <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0">
            <PageOverlay
              key={inference.submittedAt /* Re-Mount pro Lauf: Animation startet neu */}
              imageUrl={`data:image/png;base64,${inference.data.image_b64}`}
              width={inference.data.width}
              height={inference.data.height}
              words={inference.data.words}
              tags={inference.data.tags}
              entityTypes={entityTypes}
              visibleTypes={visibleTypes}
              highlight={highlight}
              showPlainWords={false}
              animate
            />
          </div>
          <div className="min-w-0 lg:sticky lg:top-24 lg:self-start">
            <EntityList
              words={inference.data.words}
              tags={inference.data.tags}
              entityTypes={entityTypes}
              visibleTypes={visibleTypes}
              onToggleType={toggleType}
              onSelect={setHighlight}
              selected={highlight}
              animate
            />
          </div>
        </div>
      )}
    </div>
  )
}
