# Steuerzentrale — Design

**Stand: 29.07.2026**

## Zweck

Die Pipeline lässt sich aus dem Frontend starten, aber nicht bedienen. Kein
Parameter ist erreichbar, kein Fehler nachvollziehbar, kein Lauf auffindbar,
sobald er vorbei ist. Dieses Dokument beschreibt den Umbau: Ausführung und
Konfiguration bekommen einen eigenen Tab, die Übersicht wird zur Lagebesprechung.

## Der Anlass, konkret

```
$ .venv/bin/python scripts/01_download_flyers.py
usage: 01_download_flyers.py [-h] [--max-pages MAX_PAGES] url
error: the following arguments are required: url
--- exit: 2
```

`runner.py` startet jeden Schritt als `python scripts/{job}.py [variant]`, und
`JOBS["01_download_flyers"]` ist leer. Der Knopf „Prospekte laden" in der
Übersicht kann also nicht funktionieren — er endet immer mit Exit-Code 2, bevor
irgendetwas passiert. Sichtbar ist davon nur eine rote Zahl.

Das ist kein Einzelfall, sondern das Muster: Der Runner kennt genau eine Sorte
Parameter, die Positional-Variante `gbert`/`layoutxlm`. Alles andere, was die
Skripte anbieten — `--max-pages`, `--epochs`, `--batch-size`, `--lr`, `--split`,
die Katalog-URL — ist vom Frontend aus unerreichbar. `07_flair_baseline` steht
gar nicht erst im Runner.

## Zwei Befunde aus dem Netz

Geprüft am 29.07.2026 gegen `penny-publish.blaetterkatalog.de`:

```
getcatalog.do?catalogId=1342881   ->  HTTP 404
   .../1342881/1/pdf/save/bk_1.pdf  ->  HTTP 200, 940 KB

getcatalog.do?catalogId=1350000   ->  HTTP 200  "KW32 34835 SUEDBAYERN"
   .../1350000/1/pdf/save/bk_1.pdf  ->  HTTP 403
```

**Erstens:** `scraping.get_catalog_version()` ruft `resp.raise_for_status()` auf.
Für Katalog 1342881 — den Katalog, auf dem das gesamte Projekt bisher beruht —
ist diese Seite inzwischen 404. Ein erneuter Download würde heute mit einer
Exception abbrechen, obwohl die PDFs noch abrufbar sind. Der im Docstring
dokumentierte Fallback `return "1"` wird nie erreicht, weil die Exception vorher
fliegt. Metadatenseiten verschwinden also früher als die PDFs.

**Zweitens:** Katalog-IDs lassen sich nicht erraten. 14 Proben rund um eine
bekannte gültige ID ergaben 0 Treffer; der ID-Raum ist dünn besetzt. Ein
Scan-Feature wäre hunderte Requests pro Fund und gegenüber dem Server unhöflich.
IDs kommen weiter von Hand aus der Penny-Website — geteilt wird stattdessen das
Ergebnis.

## Aufteilung der Oberfläche

**Übersicht** (`/`) zeigt den Stand, führt nichts aus: vier Kennzahlkarten
(geladen, extrahiert, LLM-gelabelt, von Hand annotiert), die Pipeline als reines
Zustandsdiagramm mit Link in die Steuerzentrale, die Label-Verteilung über alle
gelabelten Seiten, das beste F1 je Arm, die Katalogtabelle.

**Steuerzentrale** (`/control`, neuer Tab) führt aus: Schritte mit
Parameterformularen, laufender Job mit Konsole, Lauf-Historie, Katalog-Verwaltung.

