# Woche 2 — Gold-Annotation und Prospekt-Übersicht

**Stand: 29.07.2026**

## Was wir gemacht haben

Zwei Dinge: ein Werkzeug, mit dem wir Prospektseiten von Hand annotieren, und
eine Übersichtsebene, damit Inspektor und Annotator auch mit vielen Prospekten
bedienbar bleiben.

## Warum das Gold-Set

Wir haben bisher gegen LLM-Labels evaluiert. Die Zahlen aus Woche 1
beantworten damit die Frage *„wie gut imitiert das Modell Mistral?"* — nicht
*„wie gut extrahiert es Angebotsdaten?"*. Wenn Mistral bei BRAND selbst schwach
ist, bestrafen wir das Modell dafür, dass es Mistral nicht genau genug
nachmacht.

Handannotierte Referenzdaten lösen das. Annotiert wird **von null**, nicht
durch Korrigieren der LLM-Vorschläge: Vorbelegte Labels erzeugen einen
Anker-Bias, plausibel aussehende Fehler werden übersehen, und das Gold-Set
fiele zu LLM-ähnlich aus — es würde die LLM-Qualität dann systematisch zu gut
messen und damit genau das verfehlen, wofür es existiert.

## Das Werkzeug

`/annotate` im Dashboard. Wort anklicken (Shift-Klick erweitert die Auswahl),
Ziffer `1`–`8` setzt das Label, `0` entfernt es, `f` markiert die Seite als
fertig, Pfeiltasten blättern. Gespeichert wird laufend nach `gold/`.

Drei Entscheidungen, die nicht offensichtlich sind:

- **`gold/` wird versioniert, `data/` nicht.** Generierte Artefakte sind
  reproduzierbar, Handarbeit ist es nicht. Ein verlorenes `data/labeled/`
  kostet API-Zeit, ein verlorenes `gold/` kostet Arbeitstage.
- **Gespeichert werden Spans, keine BIO-Tags.** Eine Liste aus 180
  `"O"`-Einträgen ist in einem Git-Diff nicht überprüfbar;
  `labels.spans_to_bio()` erzeugt die Tags jederzeit daraus.
- **Jede Gold-Datei trägt einen `words_hash`.** Alle Span-Indizes zeigen in die
  Wortliste aus Schritt 02. Ändert sich die Extraktion, zeigen sie auf andere
  Wörter, ohne dass etwas kaputtgeht. Der Hash macht diesen Fehler laut statt
  leise: Die API lehnt mit 409 ab, die Übersicht markiert betroffene Seiten.

## Die Prospekt-Übersicht

Beim ersten Annotieren zeigte sich, dass eine Person einen ganzen Prospekt in
vertretbarer Zeit schafft. Damit wird die Arbeitsteilung „ein Prospekt pro
Person", und die Zahl der Kataloge wächst absehbar auf zehn bis zwanzig.

Inspektor und Annotator öffneten bis dahin direkt eine Seitenliste über *alle*
Kataloge. Bei einem Katalog sind das 40 Einträge, bei zehn wären es 400 —
unbenutzbar, ohne dass irgendetwas kaputtgeht.

Beide haben jetzt eine Übersicht davor: eine Kachel je Prospekt mit
Seitenzahl, Ladedatum und Fortschritt. Der Fortschritt bedeutet je nach
Werkzeug Verschiedenes — im Inspektor „vom LLM gelabelt", beim Annotieren „von
Hand fertig". Nebeneffekt: Die Pfeiltasten blättern jetzt nur noch innerhalb
eines Prospekts; vorher lief man am Katalogende stillschweigend in den
nächsten hinein.

## Was uns die Reviews gekostet und gebracht haben

Beide Arbeitsblöcke liefen mit Umsetzung und unabhängigem Review je Aufgabe.
Das hat sich gelohnt, aber anders als erwartet: Die meisten Fehler steckten
**nicht** in der Umsetzung, sondern im Plan.

