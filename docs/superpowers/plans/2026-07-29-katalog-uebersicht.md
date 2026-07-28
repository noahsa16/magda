# Katalog-Übersicht — Umsetzungsplan

> **Für agentische Bearbeiter:** ERFORDERLICHE SUB-SKILL: `superpowers:subagent-driven-development` (empfohlen) oder `superpowers:executing-plans`, um diesen Plan Aufgabe für Aufgabe umzusetzen. Die Schritte nutzen Checkbox-Syntax (`- [ ]`) zur Fortschrittsverfolgung.

**Ziel:** Inspektor und Annotator bekommen eine Prospekt-Übersicht vorgeschaltet, damit beide auch mit zehn bis zwanzig Katalogen bedienbar bleiben.

**Architektur:** Drei Ebenen über Query-Parameter statt neuer Routen (`/annotate` → `?catalog=X` → `?catalog=X&page=Y`). Eine geteilte Kachel-Komponente für beide Werkzeuge; die Aggregation liegt als reine Funktionen in `lib/catalogs.ts` und ist ohne Rendering testbar. Die Seitenliste wird von der aufrufenden Seite bereits gefiltert übergeben — `PageList` selbst bleibt unverändert.

**Tech-Stack:** Python 3.12, FastAPI, pytest · React 19, TypeScript, TanStack Query, Vite, Vitest, Tailwind

Zugrundeliegende Spec: `docs/superpowers/specs/2026-07-28-katalog-uebersicht-design.md`

## Globale Randbedingungen

- Kommentare und Docstrings auf **Deutsch**, Code-Identifier auf **Englisch**. Docstrings erklären *warum*, nicht *was*.
- Pfade in `magda/api.py` immer als `config.X` zur Laufzeit lesen, nie importieren — sonst können die Tests sie nicht umbiegen.
- Der **Inspektor unter `/inspector` muss weiterhin funktionieren**; `PageList` wird in diesem Plan nicht verändert.
- Keine neuen Routen. Die Ebene ergibt sich aus den Query-Parametern.
- Ausgangsstand: `.venv/bin/python -m pytest -q` → 59 grün; `cd frontend && npm test` → 65 grün; `npx tsc --noEmit` sauber. Das muss am Ende mindestens genauso gut sein.
- Deutsche Commit-Betreffs im Imperativ.
- Python aus dem Projektroot mit `.venv/bin/python -m pytest`, Frontend-Kommandos aus `frontend/`.

## Dateistruktur

| Datei | Verantwortung |
|---|---|
| `magda/api.py` | `get_status` liefert `downloaded` je Katalog |
| `tests/test_api.py` | Test dafür |
| `frontend/src/lib/types.ts` | `CatalogStatus.downloaded`, neuer Typ `CatalogTile` |
| `frontend/src/lib/catalogs.ts` | reine Aggregation, ohne React |
| `frontend/src/lib/catalogs.test.ts` | Tests dazu |
| `frontend/src/components/catalog-grid.tsx` | Kacheldarstellung, von beiden Werkzeugen genutzt |
| `frontend/src/components/catalog-grid.test.tsx` | Tests dazu |
| `frontend/src/components/crumbs.tsx` | Brotkrumen-Pfad |
| `frontend/src/features/annotate/annotate-page.tsx` | drei Ebenen |
| `frontend/src/features/inspector/inspector-page.tsx` | drei Ebenen |

---

### Task 1: Ladedatum in `/api/status`

**Dateien:**
- Ändern: `magda/api.py` (`get_status`, etwa Zeile 47-70)
- Test: `tests/test_api.py`

**Schnittstellen:**
- Erzeugt: jeder Eintrag in `catalogs` bekommt `"downloaded": "YYYY-MM-DD" | None`
- `totals` bleibt unverändert — es summiert über eine feste Schlüsselliste und darf `downloaded` nicht enthalten

- [ ] **Schritt 1: Failing Test schreiben**

An `tests/test_api.py` anhängen:

