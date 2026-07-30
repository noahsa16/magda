import {
  BarChart3, CalendarDays, Check, Copy, Cpu, Download, GitCompare,
  Lock, Scale, ScanText, Tags, Target,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import type { StepState } from "../overview/steps"

/**
 * Die Pipeline-Schritte als Anwendungen, nicht als Ordner.
 *
 * Auf der Daten-Seite stehen Ordner, weil man dort etwas öffnet und
 * durchblättert. Hier führt man etwas aus – und ein Programm sieht anders aus
 * als ein Ordner. Deshalb das Quadrat mit abgerundeten Ecken, der Punkt
 * darunter für „läuft gerade" und das Häkchen für „schon erledigt".
 */

interface AppDef {
  icon: LucideIcon
  /** Grundton der Kachel. Aus der Riso-Palette, damit nichts fremd wirkt. */
  farbe: string
}

/**
 * Die sechs Schritte der Pipeline, in ihrer Reihenfolge, plus die
 * Auswertungswerkzeuge. Wer hier etwas ergänzt, ergänzt auch `jobs.py` –
 * ohne Eintrag dort gibt es den Schritt nicht.
 */
export const PIPELINE = ["harvest", "extract", "dedupe", "label", "train", "eval"]
export const WERKZEUGE = ["download", "gold", "agreement", "flair"]

const APPS: Record<string, AppDef> = {
  harvest: { icon: CalendarDays, farbe: "var(--riso-blue)" },
  extract: { icon: ScanText, farbe: "var(--riso-blue)" },
  dedupe: { icon: Copy, farbe: "var(--riso-yellow)" },
  label: { icon: Tags, farbe: "var(--riso-pink)" },
  train: { icon: Cpu, farbe: "var(--riso-pink)" },
  eval: { icon: BarChart3, farbe: "var(--riso-blue)" },
  download: { icon: Download, farbe: "var(--riso-blue)" },
  gold: { icon: Target, farbe: "var(--riso-yellow)" },
  agreement: { icon: GitCompare, farbe: "var(--riso-yellow)" },
  flair: { icon: Scale, farbe: "var(--riso-yellow)" },
}

export interface AppItem {
  job: string
  title: string
  state: StepState | undefined
  running: boolean
  progress: string | null
}

function AppIcon({ job, state, running }: { job: string; state: StepState | undefined; running: boolean }) {
  const app = APPS[job] ?? { icon: Cpu, farbe: "var(--riso-blue)" }
  const Symbol = app.icon
  const gesperrt = state === "blocked" && !running

  return (
    <span className="relative">
      <span
        className={cn(
          "flex size-16 items-center justify-center rounded-[1.15rem] border-2 border-foreground",
          "shadow-[3px_3px_0_0_var(--color-foreground)] transition-transform duration-150",
          "group-hover:-translate-y-0.5 group-active:translate-y-0 group-active:shadow-none",
          gesperrt && "opacity-40 shadow-none",
        )}
        style={{ backgroundColor: app.farbe }}
      >
        <Symbol className="size-7 text-white" strokeWidth={2.25} />
      </span>

      {/* Häkchen und Schloss sitzen auf der Kachel wie ein Badge am App-Icon. */}
      {state === "done" && !running && (
        <span className="absolute -right-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full border-2 border-foreground bg-card">
          <Check className="size-3 text-[var(--riso-blue)]" strokeWidth={3} />
        </span>
      )}
      {gesperrt && (
        <span className="absolute -right-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full border-2 border-foreground bg-card">
          <Lock className="size-2.5 text-muted-foreground" strokeWidth={3} />
        </span>
      )}
    </span>
  )
}

export function AppGrid({
  items,
  onOpen,
  klein,
}: {
  items: AppItem[]
  onOpen: (job: string) => void
  /** Werkzeugreihe: dieselbe Kachel, nur zurückhaltender. */
  klein?: boolean
}) {
  return (
    <div
      className={cn(
        "grid gap-2",
        klein
          ? "grid-cols-3 sm:grid-cols-5 lg:grid-cols-8"
          : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6",
      )}
    >
      {items.map((item) => (
        <button
          key={item.job}
          type="button"
          onClick={() => onOpen(item.job)}
          title={item.title}
          className={cn(
            "group flex flex-col items-center gap-2 rounded-xl px-2 py-4",
            "transition-colors hover:bg-accent focus-visible:bg-accent focus-visible:outline-none",
          )}
        >
          <AppIcon job={item.job} state={item.state} running={item.running} />

          <span className="line-clamp-2 max-w-full text-center text-[13px] font-semibold leading-tight">
            {item.title}
          </span>

          {item.progress && !item.running && (
            <span className="text-center font-mono text-[10px] leading-tight text-muted-foreground">
              {item.progress}
            </span>
          )}

          {/* Der laufende Punkt aus dem Dock – die einzige Stelle, an der sich
              auf dieser Seite etwas bewegt. */}
          {item.running && (
            <span className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-primary">
              <span className="size-1.5 animate-pulse rounded-full bg-primary" />
              läuft
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
