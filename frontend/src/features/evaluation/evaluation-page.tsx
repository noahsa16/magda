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
  type MetricKey, type Row, overallF1, perEntityRows, reportsOfOneSplit,
  restrictedArms, significanceFor, sortRows, variantLabel, variantPairs,
  variantsOf,
} from "./transform"

const METRIC_LABELS: Record<MetricKey, string> = {
  "f1-score": "F1",
  precision: "Precision",
  recall: "Recall",
}

/**
 * Kategoriale Palette, feste Zuordnung je Arm – nie nach Rang vergeben.
 *
 * Die Slots stehen in der Reihenfolge der Hausvorgabe (blau, orange, aqua,
 * gelb) und sind mit dem Paletten-Validator geprüft: hell wie dunkel bestehen
 * alle Checks, schlechteste benachbarte CVD-Trennung ΔE 9.1 (Ziel ≥ 8).
 *
 * Aqua und Gelb liegen auf hellem Grund unter 3:1 Kontrast. Das ist zulässig,
 * solange die Zahlen auch als Text dastehen – die Tabelle direkt unter dem
 * Diagramm ist genau diese Absicherung und darf deshalb nicht daraus
 * verschwinden.
 */
const VARIANT_TONES: Record<string, string> = {
  gbert: "#2a78d6",
  xlmr: "#eb6834",
  lilt: "#1baf7a",
  layoutxlm: "#eda100",
}
const FALLBACK_TONE = "#8E97A8"
const toneOf = (variant: string) => VARIANT_TONES[variant] ?? FALLBACK_TONE

/** Was der Arm sieht – die Kachel ohne das ist nur eine Zahl. */
const INGREDIENTS: Record<string, string> = {
  gbert: "nur Text · deutscher Encoder",
  xlmr: "nur Text · XLM-R",
  lilt: "Text + Layout",
  layoutxlm: "Text + Layout + Bild",
}

/**
 * Wofür ein Kettenschritt steht. Nur benachbarte Schritte tragen eine Frage:
 * zwischen ihnen liegt genau eine Zutat, und nur dann ist die Differenz einer
 * Ursache zuschreibbar.
 */
const PAIR_QUESTIONS: Record<string, string> = {
  "xlmr→lilt": "was bringt Layout?",
  "lilt→layoutxlm": "was bringt das Bild?",
}

const fmt = (v: number | null | undefined) => (v == null ? "–" : v.toFixed(3))
const signed = (v: number | undefined) =>
  v == null ? "–" : `${v >= 0 ? "+" : ""}${v.toFixed(3)}`

/** `entity`, `support`, `delta` – oder der Name eines Arms. */
type SortKey = string

