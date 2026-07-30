import { entityColor } from "@/lib/entities"
import { cn } from "@/lib/utils"

interface LabelLegendProps {
  entityTypes: string[]
  /** Anzahl fertig annotierter Seiten und Gesamtzahl. */
  done: number
  total: number
  /** Seiten mit veralteter Wortliste oder unlesbarer Datei. Die zählen nicht
   * als fertig, sonst meldet der Fortschritt Arbeit, die keine mehr ist. */
  invalid: number
}

export function LabelLegend({ entityTypes, done, total, invalid }: LabelLegendProps) {
  return (
    <div className="space-y-3 rounded-lg border-2 border-foreground bg-card p-4">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          Fortschritt
        </p>
        <p className="font-mono text-sm font-semibold tabular-nums">
          {done} / {total} Seiten fertig
        </p>
        {invalid > 0 && (
          <p
            className="font-mono text-xs font-semibold tabular-nums text-destructive"
            title="Wortliste geändert oder Gold-Datei unlesbar"
          >
            {invalid} {invalid === 1 ? "Seite" : "Seiten"} ungültig
          </p>
        )}
      </div>

      <ul className="space-y-1">
        {entityTypes.map((type, i) => (
          <li key={type} className="flex items-center gap-2">
            <kbd className="w-5 rounded border border-foreground bg-background text-center font-mono text-[11px]">
              {i + 1}
            </kbd>
            <span
              className="size-3 shrink-0 rounded-sm"
              style={{ backgroundColor: entityColor(entityTypes, type) }}
            />
            <span className="font-mono text-xs">{type}</span>
          </li>
        ))}
      </ul>

      <dl className="space-y-0.5 border-t border-border pt-2 font-mono text-[11px] text-muted-foreground">
        {[
          ["Klick", "Wort wählen"],
          ["Shift-Klick", "Auswahl erweitern"],
          ["0 / Entf", "Label entfernen"],
          ["← →", "Seite wechseln"],
          ["f", "Seite fertig"],
        ].map(([key, desc]) => (
          <div key={key} className={cn("flex justify-between gap-2")}>
            <dt className="font-semibold">{key}</dt>
            <dd>{desc}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
