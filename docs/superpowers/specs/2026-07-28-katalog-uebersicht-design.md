# Katalog-Übersicht in Inspektor und Annotator

**Stand: 28.07.2026** — Design, freigegeben vor der Umsetzung.

## Warum

Inspektor und Annotator öffnen heute direkt eine Seitenliste über *alle* Seiten
*aller* Kataloge, getrennt nur durch Zwischenüberschriften. Bei einem Katalog
sind das 40 Einträge — brauchbar. Bei zehn Katalogen sind es 400, und beide
Werkzeuge werden unbenutzbar, ohne dass irgendetwas kaputtgeht.

Der Anlass ist praktisch: Beim ersten Annotieren hat sich gezeigt, dass eine
Person einen ganzen Prospekt in vertretbarer Zeit schafft. Damit wird die
Arbeitsteilung „ein Prospekt pro Person" statt „Seiten aufteilen", und die
Zahl der Kataloge wächst absehbar von einem auf zehn bis zwanzig.

Beide Werkzeuge brauchen deshalb eine Ebene davor: eine Übersicht über die
Prospekte, aus der man einen auswählt.

## Umfangsänderung, die daraus folgt

Das Gold-Spec vom selben Tag ging von 40 handannotierten Seiten aus und nannte
sie ausdrücklich *Messinstrument, nicht Datenbasis*. Bei drei Personen mit je
einem Prospekt sind es 120 Seiten. Das ist genug, um darauf zu trainieren.

