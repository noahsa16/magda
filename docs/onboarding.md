# Einstieg – für Kjell und Bogdan

Diese Seite ist zum Vorlegen gedacht: Repo klonen, Claude Code im Projektroot
starten, den Satz unten hineinkopieren. Claude liest dann diese Datei und
`CLAUDE.md` und kann von da an alles Weitere beantworten.

```
Lies docs/onboarding.md und CLAUDE.md und erklär mir das Projekt.
Ich soll den Testkatalog 1364390 von Hand annotieren.
```

Nachfragen sind der Punkt der Sache. „Was heißt Gruppen-F1?", „Warum ist der
Testsplit tabu?", „Zeig mir, wo das gemessen wird" – Claude hat das Repo vor
sich und kann auf die Datei zeigen, statt zu raten.

## Loslegen

```bash
git clone https://github.com/noahsa16/magda.git && cd magda
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cd frontend && npm install && cd ..
magda serve --frontend          # API 8000, Oberfläche 5173
```

Mehr braucht die Annotation nicht: kein Google Drive, kein API-Key, kein
Pipeline-Lauf. Die 43 Seitenbilder eurer Aufgabe liegen im Repo, alles andere
unter `data/` ebenfalls. Wenn `magda` nicht gefunden wird, fehlt das
`pip install -e` oder das falsche `python` ist aktiv – immer `.venv/bin/python`.

Eure Aufgabe steht in **[annotation-task.md](annotation-task.md)**: erst die
Angebote unter `/group`, danach die Spans unter `/annotate`. Fangt dort an.

## Worum es geht

Wir ziehen strukturierte Angebotsdaten aus Penny-Prospekten. Ein großes
Vision-LLM labelt die Trainingsdaten automatisch, und darauf lernt ein kleines
eigenes Modell. Die Projektfrage ist **nicht** „wie gut wird es?", sondern
**„wie viel schlechter wird es, wenn wir es 170-mal billiger machen?"**

Gemessen: 0,264 s je Seite für unser Modell gegen 44,8 s fürs LLM. Bei F1
0.908. Diese eine Gegenüberstellung trägt den ganzen Bericht.

## Die zwei Stufen

Ein Prospekt hat zwei Probleme, und sie sind verschiedener Art.

**Stufe 1 – was ist ein Wort?** Eine Klassifikation je Wort, neun Label:
`PRODUCT BRAND PRICE OLD_PRICE QUANTITY DISCOUNT VALID UNIT_PRICE APP_PRICE`.
Das kann ein normales NER-Modell. Vier Arme im Vergleich: `gbert`, `xlmr`,
`lilt`, `layoutxlm`.

**Stufe 2 – was gehört zusammen?** „Butter" und „1.99" sind beide erkannt –
aber gehören sie zum selben Angebot? Das ist eine *Relation*, keine
Klassifikation, und BIO-Tags können sie gar nicht ausdrücken. Dafür gibt es ein
zweites Modell, das jedes Entity-Paar bewertet („gehören die zusammen?").

Eure Handannotation sitzt auf **Stufe 2**. Deshalb zuerst `/group`.

## Warum ausgerechnet ihr

Jede Zahl im Projekt vergleicht heute unsere Pipeline mit **`claude-sonnet-5`**
– Entities wie Angebotsgruppen stammen von einem LLM. Das misst
*Übereinstimmung*, nicht *Richtigkeit*. Zwei Modelle können sich einig und
gemeinsam irren.

Eure 43 Seiten sind die erste Referenz, die von Menschen kommt. Erst mit ihr
lässt sich sagen, ob unsere Pipeline *richtiger* ist als die Vergleichs-LLMs
oder nur *ähnlicher zu Sonnet*.

Daraus folgt die wichtigste Regel eurer Arbeit: **aus dem Seitenbild
annotieren, nicht die Modellausgabe korrigieren.** Wer die Sonnet-Labels
daneben aufmacht, ankert daran – und die Messung misst hinterher das Ankern
mit, statt es zu prüfen.

## Wo was liegt

| Ordner | Inhalt |
|---|---|
| `src/magda/` | die gesamte Logik, ein Modul je Pipeline-Schritt unter `cli/` |
| `frontend/` | die Oberfläche, in der ihr annotiert |
| `data/words/` | Wörter und Koordinaten je Seite – **die Reihenfolge ist ein Vertrag** |
| `data/labeled/sonnet-5/` | die LLM-Labels, gegen die alles gemessen wird |
| `data/offer_groups/` | die LLM-Gruppierungen |
| `gold/`, `gold/offers/` | **eure Arbeit landet hier** |
| `reports/` | die Wochenberichte, dort stehen die Zahlen mit Begründung |

`CLAUDE.md` ist das Langzeitgedächtnis des Projekts: jeder nicht offensichtliche
Befund, jede Fehlentscheidung samt Grund. Lang, aber die Suche danach lohnt
sich – fragt Claude einfach danach.

## Vier Dinge, die man nicht nebenbei tut

Ausführlich stehen sie in `CLAUDE.md`; hier die, die euch treffen können.

- **`data/words/` nicht löschen und Schritt 02 nicht neu laufen lassen.** Alle
  Labels sind Indizes in diese Wortliste. Ändert sie sich, zeigen sie auf
  andere Wörter – auch eure. Meldet der Annotator „Wortliste hat sich
  geändert", bearbeitet die Seite nicht, sondern sagt Bescheid.
- **Nichts schreibt nach `data/labeled/`.** Das ist die Referenz, gegen die
  gemessen wird. Eure Arbeit gehört nach `gold/`, und der Annotator macht das
  von allein.
- **Der Testsplit ist zum Messen, nicht zum Entwickeln.** Schwellwerte und
  Heuristiken entstehen an Train/Dev. Wer eine Regel an Testseiten baut und
  danach an denselben misst, bekommt eine schöne Zahl ohne Aussage.
- **Auf `main` wird nicht gearbeitet.** Feature-Branch → Pull Request nach
  `development`. Der Grund ist nicht Bürokratie: `main` trägt die Zahlen aus
  dem Bericht, und ein Fehler in einer Heuristik sieht von innen genau wie eine
  Verbesserung aus, solange niemand gegengerechnet hat.

## Wenn etwas klemmt

Fragt Claude – mit der Fehlermeldung im Wortlaut, das reicht meist. Zwei Fälle
kommen erfahrungsgemäß zuerst:

- **`ModuleNotFoundError: magda`** – das `pip install -e '.[dev]'` fehlt, oder
  ihr seid im falschen Python. `which python` zeigt oft auf Anaconda.
- **Leere Seiten im Annotator** – dann fehlen die Seitenbilder. Für eure 43
  Seiten kann das nicht passieren, die sind im Repo. Für alle anderen:
  `magda extract --render-missing`, und das braucht die PDFs aus dem
  Drive-Archiv (`docs/archive/README.md`).

Abgegeben wird über einen Branch mit Pull Request, nicht per Zuruf – wie das
geht, steht am Ende von [annotation-task.md](annotation-task.md), und Claude
macht es auf Zuruf mit.
