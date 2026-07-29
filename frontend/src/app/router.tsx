import type { RouteObject } from "react-router-dom"
import { ControlPage } from "@/features/control/control-page"
import { DemoPage } from "@/features/demo/demo-page"
import { EvaluationPage } from "@/features/evaluation/evaluation-page"
import { InspectorPage } from "@/features/inspector/inspector-page"
import { OverviewPage } from "@/features/overview/overview-page"
import { AnnotatePage } from "@/features/annotate/annotate-page"
import { Layout } from "./layout"

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <OverviewPage /> },
      { path: "/control", element: <ControlPage /> },
      { path: "/inspector", element: <InspectorPage /> },
      { path: "/annotate", element: <AnnotatePage /> },
      { path: "/evaluation", element: <EvaluationPage /> },
      { path: "/demo", element: <DemoPage /> },
    ],
  },
]
