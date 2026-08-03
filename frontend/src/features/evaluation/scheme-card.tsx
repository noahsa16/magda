import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { EvalReport, SchemeCounts, SchemeKey } from "@/lib/types"
import { SCHEMES, errorComposition, schemeRows } from "./transform"

/**
 * Was das jeweilige Schema durchgehen lässt – und was das über unsere Daten sagt.
 *
 * Die zweite Hälfte ist der eigentliche Zweck: Vier Zahlen nebeneinander sind
 * nur dann mehr als Dekoration, wenn dabei steht, welche Frage jede von ihnen
 * beantwortet.
 */
const SCHEME_INFO: Record<SchemeKey, { title: string; rule: string; reads: string }> = {
  strict: {
    title: "strict",
    rule: "Grenze und Typ müssen exakt stimmen.",
    reads: "Das ist seqeval und bleibt unsere Hauptzahl. Ein Span, der den Sortenzusatz mitnimmt, zählt hier komplett als Fehler – doppelt sogar, als übersehen und als erfunden.",
  },
  exact: {
    title: "exact",
    rule: "Grenze exakt, der Typ wird ignoriert.",
    reads: "Findet das Modell die richtige Stelle? Der Abstand zu strict ist reine Typverwechslung – bei uns vor allem PRICE gegen APP_PRICE.",
  },
  partial: {
    title: "partial",
    rule: "Überlappung genügt, Teiltreffer zählen 0.5 (MUC-Konvention).",
    reads: "Der Abstand zu strict beziffert das Grenzproblem. Bei uns ist das fast nur die offene Frage, wo ein PRODUCT-Span endet.",
  },
  type: {
    title: "type",
    rule: "Typ muss stimmen, die Grenze darf überlappen.",
    reads: "Die nachsichtigste Sicht auf die Frage, um die es fachlich geht: Ist der Preis als Preis erkannt? Für die Weiterverarbeitung zu Angeboten ist das oft die relevantere Zahl.",
  },
}

const PART_TONES: Record<string, string> = {
  correct: "bg-emerald-500",
  partial: "bg-amber-400",
  incorrect: "bg-orange-500",
  missing: "bg-slate-400",
  spurious: "bg-red-500",
}

const fmt = (v: number | undefined) => (v == null ? "–" : v.toFixed(3))

/** Woraus sich das Ergebnis zusammensetzt, als gestapelter Balken. */
function Composition({ counts }: { counts: SchemeCounts }) {
  const composition = errorComposition(counts)
  if (!composition) return null
  return (
    <div className="space-y-1.5">
      <div className="flex h-3 overflow-hidden rounded-full border">
        {composition.parts.map((p) => (
          <div
            key={p.key}
            className={PART_TONES[p.key]}
            style={{ width: `${(p.value / composition.total) * 100}%` }}
            title={`${p.label}: ${p.value}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
        {composition.parts.map((p) => (
          <span key={p.key} className="flex items-center gap-1">
            <span className={`inline-block size-2 rounded-sm ${PART_TONES[p.key]}`} />
            {p.label} <span className="font-mono tabular-nums">{p.value}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

function ModelPanel({
  label, counts,
}: {
  label: string
  counts: SchemeCounts | undefined
}) {
  if (!counts) {
    return (
      <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
        {label} – nicht ausgewertet
      </div>
    )
  }
  return (
    <div className="space-y-3 rounded-md border p-4">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold">{label}</span>
        <span className="font-mono text-2xl font-extrabold tabular-nums">{fmt(counts.f1)}</span>
      </div>
      <div className="flex gap-4 font-mono text-xs tabular-nums text-muted-foreground">
        <span>P {fmt(counts.precision)}</span>
        <span>R {fmt(counts.recall)}</span>
        <span>
          {counts.possible} Referenz · {counts.actual} vorhergesagt
        </span>
      </div>
      <Composition counts={counts} />
    </div>
  )
}

export function SchemeCard({ reports }: { reports: EvalReport[] }) {
  const [scheme, setScheme] = useState<SchemeKey>("strict")
  const rows = schemeRows(reports)
  if (rows.length === 0) return null

  const active = rows.find((r) => r.scheme === scheme)
  const info = SCHEME_INFO[scheme]
  const source = reports.find((r) => r.matching_scheme_source)?.matching_scheme_source

  return (
    <Card className="border-2 border-foreground">
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="font-bold">Matching-Schemata</CardTitle>
          <Tabs value={scheme} onValueChange={(v) => setScheme(v as SchemeKey)}>
            <TabsList>
              {SCHEMES.map((s) => (
                <TabsTrigger key={s} value={s} className="font-mono text-xs">
                  {s}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
        <p className="text-sm text-muted-foreground">
          {source ?? "SemEval-2013 Task 9.1"} – vier Sichten auf dieselbe Vorhersage.
          Ein einzelner F1 verschweigt, ob ein Fehler eine falsche Stelle oder nur
          eine falsche Grenze war.
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-md border-l-4 border-primary bg-muted/40 px-4 py-3">
          <p className="text-sm">
            <span className="font-mono font-semibold">{info.title}</span> — {info.rule}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{info.reads}</p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <ModelPanel label="GBERT" counts={active?.gbert} />
          <ModelPanel label="LayoutXLM" counts={active?.layoutxlm} />
        </div>

        {/* Die Tabelle zeigt, was die Tabs nacheinander zeigen, auf einen Blick.
            Der Sprung von strict nach partial ist die Größe des Grenzproblems –
            der sieht man erst an, wenn alle vier Zeilen untereinander stehen. */}
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Schema</TableHead>
                <TableHead className="text-right">GBERT F1</TableHead>
                <TableHead className="text-right">LayoutXLM F1</TableHead>
                <TableHead className="text-right">Δ</TableHead>
                <TableHead className="hidden text-right sm:table-cell">gegen strict</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const base = rows.find((r) => r.scheme === "strict")?.gbert?.f1
                const gain = base != null && row.gbert ? row.gbert.f1 - base : null
                const delta =
                  row.gbert && row.layoutxlm ? row.layoutxlm.f1 - row.gbert.f1 : null
                return (
                  <TableRow
                    key={row.scheme}
                    className={row.scheme === scheme ? "bg-muted/60" : "cursor-pointer"}
                    onClick={() => setScheme(row.scheme)}
                  >
                    <TableCell className="font-mono">{row.scheme}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt(row.gbert?.f1)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt(row.layoutxlm?.f1)}</TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums text-muted-foreground">
                      {delta == null ? "–" : `${delta >= 0 ? "+" : ""}${delta.toFixed(3)}`}
                    </TableCell>
                    <TableCell className="hidden text-right font-mono text-xs tabular-nums text-muted-foreground sm:table-cell">
                      {gain == null || row.scheme === "strict"
                        ? "–"
                        : `+${gain.toFixed(3)}`}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