```python
def test_status_liefert_ladedatum_je_katalog(client):
    (config.RAW_DIR / "462828").mkdir()
    (config.RAW_DIR / "462828" / "bk_1.pdf").write_bytes(b"x")
    _write_words("462828_p1")

    row = client.get("/api/status").json()["catalogs"][0]

    assert row["downloaded"] is not None
    assert len(row["downloaded"]) == 10  # YYYY-MM-DD


def test_status_ohne_rohdaten_hat_kein_ladedatum(client):
    # Wörter da, aber data/raw/ geleert: der Katalog existiert weiter,
    # das Datum ist nicht mehr ableitbar.
    _write_words("462828_p1")

    row = client.get("/api/status").json()["catalogs"][0]

    assert row["downloaded"] is None


def test_status_totals_enthalten_kein_ladedatum(client):
    _write_words("462828_p1")

    totals = client.get("/api/status").json()["totals"]

    assert set(totals) == {"raw", "words", "images", "labeled"}
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag prüfen**

Ausführen: `.venv/bin/python -m pytest tests/test_api.py -v -k ladedatum`
Erwartet: FAIL mit `KeyError: 'downloaded'`

- [ ] **Schritt 3: Implementieren**

In `magda/api.py` vor `get_status` einfügen:

```python
def _downloaded_at(catalog: str) -> str | None:
    """Ladedatum aus der Änderungszeit des Katalogverzeichnisses.

    Katalog-IDs sind nichtssagende Blätterkatalog-Nummern. Das Datum macht sie
    in der Übersicht unterscheidbar - anders als der Gültigkeitszeitraum, der
    nur dort existiert, wo das LLM ihn als VALID erkannt hat.
    """
    directory = config.RAW_DIR / catalog
    if not directory.exists():
        return None
    return datetime.fromtimestamp(directory.stat().st_mtime).date().isoformat()
```

In `get_status` die `bump`-Vorlage um das Feld ergänzen und es nach den Schleifen füllen:

```python
    def bump(catalog: str, key: str):
        entry = catalogs.setdefault(
            catalog,
            {"id": catalog, "raw": 0, "words": 0, "images": 0, "labeled": 0,
             "downloaded": None},
        )
        entry[key] += 1
```

Direkt vor `rows = sorted(...)`:

```python
    for catalog, entry in catalogs.items():
        entry["downloaded"] = _downloaded_at(catalog)
```

`datetime` ist in `magda/api.py` bereits importiert (`from datetime import datetime`).

- [ ] **Schritt 4: Tests laufen lassen**

Ausführen: `.venv/bin/python -m pytest tests/test_api.py -v`
Erwartet: PASS

Ausführen: `.venv/bin/python -m pytest -q`
Erwartet: 62 passed (59 + 3 neue)

- [ ] **Schritt 5: Committen**

```bash
git add magda/api.py tests/test_api.py
git commit -m "Liefere das Ladedatum je Katalog im Status

Katalog-IDs sind nichtssagende Blätterkatalog-Nummern. Bei einem Prospekt
egal, bei zehn steht man vor Zahlenkolonnen. Das Datum kommt aus der
Änderungszeit des Verzeichnisses unter data/raw - anders als der
Gültigkeitszeitraum ist es immer verfügbar, auch ohne Labels."
```

---

### Task 2: Aggregation je Katalog

**Dateien:**
- Ändern: `frontend/src/lib/types.ts`
- Erstellen: `frontend/src/lib/catalogs.ts`
- Test: `frontend/src/lib/catalogs.test.ts`

**Schnittstellen:**
- Verbraucht: `GoldSummary`, `PageSummary`, `CatalogStatus` aus `lib/types.ts`
- Erzeugt: `CatalogTile` in `lib/types.ts`
- Erzeugt: `groupGoldByCatalog(summaries: GoldSummary[], status: CatalogStatus[]): CatalogTile[]`
- Erzeugt: `groupPagesByCatalog(pages: PageSummary[], status: CatalogStatus[]): CatalogTile[]`

Beide zählen **aus den Seiten**, nicht aus dem Status — ein Katalog ohne extrahierte Seiten bekommt keine Kachel, weil man dort weder annotieren noch inspizieren kann. Der Status liefert nur das Ladedatum.

- [ ] **Schritt 1: Typen ergänzen**

In `frontend/src/lib/types.ts` `CatalogStatus` um ein Feld erweitern:

```ts
export interface CatalogStatus {
  id: string
  raw: number
  words: number
  images: number
  labeled: number
  /** Ladedatum als YYYY-MM-DD; null, wenn data/raw/<id> fehlt. */
  downloaded: string | null
}
```

Und anhängen:

```ts
/** Eine Kachel in der Prospekt-Übersicht. Gleiche Form für beide Werkzeuge. */
export interface CatalogTile {
  id: string
  pages: number
  /** Annotator: Gold fertig. Inspektor: vom LLM gelabelt. */
  done: number
  downloaded: string | null
  /** Nur im Annotator > 0: Wortliste hat sich seit dem Annotieren geändert. */
  stale: number
  /** Nur im Annotator > 0: Gold-Datei nicht lesbar. */
  broken: number
}
```

- [ ] **Schritt 2: Failing Test schreiben**

`frontend/src/lib/catalogs.test.ts` erstellen:

```ts
import { describe, expect, it } from "vitest"
import { groupGoldByCatalog, groupPagesByCatalog } from "./catalogs"
import type { CatalogStatus, GoldSummary, PageSummary } from "./types"

const status: CatalogStatus[] = [
  { id: "111", raw: 2, words: 2, images: 2, labeled: 1, downloaded: "2026-07-23" },
  { id: "222", raw: 1, words: 1, images: 1, labeled: 0, downloaded: null },
]

