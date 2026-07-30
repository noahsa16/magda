import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

/** Farbe nach Güte – der Blick soll die schwache Stelle finden, nicht die Zahl lesen. */
function toneFor(value: number | null) {
  if (value === null) return "text-muted-foreground"
  if (value >= 0.8) return "text-foreground"
  if (value >= 0.5) return "text-foreground/70"
  return "text-destructive"
}

function Cell({ value }: { value: number | null }) {
  return (
    <td className={cn("px-2 py-1.5 text-right font-mono text-xs tabular-nums", toneFor(value))}>
      {value === null ? "–" : value.toFixed(2)}
    </td>
  )
}

/**
 * Rangfolge der Labeling-Modelle gegen die handannotierte Referenz.
 *
 * Beantwortet die Frage, für die `gold/` überhaupt existiert: welches Modell
 * labelt am nächsten an dem, was ein Mensch markiert hätte? Die Aufschlüsselung
 * je Entity-Typ steht daneben, weil ein micro-F1 nicht verrät, *wo* ein Modell
 * verliert – ein Modell mit starken Preisen und schwachen Marken sieht in der
 * Summe aus wie eines, das überall mittelmäßig ist.
 */
export function LabelerComparison() {
  const { data } = useQuery({ queryKey: ["labelsVsGold"], queryFn: () => api.labelsVsGold() })
  const results = data?.results ?? []
  if (results.length === 0) return null

  // Nur Typen zeigen, die überhaupt vorkommen – eine Spalte voller "–" ist
  // Rauschen, und das Label-Set wächst hinten.
  const labels = [...new Set(results.flatMap((r) => Object.keys(r.per_label)))]

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold tracking-tight">
        Labeling-Modelle gegen Gold
        <span className="ml-2 font-mono text-[11px] font-normal text-muted-foreground">
          {data?.gold_pages.length ?? 0} Referenzseiten
        </span>
      </h2>
      <div className="overflow-x-auto rounded-xl border-2 border-foreground bg-card">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b-2 border-foreground">
              <th className="px-3 py-2 text-left font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                Modell
              </th>
              <th className="px-2 py-2 text-right font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                F1
              </th>
              {labels.map((label) => (
                <th
                  key={label}
                  className="px-2 py-2 text-right font-mono text-[10px] uppercase tracking-widest text-muted-foreground"
                >
                  {label.replace("_", " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {results.map((row) => (
              <tr key={row.model}>
                <td className="px-3 py-1.5 font-mono text-xs">{row.model}</td>
                <td className="px-2 py-1.5 text-right font-mono text-xs font-bold tabular-nums">
                  {row.f1 === null ? "–" : row.f1.toFixed(3)}
                </td>
                {labels.map((label) => (
                  <Cell key={label} value={row.per_label[label] ?? null} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted-foreground">
        Entity-Level-F1 über {data?.gold_pages.length ?? 0} handannotierte Seiten. Große
        Unterschiede sind aussagekräftig, kleine nicht – bei dieser Basis bewegt eine
        einzelne Entität den Wert um mehrere Punkte. Aktualisiert sich, wenn{" "}
        <code>08_compare_labels.py</code> läuft.
      </p>
    </section>
  )
}
