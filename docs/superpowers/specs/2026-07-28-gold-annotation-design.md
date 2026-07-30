# Gold-Annotation im Dashboard

**Stand: 28.07.2026** — Design, freigegeben vor der Umsetzung.

## Warum

Wir evaluieren GBERT und LayoutXLM derzeit gegen LLM-Labels. Die Testzahlen
beantworten damit die Frage „wie gut imitiert das Modell Mistral?", nicht „wie
gut extrahiert es Angebotsdaten?". Solange Mistral bei BRAND selbst schwach
ist, bestrafen wir das Modell dafür, dass es Mistral nicht genau genug
nachmacht.

Ein von Hand annotierter Katalog löst das. Er liefert:

1. eine Messlatte für die Qualität der LLM-Labels,
2. ein Testset, das echte Leistung misst statt Übereinstimmung mit dem LLM,
3. Klarheit in der Annotationsrichtlinie — Fragen wie „ist *Bio* eine Marke
   oder Teil des Produktnamens?" beantwortet man nicht am Schreibtisch, sondern
   wenn man zum dritten Mal darüber stolpert.

Annotiert wird **von null**, nicht durch Korrigieren der LLM-Vorschläge.
Vorbelegte Labels erzeugen einen Anker-Bias: Plausibel aussehende Fehler werden
übersehen, und das Gold-Set fällt zu LLM-ähnlich aus. Es würde die LLM-Qualität
dann systematisch zu gut messen — also genau das verfehlen, wofür es existiert.

Umfang: Katalog 1342881, alle 40 Seiten. Das Team teilt die Seiten unter sich
auf.

## Abgrenzung

Nicht Teil dieses Specs, bewusst:

- **Auswertung Gold gegen LLM-Labels.** Der eigentliche Zweck, aber ein eigener
  Schritt. Sinnvoll als `scripts/06_compare_labels.py`, sobald genug Seiten
  fertig sind.
- **Rückgängig-Historie.** Ein falsch gesetzter Span ist durch erneutes
  Auswählen und Neusetzen in zwei Schritten korrigiert.
- **Nutzerverwaltung.** Der Annotatorname kommt aus einem Eingabefeld und liegt
  in `localStorage`.
- **Sperren bei Parallelzugriff.** Jeder arbeitet lokal gegen die eigene API,
  der Austausch läuft über Git.
- **Inter-Annotator-Agreement.** Keine Doppelannotation vorgesehen.

## Offene Team-Entscheidung

Aus dem Gold-Set ergibt sich eine naheliegende Split-Strategie:

```
1342881 (40 Seiten, handgelabelt)   →  Testset, vollständig
weitere Kataloge (LLM-gelabelt)     →  Trainingsset
```

Das trennt Train und Test entlang der Kataloge, beseitigt also die
Leakage-Sorge aus `CLAUDE.md`, und evaluiert gegen echte Labels. Die
Split-Strategie steht dort unter „nicht eigenmächtig festlegen" — dieses Spec
empfiehlt sie, beschließt sie aber nicht. Vor der Umstellung von
`data/splits/split.json` braucht es die Zustimmung von Bogdan und Kjell.

40 Gold-Seiten sind ausdrücklich **kein** ausreichender Trainingssatz. Sie sind
Messinstrument, nicht Datenbasis.

## Ablage

Gold-Labels liegen unter `gold/` auf Repo-Ebene und werden **versioniert** —
anders als alles unter `data/`. Der Unterschied ist grundsätzlich: Generierte
Artefakte sind reproduzierbar, Handarbeit ist es nicht. Ein verlorenes
`data/labeled/` kostet API-Zeit, ein verlorenes `gold/` kostet Arbeitstage.

Eine Datei pro Seite, `gold/1342881_p1.json`:

```json
{
  "page_id": "1342881_p1",
  "words_hash": "3f9a1c…",
  "status": "in_progress",
  "annotator": "noah",
  "updated": "2026-07-28T20:15:00",
  "spans": [
    {"start": 0, "end": 1, "label": "BRAND"},
    {"start": 1, "end": 4, "label": "PRODUCT"}
  ]
}
```

Eine Datei pro Seite heißt: Solange sich zwei Leute nicht dieselbe Seite
vornehmen, merged Git konfliktfrei. Die Aufteilung läuft über Absprache im
Team, nicht über das Werkzeug — dafür bräuchte es einen gemeinsamen Server,
den wir nicht haben.

### Spans statt BIO-Tags