export function EvaluationPage() {
  const [metric, setMetric] = useState<MetricKey>("f1-score")
  const [protocol, setProtocol] = useState<ProtocolKey>("report")
  const [sort, setSort] = useState<{ key: SortKey; descending: boolean }>({
    key: "support",
    descending: true,
  })

  // Welches Paar verglichen wird. Index statt Namen, damit die Auswahl nicht
  // ins Leere zeigt, wenn ein Arm noch nicht ausgewertet ist.
  const [pairIndex, setPairIndex] = useState(0)

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

  // Eingeschraenkte Reports (Flair misst nur BRAND) gehoeren in keine Spalte
  // dieser Seite: ihr micro-F1 beantwortet eine andere Frage. Genannt werden
  // sie trotzdem, sonst verschwinden sie stillschweigend aus dem Projekt.
  const restricted = restrictedArms(data)
  // Genau ein Split und je Variante genau ein Report: data/eval/ ist ein
  // Archiv mehrerer Laeufe, und zwei Reports derselben Variante ueberschreiben
  // einander sonst still in derselben Spalte.
  const comparable = reportsOfOneSplit(data.filter((r) => !r.restricted_to?.length))

  const variants = variantsOf(comparable)
  const pairs = variantPairs(variants)
  const pair = pairs[Math.min(pairIndex, pairs.length - 1)]
  const alone = variants.length < 2
  const paired = pair ? significanceFor(significance.data, pair[0], pair[1]) : null

  const rows = sortRows(
    perEntityRows(comparable, metric, protocol, pair), sort.key, sort.descending)
  const reference = comparable[0] ?? data[0]

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
        variants={variants}
    f1={Object.fromEntries(
          variants.map((v) => [v, overallF1(comparable, v, protocol)]),
        )}
        pairs={pairs}
        pairIndex={Math.min(pairIndex, Math.max(pairs.length - 1, 0))}
        onPairChange={setPairIndex}
        paired={paired}
        pending={significance.isPending}
      />

      {alone && (
        <p className="rounded-md border-2 border-dashed border-foreground/30 px-4 py-3 text-sm text-muted-foreground">
          Erst ein Modell ausgewertet – der Vergleich braucht mindestens zwei. Die
          fehlenden Varianten startest du auf der{" "}
          <Link to="/" className="font-medium underline underline-offset-2">Übersicht</Link>.
        </p>
      )}

      {restricted.length > 0 && (
        <p className="rounded-md border-l-4 border-foreground/40 bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
          Nicht in der Tabelle:{" "}
          {restricted.map((r, i) => (
            <span key={r.variant}>
              {i > 0 && ", "}
              <span className="font-mono text-xs">{r.variant}</span> (nur{" "}
              {r.labels.join(", ")})
            </span>
          ))}
          . Ein Arm, der nur einen Teil der Labels kennt, hat ein micro-F1 über
          eine andere Grundmenge – nebeneinandergestellt läse es sich wie ein
          schlechteres Modell statt wie eine andere Frage. Der Report liegt in{" "}
          <span className="font-mono text-xs">data/eval/</span>.
        </p>
      )}

      <SchemeCard reports={comparable} />

      <ProtocolCard reports={comparable} protocol={protocol} onProtocolChange={setProtocol} />

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
                {variants.map((v) => (
                  <Bar
                    key={v}
                    dataKey={`values.${v}`}
                    name={variantLabel(v)}
                    fill={toneOf(v)}
                    radius={[2, 2, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>

          <EntityTable
            rows={rows}
            variants={variants}
            pair={pair}
            metric={metric}
            sort={sort}
            onSort={toggleSort}
          />

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

/**
 * Das Ergebnis des Projekts: die Schätzer aller Arme und die Frage, ob sich
 * zwei davon unterscheiden.
 *
 * Verglichen wird immer nur ein *Paar*. Vier Kacheln nebeneinander laden dazu
 * ein, die höchste Zahl zum Sieger zu erklären; die Frage, die das Projekt
 * beantworten will, ist aber jedes Mal eine Differenz mit Intervall – und die
 * gibt es nur paarweise, gebootstrappt über dieselben Cluster.
 */
function ResultCard({
  variants, f1, pairs, pairIndex, onPairChange, paired, pending,
}: {
  variants: string[]
  f1: Record<string, number | null>
  pairs: [string, string][]
  pairIndex: number
  onPairChange: (index: number) => void
  paired: ReturnType<typeof significanceFor>
  pending: boolean
}) {
  const pair = pairs[pairIndex]
  return (
    <Card className="border-2 border-foreground">
      <CardHeader>
        <CardTitle className="font-bold">Bringt Layout etwas?</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {variants.map((v) => (
            <div
              key={v}
              className="plate rounded-lg border-2 border-foreground bg-card p-4"
            >
              <p className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                <span
                  aria-hidden
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-[2px]"
                  style={{ backgroundColor: toneOf(v) }}
                />
                {variantLabel(v)}
              </p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">{INGREDIENTS[v] ?? ""}</p>
              <p className="mt-1 text-4xl font-extrabold tabular-nums">{fmt(f1[v])}</p>
            </div>
          ))}
        </div>

        {pairs.length > 1 && (
          <div className="space-y-2">
            <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
              Vergleich
            </p>
            <div className="flex flex-wrap gap-2">
              {pairs.map(([a, b], i) => (
                <button
                  key={`${a}-${b}`}
                  type="button"
                  onClick={() => onPairChange(i)}
                  aria-pressed={i === pairIndex}
                  className={`rounded-md border-2 px-3 py-1.5 text-xs font-medium transition-colors ${
                    i === pairIndex
                      ? "border-foreground bg-foreground text-background"
                      : "border-foreground/30 hover:border-foreground"
                  }`}
                >
                  {variantLabel(a)} → {variantLabel(b)}
                  {PAIR_QUESTIONS[`${a}→${b}`] && (
                    <span className="ml-2 font-normal opacity-70">
                      {PAIR_QUESTIONS[`${a}→${b}`]}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {paired ? (
          <>
            <ModelIntervals
              estimates={(pair ?? []).map((v) => ({
                name: v,
                label: variantLabel(v),
                f1: paired.per_model[v].f1,
                ci95: paired.per_model[v].ci95,
                tone: toneOf(v),
              }))}
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
            {!pending && pair && (
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                magda significance --compare {pair[0]} {pair[1]} --labels-from sonnet-5
              </code>
            )}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function EntityTable({
  rows, variants, pair, metric, sort, onSort,
}: {
  rows: Row[]
  variants: string[]
  pair: [string, string] | undefined
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
            {variants.map((v) => head(v, `${variantLabel(v)} ${METRIC_LABELS[metric]}`))}
            {/* Δ nennt sein Paar: mit vier Spalten ist sonst nicht ablesbar,
                welche zwei voneinander abgezogen wurden. */}
            {head("delta", pair ? `Δ ${variantLabel(pair[0])}→${variantLabel(pair[1])}` : "Δ")}
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
              {variants.map((v) => (
                <TableCell key={v} className="text-right tabular-nums">
                  {fmt(row.values[v])}
                </TableCell>
              ))}
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
