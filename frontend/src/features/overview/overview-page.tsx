import { useQuery } from "@tanstack/react-query"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import type { EvalReport, ModelStatus } from "@/lib/types"
import { useCountUp } from "@/lib/use-count-up"
import { cn } from "@/lib/utils"

function StatCard({
  label,
  value,
  hint,
  alert,
}: {
  label: string
  value: number
  hint?: string
  /** Hebt den Hinweis hervor, wenn er auf offene Arbeit zeigt. */
  alert?: boolean
}) {
  const shown = useCountUp(value)
  return (
    <div className="plate rounded-xl border-2 border-foreground bg-card p-3.5">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 text-3xl font-extrabold tracking-tight tabular-nums">{shown}</p>
      {hint && (
        <p className={cn("text-[11px]", alert ? "font-medium text-destructive" : "text-muted-foreground")}>
          {hint}
        </p>
      )}
    </div>
  )
}

function ModelSummary({ models, reports }: { models: ModelStatus[]; reports: EvalReport[] }) {
  const best = (variant: string) =>
    reports.find((r) => r.variant === variant)?.report["micro avg"]?.["f1-score"] ?? null

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold tracking-tight">Modellstand</h2>
      <ul className="space-y-1.5 text-sm">
        {models.map((model) => {
          const f1 = best(model.variant)
          return (
            <li key={model.variant} className="flex items-baseline gap-3">
              <span className="w-24 shrink-0 font-mono text-xs">{model.variant}</span>
              <span className="min-w-0 flex-1 text-muted-foreground">
                {model.trained
                  ? `trainiert, ${model.epoch?.toFixed(0) ?? "?"} Epochen`
                  : "noch nicht trainiert"}
              </span>
              <span className="shrink-0 font-mono tabular-nums">
                {f1 == null ? "–" : `F1 ${f1.toFixed(3)}`}
              </span>
            </li>
          )
        })}
      </ul>
      <p className="text-[11px] text-muted-foreground">
        Der Flair-Arm misst nur BRAND und ist deshalb nicht mit diesen Zahlen vergleichbar.
        Aufschlüsselung nach Label unter <em>Ergebnis</em>.
      </p>
    </section>
  )
}

export function OverviewPage() {
  const { data, isPending, isError, error } = useQuery({ queryKey: ["status"], queryFn: api.status })
  const evalQ = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation })
  const modelQ = useQuery({ queryKey: ["model"], queryFn: api.model })

  if (isPending) return <Skeleton className="h-40 w-full" />
  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Backend nicht erreichbar</AlertTitle>
        <AlertDescription>
          {error.message} — läuft <code>uvicorn magda.api:app --reload</code>?
        </AlertDescription>
      </Alert>
    )
  }

  const t = data.totals
  // Gegen die verschiedenen Seiten gerechnet, nicht gegen data/raw: dort
  // stehen auch die aussortierten Duplikate, und die werden nie gelabelt.
  const labeledPct = t.words > 0 ? Math.round((t.labeled / t.words) * 100) : 0

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <section className="space-y-3 pt-2">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">
          Semesterprojekt Information Extraction · SoSe 2026
        </p>
        <h1 className="max-w-3xl text-3xl font-extrabold leading-tight tracking-tight">
          Strukturierte Angebotsdaten aus Supermarkt-Prospekten
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Ein großes Vision-LLM labelt die Trainingsdaten, darauf trainieren wir ein eigenes
          kleines Modell. Die Frage ist, wie viel davon in ein Modell passt, das lokal läuft –
          und ob Layout-Information dabei hilft.
        </p>
      </section>

      {/* Der Kostenvergleich ist die Hauptaussage des Projekts und gehört
          deshalb über die Zähler, nicht in eine Fußnote. */}
      <dl className="grid gap-3 rounded-xl border-2 border-foreground bg-card p-4 sm:grid-cols-3">
        {[
          { k: "Je Seite", llm: "44,8 s", eigen: "0,264 s" },
          { k: "Eine Wochenernte", llm: "24,9 h", eigen: "8,8 min" },
          { k: "Braucht", llm: "API, Kontingent", eigen: "nichts" },
        ].map((zeile) => (
          <div key={zeile.k} className="min-w-0">
            <dt className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              {zeile.k}
            </dt>
            <dd className="mt-1 flex items-baseline gap-2 text-sm">
              <span className="text-muted-foreground line-through">{zeile.llm}</span>
              <span className="font-bold tabular-nums">{zeile.eigen}</span>
            </dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Heruntergeladen"
          value={t.raw}
          hint={
            t.excluded > 0
              ? `${t.words} verschieden · ${t.excluded} Duplikate`
              : "Seiten in data/raw"
          }
        />
        {/* „196 von 327" sah nach Ausfall aus. Der Nenner sind die Seiten, die
            überhaupt extrahiert werden sollen – Duplikate gehören nicht dazu. */}
        <StatCard
          label="Extrahiert"
          value={t.words}
          hint={
            t.pending > 0
              ? `${t.pending} Seiten offen – Schritt 02 lief nicht durch`
              : "alle Seiten verarbeitet"
          }
          alert={t.pending > 0}
        />
        <StatCard label="Gelabelt" value={t.labeled} hint={`${labeledPct}% der Seiten`} />
        <StatCard
          label="Von Hand annotiert"
          value={t.gold_done}
          hint={
            t.gold_in_progress > 0
              ? `${t.gold_in_progress} angefangen · gold/`
              : "fertige Gold-Seiten"
          }
        />
      </div>

      <ModelSummary models={modelQ.data ?? []} reports={evalQ.data ?? []} />
    </div>
  )
}
