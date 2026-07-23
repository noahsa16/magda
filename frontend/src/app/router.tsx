import type { RouteObject } from "react-router-dom"
import { DemoPage } from "@/features/demo/demo-page"
import { EvaluationPage } from "@/features/evaluation/evaluation-page"
import { InspectorPage } from "@/features/inspector/inspector-page"
import { OverviewPage } from "@/features/overview/overview-page"
import { Layout } from "./layout"

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <OverviewPage /> },
      { path: "/inspector", element: <InspectorPage /> },
      { path: "/evaluation", element: <EvaluationPage /> },
      { path: "/demo", element: <DemoPage /> },
    ],
  },
]
