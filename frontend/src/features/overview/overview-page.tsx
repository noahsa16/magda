import { useQuery } from "@tanstack/react-query"
import { Check, Copy, FileDown, ScanText, Tags } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import { useCountUp } from "@/lib/use-count-up"
import { nextStep } from "./next-step"
import { PipelineSteps } from "./pipeline-steps"

function StatCard({
  label, value, icon: Icon, hint,
}: { label: string; value: number; icon: LucideIcon; hint?: string }) {
  const shown = useCountUp(value)
  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Icon className="size-4 text-primary" /> {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        <span className="text-4xl font-semibold tracking-tight tabular-nums">{shown}</span>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      aria-label="Kommando kopieren"
      className="shrink-0 rounded-md border border-background/20 p-2 transition-colors hover:bg-background/10"
      onClick={() => {
        navigator.clipboard?.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      }}
    >
      {copied ? <Check className="size-4 text-primary" /> : <Copy className="size-4" />}
    </button>
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
  const step = nextStep(t)
  const hasEval = (evalQ.data?.length ?? 0) > 0
  const labeledPct = t.raw > 0 ? Math.round((t.labeled / t.raw) * 100) : 0

  const steps = [
    { title: "Download", done: t.raw > 0 },
    { title: "Wort-Extraktion", done: t.raw > 0 && t.words >= t.raw },
    { title: "LLM-Labeling", done: t.words > 0 && t.labeled >= t.words },
    { title: "Training", done: hasEval },
    { title: "Evaluation", done: hasEval },
  ]

  return (
    <div className="space-y-8">
      <section className="space-y-4 pt-2">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">
          Weak Supervision · LayoutXLM vs. GBERT
        </p>
        <h1 className="max-w-2xl font-display text-4xl leading-tight tracking-tight sm:text-5xl">
          Aus Prospektseiten werden <em className="text-primary">strukturierte Angebote</em>.
        </h1>
        <p className="max-w-xl text-muted-foreground">
          Ein LLM labelt die Trainingsdaten automatisch, ein layout-aware Modell lernt daraus.
          Magda macht jeden Schritt der Pipeline sichtbar – von der PDF bis zur Evaluation.
        </p>
      </section>

      <PipelineSteps steps={steps} />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Heruntergeladen" value={t.raw} icon={FileDown} hint="Seiten aus data/raw" />
        <StatCard label="Extrahiert" value={t.words} icon={ScanText} hint="mit Wörtern & Koordinaten" />
        <StatCard label="Gelabelt" value={t.labeled} icon={Tags} hint={`${labeledPct}% aller Seiten`} />
      </div>

      {step && (
        <div className="flex items-center justify-between gap-3 rounded-xl bg-foreground px-4 py-3 text-background shadow-sm">
          <div className="min-w-0">
            <p className="font-mono text-[11px] uppercase tracking-widest text-background/60">
              Nächster Schritt · aus dem Projektroot
            </p>
            <code className="block truncate font-mono text-sm">$ {step}</code>
          </div>
          <CopyButton text={step} />
        </div>
      )}

      {data.catalogs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="font-display text-xl">Kataloge</CardTitle>
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
