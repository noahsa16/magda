import { useQuery } from "@tanstack/react-query"
import { ChevronDown } from "lucide-react"
import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import type { EvalReport, ModelStatus } from "@/lib/types"
import { useCountUp } from "@/lib/use-count-up"
import { cn } from "@/lib/utils"
import { groupByWeek } from "@/lib/weeks"
import { LabelDistribution } from "./label-distribution"
import { PipelineDiagram } from "./pipeline-diagram"
import { stepStates } from "./steps"

function StatCard({ label, value, hint }: { label: string; value: number; hint?: string }) {
  const shown = useCountUp(value)
  return (
    <div className="plate rounded-xl border-2 border-foreground bg-card p-3.5">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 text-3xl font-extrabold tracking-tight tabular-nums">{shown}</p>
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  )
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 text-sm">{children}</dd>
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
      </p>
    </section>
  )
}

export function OverviewPage() {
  const [faktenOffen, setFaktenOffen] = useState(false)
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
  const labeledPct = t.raw > 0 ? Math.round((t.labeled / t.raw) * 100) : 0
  const trainedVariants = (modelQ.data ?? []).filter((m) => m.trained).map((m) => m.variant)
  const wochen = groupByWeek(data.catalogs)

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <section className="space-y-3 pt-2">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">
          Semesterprojekt Information Extraction · SoSe 2026
        </p>
        <h1 className="max-w-3xl text-3xl font-extrabold leading-tight tracking-tight">
          Strukturierte Angebotsdaten aus Supermarkt-Prospekten
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Wie viel bringt Layout-Information bei der Extraktion? LayoutXLM kennt die Position
          jedes Wortes, GBERT nur den Text – die Differenz im F1-Wert ist das Ergebnis.
        </p>

        {/* Die Projektfakten ändern sich nie. Sie gehören auf die Seite, aber
            nicht in den Weg – eingeklappt sind sie eine Zeile statt vier. */}
        <Collapsible open={faktenOffen} onOpenChange={setFaktenOffen}>
          <CollapsibleTrigger className="flex items-center gap-1 font-mono text-[11px] uppercase tracking-widest text-muted-foreground hover:text-foreground">
            Projektfakten
            <ChevronDown
              className={cn("size-3 transition-transform", faktenOffen && "rotate-180")}
            />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <dl className="mt-3 grid gap-x-6 gap-y-4 border-t-2 border-foreground pt-4 sm:grid-cols-2 lg:grid-cols-4">
              <Fact label="Team">Bogdan Roth, Kjell Lavezzari, Noah Samel</Fact>
              <Fact label="Datenquelle">Penny-Wochenprospekte, PDF mit Textlayer</Fact>
              <Fact label="Label-Set">
                7 Typen: Produkt, Marke, Preis, Alt-Preis, Menge, Rabatt, Gültigkeit
              </Fact>
              <Fact label="Modelle">
                <span className="font-mono text-xs">layoutxlm-base</span> gegen{" "}
                <span className="font-mono text-xs">gbert-base</span>
              </Fact>
            </dl>
          </CollapsibleContent>
        </Collapsible>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Heruntergeladen" value={t.raw} hint="Seiten in data/raw" />
        <StatCard label="Extrahiert" value={t.words} hint="mit Wörtern und Koordinaten" />
        <StatCard label="Gelabelt" value={t.labeled} hint={`${labeledPct}% aller Seiten`} />
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

      <PipelineDiagram states={stepStates(t, evalQ.data ?? [], trainedVariants)} totals={t} />

      <div className="grid gap-6 lg:grid-cols-2">
        <LabelDistribution />
        <ModelSummary models={modelQ.data ?? []} reports={evalQ.data ?? []} />
      </div>

      {wochen.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold tracking-tight">
            Prospektwochen
            <span className="ml-2 font-mono text-[11px] font-normal text-muted-foreground">
              {wochen.length} Wochen · {data.catalogs.length} Regionalausgaben
            </span>
          </h2>
          {/* Vorher eine Tabelle mit einer Zeile je Regionalausgabe – 54 Zeilen
              für zwei Prospekte. Gebündelt sind es zwei. */}
          <ul className="divide-y divide-border overflow-hidden rounded-xl border-2 border-foreground bg-card">
            {wochen.map((woche) => {
              const pct = woche.raw > 0 ? (woche.labeled / woche.raw) * 100 : 0
              return (
                <li key={woche.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 p-3.5">
                  <div className="min-w-0 flex-1">
                    <p className="font-mono text-sm font-bold">{woche.id}</p>
                    <p className="truncate text-[11px] text-muted-foreground">
                      {woche.catalogs.length} Ausgaben
                      {woche.downloaded &&
                        ` · geladen ${woche.downloaded.slice(8)}.${woche.downloaded.slice(5, 7)}.`}
                      {woche.regions.length > 0 && ` · ${woche.regions.slice(0, 3).join(", ")}`}
                      {woche.regions.length > 3 && ` +${woche.regions.length - 3}`}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3 font-mono text-[11px] tabular-nums">
                    <span>{woche.raw} S.</span>
                    <span className="text-muted-foreground">{woche.labeled} gelabelt</span>
                  </div>
                  <div className="flex w-full items-center gap-2 sm:w-48">
                    <Progress value={pct} />
                    <span className="w-9 shrink-0 text-right font-mono text-[11px] text-muted-foreground tabular-nums">
                      {Math.round(pct)}%
                    </span>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      )}
    </div>
  )
}
