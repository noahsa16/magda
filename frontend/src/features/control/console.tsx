import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

/**
 * Färbt eine Ausgabezeile nach ihrer Rolle.
 *
 * Ein Lauf über tausende Seiten schreibt hunderte Zeilen, und die eine, auf
 * die es ankommt, sieht aus wie alle anderen. Geprüft wird auf die Wortlaute,
 * die unsere Schritte tatsächlich ausgeben – `sys.exit(...)` schreibt keinen
 * Traceback, sondern nur den Text, und ein Abbruch aus dem Bootstrap beginnt
 * mit "ABBRUCH:".
 */
function tonOf(line: string): string {
  if (/^(Traceback|ABBRUCH|FEHLER)|Error|error:|Exception/.test(line)) {
    return "text-[color:var(--riso-pink)]"
  }
  if (/^WARNUNG|Warning|UserWarning/.test(line)) return "text-[color:var(--riso-yellow)]"
  // Abschnittsmarken der Skripte und Shell-Zeilen des Bootstraps
  if (/^(#{3,}|\$ )/.test(line)) return "font-semibold text-background"
  if (/\b(fertig|gespeichert|Fertig)\b/.test(line)) return "text-[color:var(--riso-blue)]"
  return "text-background/70"
}

export function Console({ lines, running }: { lines: string[]; running: boolean }) {
  const endRef = useRef<HTMLDivElement>(null)

  // Immer die letzte Zeile zeigen – bei einem Lauf über tausende Seiten ist
  // das Ende die einzige interessante Stelle.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" })
  }, [lines.length])

  return (
    <div className="overflow-hidden rounded-xl border-2 border-foreground bg-foreground">
      <div className="flex items-center justify-between border-b border-background/15 px-3 py-1.5">
        <span className="font-mono text-[10px] uppercase tracking-widest text-background/50">
          Ausgabe
        </span>
        {lines.length > 0 && (
          <span className="font-mono text-[10px] text-background/40 tabular-nums">
            {lines.length} Zeilen
          </span>
        )}
      </div>
      <div className="max-h-[32rem] overflow-y-auto p-3 font-mono text-xs leading-relaxed">
        {lines.length === 0 && (
          <p className="text-background/40">
            {running ? "Warte auf Ausgabe…" : "Noch keine Ausgabe."}
          </p>
        )}
        {lines.map((line, i) => (
          <div key={i} className={cn("whitespace-pre-wrap break-all", tonOf(line))}>
            {line}
          </div>
        ))}
        {running && <span className="inline-block animate-pulse text-primary">▊</span>}
        <div ref={endRef} />
      </div>
    </div>
  )
}
