import { Outlet, useLocation } from "react-router-dom"
import { TopNav } from "./top-nav"

export function Layout() {
  const location = useLocation()
  return (
    <div className="flex min-h-svh flex-col">
      <TopNav />
      {/* min-w-0: sonst können Grids in den Seiten breiter als der Viewport werden */}
      <main className="mx-auto w-full min-w-0 max-w-6xl flex-1 px-4 py-8 sm:px-6">
        {/* key erzwingt Re-Mount pro Route: sanftes Einblenden beim Seitenwechsel */}
        <div key={location.pathname} className="page-fade">
          <Outlet />
        </div>
      </main>
      <footer className="border-t border-border/60 py-5 text-center text-xs text-muted-foreground">
        Magda · Semesterprojekt Information Extraction · Leuphana Universität Lüneburg
      </footer>
    </div>
  )
}
