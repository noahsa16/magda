import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"

const items = [
  { title: "Übersicht", url: "/" },
  { title: "Inspektor", url: "/inspector" },
  { title: "Evaluation", url: "/evaluation" },
  { title: "Demo", url: "/demo" },
]

export function TopNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <NavLink to="/" className="flex shrink-0 items-center gap-2">
          {/* Funke als Wortmarke – der einzige rein dekorative Coral-Einsatz */}
          <svg viewBox="0 0 24 24" aria-hidden className="size-5 text-primary">
            <path
              fill="currentColor"
              d="M12 2c.6 4.9 3.1 7.4 8 8-4.9.6-7.4 3.1-8 8-.6-4.9-3.1-7.4-8-8 4.9-.6 7.4-3.1 8-8Z"
            />
          </svg>
          <span className="font-display text-xl tracking-tight">Magda</span>
        </NavLink>

        <nav
          aria-label="Hauptnavigation"
          className="flex min-w-0 items-center gap-1 overflow-x-auto rounded-full border border-border/70 bg-card p-1 shadow-sm"
        >
          {items.map((item) => (
            <NavLink
              key={item.url}
              to={item.url}
              end={item.url === "/"}
              className={({ isActive }) =>
                cn(
                  "whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )
              }
            >
              {item.title}
            </NavLink>
          ))}
        </nav>

        <span className="hidden shrink-0 font-mono text-[11px] text-muted-foreground lg:block">
          Information Extraction · Leuphana
        </span>
      </div>
    </header>
  )
}