```
+-- Schritte ----------+-- Live -------------+-- Historie --------+
| 01 Prospekte laden   | 04_train gbert      | x 01_download 14:22|
|   URL   [.........]  | 3m12s . laeuft      |   Exit 2, url fehlt|
|   Seiten[ 40 ]  >    |                     | v 02_extract  14:25|
| 02 Woerter    >      | Epoch 2/10          | v 04_train    14:31|
| 03 LLM-Label  >      | loss 0.31 ...       | x 03_label    15:02|
| 04 Training          | ###########         |   Exit 1, HTTP 429 |
|   Variante[gbert v]  |                     |                    |
|   Epochen [ 10 ]     | [ Stoppen ]         | Klick -> voller Log|
|   Lernrate[5e-5]  >  |                     |                    |
| 05 Evaluation >      |                     |                    |
| 07 Flair      >      |                     |                    |
+----------------------+---------------------+--------------------+
| Kataloge: 1342881 KW30 (40 S. lokal)  1350000 KW32 (403)        |
| Neuer Katalog: URL [......]  [Pruefen] -> KW33, v2, S.1 ok  [+] |
+------------------------------------------------------------------+
```

## Job-Katalog als Datenstruktur

Neu: `magda/jobs.py`. Der Runner kümmert sich künftig nur um Prozesse; *was*
startbar ist und *womit*, steht hier.

```python
@dataclass(frozen=True)
class Param:
    name: str            # argv-Form: "url" oder "--max-pages"
    kind: str            # "str" | "int" | "float" | "choice"
    label: str           # Anzeigename im Formular
    default: object | None = None
    choices: tuple[str, ...] = ()
    required: bool = False
    help: str = ""

    @property
    def key(self) -> str:
        """Name in JSON und Formular: "--max-pages" -> "max_pages"."""
        return self.name.lstrip("-").replace("-", "_")

@dataclass(frozen=True)
class Job:
    script: str          # "01_download_flyers"
    title: str
    what: str
    params: tuple[Param, ...]

def build_command(job: str, values: dict) -> list[str]:
    """Validiert und baut argv. Wirft ValueError bei allem Unerwarteten."""
```

Die Schlüssel im `values`-Dict sind `Param.key`, nicht `Param.name` — also
`{"url": "...", "max_pages": 40}`. Die argv-Form kennt nur `build_command`;
Frontend und JSON sehen sie nie.

`build_command` ist die Sicherheitsgrenze. Sie ersetzt die bisherige
Varianten-Prüfung und lehnt ab: unbekannter Job, unbekannter Parametername,
nicht konvertierbarer Wert, Wert außerhalb `choices`, fehlender Pflichtparameter.
Werte werden **typkonvertiert, nie als Text zusammengeklebt**, und der Prozess
startet weiterhin ohne Shell.

Der Vertrag aus CLAUDE.md — „kein Durchreichen beliebiger Kommandos" — bleibt
damit erhalten. Er wird von „eine feste Liste Varianten" auf „eine feste Liste
typisierter Parameter" gehoben. Ein freies Argument-Textfeld wäre effektiv eine
Remote-Shell und ist ausdrücklich nicht Teil dieses Entwurfs.

Die Sonderrolle von `variant` entfällt: es wird ein gewöhnlicher
`choice`-Parameter. `POST /api/run` nimmt künftig `{job, args: {...}}` statt
`{job, variant}`.

Abgedeckte Jobs und ihre Parameter:

| Job | Parameter |
|---|---|
| `01_download_flyers` | `url` (str, Pflicht), `--max-pages` (int, 40) |
| `02_extract_words` | keine |
| `03_label_words` | keine |
| `04_train` | `variant` (choice), `--epochs` (int, 10), `--batch-size` (int, 8), `--lr` (float, 5e-5) |
| `05_evaluate` | `variant` (choice), `--split` (choice: dev/test) |
| `07_flair_baseline` | `--reference` (choice: gold/llm), `--split` (choice: dev/test/all), `--model` (str) |

## Lauf-Historie

Neu: `magda/runs.py`. Pro Lauf zwei Dateien unter `data/runs/`:

| Datei | Inhalt |
|---|---|
| `20260729-142201_01_download_flyers.json` | Job, Parameter, vollständiges argv, Start, Ende, Exit-Code, Dauer |
| `20260729-142201_01_download_flyers.log` | roher Output, ungekürzt |

