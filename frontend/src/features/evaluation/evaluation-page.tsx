import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { Link } from "react-router-dom"
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import type { ProtocolKey } from "@/lib/types"
import { DifferencePlot, ModelIntervals } from "./ci-plot"
import { EvaluationEmptyState } from "./empty-state"
import { ProtocolCard } from "./protocol-card"
import { SchemeCard } from "./scheme-card"
import {
  type MetricKey, type Row, overallF1, perEntityRows, significanceFor, sortRows,
} from "./transform"

const METRIC_LABELS: Record<MetricKey, string> = {
  "f1-score": "F1",
  precision: "Precision",
  recall: "Recall",
}

const GBERT_TONE = "#8E97A8"
const LAYOUT_TONE = "#2951E8"

const fmt = (v: number | null | undefined) => (v == null ? "–" : v.toFixed(3))
const signed = (v: number | undefined) =>
  v == null ? "–" : `${v >= 0 ? "+" : ""}${v.toFixed(3)}`

type SortKey = "entity" | "gbert" | "layoutxlm" | "support" | "delta"

export function EvaluationPage() {
  const [metric, setMetric] = useState<MetricKey>("f1-score")
  const [protocol, setProtocol] = useState<ProtocolKey>("report")
  const [sort, setSort] = useState<{ key: SortKey; descending: boolean }>({
    key: "support",
    descending: true,
  })

  const { data, isPending } = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation })
  // Der Vergleich liegt in einer eigenen Datei und fällt in /api/evaluation
  // durch die Formprüfung – er gehört keiner der beiden Varianten.
  const significance = useQuery({ queryKey: ["significance"], queryFn: api.significance })

  if (isPending) return <Skeleton className="h-40 w-full" />

  if (!data || data.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-extrabold tracking-tight">Evaluation</h1>
        <EvaluationEmptyState />
      </div>
    )
  }

  const gbert = overallF1(data, "gbert", protocol)
  const layoutxlm = overallF1(data, "layoutxlm", protocol)
  const missing = layoutxlm == null || gbert == null
  const paired = significanceFor(significance.data, "gbert", "layoutxlm")

  const rows = sortRows(perEntityRows(data, metric, protocol), sort.key, sort.descending)
  const reference = data[0]

  const toggleSort = (key: SortKey) =>
    setSort((s) => ({ key, descending: s.key === key ? !s.descending : true }))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-3xl font-extrabold tracking-tight">Evaluation</h1>
        <p className="font-mono text-xs text-muted-foreground">
          {reference.split}-Split · {reference.num_pages} Seiten ·{" "}
          {new Date(reference.created).toLocaleDateString("de-DE")}
        </p>
      </div>

      <p className="max-w-3xl text-sm text-muted-foreground">
        Gemessen wird, wie weit die eigenen Modelle die Labels des Vision-LLM
        reproduzieren – nicht, wie gut sie Prospekte im absoluten Sinn verstehen.
        Genau das ist die Projektfrage: ein Modell mit 109 Mio. Parametern läuft
        lokal auf CPU, das LLM braucht Netz, Key und Kontingent.
      </p>

      <ResultCard
        gbert={gbert}
        layoutxlm={layoutxlm}
        paired={paired}
        pending={significance.isPending}
      />

      {missing && (
        <p className="rounded-md border-2 border-dashed border-foreground/30 px-4 py-3 text-sm text-muted-foreground">
          Erst ein Modell ausgewertet – der Vergleich braucht beide. Die fehlende Variante
          startest du auf der{" "}
          <Link to="/" className="font-medium underline underline-offset-2">Übersicht</Link>.
        </p>
      )}

      <SchemeCard reports={data} />

      <ProtocolCard reports={data} protocol={protocol} onProtocolChange={setProtocol} />

      <Card className="border-2 border-foreground">
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
          <CardTitle className="font-bold">{METRIC_LABELS[metric]} pro Entity-Typ</CardTitle>
          <Tabs value={metric} onValueChange={(v) => setMetric(v as MetricKey)}>
            <TabsList>
              {(Object.keys(METRIC_LABELS) as MetricKey[]).map((k) => (
                <TabsTrigger key={k} value={k}>{METRIC_LABELS[k]}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="entity" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(v) => (typeof v === "number" ? v.toFixed(3) : "–")}
                  // Der Support gehört in den Tooltip, weil er die Zahl daneben
                  // relativiert: 0.87 auf 96 Instanzen ist etwas anderes als
                  // 0.87 auf 1003.
                  labelFormatter={(label) => {
                    const row = rows.find((r) => r.entity === label)
                    return row?.support ? `${label} · ${row.support} Instanzen` : String(label)
                  }}
                />
                <Legend />
                <Bar dataKey="gbert" name="GBERT" fill={GBERT_TONE} radius={[2, 2, 0, 0]} />
                <Bar dataKey="layoutxlm" name="LayoutXLM" fill={LAYOUT_TONE} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <EntityTable rows={rows} metric={metric} sort={sort} onSort={toggleSort} />

          <p className="text-xs text-muted-foreground">
            Support ist die Zahl der Referenz-Instanzen. Bei kleinem Support bewegt eine
            einzelne Instanz den Wert um mehrere Punkte – die Spalte gehört zu jeder
            Zahl dazu, die man aus dieser Tabelle zitiert.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

/** Das Ergebnis des Projekts: zwei Schätzer und die Frage, ob sie sich unterscheiden. */
function ResultCard({
  gbert, layoutxlm, paired, pending,
}: {
  gbert: number | null
  layoutxlm: number | null
  paired: ReturnType<typeof significanceFor>
  pending: boolean
}) {
  return (
    <Card className="border-2 border-foreground">
      <CardHeader>
        <CardTitle className="font-bold">Bringt Layout etwas?</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="plate rounded-lg border-2 border-foreground bg-card p-4">
            <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
              GBERT · nur Text
            </p>
            <p className="mt-1 text-4xl font-extrabold tabular-nums">{fmt(gbert)}</p>
          </div>
          <div className="plate rounded-lg border-2 border-foreground bg-card p-4">
            <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
              LayoutXLM · Text + Layout
            </p>
            <p className="mt-1 text-4xl font-extrabold tabular-nums">{fmt(layoutxlm)}</p>
          </div>
        </div>

        {paired ? (
          <>
            <ModelIntervals
              estimates={[
                {
                  name: "gbert",
                  label: "GBERT",
                  f1: paired.per_model.gbert.f1,
                  ci95: paired.per_model.gbert.ci95,
                  tone: "bg-slate-400",
                },
                {
                  name: "layoutxlm",
                  label: "LayoutXLM",
                  f1: paired.per_model.layoutxlm.f1,
                  ci95: paired.per_model.layoutxlm.ci95,
                  tone: "bg-primary",
                },
              ]}
            />
            <DifferencePlot
              difference={paired.paired.difference}
              ci95={paired.paired.ci95}
              pValue={paired.paired.p_value}
            />
            <div className="rounded-md border-l-4 border-primary bg-muted/40 px-4 py-3 text-sm">
              <p className="font-semibold">
                {paired.paired.significant
                  ? "Der Unterschied ist über die Cluster hinweg stabil."
                  : "Kein Effekt nachweisbar – in keine Richtung."}
              </p>
              <p className="mt-1 text-muted-foreground">
                Gebootstrappt über{" "}
                <span className="font-mono tabular-nums">{paired.clusters}</span>{" "}
                Duplikat-Cluster (Jaccard {paired.cluster_threshold}), nicht über{" "}
                <span className="font-mono tabular-nums">{paired.pages}</span> Seiten:
                elf Regionalfassungen derselben Vorlage sind eine Beobachtung, nicht elf.
                Über Seiten gezogen wäre das Intervall zu eng.
              </p>
            </div>
          </>
        ) : (
          <p className="rounded-md border-2 border-dashed border-foreground/30 px-4 py-3 text-sm text-muted-foreground">
            {pending
              ? "Konfidenzintervall wird geladen …"
              : "Kein Konfidenzintervall vorhanden. Eine Differenz ohne Intervall behauptet mehr, als die Daten hergeben – "}
            {!pending && (
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                magda significance --labels-from sonnet-5
              </code>
            )}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function EntityTable({
  rows, metric, sort, onSort,
}: {
  rows: Row[]
  metric: MetricKey
  sort: { key: SortKey; descending: boolean }
  onSort: (key: SortKey) => void
}) {
  const arrow = (key: SortKey) => (sort.key === key ? (sort.descending ? " ↓" : " ↑") : "")
  const head = (key: SortKey, label: string, align = "text-right") => (
    <TableHead
      className={`${align} cursor-pointer select-none hover:text-foreground`}
      onClick={() => onSort(key)}
    >
      {label}
      <span className="text-muted-foreground">{arrow(key)}</span>
    </TableHead>
  )

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            {head("entity", "Entity", "text-left")}
            {head("gbert", `GBERT ${METRIC_LABELS[metric]}`)}
            {head("layoutxlm", `LayoutXLM ${METRIC_LABELS[metric]}`)}
            {head("delta", "Δ")}
            {head("support", "Support")}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.entity}>
              <TableCell className="font-mono">
                {row.entity}
                {/* Unter 150 Instanzen ist eine Nachkommastelle Rauschen; das
                    gehört an die Zahl und nicht in eine Fußnote. */}
                {row.support != null && row.support < 150 && (
                  <Badge variant="outline" className="ml-2 text-[10px] font-normal">
                    dünn
                  </Badge>
                )}
              </TableCell>
              <TableCell className="text-right tabular-nums">{fmt(row.gbert)}</TableCell>
              <TableCell className="text-right tabular-nums">{fmt(row.layoutxlm)}</TableCell>
              <TableCell
                className={`text-right font-mono text-xs tabular-nums ${
                  row.delta == null ? "text-muted-foreground" : ""
                }`}
              >
                {signed(row.delta)}
              </TableCell>
              <TableCell className="text-right tabular-nums text-muted-foreground">
                {row.support ?? "–"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
