import type { RouteObject } from "react-router-dom"
import { ControlPage } from "@/features/control/control-page"
import { EvaluationPage } from "@/features/evaluation/evaluation-page"
import { BrowsePage } from "@/features/browse/browse-page"
import { InspectorPage } from "@/features/inspector/inspector-page"
import { OverviewPage } from "@/features/overview/overview-page"
import { AnnotatePage } from "@/features/annotate/annotate-page"
import { AuditPage } from "@/features/audit/audit-page"
import { Layout } from "./layout"

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <OverviewPage /> },
      { path: "/pipeline", element: <ControlPage /> },
      // Ein Einstieg für beides. /inspector und /annotate bleiben als
      // direkte Wege bestehen – die Agreement-Karte verlinkt dorthin.
      { path: "/labels", element: <BrowsePage /> },
      { path: "/inspector", element: <InspectorPage /> },
      { path: "/annotate", element: <AnnotatePage /> },
      { path: "/audit", element: <AuditPage /> },
      { path: "/evaluation", element: <EvaluationPage /> },
    ],
  },
]
