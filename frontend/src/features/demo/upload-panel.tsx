import { Play, Upload } from "lucide-react"
import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

type Variant = "gbert" | "layoutxlm"

const VARIANTS: { value: Variant; title: string; subtitle: string }[] = [
  { value: "gbert", title: "gbert", subtitle: "schnell, nur CPU" },
  { value: "layoutxlm", title: "layoutxlm", subtitle: "sieht das Seitenbild" },
]

interface UploadPanelProps {
  variant: Variant
  onVariantChange: (variant: Variant) => void
  onStartFile: (file: File) => void
  onStartUrl: (url: string) => void
  busy: boolean
}

/** Eingabekarte der Demo: PDF per Drag-and-drop oder Dateiauswahl, alternativ
 * eine Penny-Katalog-URL, dazu die Modellwahl. Reiner Formularzustand - was
 * beim Start passiert (Upload/Import, dann der Runner-Job), entscheidet
 * `DemoPage`. */
export function UploadPanel({ variant, onVariantChange, onStartFile, onStartUrl, busy }: UploadPanelProps) {
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState("")
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function pickFile(candidate: File | null) {
    if (!candidate) return
    if (candidate.type !== "application/pdf" && !candidate.name.toLowerCase().endsWith(".pdf")) return
    setFile(candidate)
    setUrl("")
  }

  function changeUrl(value: string) {
    setUrl(value)
    if (value) setFile(null)
  }

  function start() {
    if (file) onStartFile(file)
    else if (url.trim()) onStartUrl(url.trim())
  }

  const canStart = !busy && (file != null || url.trim() !== "")

  return (
    <div className="space-y-4 rounded-xl border-2 border-foreground bg-card p-4">
      <div
        role="button"
        tabIndex={0}
        aria-label="PDF auswählen"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          pickFile(e.dataTransfer.files[0] ?? null)
        }}
        className={cn(
          "flex h-32 cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed text-center transition-colors",
          dragOver ? "border-primary bg-primary/5" : "border-foreground/30 hover:border-foreground/50",
        )}
      >
        <Upload className="size-5 text-muted-foreground" />
        {file ? (
          <p className="max-w-[90%] truncate text-sm font-medium">{file.name}</p>
        ) : (
          <p className="text-sm text-muted-foreground">PDF hierher ziehen oder klicken</p>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          aria-hidden
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
        />
      </div>

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <div className="h-px flex-1 bg-foreground/15" />
        oder
        <div className="h-px flex-1 bg-foreground/15" />
      </div>

      <div className="space-y-1">
        <label
          htmlFor="demo-catalog-url"
          className="block font-mono text-[11px] uppercase tracking-widest text-muted-foreground"
        >
          Penny-Katalog-URL
        </label>
        <Input
          id="demo-catalog-url"
          value={url}
          onChange={(e) => changeUrl(e.target.value)}
          placeholder="https://penny-publish.blaetterkatalog.de/...?catalogId=..."
        />
      </div>

      <div className="space-y-1">
        <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">Modell</p>
        <div className="grid grid-cols-2 gap-2">
          {VARIANTS.map((v) => (
            <button
              key={v.value}
              type="button"
              aria-pressed={variant === v.value}
              onClick={() => onVariantChange(v.value)}
              className={cn(
                "rounded-lg border-2 px-3 py-2 text-left transition-colors",
                variant === v.value
                  ? "border-primary bg-primary/5"
                  : "border-foreground/20 hover:border-foreground/40",
              )}
            >
              <p className="text-sm font-semibold">{v.title}</p>
              <p className="text-xs text-muted-foreground">{v.subtitle}</p>
            </button>
          ))}
        </div>
      </div>

      <Button disabled={!canStart} onClick={start}>
        <Play className="size-3.5" /> Verarbeiten
      </Button>
    </div>
  )
}