const gold = (page_id: string, s: GoldSummary["status"], stale = false): GoldSummary => ({
  page_id, catalog: page_id.split("_")[0], status: s, annotator: "", num_spans: 0, stale,
})

const page = (page_id: string, labeled: boolean): PageSummary => ({
  page_id, catalog: page_id.split("_")[0], labeled,
})

describe("groupGoldByCatalog", () => {
  it("zählt fertige Seiten je Katalog", () => {
    const tiles = groupGoldByCatalog(
      [gold("111_p1", "done"), gold("111_p2", "in_progress"), gold("222_p1", "done")],
      status,
    )
    expect(tiles).toEqual([
      { id: "111", pages: 2, done: 1, downloaded: "2026-07-23", stale: 0, broken: 0 },
      { id: "222", pages: 1, done: 1, downloaded: null, stale: 0, broken: 0 },
    ])
  })

  it("zählt eine veraltete Seite nicht als fertig", () => {
    // Dieselbe Regel wie doneCount in annotate-page.tsx: bei geänderter
    // Wortliste zeigen die Span-Indizes auf andere Wörter.
    const tiles = groupGoldByCatalog([gold("111_p1", "done", true)], status)
    expect(tiles[0].done).toBe(0)
    expect(tiles[0].stale).toBe(1)
  })

  it("zählt kaputte Gold-Dateien getrennt", () => {
    const tiles = groupGoldByCatalog([gold("111_p1", "broken")], status)
    expect(tiles[0].broken).toBe(1)
    expect(tiles[0].done).toBe(0)
  })

  it("sortiert nach Katalog-ID", () => {
    const tiles = groupGoldByCatalog([gold("222_p1", "done"), gold("111_p1", "done")], status)
    expect(tiles.map((t) => t.id)).toEqual(["111", "222"])
  })

  it("kommt ohne Statuseintrag aus", () => {
    const tiles = groupGoldByCatalog([gold("999_p1", "done")], status)
    expect(tiles).toEqual([
      { id: "999", pages: 1, done: 1, downloaded: null, stale: 0, broken: 0 },
    ])
  })

  it("liefert für keine Seiten eine leere Liste", () => {
    expect(groupGoldByCatalog([], status)).toEqual([])
  })
})

describe("groupPagesByCatalog", () => {
  it("zählt gelabelte Seiten je Katalog", () => {
    const tiles = groupPagesByCatalog(
      [page("111_p1", true), page("111_p2", false), page("222_p1", false)],
      status,
    )
    expect(tiles).toEqual([
      { id: "111", pages: 2, done: 1, downloaded: "2026-07-23", stale: 0, broken: 0 },
      { id: "222", pages: 1, done: 0, downloaded: null, stale: 0, broken: 0 },
    ])
  })
})
```

- [ ] **Schritt 3: Test laufen lassen, Fehlschlag prüfen**

Ausführen: `cd frontend && npx vitest run src/lib/catalogs.test.ts`
Erwartet: FAIL, Modul nicht gefunden

- [ ] **Schritt 4: Implementieren**

`frontend/src/lib/catalogs.ts` erstellen:

```ts
// Aggregation für die Prospekt-Übersicht, bewusst ohne React: Das Zählen ist
// der Teil, in dem sich Fehler still in eine Fortschrittsanzeige schreiben.

import type { CatalogStatus, CatalogTile, GoldSummary, PageSummary } from "./types"

function emptyTile(id: string, status: CatalogStatus[]): CatalogTile {
  return {
    id,
    pages: 0,
    done: 0,
    downloaded: status.find((s) => s.id === id)?.downloaded ?? null,
    stale: 0,
    broken: 0,
  }
}

/** Kacheln aus einer Liste von Einträgen, gruppiert über deren Katalog. */
function tilesFrom<T extends { catalog: string }>(
  rows: T[],
  status: CatalogStatus[],
  count: (tile: CatalogTile, row: T) => void,
): CatalogTile[] {
  const byId = new Map<string, CatalogTile>()
  for (const row of rows) {
    let tile = byId.get(row.catalog)
    if (!tile) {
      tile = emptyTile(row.catalog, status)
      byId.set(row.catalog, tile)
    }
    tile.pages += 1
    count(tile, row)
  }
  return [...byId.values()].sort((a, b) => a.id.localeCompare(b.id))
}

export function groupGoldByCatalog(
  summaries: GoldSummary[],
  status: CatalogStatus[],
): CatalogTile[] {
  return tilesFrom(summaries, status, (tile, row) => {
    if (row.status === "broken") tile.broken += 1
    else if (row.stale) tile.stale += 1
    else if (row.status === "done") tile.done += 1
  })
}

