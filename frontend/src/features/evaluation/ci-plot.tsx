/**
 * Konfidenzintervalle als Balken auf einer gemeinsamen Achse.
 *
 * Der Grund für dieses Bauteil steht in CLAUDE.md: Frühere Zahlen sahen nach
 * einem klaren Ergebnis aus, weil das Intervall fehlte. Zwei Punktschätzer
 * nebeneinander laden zum Vergleich ein, auch wenn der Abstand kleiner ist als
 * die Unsicherheit. Auf einer gemeinsamen Achse *sieht* man die Überlappung,
 * und das ist schwerer zu übersehen als eine Zahl in Klammern.
 */

interface Domain {
  min: number
  max: number
}

function position(value: number, domain: Domain): number {
  const span = domain.max - domain.min
  if (span <= 0) return 0
  return ((value - domain.min) / span) * 100
}

/** Ein Intervall auf der Achse, mit dem Punktschätzer als Marke. */
function IntervalBar({
  lo, hi, point, domain, tone,
}: {
  lo: number
  hi: number
  point: number
  domain: Domain
  tone: string
}) {
  const left = position(lo, domain)
  const right = position(hi, domain)
  return (
    <div className="relative h-6">
      <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border" />
      <div
        className={`absolute top-1/2 h-2 -translate-y-1/2 rounded-full ${tone}`}
        style={{ left: `${left}%`, width: `${Math.max(right - left, 0.5)}%` }}
      />
      {/* Der Punktschätzer als senkrechter Strich: ein Punkt auf dem Balken
          verschwindet, sobald das Intervall schmal wird. */}
      <div
        className="absolute top-1/2 h-5 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded bg-foreground"
        style={{ left: `${position(point, domain)}%` }}
      />
    </div>
  )
}

function Axis({ domain, ticks }: { domain: Domain; ticks: number[] }) {
  return (
    <div className="relative h-4">
      {ticks.map((t) => (
        <span
          key={t}
          className="absolute -translate-x-1/2 font-mono text-[10px] tabular-nums text-muted-foreground"
          style={{ left: `${position(t, domain)}%` }}
        >
          {t.toFixed(2)}
        </span>
      ))}
    </div>
  )
}

export interface Estimate {
  name: string
  label: string
  f1: number
  ci95: [number, number]
  tone: string
}

/** Die beiden Modelle auf einer Achse – die Frage ist, ob sich die Balken überlappen. */
export function ModelIntervals({ estimates }: { estimates: Estimate[] }) {
  const values = estimates.flatMap((e) => [e.ci95[0], e.ci95[1]])
  const pad = (Math.max(...values) - Math.min(...values)) * 0.15 || 0.01
  const domain = { min: Math.min(...values) - pad, max: Math.max(...values) + pad }
  const ticks = [domain.min, (domain.min + domain.max) / 2, domain.max]

  return (
    <div className="space-y-2">
      {estimates.map((e) => (
        <div key={e.name} className="grid grid-cols-[8.5rem_1fr] items-center gap-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{e.label}</div>
            <div className="font-mono text-[11px] tabular-nums text-muted-foreground">
              {e.f1.toFixed(4)} [{e.ci95[0].toFixed(3)}, {e.ci95[1].toFixed(3)}]
            </div>
          </div>
          <IntervalBar lo={e.ci95[0]} hi={e.ci95[1]} point={e.f1} domain={domain} tone={e.tone} />
        </div>
      ))}
      <div className="grid grid-cols-[8.5rem_1fr] gap-3">
        <span />
        <Axis domain={domain} ticks={ticks} />
      </div>
    </div>
  )
}

/**
 * Die gepaarte Differenz mit der Null als Bezugslinie.
 *
 * Gepaart, weil beide Modelle auf denselben Clustern gemessen wurden – die
 * Differenz je Cluster hat weniger Streuung als die zwei Einzelschätzer.
 * Deshalb kann ihr Intervall schmaler sein als die Überlappung oben vermuten
 * lässt, und deshalb steht es hier separat.
 */
export function DifferencePlot({
  difference, ci95, pValue,
}: {
  difference: number
  ci95: [number, number]
  pValue: number
}) {
  const reach = Math.max(Math.abs(ci95[0]), Math.abs(ci95[1]), Math.abs(difference)) * 1.25
  const domain = { min: -reach, max: reach }
  const coversZero = ci95[0] <= 0 && ci95[1] >= 0

  return (
    <div className="space-y-1">
      <div className="relative h-7">
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border" />
        {/* Die Nulllinie ist der ganze Punkt der Grafik: liegt sie im Balken,
            ist kein Effekt nachweisbar. */}
        <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 border-l-2 border-dashed border-foreground/50" />
        <div
          className={`absolute top-1/2 h-2.5 -translate-y-1/2 rounded-full ${coversZero ? "bg-muted-foreground/50" : "bg-primary"}`}
          style={{
            left: `${position(ci95[0], domain)}%`,
            width: `${Math.max(position(ci95[1], domain) - position(ci95[0], domain), 0.5)}%`,
          }}
        />
        <div
          className="absolute top-1/2 h-6 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded bg-foreground"
          style={{ left: `${position(difference, domain)}%` }}
        />
      </div>
      <div className="flex justify-between font-mono text-[10px] tabular-nums text-muted-foreground">
        <span>{domain.min.toFixed(3)}</span>
        <span>0 · kein Unterschied</span>
        <span>+{domain.max.toFixed(3)}</span>
      </div>
      <p className="pt-1 text-sm">
        Differenz{" "}
        <span className="font-mono font-semibold tabular-nums">
          {difference >= 0 ? "+" : ""}{difference.toFixed(4)}
        </span>{" "}
        <span className="font-mono text-muted-foreground tabular-nums">
          [{ci95[0].toFixed(4)}, {ci95[1].toFixed(4)}]
        </span>
        , p = <span className="font-mono tabular-nums">{pValue.toFixed(3)}</span>
      </p>
    </div>
  )
}
