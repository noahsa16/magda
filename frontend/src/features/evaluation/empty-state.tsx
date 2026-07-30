import { ArrowRight } from "lucide-react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"

/** Skizze des Balkenpaars, das hier später mit echten Zahlen steht. */
function ChartSketch() {
  const bars = [
    { entity: "PRODUCT", a: 0.62, b: 0.78 },
    { entity: "PRICE", a: 0.71, b: 0.91 },
    { entity: "BRAND", a: 0.55, b: 0.7 },
    { entity: "QUANTITY", a: 0.48, b: 0.66 },
  ]
  return (
    <div className="flex h-40 items-end gap-6" aria-hidden>
      {bars.map((b) => (
        <div key={b.entity} className="flex flex-1 flex-col items-center gap-1">
          <div className="flex h-32 w-full items-end justify-center gap-1">
            <div className="w-1/3 rounded-t-sm bg-muted-foreground/25" style={{ height: `${b.a * 100}%` }} />
            <div className="w-1/3 rounded-t-sm bg-muted-foreground/40" style={{ height: `${b.b * 100}%` }} />
          </div>
          <span className="font-mono text-[10px] text-muted-foreground">{b.entity}</span>
        </div>
      ))}
    </div>
  )
}

export function EvaluationEmptyState() {
  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <h2 className="text-xl font-bold tracking-tight">
            Hier steht später die Antwort auf die Forschungsfrage
          </h2>
          <p className="text-muted-foreground">
            Gemessen wird auf Entity-Ebene mit seqeval: ein Angebot zählt nur als Treffer, wenn
            Span <em>und</em> Typ exakt stimmen. Das ist strenger als Token-Genauigkeit und
            entspricht dem, was im Proposal steht.
          </p>
          <p className="text-muted-foreground">
            Sobald beide Varianten ausgewertet sind, vergleicht diese Seite sie Balken für Balken
            pro Entity-Typ. Die Differenz im F1 zwischen{" "}
            <span className="font-mono text-xs">layoutxlm</span> (Text und Position) und{" "}
            <span className="font-mono text-xs">gbert</span> (nur Text) ist das eigentliche
            Ergebnis des Projekts.
          </p>
          <Button asChild>
            <Link to="/">
              Training auf der Übersicht starten <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>

        <div className="rounded-lg border-2 border-dashed border-foreground/30 p-4">
          <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            Vorschau · Beispielwerte
          </p>
          <ChartSketch />
        </div>
      </div>

      <ol className="grid gap-3 border-t-2 border-foreground pt-5 sm:grid-cols-3">
        {[
          { n: "01", t: "Seiten labeln", d: "Mindestens ein paar Dutzend Seiten in data/labeled." },
          { n: "02", t: "Beide Modelle trainieren", d: "layoutxlm und gbert, sonst fehlt der Vergleich." },
          { n: "03", t: "Auswerten", d: "Schreibt je einen Report nach data/eval." },
        ].map((s) => (
          <li key={s.n} className="flex gap-3">
            <span className="font-mono text-sm font-bold text-primary">{s.n}</span>
            <div>
              <p className="text-sm font-semibold">{s.t}</p>
              <p className="text-xs text-muted-foreground">{s.d}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
