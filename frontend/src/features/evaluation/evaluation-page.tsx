import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, XAxis, YAxis,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import { EvaluationEmptyState } from "./empty-state"
import { type MetricKey, overallF1, perEntityRows } from "./transform"

const METRIC_LABELS: Record<MetricKey, string> = {
  "f1-score": "F1",
  precision: "Precision",
  recall: "Recall",
}

const fmt = (v: number | null | undefined) => (v == null ? "–" : v.toFixed(3))

export function EvaluationPage() {
  const [metric, setMetric] = useState<MetricKey>("f1-score")
  const { data, isPending } = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation })

  if (isPending) return <Skeleton className="h-40 w-full" />

  if (!data || data.length === 0) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <h1 className="text-3xl font-extrabold tracking-tight">Evaluation</h1>
        <EvaluationEmptyState />
      </div>
    )
  }

  const gbert = overallF1(data, "gbert")
  const layoutxlm = overallF1(data, "layoutxlm")
  const delta = gbert != null && layoutxlm != null ? layoutxlm - gbert : null
  const rows = perEntityRows(data, metric)

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl tracking-tight">Evaluation</h1>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">GBERT (nur Text) · F1</CardTitle>
          </CardHeader>
          <CardContent><span className="text-3xl font-semibold tabular-nums">{fmt(gbert)}</span></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">LayoutXLM (Text + Layout) · F1</CardTitle>
          </CardHeader>
          <CardContent><span className="text-3xl font-semibold tabular-nums">{fmt(layoutxlm)}</span></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Layout-Gewinn (Δ F1)</CardTitle>
          </CardHeader>
          <CardContent>
            {/* Der Layout-Gewinn ist DAS Ergebnis des Projekts – Coral, wenn positiv */}
            <span className={`text-3xl font-semibold tabular-nums ${delta != null && delta > 0 ? "text-primary" : ""}`}>
              {delta == null ? "–" : `${delta >= 0 ? "+" : ""}${delta.toFixed(3)}`}
            </span>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>{METRIC_LABELS[metric]} pro Entity-Typ</CardTitle>
          <Tabs value={metric} onValueChange={(v) => setMetric(v as MetricKey)}>
            <TabsList>
              {(Object.keys(METRIC_LABELS) as MetricKey[]).map((k) => (
                <TabsTrigger key={k} value={k}>{METRIC_LABELS[k]}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="entity" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
              <Legend />
              <Bar dataKey="gbert" name="GBERT" fill="#B8B2A6" radius={[3, 3, 0, 0]} />
              <Bar dataKey="layoutxlm" name="LayoutXLM" fill="#C96442" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {data.map((r) => (
        <Card key={`${r.variant}-${r.split}`}>
          <CardHeader>
            <CardTitle className="text-base">
              {r.variant} · {r.split}-Split · {r.num_pages} Seiten · {r.created}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Entity</TableHead>
                  <TableHead className="text-right">Precision</TableHead>
                  <TableHead className="text-right">Recall</TableHead>
                  <TableHead className="text-right">F1</TableHead>
                  <TableHead className="text-right">Support</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(r.report).map(([entity, m]) => (
                  <TableRow key={entity}>
                    <TableCell className="font-mono">{entity}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt(m.precision)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt(m.recall)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt(m["f1-score"])}</TableCell>
                    <TableCell className="text-right tabular-nums">{m.support}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
