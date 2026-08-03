import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { EvalReport, ProtocolKey } from "@/lib/types"
import { hasProtocol, overallF1 } from "./transform"

/**
 * Die drei Auswertungsprotokolle nebeneinander.
 *
 * Sie beantworten verschiedene Fragen, und genau das war der Fehler in der
 * alten Fassung: Das truncated-Protokoll wertete nur aus, was ins 512er-Fenster
 * passte, und Entitäten dahinter fehlten nicht als Falsch-Negative, sondern im
 * Nenner. Die Zahl war nicht falsch berechnet – sie beantwortete "F1 auf den
 * ersten 512 Subwords" und stand als Gesamtergebnis da.
 */
export const PROTOCOLS: { key: ProtocolKey; title: string; hint: string }[] = [
  {
    key: "report",
    title: "windowed",
    hint: "Sliding Window über lange Seiten, gemessen gegen die volle Referenz. Misst das, was magda predict tatsächlich ausliefert – deshalb die Primärmetrik.",
  },
  {
    key: "report_no_windows",
    title: "no-windows",
    hint: "Ohne Fenster, aber gegen dieselbe volle Referenz. Der Abstand zu windowed ist der Wert der Fenster im Einsatz.",
  },
  {
    key: "report_truncated",
    title: "truncated",
    hint: "Das alte Protokoll: nur die Positionen im 512er-Fenster, Entitäten dahinter fehlen auch im Nenner. Steht hier zum Vergleich, nicht zum Berichten.",
  },
]

const fmt = (v: number | null) => (v == null ? "–" : v.toFixed(4))

export function ProtocolCard({
  reports, protocol, onProtocolChange,
}: {
  reports: EvalReport[]
  protocol: ProtocolKey
  onProtocolChange: (p: ProtocolKey) => void
}) {
  const available = PROTOCOLS.filter((p) => hasProtocol(reports, p.key))
  if (available.length < 2) return null

  const active = PROTOCOLS.find((p) => p.key === protocol) ?? PROTOCOLS[0]
  const lost = reports.find((r) => r.words_without_prediction_unwindowed != null)
  const stride = reports.find((r) => r.window_stride != null)?.window_stride

  return (
    <Card className="border-2 border-foreground">
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="font-bold">Auswertungsprotokoll</CardTitle>
          <Tabs value={protocol} onValueChange={(v) => onProtocolChange(v as ProtocolKey)}>
            <TabsList>
              {available.map((p) => (
                <TabsTrigger key={p.key} value={p.key} className="font-mono text-xs">
                  {p.title}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
        <p className="text-sm text-muted-foreground">{active.hint}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          {available.map((p) => {
            const gbert = overallF1(reports, "gbert", p.key)
            const layoutxlm = overallF1(reports, "layoutxlm", p.key)
            return (
              <button
                key={p.key}
                type="button"
                onClick={() => onProtocolChange(p.key)}
                className={`rounded-md border-2 p-3 text-left transition-colors ${
                  p.key === protocol ? "border-foreground bg-muted/50" : "border-border hover:bg-muted/30"
                }`}
              >
                <div className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                  {p.title}
                </div>
                <div className="mt-1 flex gap-4 font-mono text-sm tabular-nums">
                  <span>
                    <span className="text-muted-foreground">G</span> {fmt(gbert)}
                  </span>
                  <span>
                    <span className="text-muted-foreground">L</span> {fmt(layoutxlm)}
                  </span>
                </div>
              </button>
            )
          })}
        </div>

        {lost?.words_without_prediction_unwindowed != null && (
          <p className="text-sm text-muted-foreground">
            Ohne Fenster hätten{" "}
            <span className="font-mono font-semibold text-foreground tabular-nums">
              {lost.words_without_prediction_unwindowed}
            </span>{" "}
            Wörter der Testwoche keine Vorhersage – mit Fenstern (Stride{" "}
            <span className="font-mono">{stride ?? "?"}</span>) sind es null. Das Fenster
            steckt bewusst nur in der Inferenz: im Training wäre es Augmentierung und
            würde die Vergleichbarkeit der Checkpoints verändern.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
