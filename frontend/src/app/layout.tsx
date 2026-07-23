import { Outlet } from "react-router-dom"
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { AppSidebar } from "./app-sidebar"

export function Layout() {
  return (
    <SidebarProvider>
      <AppSidebar />
      {/* min-w-0: sonst können Grids in den Seiten breiter als der Viewport werden */}
      <main className="min-w-0 flex-1 p-6">
        <SidebarTrigger className="mb-4 md:hidden" />
        <div className="mx-auto max-w-6xl">
          <Outlet />
        </div>
      </main>
    </SidebarProvider>
  )
}
