# Die Rohdaten liegen nicht mehr im Repo

`data/raw/` (Original-PDFs) und `data/images/` (gerenderte Seitenbilder) sind
seit diesem Commit nicht mehr versioniert. Alles andere unter `data/` bleibt
es – das ist die Grundlage, auf der jede Zahl im Bericht nachrechenbar ist.

## Warum ausgerechnet diese beiden

| Ordner | Größe | ersetzbar? | wofür gebraucht |
|---|---|---|---|
| `data/images` | 809 MB | **ja, vollständig** | LayoutXLM-Training, Annotator |
| `data/raw` | 763 MB | **nein** | nur Schritt 02 und die Bildgenerierung |
| `data/words` | 5,7 MB | aus den PDFs | alles danach |
| `data/labeled` | 15 MB | nur mit ~3,5 h LLM-Zeit | Training, Messung |
| `data/predictions`, `eval`, `splits`, `offer_groups`, `gold` | ~11 MB | nein | der Bericht |

Die Aufteilung folgt einer einzigen Frage: *Was ist eine Ableitung, und was ist
ein Beleg?* `data/images` ist eine Ableitung – `cli/extract.py` rendert die
PNGs deterministisch aus den PDFs, sie stehen in git wie ein eingecheckter
Build-Ordner. `data/raw` ist das Gegenteil: unersetzlich, aber am seltensten
gebraucht. Pennys Markt-API kennt nur die laufende Woche, und Katalog-IDs
lassen sich nicht erraten (14 Proben rund um eine gültige ID ergaben 0
Treffer). Eine verlorene Woche ist endgültig verloren.

Zusammen sind das 1,57 GB Binärmasse gegen ~32 MB, an denen die Messungen
hängen. Bei ~440 MB je Erntewoche wäre das Repo binnen zwei Monaten jenseits
von 5 GB gewachsen.

Was dadurch **nicht** verlorengeht, ist der ursprüngliche Zweck der
Versionierung (CLAUDE.md, 02.08.2026): dass niemand im Team Ernte, Extraktion
und Labeling selbst durchlaufen muss. `data/words/` und `data/labeled/` bleiben
in git – wer trainieren oder messen will, braucht das Archiv gar nicht
anzufassen.

## Woher man die PDFs bekommt

Sie liegen im geteilten Google-Drive-Ordner des Projekts. Wer Zugriff braucht,
fragt Noah.

```bash
# 1. Ordner data/raw/ aus Drive herunterladen und ins Projektroot entpacken
# 2. Vollständigkeit und Unversehrtheit prüfen:
shasum -a 256 -c docs/archive/data-raw.sha256
```

Die Prüfung ist der eigentliche Grund für das Manifest. Ein Drive-Ordner sagt
einem nicht, ob eine Datei fehlt oder sich verändert hat – git täte das über
seine Hashes, Drive tut es nicht. `shasum -c` meldet jede fehlende Datei als
`FAILED open or read` und jede veränderte als `FAILED`.

Erzeugt wurde das Manifest mit:

```bash
find data/raw -name "*.pdf" | sort | xargs shasum -a 256 > docs/archive/data-raw.sha256
```

Nach jeder Erntewoche gehört es neu erzeugt und mitcommittet – sonst gilt die
neue Woche als fehlend.

## Wie man die Seitenbilder zurückbekommt

Gar nicht herunterladen: neu rendern.

```bash
magda extract --render-missing
```

Der Schritt schreibt die fehlenden PNGs nach `data/images/` und lässt
`data/words/` unangetastet. Er braucht dafür `data/raw/`, also das Archiv. Wer
nur GBERT trainiert oder auswertet, braucht die Bilder überhaupt nicht – nur
LayoutXLM (visueller Backbone) und der Annotator im Frontend greifen darauf zu.

**Hier stand bis zum 03.09.2026 `magda extract` ohne Option, und das war
falsch.** Der normale Lauf überspringt eine Seite an ihrer vorhandenen
Wortdatei, *bevor* er das Bild rendert (`cli/extract.py`) – und `data/words/`
ist versioniert. In einem frischen Klon entstand damit kein einziges Bild, bei
der Erfolgsmeldung „0 Seiten verarbeitet, 666 schon vorhanden". Der Fehler war
still: die Anleitung lief durch, der Annotator zeigte danach leere Seiten. Das
ist die Kehrseite von „`data/images` ist eine Ableitung" – die Ableitung stimmt
nur, solange der ableitende Schritt sie auch wirklich herstellt.

## Die eine Ausnahme im Repo

43 Seitenbilder liegen doch in git: die Seiten der Handannotation
(`docs/annotation-task.md`), also der Testkatalog 1364390 plus die vier
übrigen Cluster-Vertreter. 89 MB, und sie widersprechen der Tabelle oben mit
Absicht. Der Grund ist der Adressat: Wer nur annotiert, sollte nicht erst ein
1,1-GB-Archiv aus Drive holen, ein Manifest prüfen und einen Renderschritt
laufen lassen, um 43 von 668 Bildern zu bekommen. `git clone` und `magda serve
--frontend` reichen jetzt.

Abgelegt sind sie **byte-identisch zum lokalen Stand, nicht verkleinert**.
`offer_pairs.load_pixels` liest dieselben Dateien für die Farbmerkmale;
verkleinerte Bilder ergäben auf einem anderen Rechner andere Merkmalswerte und
damit stillschweigend andere Zahlen.

Die Ausnahme steht als Positivliste in `.gitignore` und gilt nur für diese
Seiten. Sie ist kein Präzedenzfall für die nächste Erntewoche: bei ~440 MB je
Woche wäre das genau der Weg, den die Auslagerung beenden sollte.