- **Vier Nebenläufigkeitsfehler im Auto-Speichern.** Jede Runde behob den
  gemeldeten Fehler und führte einen neuen derselben Klasse ein. Alle vier
  hatten dieselbe Signatur: kein Absturz, keine Fehlermeldung, nur
  verschwundene oder zurückgesetzte Arbeit. Der letzte kam über
  `queryClient.invalidateQueries({ queryKey: ["gold"] })` — das sieht aus wie
  „lade die Übersicht neu", macht aber ein *Präfix*-Match und trifft damit auch
  die Query der offenen Seite.
- **Eine Grenzprüfung ging bei der Portierung verloren.**
  `labels.spans_to_bio()` verwirft ungültige Spans; die TypeScript-Fassung tat
  das nicht. In JavaScript ist das gefährlicher, weil eine Zuweisung jenseits
  der Array-Länge das Array stillschweigend *erweitert*.
- **Ein Test, der nicht fehlschlagen konnte.** Er klickte eine Kachel an und
  prüfte auf einen Text, der schon vorher auf dem Bildschirm stand.
- **`mkstemp` legt Dateien mit Modus 0600 an**, und `os.replace` nimmt den
  Modus mit. Der Fix gegen Datenverlust hätte fast ein Zugriffsproblem
  eingeschleppt: Gold-Dateien wären nur für die Person lesbar gewesen, die sie
  geschrieben hat — in einem per Git geteilten Verzeichnis ein Problem, das
  niemand mit dem Annotationswerkzeug in Verbindung gebracht hätte.
- **Der fünfte Nebenläufigkeitsfehler lag unter den anderen vier.** Alle vier
  Runden hatten *Antworten* geordnet; keine hatte verhindert, dass zwei PUTs
  derselben Seite überhaupt gleichzeitig fliegen. Beim Server kommen sie in
  beliebiger Reihenfolge an, und `os.replace` macht den letzten zum Gewinner —
  die Oberfläche meldet dann „gespeichert" mit dem neueren Stand, während auf
  der Platte der ältere liegt. Auslöser ist kein Sonderfall, sondern zügiges
  Annotieren an einem trägen Server: Debounce 300 ms, Serverlatenz darüber.
  Speichervorgänge stehen jetzt pro Seite in einer Warteschlange. Das ersetzt
  die Sequenznummer-Buchhaltung der vierten Runde — sie ordnete Symptome, die
  jetzt nicht mehr entstehen.

## Offen

**Für das Team zu entscheiden:**

- **Split-Strategie.** Naheliegend wäre: Gold-Katalog als Testset, LLM-gelabelte
  Kataloge als Trainingsset. Das trennt Train und Test entlang der Kataloge und
  beseitigt die Leakage-Sorge. Bei drei Personen mit je einem Prospekt sind es
  aber 120 Gold-Seiten — genug, um darauf zu trainieren. Dann wäre die
  Alternative stärker: auf Gold trainieren *und* testen, LLM-Labels nur noch
  als Vergleichsarm. Kein Label-Rauschen mehr im Training.
- **Annotationsrichtlinie.** Ist „Bio" eine Marke oder Teil des Produktnamens?
  Das beantwortet man nicht am Schreibtisch, sondern wenn man zum dritten Mal
  darüber stolpert. Sollte vor dem großen Durchlauf festgehalten werden.

**Technisch offen:**

- **Gleichzeitiges Annotieren derselben Seite** aus zwei Tabs oder von zwei
  Personen bleibt Last-Write-Wins. Die Warteschlange sitzt im Client und ordnet
  nur dessen eigene Speicherungen; der `words_hash` greift nicht, weil er für
  beide Seiten identisch ist. Eine Lösung bräuchte optimistisches Locking über
  `updated`. Praktisch relevant erst, wenn jemand zwei Fenster offen hat —
  bei „ein Prospekt pro Person" also kaum.
- **Endgültig fehlgeschlagene Datenabfrage** zeigt in beiden Werkzeugen den
  Leerhinweis statt einer Fehlermeldung („noch nichts extrahiert", obwohl die
  Daten da sind).
- **Fehlgeschlagenes Speichern beim Seitenwechsel** wird nirgends angezeigt.
- **`scripts/06_compare_labels.py`** — das eigentliche Ziel: Gold gegen
  `data/labeled/` halten und beziffern, wie gut Mistral wirklich labelt.

## Zahlen

62 Python-Tests, 93 Frontend-Tests, TypeScript sauber. 39 Commits.
