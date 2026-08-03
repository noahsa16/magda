import { useQuery } from "@tanstack/react-query"
import { NavLink } from "react-router-dom"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

// Reihenfolge entlang des Arbeitsflusses: Stand ansehen, Daten erzeugen,
// Daten prüfen und annotieren, Ergebnis lesen.
const items = [
  { title: "Übersicht", url: "/" },
  { title: "Pipeline", url: "/pipeline" },
  // Ein Einstieg für Modell-Labels und Handannotation: seit es mehrere
  // Labeling-Läufe gibt, ist "wessen Labels?" die erste Frage, und die
  // beantwortet sich in einer Ordnerebene besser als in zwei Menüpunkten.
  { title: "Daten", url: "/labels" },
  // Eigener Punkt statt unter "Daten": hier wird die Referenz selbst
  // geprüft, nicht in ihr geblättert.
  { title: "Prüfung", url: "/audit" },
  { title: "Ergebnis", url: "/evaluation" },
]

function BackendStatus() {
  const { isSuccess, isError } = useQuery({
    queryKey: ["schema"],
    queryFn: api.schema,
    refetchInterval: 30_000,
  })
  const label = isError ? "offline" : isSuccess ? "verbunden" : "verbinde…"
  return (
    <span className="hidden items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted-foreground lg:flex">
      <span
        className={cn(
          "size-2 rounded-full",
          isError ? "bg-destructive" : isSuccess ? "bg-[var(--riso-blue)]" : "bg-muted-foreground",
        )}
      />
      API {label}
    </span>
  )
}

export function TopNav() {
  return (
    <header className="sticky top-0 z-40 border-b-2 border-foreground bg-background/90 backdrop-blur">
      <div className="mx-auto grid h-16 max-w-[1600px] grid-cols-[1fr_auto_1fr] items-center gap-4 px-4 sm:px-6">
        <NavLink to="/" className="flex shrink-0 items-center gap-2.5">
          {/* Funke als Wortmarke, im Pink des zweiten Druckgangs */}
          <svg viewBox="0 0 24 24" aria-hidden className="size-7 text-primary">
            <path
              fill="currentColor"
              d="M12 2c.6 4.9 3.1 7.4 8 8-4.9.6-7.4 3.1-8 8-.6-4.9-3.1-7.4-8-8 4.9-.6 7.4-3.1 8-8Z"
            />
          </svg>
          <span className="misprint text-2xl font-extrabold uppercase leading-none tracking-tight">
            Magda
          </span>
        </NavLink>

        <nav
          aria-label="Hauptnavigation"
          className="flex min-w-0 items-center gap-0.5 overflow-x-auto rounded-full border-2 border-foreground bg-card p-1"
        >
          {items.map((item) => (
            <NavLink
              key={item.url}
              to={item.url}
              end={item.url === "/"}
              className={({ isActive }) =>
                cn(
                  "whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-semibold transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )
              }
            >
              {item.title}
            </NavLink>
          ))}
        </nav>

        <div className="flex justify-end">
          <BackendStatus />
        </div>
      </div>
    </header>
  )
}