export function groupPagesByCatalog(
  pages: PageSummary[],
  status: CatalogStatus[],
): CatalogTile[] {
  return tilesFrom(pages, status, (tile, row) => {
    if (row.labeled) tile.done += 1
  })
}
```

- [ ] **Schritt 5: Tests laufen lassen**

Ausführen: `cd frontend && npx vitest run src/lib/catalogs.test.ts`
Erwartet: PASS, 7 Tests

Ausführen: `cd frontend && npx tsc --noEmit`
Erwartet: keine Fehler. Schlägt es fehl, weil ein Test-Fixture `downloaded` nicht setzt, ergänze das Feld dort — `CatalogStatus` hat es jetzt verpflichtend.

- [ ] **Schritt 6: Committen**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/catalogs.ts frontend/src/lib/catalogs.test.ts
git commit -m "Ergänze Aggregation je Katalog für die Übersicht

Gezählt wird aus den Seiten, nicht aus dem Status: Ein Katalog ohne
extrahierte Seiten bekommt keine Kachel, weil man dort weder annotieren
noch inspizieren kann. Eine veraltete Seite zählt nicht als fertig -
dieselbe Regel wie in doneCount."
```

---

### Task 3: Kachel-Raster und Brotkrumen

**Dateien:**
- Erstellen: `frontend/src/components/catalog-grid.tsx`
- Erstellen: `frontend/src/components/crumbs.tsx`
- Test: `frontend/src/components/catalog-grid.test.tsx`

**Schnittstellen:**
- Verbraucht: `CatalogTile` aus `lib/types.ts` (Task 2)
- Erzeugt: `<CatalogGrid tiles={...} unit="fertig" | "gelabelt" onSelect={(id) => void} emptyHint={ReactNode} />`
- Erzeugt: `<Crumbs items={[{label, onClick?}, …]} />`

Das Raster weiß nicht, ob es Gold oder LLM-Labels zeigt — `unit` ist nur die Beschriftung, `stale`/`broken` werden angezeigt, sobald sie größer als null sind.

- [ ] **Schritt 1: Failing Test schreiben**

`frontend/src/components/catalog-grid.test.tsx` erstellen:

```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { renderWithProviders } from "@/test/utils"
import { CatalogGrid } from "./catalog-grid"
import type { CatalogTile } from "@/lib/types"

const tile = (over: Partial<CatalogTile> = {}): CatalogTile => ({
  id: "1342881", pages: 40, done: 18, downloaded: "2026-07-23", stale: 0, broken: 0, ...over,
})

describe("CatalogGrid", () => {
  it("zeigt Kennzahlen und Beschriftung je Kachel", () => {
    renderWithProviders(<CatalogGrid tiles={[tile()]} unit="fertig" onSelect={() => {}} />)
    expect(screen.getByText("1342881")).toBeInTheDocument()
    expect(screen.getByText(/40 Seiten/)).toBeInTheDocument()
    expect(screen.getByText("18/40 fertig")).toBeInTheDocument()
  })

  it("meldet die Auswahl mit der Katalog-ID", async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    renderWithProviders(<CatalogGrid tiles={[tile()]} unit="fertig" onSelect={onSelect} />)
    await user.click(screen.getByRole("button", { name: /1342881/ }))
    expect(onSelect).toHaveBeenCalledWith("1342881")
  })

  it("weist auf veraltete und kaputte Seiten hin", () => {
    renderWithProviders(
      <CatalogGrid tiles={[tile({ stale: 3, broken: 1 })]} unit="fertig" onSelect={() => {}} />,
    )
    expect(screen.getByText(/4 ungültig/)).toBeInTheDocument()
  })

  it("verschweigt den Hinweis, wenn nichts ungültig ist", () => {
    renderWithProviders(<CatalogGrid tiles={[tile()]} unit="fertig" onSelect={() => {}} />)
    expect(screen.queryByText(/ungültig/)).not.toBeInTheDocument()
  })

  it("lässt das Ladedatum weg, wenn es fehlt", () => {
    renderWithProviders(
      <CatalogGrid tiles={[tile({ downloaded: null })]} unit="fertig" onSelect={() => {}} />,
    )
    expect(screen.getByText("40 Seiten")).toBeInTheDocument()
  })

  it("zeigt den Leerzustand ohne Kacheln", () => {
    renderWithProviders(
      <CatalogGrid tiles={[]} unit="fertig" onSelect={() => {}} emptyHint="Nichts da" />,
    )
    expect(screen.getByText("Nichts da")).toBeInTheDocument()
  })
})
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag prüfen**

Ausführen: `cd frontend && npx vitest run src/components/catalog-grid.test.tsx`
Erwartet: FAIL, Modul nicht gefunden

- [ ] **Schritt 3: Brotkrumen schreiben**

`frontend/src/components/crumbs.tsx` erstellen:

```tsx
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

