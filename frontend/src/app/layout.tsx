import { Outlet, useLocation } from "react-router-dom"
import { TooltipProvider } from "@/components/ui/tooltip"
import { TopNav } from "./top-nav"

export function Layout() {
  const location = useLocation()
  return (
    // Der Tooltip-Provider steht einmal hier statt in jeder Seite. Ohne ihn
    // wirft Radix beim ersten Tooltip und reißt die ganze Seite mit.
    <TooltipProvider delayDuration={200}>
    <div className="flex min-h-svh flex-col">
      <TopNav />
      {/* Breiter Rahmen; schmalere Seiten zentrieren sich selbst, der
          Inspektor nutzt die volle Fläche. min-w-0 gegen Grid-Overflow. */}
      <main className="mx-auto w-full min-w-0 max-w-[1600px] flex-1 px-4 py-8 sm:px-6">
        {/* key erzwingt Re-Mount pro Route: sanftes Einblenden beim Seitenwechsel */}
        <div key={location.pathname} className="page-fade">
          <Outlet />
        </div>
      </main>
      <footer className="border-t-2 border-foreground py-5 text-center font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
        Magda · Information Extraction · Leuphana Universität Lüneburg
      </footer>
    </div>
    </TooltipProvider>
  )
}
