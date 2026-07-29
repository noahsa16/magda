import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import type { ProbeResult } from "@/lib/types"

/**
 * Das Katalog-Verzeichnis samt Prüf-Knopf.
 *
 * Katalog-IDs lassen sich nicht erraten – sie kommen von Hand aus der
 * Penny-Website. Geteilt wird deshalb das Ergebnis: catalogs.json ist
 * versioniert, jeder trägt ein, was er gefunden hat.
 */
export function CatalogManager({ onUse }: { onUse: (url: string) => void }) {
  const qc = useQueryClient()
  const [url, setUrl] = useState("")
  const [probe, setProbe] = useState<ProbeResult | null>(null)

  const { data } = useQuery({ queryKey: ["catalogs"], queryFn: api.catalogs })

  const check = useMutation({
    mutationFn: () => api.probeCatalog(url),
    onSuccess: setProbe,
  })
  const add = useMutation({
    mutationFn: () =>
      api.addCatalog({
        id: (probe as ProbeResult).catalog_id,
        url,
        title: probe?.title ?? "",
        version: probe?.version ?? "1",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["catalogs"] })
      setProbe(null)
      setUrl("")
    },
  })
  const drop = useMutation({
    mutationFn: (id: string) => api.removeCatalog(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["catalogs"] }),
  })

  const entries = data?.entries ?? []

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold tracking-tight">Kataloge</h2>

      {data?.error && (
        <Alert variant="destructive">
          <AlertTitle>Verzeichnis nicht lesbar</AlertTitle>
          <AlertDescription>{data.error}</AlertDescription>
        </Alert>
      )}

      {entries.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-lg border-2 border-foreground bg-card text-sm">
          {entries.map((entry) => (
            <li key={entry.id} className="flex flex-wrap items-center gap-3 p-3">
              <span className="font-mono text-xs">{entry.id}</span>
              <span className="min-w-0 flex-1 truncate">{entry.title || "ohne Titel"}</span>
              <span className="shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">
                {entry.local_pages} S. lokal
              </span>
              <Button variant="outline" size="sm" onClick={() => onUse(entry.url)}>
                Übernehmen
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => drop.mutate(entry.id)}
                aria-label={`${entry.id} entfernen`}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2 rounded-lg border-2 border-dashed border-border p-3">
        <label
          htmlFor="new-catalog"
          className="block font-mono text-[11px] uppercase tracking-widest text-muted-foreground"
        >
          Neuen Katalog eintragen
        </label>
        <div className="flex flex-wrap gap-2">
          <Input
            id="new-catalog"
            value={url}
            placeholder="https://…blaetterkatalog.de/…?catalogId=…"
            onChange={(e) => {
              setUrl(e.target.value)
              setProbe(null)
            }}
            className="min-w-0 flex-1"
          />
          <Button
            variant="outline"
            size="sm"
            disabled={!url.trim() || check.isPending}
            onClick={() => check.mutate()}
          >
            Prüfen
          </Button>
        </div>

        {check.isError && <p className="text-xs text-destructive">{check.error.message}</p>}
        {add.isError && <p className="text-xs text-destructive">{add.error.message}</p>}

        {probe && (
          <div className="space-y-2 text-xs">
            <p>
              <span className="font-mono">{probe.catalog_id}</span>
              {probe.title ? ` · ${probe.title}` : " · ohne Titel"} · Version {probe.version}
              {!probe.meta_found && " (Metadatenseite abgelaufen, Version geraten)"}
            </p>
            <p
              className={
                probe.page_1_status === 200 ? "text-[var(--riso-blue)]" : "text-destructive"
              }
            >
              {probe.page_1_status === 200
                ? `Seite 1 erreichbar (${Math.round(probe.page_1_bytes / 1024)} KB)`
                : `Seite 1 nicht abrufbar (HTTP ${probe.page_1_status})`}
            </p>
            <Button size="sm" onClick={() => add.mutate()}>
              Ins Verzeichnis
            </Button>
          </div>
        )}
      </div>
    </section>
  )
}
