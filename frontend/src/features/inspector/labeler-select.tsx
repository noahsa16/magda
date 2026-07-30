import { useQuery } from "@tanstack/react-query"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { api } from "@/lib/api"

/**
 * Auswahl, wessen Labels der Inspektor zeigt.
 *
 * Rendert nichts, solange nur ein Modell gelabelt hat: eine Auswahl mit genau
 * einem Eintrag ist kein Werkzeug, sondern Deko. Sichtbar wird sie in dem
 * Moment, in dem es tatsächlich etwas zu vergleichen gibt.
 */
export function LabelerSelect({
  value,
  onChange,
}: {
  value: string | undefined
  onChange: (model: string) => void
}) {
  const labelers = useQuery({ queryKey: ["labelers"], queryFn: () => api.labelers() })
  const options = labelers.data ?? []
  if (options.length < 2) return null

  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        Labels von
      </span>
      <Select value={value ?? options[0].model} onValueChange={onChange}>
        <SelectTrigger className="h-8 w-[230px] font-mono text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.model} value={option.model} className="font-mono text-xs">
              {option.model}
              <span className="ml-2 text-muted-foreground">{option.pages} S.</span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
