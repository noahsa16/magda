import { useMutation, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { EntityList } from "@/components/entity-list"
import { PageOverlay } from "@/components/page-overlay"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"

export function DemoPage() {
  const [file, setFile] = useState<File | null>(null)
  const [visibleTypes, setVisibleTypes] = useState<Set<string> | null>(null)
  const [highlight, setHighlight] = useState<{ start: number; end: number } | null>(null)

  const schema = useQuery({ queryKey: ["schema"], queryFn: api.schema })
  const entityTypes = schema.data?.entity_types ?? []

  const inference = useMutation({ mutationFn: api.inference })

  function toggleType(type: string) {
    setVisibleTypes((prev) => {
      const next = new Set(prev ?? entityTypes)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next.size === entityTypes.length ? null : next
    })
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Live-Demo</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Einseitiges Prospekt-PDF hochladen</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <Input
            type="file"
            accept="application/pdf"
            className="max-w-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <Button
            disabled={!file || inference.isPending}
            onClick={() => file && inference.mutate(file, { onSuccess: () => setHighlight(null) })}
          >
            {inference.isPending ? "Extrahiere…" : "Extrahieren"}
          </Button>
        </CardContent>
      </Card>

      {inference.isError && (
        <Alert variant="destructive">
          <AlertTitle>Extraktion fehlgeschlagen</AlertTitle>
          <AlertDescription>{inference.error.message}</AlertDescription>
        </Alert>
      )}

      {inference.data && (
        <div className="grid grid-cols-[1fr_280px] gap-4">
          <PageOverlay
            imageUrl={`data:image/png;base64,${inference.data.image_b64}`}
            width={inference.data.width}
            height={inference.data.height}
            words={inference.data.words}
            tags={inference.data.tags}
            entityTypes={entityTypes}
            visibleTypes={visibleTypes}
            highlight={highlight}
          />
          <EntityList
            words={inference.data.words}
            tags={inference.data.tags}
            entityTypes={entityTypes}
            visibleTypes={visibleTypes}
            onToggleType={toggleType}
            onSelect={setHighlight}
          />
        </div>
      )}
    </div>
  )
}