`data/labeled/` speichert Tag-Listen, `gold/` speichert Spans. Zwei Gründe:
Ein Mensch denkt in Spans, und eine Liste aus 180 `"O"`-Einträgen ist in einem
Git-Diff nicht überprüfbar. `labels.spans_to_bio()` erzeugt die Tag-Liste
jederzeit daraus; die Funktion existiert und ist getestet.

### `words_hash`

SHA-256 über die Wortliste aus `data/words/{page_id}.json`: die Texte in ihrer
Reihenfolge als kompaktes JSON-Array, UTF-8 kodiert. Koordinaten gehen nicht
ein — verschiebt sich eine Box um einen Punkt, bleiben die Indizes gültig.

Die Wortreihenfolge aus Schritt 02 ist ein Vertrag, alle Spans sind Indizes
hinein. Ändert sich die Extraktion, zeigen die Indizes auf andere Wörter —
ohne dass irgendetwas kaputtgeht. Bei LLM-Labels ist das verkraftbar, man
erzeugt sie neu. Bei Handarbeit wäre es stiller Verlust von Arbeitstagen. Der
Hash macht den Fehler laut: Das Werkzeug weigert sich dann, die Annotation zu
bearbeiten, statt sie falsch darzustellen.

## API

Drei Endpunkte in `magda/api.py`:

| Methode | Pfad | Zweck |
|---|---|---|
| `GET` | `/api/gold` | Übersicht: `page_id` → Status, Annotator, Span-Zahl |
| `GET` | `/api/gold/{page_id}` | eine Annotation |
| `PUT` | `/api/gold/{page_id}` | speichern (Spans + Status) |

Das bricht die Read-only-Zusage im Modul-Docstring, also wird sie angepasst
statt stillschweigend verletzt. Vorbild ist `magda/runner.py`: Der darf
ausführen, kennt aber nur fünf Skripte und keine beliebigen Kommandos. Analog
darf die API schreiben, aber ausschließlich nach `gold/`.

`GET /api/gold` listet jede Seite aus `data/words/` — auch die ohne
Gold-Datei, dann mit Status `untouched`. So kann das Frontend den Fortschritt
anzeigen, ohne die Seitenliste separat abzugleichen. Gefiltert wird nicht: Bei
mehreren Katalogen im Bestand entscheidet das Frontend, welchen es zeigt.

### Validierung

`PUT` prüft serverseitig und lehnt ab, statt zu reparieren:

| Prüfung | Antwort |
|---|---|
| Span verletzt `0 ≤ start < end ≤ len(words)` | 422 |
| `label` nicht in `ENTITY_TYPES` | 422 |
| zwei Spans überlappen | 422 |
| `status` weder `in_progress` noch `done` | 422 |
| `words_hash` passt nicht zu `data/words/` | 409 |
| Seite existiert nicht in `data/words/` | 404 |

Die Überlappungsprüfung ist keine Förmlichkeit: BIO kann überlappende Entities
nicht darstellen. Was hier durchrutscht, geht beim Konvertieren still verloren.

Die ersten drei Prüfungen gehören nach `magda/labels.py` als
`validate_spans(spans, num_words)` und nicht in die API — sie sind
Domänenlogik und werden später auch vom Vergleichsskript gebraucht. Status,
Hash und Existenz der Seite prüft die API selbst; sie hängen am Dateizustand,
nicht an den Spans.

## Frontend

Eigene Route `/annotate`, neue Feature-Komponente. Der Inspektor bleibt
unangetastet: Er beantwortet „was hat das LLM getan?" und liest
`data/labeled/`; der Annotator beantwortet „was ist richtig?" und schreibt
`gold/`. Andere Datenquelle, anderer Zustand, anderer Schreibpfad.

```
frontend/src/features/annotate/
  annotate-page.tsx     Layout, Seitenwahl, Tastaturbelegung
  use-annotation.ts     Laden, Auto-Speichern (300 ms Debounce), Speicherstatus
  span-editor.ts        reine Funktionen: Span setzen, entfernen, auflösen
  label-legend.tsx      Ziffernlegende + Fortschritt über alle Seiten
```

`span-editor.ts` hält die gesamte Auswahl- und Überlappungslogik als reine
Funktionen ohne React (`applyLabel`, `removeAt`, `spansOverlapping`). Damit ist
der fehleranfälligste Teil ohne Rendering testbar.

`PageOverlay` bekommt keinen zweiten Datenpfad. Der Annotator hält Spans als
Zustand und rechnet sie über eine neue Funktion `spansToTags()` in `lib/bio.ts`
in genau das Tag-Format um, das das Overlay bereits versteht. Einzige Änderung
am Overlay: `onWordClick` reicht das Maus-Event als zweiten Parameter durch,
damit der Annotator die Shift-Taste sieht. Bestehende Aufrufer ignorieren ihn. `spansToTags` ist damit
das Frontend-Gegenstück zu `spans_to_bio()` — die Richtung, die dort bisher
fehlt. `groupEntities()` deckt die Gegenrichtung ab.

