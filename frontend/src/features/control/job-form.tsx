import { Play } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { JobDef } from "@/lib/types"

/**
 * Startwerte eines Schritts, alles als String.
 *
 * Ein Formularfeld liefert ohnehin nur Strings, und die Typkonvertierung
 * gehört ins Backend – `jobs.build_command` ist die Stelle, die entscheidet,
 * was eine gültige Zahl ist.
 */
export function defaultValues(job: JobDef): Record<string, string> {
  return Object.fromEntries(
    job.params.map((p) => [
      p.key,
      // Ein Schalter startet immer aus. Ein Default "an" hiesse, dass ein
      // unbedachter Klick loeschen koennte.
      p.kind === "flag" ? "" : p.default == null ? "" : String(p.default),
    ]),
  )
}

/** Labels der leeren Pflichtfelder. Leer = startbar. */
export function missingRequired(job: JobDef, values: Record<string, string>): string[] {
  return job.params
    .filter((p) => p.required && !(values[p.key] ?? "").trim())
    .map((p) => p.label)
}

interface JobFormProps {
  job: JobDef
  values: Record<string, string>
  onChange: (key: string, value: string) => void
  onStart: (values: Record<string, string>) => void
  disabled: boolean
}

export function JobForm({ job, values, onChange, onStart, disabled }: JobFormProps) {
  const missing = missingRequired(job, values)

  return (
    <div className="space-y-3">
      {job.params.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {job.params.map((param) => {
            const id = `${job.job}-${param.key}`
            return (
              <div key={param.key} className="space-y-1">
                <label
                  htmlFor={id}
                  className="block font-mono text-[11px] uppercase tracking-widest text-muted-foreground"
                >
                  {param.label}
                  {param.required && <span className="text-destructive"> *</span>}
                </label>
                {param.kind === "flag" ? (
                  <label className="flex h-9 items-center gap-2 text-sm">
                    <input
                      id={id}
                      type="checkbox"
                      checked={values[param.key] === "true"}
                      onChange={(e) => onChange(param.key, e.target.checked ? "true" : "")}
                      className="size-4 accent-[var(--riso-blue)]"
                    />
                    <span className="text-muted-foreground">{param.help || "aktivieren"}</span>
                  </label>
                ) : param.kind === "choice" ? (
                  <select
                    id={id}
                    value={values[param.key] ?? ""}
                    onChange={(e) => onChange(param.key, e.target.value)}
                    className="h-9 w-full rounded-md border-2 border-foreground bg-card px-2 text-sm"
                  >
                    <option value="">– wählen –</option>
                    {param.choices.map((choice) => (
                      <option key={choice} value={choice}>
                        {choice}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    id={id}
                    value={values[param.key] ?? ""}
                    inputMode={param.kind === "str" ? "text" : "decimal"}
                    placeholder={param.help}
                    onChange={(e) => onChange(param.key, e.target.value)}
                  />
                )}
              </div>
            )
          })}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" disabled={disabled || missing.length > 0} onClick={() => onStart(values)}>
          <Play className="size-3.5" /> Starten
        </Button>
        {missing.length > 0 && (
          <p className="text-xs text-muted-foreground">Fehlt noch: {missing.join(", ")}</p>
        )}
      </div>
    </div>
  )
}
