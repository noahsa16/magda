import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import { Crumbs } from "@/components/crumbs"
import { FolderGrid, type FolderItem } from "@/components/folder-grid"
import { Skeleton } from "@/components/ui/skeleton"
import { AnnotatePage } from "@/features/annotate/annotate-page"
import { InspectorPage } from "@/features/inspector/inspector-page"
import { api } from "@/lib/api"

/**
 * Der gemeinsame Einstieg in alles, was Labels trägt.
 *
 * Vorher waren Inspektor und Annotator zwei Menüpunkte, und wessen Labels man
 * sieht, war ein Auswahlfeld irgendwo in der Kopfzeile. Inzwischen gibt es
 * mehrere Labeling-Modelle und zwei Sorten Handannotation – damit ist die
 * Quelle die erste Frage und nicht eine Einstellung. Als Ordner, durch die man
 * sich klickt, beantwortet sie sich von selbst.
 *
 * Die Ebenen darunter bleiben, wie sie waren: InspectorPage zeigt fertige
 * Labels an, AnnotatePage bearbeitet Gold. Diese Seite entscheidet nur, welche
 * von beiden dran ist.
 */
export function BrowsePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const group = searchParams.get("group")
  const model = searchParams.get("model")
  const annotator = searchParams.get("annotator")

  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api.sources() })

  // Ist eine Quelle gewählt, übernimmt die zuständige Seite vollständig –
  // samt eigener Brotkrumen, Blättern und Tastatursteuerung.
  if (model) return <InspectorPage />
  if (annotator) return <AnnotatePage />

  if (sources.isPending) return <Skeleton className="h-40 w-full" />

  const all = sources.data ?? []
  const models = all.filter((s) => s.kind === "model")
  const golds = all.filter((s) => s.kind === "gold")

  const header = (crumbs: { label: string; onClick?: () => void }[]) => (
    <div className="flex flex-wrap items-baseline gap-3">
      <h1 className="text-3xl font-extrabold tracking-tight">Labels</h1>
      <Crumbs items={crumbs} />
    </div>
  )

  if (group === "model") {
    const items: FolderItem[] = models.map((source) => ({
      id: source.id,
      label: source.name,
      sublabel: `${source.pages} Seiten`,
      tone: "model",
    }))
    return (
      <div className="flex min-w-0 flex-col gap-5">
        {header([
          { label: "Labels", onClick: () => setSearchParams({}) },
          { label: "Modell-Labels" },
        ])}
        <FolderGrid
          items={items}
          onOpen={(id) => setSearchParams({ model: id })}
          emptyHint={
            <>
              Noch kein Modell hat gelabelt. Im Tab <em>Pipeline</em>{" "}
              <code>magda label</code> starten.
            </>
          }
        />
      </div>
    )
  }

  if (group === "gold") {
    const items: FolderItem[] = golds.map((source) => {
      // Ungeprüfte Vorannotation ist etwas anderes als bestätigte Handarbeit
      // und darf nicht gleich aussehen – sonst verlässt sich jemand darauf.
      const unchecked = source.done === 0 && source.pages > 0
      return {
        id: source.id,
        label: source.name.split("(")[0].trim(),
        sublabel: unchecked
          ? `${source.pages} Seiten`
          : `${source.done} von ${source.pages} geprüft`,
        badge: unchecked ? "ungeprüft" : undefined,
        tone: unchecked ? "unchecked" : "gold",
      }
    })
    return (
      <div className="flex min-w-0 flex-col gap-5">
        {header([
          { label: "Labels", onClick: () => setSearchParams({}) },
          { label: "Handannotation" },
        ])}
        <FolderGrid
          items={items}
          onOpen={(id) => setSearchParams({ annotator: id })}
          emptyHint="Noch nichts von Hand annotiert."
        />
        <button
          type="button"
          onClick={() => setSearchParams({ annotator: "" })}
          className="self-start font-mono text-xs text-muted-foreground underline-offset-4 hover:underline"
        >
          … oder alle Seiten ohne Filter öffnen
        </button>
      </div>
    )
  }

  const goldPages = golds.reduce((sum, s) => sum + s.pages, 0)
  const goldDone = golds.reduce((sum, s) => sum + s.done, 0)

  return (
    <div className="flex min-w-0 flex-col gap-5">
      {header([{ label: "Labels" }])}
      <p className="max-w-2xl text-sm text-muted-foreground">
        Zwei Sorten Labels, die sich grundsätzlich unterscheiden: was ein
        Vision-Modell erzeugt hat – reproduzierbar, jederzeit neu berechenbar –
        und was von Hand entstanden ist.
      </p>
      <FolderGrid
        items={[
          {
            id: "model",
            label: "Modell-Labels",
            sublabel: `${models.length} ${models.length === 1 ? "Lauf" : "Läufe"}`,
            tone: "group",
          },
          {
            id: "gold",
            label: "Handannotation",
            sublabel: `${goldDone} von ${goldPages} geprüft`,
            tone: "gold",
          },
        ]}
        onOpen={(id) => setSearchParams({ group: id })}
      />
    </div>
  )
}