interface Crumb {
  label: string
  /** Fehlt bei der aktuellen Ebene - die ist kein Ziel. */
  onClick?: () => void
}

export function Crumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Pfad" className="flex items-center gap-1 font-mono text-xs">
      {items.map((item, i) => (
        <span key={item.label} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="size-3 text-muted-foreground" />}
          {item.onClick ? (
            <button
              type="button"
              onClick={item.onClick}
              className="text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              {item.label}
            </button>
          ) : (
            <span className={cn("font-semibold")}>{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}
```

- [ ] **Schritt 4: Kachel-Raster schreiben**

`frontend/src/components/catalog-grid.tsx` erstellen:

```tsx
import { AlertTriangle } from "lucide-react"
import type { ReactNode } from "react"
import { Progress } from "@/components/ui/progress"
import type { CatalogTile } from "@/lib/types"

interface CatalogGridProps {
  tiles: CatalogTile[]
  /** Beschriftung der Kennzahl: "fertig" im Annotator, "gelabelt" im Inspektor. */
  unit: string
  onSelect: (id: string) => void
  emptyHint?: ReactNode
}

/** Ladedatum als TT.MM., der Rest ist bei Wochenprospekten Rauschen. */
function shortDate(iso: string): string {
  const [, month, day] = iso.split("-")
  return `${day}.${month}.`
}

export function CatalogGrid({ tiles, unit, onSelect, emptyHint }: CatalogGridProps) {
  if (tiles.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border-2 border-dashed border-foreground/30 px-6 text-center">
        <p className="text-muted-foreground">{emptyHint}</p>
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {tiles.map((tile) => {
        const invalid = tile.stale + tile.broken
        const pct = tile.pages > 0 ? (tile.done / tile.pages) * 100 : 0
        return (
          <button
            key={tile.id}
            type="button"
            onClick={() => onSelect(tile.id)}
            className="plate space-y-2 rounded-lg border-2 border-foreground bg-card p-4 text-left transition-colors hover:bg-accent"
          >
            <p className="font-mono text-lg font-bold tracking-tight">{tile.id}</p>
            <p className="font-mono text-[11px] text-muted-foreground">
              {tile.pages} Seiten
              {tile.downloaded && ` · geladen ${shortDate(tile.downloaded)}`}
            </p>
            <div className="flex items-center gap-2">
              <Progress value={pct} />
              <span className="shrink-0 font-mono text-[11px] tabular-nums">
                {tile.done}/{tile.pages} {unit}
              </span>
            </div>
            {invalid > 0 && (
              <p className="flex items-center gap-1 font-mono text-[11px] text-destructive">
                <AlertTriangle className="size-3" />
                {invalid} ungültig
              </p>
            )}
          </button>
        )
      })}
    </div>
  )
}
```

- [ ] **Schritt 5: Tests laufen lassen**

Ausführen: `cd frontend && npx vitest run src/components/catalog-grid.test.tsx`
Erwartet: PASS, 6 Tests

- [ ] **Schritt 6: Committen**

```bash
git add frontend/src/components/catalog-grid.tsx frontend/src/components/crumbs.tsx frontend/src/components/catalog-grid.test.tsx
git commit -m "Ergänze Kachel-Raster und Brotkrumen für die Übersicht

Das Raster weiß nicht, ob es Gold oder LLM-Labels zeigt - die Beschriftung
kommt als Prop. Damit teilen sich Inspektor und Annotator eine Darstellung,
statt zwei Kopien auseinanderlaufen zu lassen."
```

---

### Task 4: Annotator auf drei Ebenen

**Dateien:**
- Ändern: `frontend/src/features/annotate/annotate-page.tsx`
- Test: `frontend/src/features/annotate/annotate-page.test.tsx`

**Schnittstellen:**
- Verbraucht: `groupGoldByCatalog` (Task 2), `CatalogGrid` und `Crumbs` (Task 3)
- `PageList` wird **nicht** verändert — sie bekommt eine bereits gefilterte Seitenliste

- [ ] **Schritt 1: Failing Test schreiben**

In `frontend/src/features/annotate/annotate-page.test.tsx` die vorhandene `setup`-Hilfsfunktion um einen Routenparameter erweitern (Standard bleibt die bisherige Route) und diese Tests anhängen:

```tsx
describe("AnnotatePage — Ebenen", () => {
  it("zeigt ohne Parameter die Prospekt-Übersicht", async () => {
    setup({ route: "/annotate" })
    expect(await screen.findByText("462828")).toBeInTheDocument()
    expect(screen.queryByLabelText("Annotator")).not.toBeInTheDocument()
  })

  it("öffnet per Klick auf eine Kachel die Seitenliste", async () => {
    const user = userEvent.setup()
    setup({ route: "/annotate" })
    await user.click(await screen.findByRole("button", { name: /462828/ }))
    expect(await screen.findByLabelText("Annotator")).toBeInTheDocument()
  })

  it("führt über den Brotkrumen zurück zur Übersicht", async () => {
    const user = userEvent.setup()
    setup({ route: "/annotate?catalog=462828" })
    await user.click(await screen.findByRole("button", { name: "Prospekte" }))
    expect(await screen.findByText(/Seiten/)).toBeInTheDocument()
    expect(screen.queryByLabelText("Annotator")).not.toBeInTheDocument()
  })

  it("zeigt bei unbekanntem Katalog die Übersicht mit Hinweis", async () => {
    setup({ route: "/annotate?catalog=gibtsnicht" })
    expect(await screen.findByText(/nicht gefunden/i)).toBeInTheDocument()
  })
})
```

Die bestehenden Tests der Datei rufen `setup()` ohne Route auf und müssen weiter grün bleiben — sie decken die Seitenansicht ab, für die jetzt zusätzlich `?catalog=` gesetzt sein muss. Passe die Standardroute in `setup` entsprechend auf `/annotate?catalog=462828&page=462828_p1` an.

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag prüfen**

Ausführen: `cd frontend && npx vitest run src/features/annotate/annotate-page.test.tsx`
Erwartet: FAIL — die Übersicht existiert noch nicht

- [ ] **Schritt 3: Ebenenlogik einbauen**

In `annotate-page.tsx` nach dem Auslesen von `selected` ergänzen:

```tsx
  const selected = searchParams.get("page")
  // Die page_id enthält den Katalog bereits (1342881_p3); ein gesetzter
  // ?page= impliziert ihn also. Eigenen Parameter braucht nur der Zustand
  // "Prospekt offen, aber keine Seite gewählt".
  const catalog = searchParams.get("catalog") ?? selected?.split("_p")[0] ?? null
```

Nach den Queries die Kacheln und die gefilterte Seitenliste ableiten:

```tsx
  const status = useQuery({ queryKey: ["status"], queryFn: api.status })

  const tiles = useMemo(
    () => groupGoldByCatalog(gold.data ?? [], status.data?.catalogs ?? []),
    [gold.data, status.data],
  )
  const catalogPages = useMemo(
    () => (pages.data ?? []).filter((p) => p.catalog === catalog),
    [pages.data, catalog],
  )
```

`ids` und `goldRows` auf den Katalog beziehen, damit Pfeiltasten und Fortschritt nicht über die Katalog-Grenze laufen:

```tsx
  const ids = useMemo(() => catalogPages.map((p) => p.page_id), [catalogPages])
  const goldRows = (gold.data ?? []).filter((g) => g.catalog === catalog)
```

`goto` und die Seitenauswahl müssen den Katalog mitschreiben:

```tsx
  function goto(i: number) {
    if (i < 0 || i >= ids.length) return
    setSel(null)
    setSearchParams({ catalog: catalog!, page: ids[i] })
  }
```

Vor dem bestehenden `return` die Übersicht als eigenen Zweig einfügen — nach den Ladeprüfungen, aber vor allem anderen:

```tsx
  if (catalog === null) {
    return (
      <div className="flex min-w-0 flex-col gap-4">
        <h1 className="text-3xl font-extrabold tracking-tight">Annotieren</h1>
        <CatalogGrid
          tiles={tiles}
          unit="fertig"
          onSelect={(id) => setSearchParams({ catalog: id })}
          emptyHint={
            <>Noch keine Prospekte extrahiert. Auf der Übersicht <code>01_download_flyers</code> und <code>02_extract_words</code> starten.</>
          }
        />
      </div>
    )
  }

  if (tiles.length > 0 && !tiles.some((t) => t.id === catalog)) {
    return (
      <div className="flex min-w-0 flex-col gap-4">
        <h1 className="text-3xl font-extrabold tracking-tight">Annotieren</h1>
        <Alert variant="destructive">
          <AlertTitle>Prospekt nicht gefunden</AlertTitle>
          <AlertDescription>
            Der Katalog <code>{catalog}</code> existiert nicht (mehr). Unten stehen die vorhandenen.
          </AlertDescription>
        </Alert>
        <CatalogGrid tiles={tiles} unit="fertig" onSelect={(id) => setSearchParams({ catalog: id })} />
      </div>
    )
  }
```

In der Kopfzeile der Seitenansicht die Überschrift durch den Brotkrumen ersetzen:

```tsx
        <div className="flex items-baseline gap-3">
          <Crumbs
            items={[
              { label: "Prospekte", onClick: () => setSearchParams({}) },
              selected
                ? { label: catalog, onClick: () => setSearchParams({ catalog }) }
                : { label: catalog },
              ...(selected ? [{ label: selected.split("_").pop()! }] : []),
            ]}
          />
          <p className="font-mono text-xs text-muted-foreground">
            {idx >= 0 ? `${idx + 1} / ${ids.length}` : `${ids.length} Seiten`}
          </p>
        </div>
```

`PageList` bekommt die gefilterte Liste und schreibt den Katalog mit:

```tsx
        <PageList
          pages={catalogPages}
          selected={selected}
          onSelect={(id) => { setSel(null); setSearchParams({ catalog: catalog, page: id }) }}
          goldStatus={goldRows}
        />
```

Importe ergänzen: `CatalogGrid`, `Crumbs`, `groupGoldByCatalog`.

- [ ] **Schritt 4: Tests laufen lassen**

Ausführen: `cd frontend && npx vitest run src/features/annotate/`
Erwartet: PASS, alle Tests der Datei einschließlich der vier neuen

Ausführen: `cd frontend && npx tsc --noEmit`
Erwartet: keine Fehler

- [ ] **Schritt 5: Committen**

```bash
git add frontend/src/features/annotate/
git commit -m "Stelle den Annotator auf drei Ebenen um

Prospekt-Übersicht, Seitenliste, Seite - über Query-Parameter statt neuer
Routen. Pfeiltasten und Fortschritt beziehen sich jetzt auf den gewählten
Prospekt; bisher blätterte man am Katalogende stillschweigend in den
nächsten hinein."
```

---

### Task 5: Inspektor auf drei Ebenen

**Dateien:**
- Ändern: `frontend/src/features/inspector/inspector-page.tsx`
- Test: `frontend/src/features/inspector/inspector-page.test.tsx`

**Schnittstellen:**
- Verbraucht: `groupPagesByCatalog` (Task 2), `CatalogGrid` und `Crumbs` (Task 3)

Gleiche Struktur wie Task 4, mit drei Unterschieden: Die Kacheln kommen aus `groupPagesByCatalog`, die Beschriftung lautet `"gelabelt"`, und `PageList` wird **ohne** `goldStatus` aufgerufen (der Inspektor zeigt LLM-Labels).

- [ ] **Schritt 1: Failing Test schreiben**

An `frontend/src/features/inspector/inspector-page.test.tsx` anhängen (die vorhandene Setup-Hilfe analog zu Task 4 um eine Route erweitern):

```tsx
describe("InspectorPage — Ebenen", () => {
  it("zeigt ohne Parameter die Prospekt-Übersicht", async () => {
    setup({ route: "/inspector" })
    expect(await screen.findByText("462828")).toBeInTheDocument()
  })

  it("beschriftet die Kennzahl als gelabelt", async () => {
    setup({ route: "/inspector" })
    expect(await screen.findByText(/gelabelt$/)).toBeInTheDocument()
  })

  it("öffnet per Klick auf eine Kachel die Seitenliste", async () => {
    const user = userEvent.setup()
    setup({ route: "/inspector" })
    await user.click(await screen.findByRole("button", { name: /462828/ }))
    expect(await screen.findByText("Label-Inspektor")).toBeInTheDocument()
  })
})
```

Bestehende Tests, die direkt eine Seite öffnen, brauchen jetzt zusätzlich `?catalog=`; passe ihre Route entsprechend an.

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag prüfen**

Ausführen: `cd frontend && npx vitest run src/features/inspector/`
Erwartet: FAIL

- [ ] **Schritt 3: Ebenenlogik einbauen**

In `inspector-page.tsx` nach dem Auslesen von `selected` ergänzen:

```tsx
  const selected = searchParams.get("page")
  // Die page_id enthält den Katalog bereits (1342881_p3); ein gesetzter
  // ?page= impliziert ihn also. Eigenen Parameter braucht nur der Zustand
  // "Prospekt offen, aber keine Seite gewählt".
  const catalog = searchParams.get("catalog") ?? selected?.split("_p")[0] ?? null
```

Die Statusabfrage und die abgeleiteten Listen ergänzen:

```tsx
  const status = useQuery({ queryKey: ["status"], queryFn: api.status })

  const tiles = useMemo(
    () => groupPagesByCatalog(pages.data ?? [], status.data?.catalogs ?? []),
    [pages.data, status.data],
  )
  const catalogPages = useMemo(
    () => (pages.data ?? []).filter((p) => p.catalog === catalog),
    [pages.data, catalog],
  )
```

`ids` auf den Katalog beziehen, damit Pfeiltasten nicht über die Grenze laufen:

```tsx
  const ids = useMemo(() => catalogPages.map((p) => p.page_id), [catalogPages])
```

`goto` schreibt den Katalog mit. `catalog` ist an dieser Stelle noch
`string | null` (die Prüfung folgt erst weiter unten), daher die Zusicherung:

```tsx
  function goto(i: number) {
    if (i < 0 || i >= ids.length) return
    setPicked(null)
    setHovered(null)
    setSearchParams({ catalog: catalog!, page: ids[i] })
  }
```

Den bestehenden Leerzustand ersetzen — der Block

```tsx
  if (pages.data?.length === 0) {
    return (
      <Alert>
        <AlertTitle>Noch keine Seiten extrahiert</AlertTitle>
        …
      </Alert>
    )
  }
```

entfällt, weil ihn das Raster abdeckt. An seine Stelle treten die beiden
Ebenen-Zweige, direkt nach der Ladeprüfung:

```tsx
  if (catalog === null) {
    return (
      <div className="flex min-w-0 flex-col gap-4">
        <h1 className="text-3xl font-extrabold tracking-tight">Label-Inspektor</h1>
        <CatalogGrid
          tiles={tiles}
          unit="gelabelt"
          onSelect={(id) => setSearchParams({ catalog: id })}
          emptyHint={
            <>Noch keine Seiten extrahiert. Auf der Übersicht <code>02_extract_words</code> starten (davor <code>01_download_flyers</code>, falls data/raw/ leer ist).</>
          }
        />
      </div>
    )
  }

  if (tiles.length > 0 && !tiles.some((t) => t.id === catalog)) {
    return (
      <div className="flex min-w-0 flex-col gap-4">
        <h1 className="text-3xl font-extrabold tracking-tight">Label-Inspektor</h1>
        <Alert variant="destructive">
          <AlertTitle>Prospekt nicht gefunden</AlertTitle>
          <AlertDescription>
            Der Katalog <code>{catalog}</code> existiert nicht (mehr). Unten stehen die vorhandenen.
          </AlertDescription>
        </Alert>
        <CatalogGrid tiles={tiles} unit="gelabelt" onSelect={(id) => setSearchParams({ catalog: id })} />
      </div>
    )
  }
```

In der Kopfzeile der Seitenansicht den Brotkrumen unter die Überschrift setzen
(anders als im Annotator bleibt „Label-Inspektor" als Titel stehen):

```tsx
        <div className="flex items-baseline gap-3">
          <h1 className="text-3xl font-extrabold tracking-tight">Label-Inspektor</h1>
          <Crumbs
            items={[
              { label: "Prospekte", onClick: () => setSearchParams({}) },
              selected
                ? { label: catalog, onClick: () => setSearchParams({ catalog }) }
                : { label: catalog },
              ...(selected ? [{ label: selected.split("_").pop()! }] : []),
            ]}
          />
          <p className="font-mono text-xs text-muted-foreground">
            {idx >= 0 ? `${idx + 1} / ${ids.length}` : `${ids.length} Seiten`}
          </p>
        </div>
```

`PageList` bekommt die gefilterte Liste, aber **kein** `goldStatus` — der
Inspektor zeigt LLM-Labels:

```tsx
          <PageList
            pages={catalogPages}
            selected={selected}
            onSelect={(id) => {
              setPicked(null)
              setHovered(null)
              setSearchParams({ catalog: catalog, page: id })
            }}
          />
```

Importe ergänzen: `CatalogGrid`, `Crumbs`, `groupPagesByCatalog`, `useMemo`
(falls noch nicht vorhanden).

- [ ] **Schritt 4: Tests laufen lassen**

Ausführen: `cd frontend && npm test`
Erwartet: alle Tests grün

Ausführen: `cd frontend && npx tsc --noEmit`
Erwartet: keine Fehler

Ausführen: `.venv/bin/python -m pytest -q` (aus dem Projektroot)
Erwartet: 62 passed

- [ ] **Schritt 5: Doku ergänzen**

In `README.md` im Frontend-Abschnitt diesen Absatz ergänzen:

```markdown
### Prospekt-Übersicht

Inspektor und Annotieren beginnen mit einer Übersicht über alle Prospekte —
eine Kachel je Katalog mit Seitenzahl, Ladedatum und Fortschritt. Erst ein
Klick darauf öffnet die Seitenliste. Der Weg zurück führt über den Pfad in
der Kopfzeile. Der Fortschritt bedeutet je nach Werkzeug Verschiedenes: im
Inspektor „vom LLM gelabelt", beim Annotieren „von Hand fertig annotiert".
```

- [ ] **Schritt 6: Committen**

```bash
git add frontend/src/features/inspector/ README.md
git commit -m "Stelle den Inspektor auf drei Ebenen um

Gleiche Kachel-Darstellung wie im Annotator, andere Kennzahl: hier zählt,
was das LLM gelabelt hat. Der bisherige Leerzustand entfällt - ihn deckt
jetzt das Raster ab."
```

---

## Nach der Umsetzung

Der Hover-Fix aus der vorherigen Runde (`pointerEvents` im Overlay) ist nur durch einen CSS-Test abgesichert, weil jsdom kein SVG-Hit-Testing macht. Er braucht eine manuelle Probe unter `/annotate`: Wortkästen sollten auf ganzer Fläche treffbar sein, nicht nur an der Kontur.
