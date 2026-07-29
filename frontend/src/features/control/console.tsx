import { useEffect, useRef } from "react"

export function Console({ lines, running }: { lines: string[]; running: boolean }) {
  const endRef = useRef<HTMLDivElement>(null)

  // Immer die letzte Zeile zeigen – bei einem Lauf über tausende Seiten ist
  // das Ende die einzige interessante Stelle.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" })
  }, [lines.length])

  return (
    <div className="max-h-[28rem] overflow-y-auto rounded-md bg-foreground p-4 font-mono text-xs leading-relaxed text-background">
      {lines.length === 0 && (
        <p className="text-background/50">
          {running ? "Warte auf Ausgabe…" : "Noch keine Ausgabe."}
        </p>
      )}
      {lines.map((line, i) => (
        <div key={i} className="whitespace-pre-wrap break-all">
          {line}
        </div>
      ))}
      {running && <span className="inline-block animate-pulse text-primary">▊</span>}
      <div ref={endRef} />
    </div>
  )
}
