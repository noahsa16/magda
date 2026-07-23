import { ChartColumn, LayoutDashboard, Play, ScanSearch } from "lucide-react"
import { NavLink } from "react-router-dom"
import {
  Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent, SidebarGroupLabel,
  SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem,
} from "@/components/ui/sidebar"

const items = [
  { title: "Übersicht", url: "/", icon: LayoutDashboard },
  { title: "Inspektor", url: "/inspector", icon: ScanSearch },
  { title: "Evaluation", url: "/evaluation", icon: ChartColumn },
  { title: "Demo", url: "/demo", icon: Play },
]

export function AppSidebar() {
  return (
    <Sidebar>
      <SidebarHeader className="px-4 py-3">
        <span className="text-lg font-semibold tracking-tight">Magda</span>
        <span className="text-xs text-muted-foreground">Angebots-Extraktion aus Prospekten</span>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Pipeline</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.url}>
                  <SidebarMenuButton asChild>
                    <NavLink to={item.url} end={item.url === "/"}>
                      <item.icon />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