Getrennt, weil ein Trainingslauf zehntausende Zeilen schreibt und die Liste
trotzdem schnell laden muss — die Historie liest nur die JSON-Dateien. Der
400-Zeilen-Ringpuffer in `runner.py` bleibt für die Live-Ansicht bestehen; der
Log auf Platte ist vollständig und überlebt den Backend-Neustart.

Beim Anlegen eines Laufs werden die ältesten über 100 hinaus gelöscht. `data/`
ist gitignored, aber nicht unbegrenzt.

`config.RUNS_DIR = DATA_DIR / "runs"`.

## Katalog-Verzeichnis

Neu: `magda/catalogs.py` und `catalogs.json` im Projektwurzelverzeichnis,
**versioniert**. Dieselbe Begründung wie bei `gold/`: eine gefundene Katalog-ID
ist nicht reproduzierbar, ein verlorenes Verzeichnis kostet Sucharbeit.

Ein Eintrag: `{id, url, title, version, pages, added, added_by, note}`.
Geschrieben wird atomar über `mkstemp` + `os.replace`, wie in `put_gold`.

`magda/scraping.py` bekommt zwei Änderungen:

- `get_catalog_version` fängt 404 ab und nutzt endlich den dokumentierten
  Fallback `"1"`. Bei 5xx und Verbindungsfehlern wird weiterhin geworfen — ein
  ausgefallener Server ist etwas anderes als eine abgelaufene Metadatenseite.
- `probe_catalog(url, session)` → `{catalog_id, version, title, page_1_ok,
  page_1_bytes, error}`. Für den Prüfen-Knopf: zeigt vor dem Download, was man
  bekommt, statt es aus einem fehlgeschlagenen Lauf zu erschließen.

## API

Neu beziehungsweise geändert:

| Endpunkt | Zweck |
|---|---|
| `GET /api/jobs` | Job-Katalog samt Parametern; das Frontend baut daraus die Formulare |
| `POST /api/run` | **geändert**: `{job, args}` statt `{job, variant}` |
| `GET /api/runs` | Historien-Metadaten, neueste zuerst |
| `GET /api/runs/{run_id}` | Metadaten samt vollständigem Log |
| `GET /api/catalogs` | Verzeichnis, angereichert um lokal vorhandene Seitenzahl |
| `POST /api/catalogs` | Eintrag anlegen |
| `DELETE /api/catalogs/{id}` | Eintrag entfernen |
| `POST /api/catalogs/probe` | URL prüfen, ohne herunterzuladen |
| `GET /api/labels/distribution` | Tag-Häufigkeit je Entity-Typ über `data/labeled/` |
| `GET /api/status` | **erweitert**: `gold_done`, `gold_in_progress` in `totals` |

**Vertragsänderung, gehört in CLAUDE.md:** Die API schreibt bisher
„ausschließlich nach `gold/`". Künftig zusätzlich nach `catalogs.json` und
`data/runs/`. Das bleibt eine aufgezählte Erlaubnisliste, kein freier
Schreibzugriff — aber die Zeile in der Doku stimmt sonst nicht mehr.

## Frontend

```
features/control/          neu
  control-page.tsx         Dreispalter, Zusammenbau
  job-form.tsx             baut Formular aus /api/jobs
  run-history.tsx          Liste + Detailansicht
  catalog-manager.tsx      Verzeichnis + Pruefen-Knopf
  use-run.ts               Polling/Start/Stop, aus pipeline-runner geloest
  console.tsx              aus pipeline-runner uebernommen

features/overview/
  overview-page.tsx        umgebaut, volle Breite
  pipeline-diagram.tsx     neu: nur Anzeige, Link nach /control
  label-distribution.tsx   neu
  pipeline-runner.tsx      entfaellt
  steps.ts                 bleibt, ergaenzt um 07_flair_baseline
```