Damit wird die dortige Empfehlung („Gold = Testset, LLM-Labels =
Trainingsset") fragwürdig — eine Alternative wäre, auf Gold zu trainieren und
zu testen und die LLM-Labels nur noch als Vergleichsarm zu behalten. Das wäre
wissenschaftlich stärker, weil dann kein Label-Rauschen mehr im Training steckt.

**Das ist keine Entscheidung dieses Specs.** Sie gehört zu den offenen Punkten
in `CLAUDE.md` und braucht Bogdan und Kjell. Hier steht sie nur, weil sie ohne
die Beobachtung „ein Prospekt pro Person ist machbar" nicht sichtbar geworden
wäre.

## Abgrenzung

Nicht Teil dieses Specs:

- **Prospekte aus der Übersicht herunterladen.** Überschneidet sich mit dem
  bestehenden Pipeline-Runner auf der Übersichtsseite.
- **Zuständigkeiten verwalten.** Wer welchen Prospekt annotiert, klärt das Team
  per Absprache; der Annotatorname steht ohnehin in jeder Gold-Datei.
- **Vorschaubilder der Titelseiten.** Wäre gut wiedererkennbar, kostet aber
  Ladezeit für einen Nutzen, den ID und Datum auch stiften.
- **Eigene Kennzahlen für die Fehleranalyse** (Anteil getaggter Wörter, Zahl
  leerer Seiten). Bräuchte eine neue Aggregation im Backend; der Nutzen fällt
  erst bei der Fehleranalyse an.

## Navigation

Drei Ebenen, ohne neue Routen — gesteuert über Query-Parameter, wie im
bestehenden Code (`useSearchParams` mit `?page=`):

| URL | Ansicht |
|---|---|
| `/annotate` | Prospekt-Übersicht |
| `/annotate?catalog=1342881` | Seitenliste dieses Prospekts |
| `/annotate?catalog=1342881&page=1342881_p3` | Seite geöffnet |

Für `/inspector` identisch.

Die `page_id` enthält den Katalog bereits (`1342881_p3`), serverseitig gibt es
dafür `_catalog_of()`. Ein gesetzter `?page=` impliziert also den Katalog; der
einzige Zustand, der einen eigenen Parameter braucht, ist „Prospekt geöffnet,
aber noch keine Seite gewählt". Die Ebene ergibt sich daraus:

```
page gesetzt   -> Seitenansicht (Katalog notfalls aus der page_id ableiten)
catalog gesetzt -> Seitenliste
sonst          -> Übersicht
```

Zurück führt ein Brotkrumen-Pfad in der Kopfzeile: `Prospekte / 1342881 / p3`.

Pfeiltasten blättern weiterhin durch die Seiten — aber nur noch **innerhalb**
des gewählten Prospekts. Das ist keine Einschränkung, sondern die Behebung
eines Nebeneffekts: Bisher blättert man am Katalogende stillschweigend in den
nächsten hinein.

## Kachel

```
┌────────────────────────────────┐
│ 1342881                        │
│ 40 Seiten · geladen 23.07.     │
│ ████████░░░░░░░░  18/40 fertig │
└────────────────────────────────┘
```

Katalog-IDs sind nichtssagende Blätterkatalog-Nummern. Seitenzahl und
Ladedatum machen sie unterscheidbar, und beides ist aus dem Dateisystem
ableitbar — anders als der Gültigkeitszeitraum, der nur dort existiert, wo das
LLM ihn als `VALID` erkannt hat, und im Annotator anfangs gar nicht.

Die Zahl unten bedeutet je nach Werkzeug etwas anderes:

- **Annotator:** Seiten mit Gold-Status `done`
- **Inspektor:** Seiten mit LLM-Labels

Beide Male ist der Balken aussagekräftig, sobald mehrere Kataloge im Bestand
sind — ein frisch geladener Prospekt steht dann sichtbar bei `0/40`.

Kacheln sind nach Katalog-ID sortiert, wie die bestehende Katalogtabelle auf
der Übersichtsseite.

### Warnzustände im Annotator

Die Gold-Übersicht kennt seit der Härtungsrunde zwei Sonderzustände pro Seite,
die auf Katalogebene sichtbar bleiben müssen:

- **`stale`** — die Wortliste hat sich seit dem Annotieren geändert, die
  Span-Indizes zeigen auf andere Wörter. Auf der Kachel als Warnung mit Anzahl.
- **`broken`** — die Gold-Datei ist nicht lesbar (wahrscheinlichster Fall: ein
  Merge-Konflikt in dem versionierten Verzeichnis). Ebenso.

Ohne das meldet die Kachel „40/40 fertig", während jede Seite ungültig ist —
genau der Schaden, den man in der Übersicht zuerst sehen sollte.

## Architektur

Eine geteilte Komponente, zwei Aufrufer.

```
frontend/src/lib/catalogs.ts           reine Aggregation, ohne React
frontend/src/components/catalog-grid.tsx   Kacheldarstellung
frontend/src/components/breadcrumb.tsx     Brotkrumen-Pfad
```

Die beiden Übersichten unterscheiden sich nur in der Zahl auf der Kachel und im
Ziel des Klicks. Layout, Fortschrittsbalken, Sortierung und Leerzustand sind
identisch. Zwei Kopien davon laufen innerhalb weniger Wochen auseinander — dann
sieht der Inspektor anders aus als der Annotator, ohne dass das jemand
entschieden hätte.

`catalogs.ts` enthält die Gruppierung als reine Funktionen:

```ts
interface CatalogTile {
  id: string
  pages: number        // Seiten mit extrahierten Wörtern
  done: number         // je nach Werkzeug: Gold fertig, oder LLM-gelabelt
  downloaded: string | null
  stale: number        // nur im Annotator > 0
  broken: number       // nur im Annotator > 0
}

groupGoldByCatalog(summaries: GoldSummary[], status: CatalogStatus[]): CatalogTile[]
groupPagesByCatalog(pages: PageSummary[], status: CatalogStatus[]): CatalogTile[]
```

Beide liefern dieselbe Form; `stale` und `broken` bleiben in der
Inspektor-Variante auf `0`, weil es dort keine Gold-Zustände gibt. Die Kachel
zeigt sie nur an, wenn sie größer als null sind — damit braucht sie keine
Kenntnis darüber, welches Werkzeug sie gerade darstellt.

`CatalogStatus` ist der bestehende Typ aus `/api/status` (um `downloaded`
erweitert). Damit ist der fehleranfällige Teil — das Zählen — ohne Rendering
testbar, nach dem Vorbild von `span-editor.ts`.

Die Kachel-Komponente bekommt fertige `CatalogTile`-Objekte und einen
Klick-Handler. Sie weiß nicht, ob sie Gold oder LLM-Labels zeigt.

## Backend

Eine einzige Ergänzung: `/api/status` liefert pro Katalog ein Ladedatum.

```python
{"id": "1342881", "raw": 40, "words": 40, "images": 40, "labeled": 40,
 "downloaded": "2026-07-23"}
```

Abgeleitet aus der Änderungszeit des Katalogverzeichnisses unter `data/raw/`.
Fehlt das Verzeichnis, ist das Feld `null`.

Alles andere ist bereits vorhanden: `/api/gold` liefert jede Seite mit Status,
`/api/pages` jede Seite mit `labeled`. Die Aggregation pro Katalog macht das
Frontend — sie ist billig (Hunderte Einträge) und hält die API frei von
Anzeigelogik.

## Fehlerbehandlung

- **Kein Katalog vorhanden:** Leerzustand mit Hinweis auf
  `01_download_flyers`, analog zum bestehenden Leerzustand im Inspektor.
- **Unbekannter Katalog in der URL** (`?catalog=gibtsnicht`): Übersicht mit
  Hinweis statt leerer Seitenliste. Ein veralteter Lesezeichen-Link darf nicht
  in einer Ansicht ohne Ausweg enden.
- **Seite ohne zugehörigen Katalog** (`?page=` auf eine gelöschte Seite):
  bestehendes Verhalten, die Seitenabfrage liefert 404.

## Tests

| Datei | Deckt ab |
|---|---|
| `frontend/src/lib/catalogs.test.ts` | Gruppierung, Zählung, Sortierung, `stale`/`broken`, fehlende Metadaten |
| `frontend/src/components/catalog-grid.test.tsx` | Darstellung, Klick, Leerzustand |
| `frontend/src/features/annotate/annotate-page.test.tsx` | Ebenenwechsel: Übersicht ohne Parameter, Liste mit `catalog`, Seite mit `page` |
| `frontend/src/features/inspector/inspector-page.test.tsx` | dieselben drei Ebenen |
| `tests/test_api.py` | `downloaded` im Status, `null` ohne Verzeichnis |

## Reihenfolge der Umsetzung

1. `downloaded` in `/api/status` + Test
2. `catalogs.ts` mit den beiden Gruppierungsfunktionen + Tests
3. `catalog-grid.tsx` und `breadcrumb.tsx` + Tests
4. Annotator auf drei Ebenen umstellen
5. Inspektor auf drei Ebenen umstellen

Die Schritte 1 und 2 sind ohne Oberfläche testbar. Schritt 4 und 5 sind
bewusst getrennt: Der Annotator ist der dringendere Fall, und wenn Schritt 5
scheitert, bleibt der Inspektor im heutigen, funktionierenden Zustand.

## Getroffene Annahmen

Der Auftrag zur eigenständigen Umsetzung kam, bevor eine Frage beantwortet war.
Entschieden wurde:

- **Gleiche Kachel für beide Werkzeuge, unterschiedliche Bedeutung der Zahl.**
  Die Alternative wäre eine eigene Kennzahl für den Inspektor gewesen (Anteil
  getaggter Wörter, Zahl leerer Seiten). Dagegen sprach, dass sie eine neue
  Backend-Aggregation braucht und der Nutzen erst bei der Fehleranalyse
  anfällt. Der einfache Balken ist bei mehreren Katalogen auch im Inspektor
  aussagekräftig.
