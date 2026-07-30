import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

const pct = (value: number) => `${Math.round(value * 100)} %`

/**
 * Wo widersprechen sich die beiden größten Labeling-Läufe?
 *
 * Der Gold-Vergleich daneben misst gegen drei handannotierte Seiten – die
 * verlässlichste Zahl im Projekt, aber eine schmale. Diese hier misst über
 * alle gemeinsam gelabelten Seiten, ohne eine einzige zu annotieren.
 *
 * Der praktische Teil ist die Seitenliste: die uneinigsten Seiten bringen
 * pro Annotationsstunde am meisten, auf den einigen bestätigt Handarbeit
 * nur, was ohnehin feststeht. Deshalb führt jede Zeile in den Inspektor.
 */
export function AgreementCard() {
  const labelers = useQuery({ queryKey: ["labelers"], queryFn: () => api.labelers() })
  // Die beiden vollständigsten Läufe – bei weniger als zwei gibt es nichts
  // zu vergleichen, und ein Zehn-Seiten-Probelauf verzerrt die Quote.
  const top = [...(labelers.data ?? [])].sort((a, b) => b.pages - a.pages).slice(0, 2)

  const { data } = useQuery({
    queryKey: ["agreement", top[0]?.model, top[1]?.model],
    queryFn: () => api.agreement(top[0].model, top[1].model),
    enabled: top.length === 2,
  })

  if (top.length < 2 || !data || data.pages_compared === 0) return null

  const perLabel = Object.entries(data.per_label).sort((a, b) => a[1] - b[1])

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold tracking-tight">
        Wo die Modelle sich widersprechen
        <span className="ml-2 font-mono text-[11px] font-normal text-muted-foreground">
          {data.pages_compared} gemeinsame Seiten
        </span>
      </h2>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-xl border-2 border-foreground bg-card p-4">
          <p className="font-mono text-xs text-muted-foreground">
            {data.model_a}
            <br />
            gegen {data.model_b}
          </p>
          <p className="text-4xl font-extrabold tabular-nums">{pct(data.agreement)}</p>
          <p className="text-[11px] text-muted-foreground">
            der Wörter tragen bei beiden dasselbe Label.
          </p>
          <ul className="space-y-1 border-t-2 border-foreground pt-3">
            {perLabel.map(([entity, score]) => (
              <li key={entity} className="flex items-center gap-2 text-xs">
                <span className="w-24 shrink-0 font-mono">{entity}</span>
                <span className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <span
                    className={cn(
                      "block h-full rounded-full",
                      score >= 0.8 ? "bg-foreground" : score >= 0.5 ? "bg-foreground/50" : "bg-destructive",
                    )}
                    style={{ width: `${Math.max(2, score * 100)}%` }}
                  />
                </span>
                <span className="w-10 shrink-0 text-right font-mono tabular-nums">
                  {pct(score)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border-2 border-foreground bg-card p-4">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            Als Nächstes annotieren
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Die uneinigsten Seiten zuerst – dort bringt Handarbeit am meisten.
          </p>
          <ul className="mt-3 space-y-1">
            {data.pages.slice(0, 8).map((page) => (
              <li key={page.page_id}>
                <Link
                  to={`/annotate?catalog=${page.page_id.split("_p")[0]}&page=${page.page_id}`}
                  className="flex items-baseline gap-3 rounded px-1 py-0.5 font-mono text-xs hover:bg-muted"
                >
                  <span className="flex-1 truncate">{page.page_id}</span>
                  <span className="tabular-nums text-muted-foreground">
                    {page.conflicts}/{page.words}
                  </span>
                  <span className="w-10 text-right tabular-nums">{pct(page.agreement)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="text-[11px] text-muted-foreground">
        Übereinstimmung ist keine Richtigkeit – zwei Modelle können sich einig und gemeinsam
        irren. Die Zahl ist eine Obergrenze für Vertrauen, kein Ersatz für{" "}
        <code>gold/</code>.
      </p>
    </section>
  )
}
