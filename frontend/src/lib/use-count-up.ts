import { useEffect, useRef, useState } from "react"

/**
 * Zählt animiert zum Zielwert hoch. Bei prefers-reduced-motion wird der
 * Zielwert sofort gesetzt – die Zahl selbst ist die Information, nicht
 * die Animation.
 */
export function useCountUp(target: number, durationMs = 600): number {
  const [value, setValue] = useState(0)
  const from = useRef(0)

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      from.current = target
      setValue(target)
      return
    }
    const start = performance.now()
    const base = from.current
    from.current = target
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - Math.pow(1 - t, 3)
      setValue(Math.round(base + (target - base) * eased))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, durationMs])

  return value
}
