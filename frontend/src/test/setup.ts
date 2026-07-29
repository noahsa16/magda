import "@testing-library/jest-dom/vitest"

// jsdom kennt weder matchMedia noch ResizeObserver – beides brauchen die
// shadcn-Sidebar (use-mobile-Hook) und Radix ScrollArea.
//
// prefers-reduced-motion meldet true: jsdom feuert kein requestAnimationFrame,
// eine laufende Animation bliebe also für immer beim Startwert stehen. Über den
// Reduced-Motion-Pfad setzt useCountUp den Zielwert sofort – die Kennzahlen
// sind damit prüfbar, ohne rAF zu fälschen.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: query.includes("prefers-reduced-motion"),
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

// jsdom implementiert scrollIntoView nicht. Die Konsole der Steuerzentrale
// scrollt nach jeder Ausgabezeile ans Ende und riss sonst die ganze Seite mit.
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => {})

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = window.ResizeObserver ?? (ResizeObserverStub as unknown as typeof ResizeObserver)

// Node bringt seit Version 22 ein eigenes globales localStorage mit, das ohne
// --localstorage-file nicht funktioniert (getItem etc. fehlen) und jsdoms
// funktionierende Implementierung in diesem Setup überschattet. Ersatz durch
// eine einfache In-Memory-Variante, ausschließlich für Tests.
class MemoryStorageStub implements Storage {
  private store = new Map<string, string>()
  get length() {
    return this.store.size
  }
  clear() {
    this.store.clear()
  }
  getItem(key: string) {
    return this.store.has(key) ? this.store.get(key)! : null
  }
  key(index: number) {
    return [...this.store.keys()][index] ?? null
  }
  removeItem(key: string) {
    this.store.delete(key)
  }
  setItem(key: string, value: string) {
    this.store.set(key, String(value))
  }
}
Object.defineProperty(window, "localStorage", { value: new MemoryStorageStub(), writable: true })