`PageList` bekommt einen dritten Zustand. Bisher kennt sie gelabelt/nicht
gelabelt, jetzt zusätzlich `untouched` / `in_progress` / `done`. Die Komponente
wird dafür um eine optionale Statusquelle erweitert, nicht kopiert.

### Bedienung

| Eingabe | Wirkung |
|---|---|
| Klick | Wort auswählen |
| Shift-Klick | Auswahl bis dorthin erweitern |
| `1`–`8` | Label setzen (Reihenfolge = `ENTITY_TYPES`) |
| `0` / `Entf` | Label der Auswahl entfernen |
| `←` `→` | Seite wechseln (wie im Inspektor) |
| `f` | Seite als fertig markieren |

Die Auswahl gehört zur Maus, das Label zur Tastatur. Wortweise
Tastaturnavigation wäre hier irreführend: Die Wortreihenfolge kommt aus
PyMuPDFs Textlayer und folgt nicht der visuellen Anordnung — bei einem Raster
aus Angebotskacheln liegt „Wort n+1" oft in einer anderen Kachel.

Die Ziffern folgen der Reihenfolge in `ENTITY_TYPES`, also `1` = PRODUCT bis
`8` = VALID. Ein später ergänzter Typ bekommt die nächste Ziffer — dieselbe
Nur-hinten-anhängen-Regel wie bei den Label-IDs.

Setzt ein neuer Span auf bestehende auf, gewinnt der neue; überlappende alte
werden entfernt. Eine Regel ohne Sonderfälle. Beim schnellen Arbeiten ist
Vorhersagbarkeit mehr wert als Cleverness.

### Status und Speichern

Jede Änderung wird nach 300 ms Ruhe automatisch gespeichert. Die Seite zählt
aber erst als Gold, wenn sie ausdrücklich auf `done` gesetzt wurde. Ohne dieses
Signal wäre eine leere Seite nicht von einer unbearbeiteten zu unterscheiden —
bei „von null annotieren" gibt es keine Vorbelegung, an der man das erkennt.
Halbfertige Seiten würden sonst ins Gold-Set rutschen und genau die Messung
verfälschen, für die es gebaut wird.

Nur Seiten mit `status: "done"` gehen später in Auswertung und Export.

## Fehlerbehandlung

Auto-Speichern darf nicht stillschweigend scheitern — sonst annotiert man
zwanzig Minuten ins Leere. Die Kopfzeile zeigt dauerhaft einen von drei
Zuständen: „gespeichert", „speichert…", „**nicht gespeichert**" (rot, mit
Wiederholen-Knopf). Der Zustand bleibt dabei im Speicher; ein erneuter Versuch
verliert nichts.

Bei 409 (`words_hash` passt nicht) wird die Seite schreibgeschützt mit
deutlicher Warnung angezeigt, statt sie zu überschreiben.

Bei 422 ist ein Fehler im Frontend passiert — die Bedienung kann keine
ungültigen Spans erzeugen. Die Meldung wird als Fehler angezeigt, nicht
weggeschluckt.

## Tests

| Datei | Deckt ab |
|---|---|
| `frontend/src/features/annotate/span-editor.test.ts` | Label setzen, Überlappung auflösen, Entfernen, Grenzfälle an Seitenanfang und -ende |
| `frontend/src/lib/bio.test.ts` | `spansToTags`, Rundlauf gegen `groupEntities` |
| `tests/test_labels.py` | `validate_spans` — Indexbereich, unbekanntes Label, Überlappung |
| `tests/test_api.py` | Speichern und Wiederlesen, 404/409/422-Fälle, `GET /api/gold` mit unberührten Seiten |

Die Tests biegen `config`-Pfade auf ein Temp-Verzeichnis um, wie die
bestehenden API-Tests.

## Reihenfolge der Umsetzung

1. `validate_spans` in `magda/labels.py` + Tests
2. Gold-Endpunkte in `magda/api.py` + Tests
3. `spansToTags` in `lib/bio.ts` + Test
4. `span-editor.ts` + Tests
5. `annotate-page.tsx`, `use-annotation.ts`, `label-legend.tsx`
6. `PageList` um Statusanzeige erweitern, Route und Navigation eintragen

Schritte 1–4 sind ohne Oberfläche testbar. Erst danach entsteht UI.
