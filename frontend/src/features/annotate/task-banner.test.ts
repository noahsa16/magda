import { expect, it } from "vitest"
import { taskProgress } from "./task-banner"

it("zaehlt maschinell fertige Gruppen nicht als Handarbeit", () => {
  const task = { title: "Test", why: "", created: "", for: [], pages: ["p1", "p2"] }
  expect(taskProgress(task, [
    { page_id: "p1", status: "done", stale: false, source: "sonnet" },
    { page_id: "p2", status: "done", stale: false, source: "gold" },
  ])).toEqual({ done: 1, next: "p1" })
})