`steps.ts` überlebt unverändert: die `stepStates`-Logik ist getestet und wird von
Diagramm *und* Steuerzentrale gebraucht.

Breite: `max-w-5xl` (1024 px) fliegt aus Übersicht und Evaluation. Der Rahmen
`max-w-[1600px]` steht bereits in `layout.tsx`, er wurde nur nirgends genutzt.
Fließtextabsätze behalten eine eigene Lesebreite — Volltextzeilen über 1600 px
liest niemand.

## Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| Pflichtparameter leer (URL) | Startknopf gesperrt, Hinweis am Feld — kein Lauf, der mit Exit 2 endet |
| Unbekannter Parameter im Request | 400, `build_command` wirft |
| Wert außerhalb `choices` | 400 |
| `getcatalog.do` liefert 404 | Version `"1"`, Warnung im Log, Download läuft weiter |
| PDFs liefern 403 | Lauf endet mit Exit ≠ 0; Historie zeigt Status, URL und vollen Log |
| Katalog schon im Verzeichnis | 409, kein stiller Duplikat |
| `catalogs.json` kaputt (Merge-Konflikt) | Verzeichnis leer plus sichtbare Warnung, Rest der Seite lebt — wie bei `gold/` |
| Zweiter Lauf während eines Laufs | 409, unverändert |
| `data/runs/` fehlt | wird angelegt; leere Historie ist kein Fehler |
| `run_id` mit `/` oder `..` | 404. Die ID ist ein opaker Schlüssel, kein Pfad — `GET /api/runs/{id}` gleicht sie gegen die vorhandenen Dateien ab, statt sie an `Path` zu geben |

## Tests

Backend:

- `build_command` baut korrektes argv für jeden Job
- `build_command` lehnt unbekannten Job, unbekannten Parameter, falschen Typ,
  Wert außerhalb `choices` und fehlenden Pflichtparameter ab
- `runs`: Lauf schreibt JSON und Log, `list_runs` sortiert neueste zuerst,
  Aufräumen kappt bei 100
- `catalogs`: Anlegen, Duplikat → Konflikt, atomares Schreiben, kaputte Datei
  ergibt leeres Verzeichnis statt Exception
- `scraping.get_catalog_version` fällt bei 404 auf `"1"` zurück und wirft bei 500
- `probe_catalog` mit gefälschter Session
- Die neuen Endpunkte, und `POST /api/run` mit `args`

Frontend:

- `job-form` rendert Felder aus einem Schema und sperrt bei leerem Pflichtfeld
- `control-page` schickt die eingegebenen Args beim Start
- `run-history` zeigt Exit-Code und öffnet das Detail
- `pipeline-diagram` stellt die drei Zustände dar und verlinkt nach `/control`
- Übersicht zeigt die vierte Karte mit der Zahl handannotierter Seiten

## Nicht im Scope

- **Keine Presets.** Benannte Parametersätze lohnen sich erst, wenn wiederkehrende
  Konfigurationen entstehen. Die Historie zeigt ohnehin, womit ein Lauf lief.
- **Kein SSE-Streaming.** Das Polling alle 1,5 s funktioniert; ein zweiter
  Übertragungsweg brächte eigene Fehlerfälle ohne neuen Nutzen.
- **Kein ID-Scannen.** Empirisch widerlegt, siehe oben.
- **Keine parallelen Jobs.** Ein Job zur Zeit bleibt; die Skripte sind idempotent,
  Abbruch ist folgenlos.
- **Keine Authentifizierung.** Lokales Forschungssetup, unverändert.

## Offen, bewusst nicht entschieden

- **Ob `catalogs.json` je Team-Mitglied Einträge oder eine gemeinsame Liste
  führt.** Aktuell eine Liste mit `added_by`-Feld. Ob daraus Merge-Konflikte
  werden, zeigt sich erst, wenn alle drei gleichzeitig Kataloge eintragen; der
  Fehlerfall ist abgefangen, die Ergonomie nicht entschieden.
