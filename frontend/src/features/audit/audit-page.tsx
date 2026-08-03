import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import type { AuditCandidate, AuditReport } from "@/lib/types"
import { SpanCrop } from "./span-crop"

const LABEL = "APP_PRICE"

type Filter = "likely_missing" | "check" | "low" | "judged" | "all"

const FILTERS: { key: Filter; title: string; hint: string }[] = [
  { key: "likely_missing", title: "Fehlt vermutlich", hint: "Preis auf App-Hintergrund, aber nicht so gelabelt" },
  { key: "check", title: "Gegenprüfen", hint: "Trägt das Label bereits" },
  { key: "low", title: "Vermutlich richtig", hint: "Streichpreis im App-Kasten – bleibt OLD_PRICE" },
  { key: "judged", title: "Beurteilt", hint: "Schon entschieden" },
  { key: "all", title: "Alle", hint: "" },
]

/** Zwei Kandidaten mit gleichem Wortlaut sind dieselbe Vorlage aus 44 Regionen. */
function visible(report: AuditReport, filter: Filter): AuditCandidate[] {
  const judged = (c: AuditCandidate) => Boolean(report.verdicts[c.key])
  return report.candidates
    .filter((c) => !c.duplicate_of)
    .filter((c) => {
      if (filter === "all") return true
      if (filter === "judged") return judged(c)
      return c.priority === filter && !judged(c)
    })
    .sort((a, b) => b.duplicates - a.duplicates)
}

export function AuditPage() {
  const [filter, setFilter] = useState<Filter>("likely_missing")
  const queryClient = useQueryClient()
  const { data, isPending, error } = useQuery({
    queryKey: ["audit", LABEL],
    queryFn: () => api.audit(LABEL),
  })

  const save = useMutation({
    mutationFn: ({ key, verdict }: { key: string; verdict: "correct" | "wrong" | "unsure" }) =>
      api.saveVerdict(LABEL, key, { verdict, apply_to_duplicates: true }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["audit", LABEL] }),
  })

  const rows = useMemo(() => (data ? visible(data, filter) : []), [data, filter])

  if (isPending) return <Skeleton className="h-64 w-full" />
  if (error || !data) {
    return (
      <div className="space-y-4">
        <h1 className="text-3xl font-extrabold tracking-tight">Label-Prüfung</h1>
        <Card>
          <CardContent className="space-y-2 py-6 text-sm text-muted-foreground">
            <p>Für {LABEL} ist nichts vorsortiert.</p>
            <code className="block rounded bg-muted px-2 py-1 font-mono text-xs">
              magda audit {LABEL} --labels-from sonnet-5
            </code>
          </CardContent>
        </Card>
      </div>
    )
  }

  const { summary } = data
  const unique = data.candidates.filter((c) => !c.duplicate_of).length

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight">Label-Prüfung · {LABEL}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Vorsortiert aus <span className="font-mono">{data.labels_from}</span> nach der
          Hintergrundfarbe an der Wortposition. Die Farbe schlägt vor, entschieden wird hier –
          die Labels bleiben unberührt, bis jemand die Urteile übernimmt.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-6 py-4">
          <div className="min-w-52 flex-1">
            <div className="mb-1 flex justify-between text-sm">
              <span className="text-muted-foreground">Durchgesehen</span>
              <span className="font-medium">
                {summary.judged} von {summary.total}
              </span>
            </div>
            <Progress value={(summary.judged / Math.max(summary.total, 1)) * 100} />
            <p className="mt-1 text-xs text-muted-foreground">
              {unique} verschiedene Vorlagen – ein Urteil gilt für alle Regionalausgaben.
            </p>
          </div>
          <div className="flex gap-5 text-sm">
            <Stat label="richtig" value={summary.correct} tone="text-emerald-600" />
            <Stat label="falsch" value={summary.wrong} tone="text-red-600" />
            <Stat label="unsicher" value={summary.unsure} tone="text-amber-600" />
          </div>
        </CardContent>
      </Card>

      <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
        <TabsList>
          {FILTERS.map((f) => (
            <TabsTrigger key={f.key} value={f.key} title={f.hint}>
              {f.title}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {rows.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Nichts mehr in dieser Gruppe.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {rows.map((candidate) => (
            <CandidateRow
              key={candidate.key}
              candidate={candidate}
              verdict={data.verdicts[candidate.key]?.verdict}
              pending={save.isPending && save.variables?.key === candidate.key}
              onJudge={(verdict) => save.mutate({ key: candidate.key, verdict })}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="text-center">
      <div className={`text-xl font-bold tabular-nums ${tone}`}>{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  )
}

function CandidateRow({
  candidate,
  verdict,
  pending,
  onJudge,
}: {
  candidate: AuditCandidate
  verdict?: "correct" | "wrong" | "unsure"
  pending: boolean
  onJudge: (verdict: "correct" | "wrong" | "unsure") => void
}) {
  const [before, span, after] = splitContext(candidate.context)
  return (
    <Card className={verdict ? "opacity-60" : ""}>
      <CardContent className="flex flex-wrap items-center gap-4 py-4">
        <SpanCrop candidate={candidate} />

        <div className="min-w-64 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={candidate.source === "labeled" ? "default" : "secondary"}>
              {candidate.current_label}
            </Badge>
            {candidate.split && <Badge variant="outline">{candidate.split}</Badge>}
            {candidate.duplicates > 1 && (
              <Badge variant="outline">{candidate.duplicates}× im Korpus</Badge>
            )}
            {candidate.app_in_context ? (
              <Badge variant="outline">„App" im Text</Badge>
            ) : (
              <Badge variant="outline" className="text-muted-foreground">
                nur im Bild erkennbar
              </Badge>
            )}
            <span className="font-mono text-xs text-muted-foreground">{candidate.page_id}</span>
          </div>

          <p className="text-sm leading-relaxed">
            <span className="text-muted-foreground">{before}</span>
            <span className="mx-1 rounded bg-primary/15 px-1.5 py-0.5 font-semibold">{span}</span>
            <span className="text-muted-foreground">{after}</span>
          </p>

          {candidate.background && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span
                className="inline-block size-3 rounded-sm border"
                style={{ background: `rgb(${candidate.background.join(",")})` }}
              />
              Hintergrund rgb({candidate.background.join(", ")})
              {candidate.color_distance != null && ` · Abstand zum App-Ton ${candidate.color_distance}`}
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <Button
            size="sm"
            variant={verdict === "correct" ? "default" : "outline"}
            disabled={pending}
            onClick={() => onJudge("correct")}
          >
            Stimmt
          </Button>
          <Button
            size="sm"
            variant={verdict === "wrong" ? "destructive" : "outline"}
            disabled={pending}
            onClick={() => onJudge("wrong")}
          >
            Falsch
          </Button>
          <Button
            size="sm"
            variant={verdict === "unsure" ? "secondary" : "outline"}
            disabled={pending}
            onClick={() => onJudge("unsure")}
          >
            Unsicher
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

/** Der Kontext trägt «…» um den Span – daraus drei Teile für die Hervorhebung. */
function splitContext(context: string): [string, string, string] {
  const open = context.indexOf("«")
  const close = context.indexOf("»")
  if (open < 0 || close < 0) return ["", context, ""]
  return [
    context.slice(0, open),
    context.slice(open + 1, close),
    context.slice(close + 1),
  ]
}
