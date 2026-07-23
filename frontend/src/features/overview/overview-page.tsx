import { useQuery } from "@tanstack/react-query"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import { useCountUp } from "@/lib/use-count-up"
import { PipelineRunner } from "./pipeline-runner"

function StatCard({ label, value, hint }: { label: string; value: number; hint?: string }) {
  const shown = useCountUp(value)
  return (
    <div className="plate rounded-lg border-2 border-foreground bg-card p-4">
      <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-4xl font-extrabold tracking-tight tabular-nums">{shown}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
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

export function OverviewPage() {
  const { data, isPending, isError, error } = useQuery({ queryKey: ["status"], queryFn: api.status })
  const evalQ = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation })

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

  return (
    <div className="mx-auto max-w-5xl space-y-10">
      <section className="space-y-5 pt-2">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">
          Semesterprojekt Information Extraction · SoSe 2026
        </p>
        <h1 className="max-w-3xl text-3xl font-extrabold leading-tight tracking-tight sm:text-4xl">
          Strukturierte Angebotsdaten aus deutschen Supermarkt-Prospekten
        </h1>
        <p className="max-w-2xl text-muted-foreground">
          Die Forschungsfrage: Wie viel bringt Layout-Information bei der Extraktion? Ein
          Vision-LLM labelt die Trainingsdaten automatisch (weak supervision). Darauf werden zwei
          Modelle trainiert – LayoutXLM kennt die Position jedes Wortes, GBERT nur den Text. Die
          Differenz im F1-Wert ist das Ergebnis.
        </p>

        <dl className="grid gap-x-6 gap-y-4 border-t-2 border-foreground pt-5 sm:grid-cols-2 lg:grid-cols-4">
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
      </section>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Heruntergeladen" value={t.raw} hint="Seiten in data/raw" />
        <StatCard label="Extrahiert" value={t.words} hint="mit Wörtern und Koordinaten" />
        <StatCard label="Gelabelt" value={t.labeled} hint={`${labeledPct}% aller Seiten`} />
      </div>

      <PipelineRunner totals={t} reports={evalQ.data ?? []} />

      {data.catalogs.length > 0 && (
        <Card className="border-2 border-foreground">
          <CardHeader>
            <CardTitle className="text-xl font-bold tracking-tight">Kataloge</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Katalog</TableHead>
                  <TableHead className="text-right">Seiten</TableHead>
                  <TableHead className="text-right">Extrahiert</TableHead>
                  <TableHead className="text-right">Gelabelt</TableHead>
                  <TableHead className="w-[30%]">Fortschritt</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.catalogs.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-mono">{c.id}</TableCell>
                    <TableCell className="text-right tabular-nums">{c.raw}</TableCell>
                    <TableCell className="text-right tabular-nums">{c.words}</TableCell>
                    <TableCell className="text-right tabular-nums">{c.labeled}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress value={c.raw > 0 ? (c.labeled / c.raw) * 100 : 0} />
                        <span className="w-10 text-right font-mono text-xs text-muted-foreground tabular-nums">
                          {c.raw > 0 ? Math.round((c.labeled / c.raw) * 100) : 0}%
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
