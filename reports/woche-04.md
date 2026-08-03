# Woche 4 — Drei Wochen Daten, ehrliche Messung, der Grenzfall APP_PRICE

Stand: 03.08.2026

## Kurzfassung

Der Korpus ist auf drei Erscheinungswochen gewachsen, das Training läuft
darauf, und der größere Teil der Woche ging nicht in bessere Zahlen, sondern
in **belastbarere** Zahlen: Konfidenzintervalle, vier Matching-Schemata,
vollständige Vorhersagen über lange Seiten und eine Handprüfung des Labels,
das den Modellen am meisten Ärger macht.

| | Woche 3 | Woche 4 |
|---|---:|---:|
| Erscheinungswochen | 2 | 3 |
| Seiten Train / Dev / Test | 81 / 8 / 107 | 175 / 21 / 100 |
| Test-Entitäten | 3901 | 5080 |
| Test-F1 GBERT | 0.908 | 0.8938 [0.8484, 0.9306] |
| Test-F1 LayoutXLM | 0.895 | 0.8952 [0.8418, 0.9366] |
| Differenz GBERT − LayoutXLM | +0.013 (ohne Intervall) | −0.0014, p = 0.843 |
| Matching-Schemata | 1 (strikt) | 4 (SemEval-2013) |
| Wörter ohne Vorhersage (KW32) | 1476 von 20952 | 0 |

Die beiden F1-Spalten stehen über **verschiedenen Testsätzen** (KW31 mit 107
Seiten gegen KW32 mit 100) und sind nicht direkt vergleichbar. Der Vergleich,
der zählt, steht innerhalb einer Spalte.

Die Punktschätzer bewegen sich kaum. Die Aussage dahinter ändert sich
erheblich: Aus „GBERT ist besser" wird „zwischen den beiden Armen ist über 43
unabhängige Einheiten **kein Effekt nachweisbar**, in keine Richtung." Das ist
kein schwächeres Ergebnis, sondern das erste, das man verteidigen kann.

Zwei Zahlen aus Woche 3 waren nicht falsch berechnet, aber sie beantworteten
eine andere Frage als die, die im Bericht stand. Beides ist unten aufgeführt.

## Datenlage

52 Kataloge in drei Wochen, 463 heruntergeladene PDF-Seiten, davon 296
verschiedene und 167 als Regionalduplikat ausgeschlossen. `data/` ist seit
dem 02.08. mitversioniert (1,2 GB) – die Alternative war, dass jede Person im
Team Ernte, Extraktion und Labeling selbst durchläuft und dafür
LLM-Kontingent verbrennt für ein Ergebnis, das identisch sein soll.

| Woche | Kataloge | Seiten |
|---|---:|---:|
| KW30 (1342812–1342929) | 13 | 89 |
| KW31 (1347375–1347504) | 23 | 107 |
| KW32 (1351497–1351626) | 16 | 100 |

Referenz ist `data/labeled/sonnet-5/` über alle 296 Seiten, 13827 Spans.

Ein Zwischenschritt gehört dazu: Die KW32-Labels waren nie durch
`labeling.trim_spans()` gelaufen – der Guard, der „oder" aus Spans hält, die
Grundpreis-Klammer als Spanende erzwingt und numerische Label ohne Ziffer
verwirft. `magda label --repair` hat das nachgeholt. Der Testsatz hat dadurch
**5080 statt 5107 Entitäten**; Zahlen aus dem Vorlauf sind mit den hier
berichteten deshalb nicht ganz direkt vergleichbar.

| Label | gesamt | train | dev | test |
|---|---:|---:|---:|---:|
| PRODUCT | 2702 | 1536 | 163 | 1003 |
| PRICE | 2444 | 1396 | 164 | 884 |
| QUANTITY | 2115 | 1226 | 127 | 762 |
| UNIT_PRICE | 1883 | 1104 | 112 | 667 |
| BRAND | 1692 | 1010 | 76 | 606 |
| OLD_PRICE | 1300 | 745 | 34 | 521 |
| DISCOUNT | 1187 | 719 | 25 | 443 |
| VALID | 280 | 166 | 18 | 96 |
| APP_PRICE | 224 | 115 | 11 | 98 |

Der Split ist der Wochen-Split aus Woche 3, jetzt über drei Wochen:
**KW30 + KW31 lernen, KW32 testet.** Dev wird clusterweise aus den
Trainingswochen gezogen (Jaccard 0.7), nicht seitenweise – seitenweise lag die
Median-Ähnlichkeit von Dev zu Train bei 0.721 und die Checkpoint-Auswahl
bewertete teils Auswendiggelerntes.

Zwei Eigenschaften dieses Splits sind unbequem und gehören genannt. **Dev ist
mit 21 Seiten in 14 Clustern dünn** und enthält nur 2 APP_PRICE-Spans – dieses
Label kann die Checkpoint-Auswahl praktisch nicht bewerten. Und Dev stammt aus
den Trainingswochen, misst also In-Distribution-Fit, während Test die
Zeitverschiebung misst. Mit drei Wochen ist das nicht besser lösbar.

Dass die Zeitverschiebung real ist, zeigt APP_PRICE selbst: über die drei
Wochen wächst es von 2 auf 57 auf 98 Spans. **Penny rollt den App-Preis gerade
aus.** Wir trainieren auf 115 Beispielen und messen gegen 98 – ein
Zufallssplit hätte die Spans verteilt und eine passable Zahl geliefert, aber
den Befund „die Pipeline hinkt Sortimentsänderungen eine Woche hinterher"
unsichtbar gemacht.

## Drei Korrekturen an der Messung

### 1. Der Signifikanztest hat still das Falsche gemessen

`magda significance` bildet Duplikat-Cluster über die Wortlisten und resampelt
über Cluster statt über Seiten – sonst gelten elf Kopien einer Vorlage als elf
Beobachtungen. Fehlten die Wortlisten, fiel die Funktion auf **einen einzigen
Sammel-Cluster** zurück.

Auf dem Trainings-Pod ist genau das passiert: das Bundle liefert `data/words`
nicht mit, also lagen alle 100 Testseiten in einem Cluster. Ergebnis:
Konfidenzintervall der Breite null, p = 0.0. Also die Optik eines
hochsignifikanten Befunds an genau der Stelle, die Unsicherheit ausweisen
soll. Der Schritt bricht jetzt ab und nennt die fehlenden Seiten
(`test_bricht_ab_wenn_wortlisten_fehlen`).

Ein stiller Fallback ist an einer Messstelle schlimmer als ein Absturz: Ein
Absturz kostet zehn Minuten, eine plausible falsche Zahl kann in einen Bericht
wandern.

### 2. Lange Seiten wurden nicht bewertet, sondern übersprungen

Das alte Evaluationsprotokoll wertete nur die Tensorpositionen aus, die ins
512-Subword-Fenster passten. Entitäten dahinter fehlten damit nicht als
Falsch-Negative, sondern **im Nenner**: gemessen wurde 0.890 über 4921
Entitäten statt über 5107. Die Zahl war nicht falsch berechnet, sie
beantwortete die Frage „F1 auf den ersten 512 Subwords".

`magda eval` berichtet jetzt drei Protokolle gegen dieselbe volle Referenz:

| Protokoll | GBERT | LayoutXLM |
|---|---:|---:|
| `windowed` (Primärmetrik) | 0.8938 | 0.8952 |
| `truncated` (alt) | 0.8918 | 0.8941 |
| `no-windows` | 0.8754 | 0.8862 |

Primär ist `windowed`, weil es misst, was `magda predict` tatsächlich
ausliefert. Der Wert der Fenster ist die Differenz zu `no-windows`, also
**1,8 Punkte bei GBERT**, nicht die 0.002 gegen `truncated`.

Sliding Window (`windows.py`, Stride 128) steckt bewusst nur in der Inferenz.
Auf der Testwoche haben damit **0 statt 1476 von 20952 Wörtern** keine
Vorhersage mehr. Im Training wäre es Augmentierung und keine Korrektur –
Trainingssignal und Checkpoint-Auswahl bleiben deshalb unverändert
vergleichbar.

Eine Feinheit, die zwei Anläufe gekostet hat: Fenstergrenzen liegen auf
Subwords, nicht auf Wörtern. Das erste Wort eines Folgefensters kann mit einem
Fortsetzungs-Subword beginnen, das im Training mit `-100` maskiert war.
`merge_windows` überspringt es, solange ein anderes Fenster das Wort ganz
sieht.

### 3. Ein einziges Schema ist zu grob

Bisher galt seqeval, also strikt: richtige Grenze **und** richtiger Typ, sonst
null. Für Prospektdaten ist das streng – ob ein PRODUCT-Span den Sortenzusatz
einschließt, ist bei uns eine offene Teamfrage und keine Modelleigenschaft.
Neu sind vier Schemata nach SemEval-2013 Task 9.1 (Zählweise nach MUC-5).

| Schema | GBERT | LayoutXLM | Bedeutung |
|---|---:|---:|---|
| `strict` | 0.894 | 0.895 | Grenze und Typ exakt |
| `exact` | 0.909 | 0.921 | Grenze exakt, Typ ignoriert |
| `partial` | 0.926 | 0.935 | Überlappung, Teiltreffer 0.5 |
| `type` | 0.925 | 0.923 | Typ richtig, Grenze überlappend |

Der Abstand `strict → partial` von rund 3 Punkten **ist** das Grenzproblem:
176 GBERT-Spans (LayoutXLM 151) sitzen an der richtigen Stelle, aber nicht auf
der exakten Wortgrenze. Der Vergleich `exact` gegen `type` sagt, welche
Fehlerart überwiegt – bei beiden Modellen liegen sie gleichauf, es sind also
Typverwechslungen und Grenzfehler in ähnlichem Umfang.

Berichtet wird weiter `strict` als Hauptzahl. Die übrigen drei stehen daneben,
damit klar ist, wie viel davon Grenzstreit ist und wie viel echte Fehler sind.

## Ergebnis

100 Testseiten, 5080 Entitäten, Referenz `sonnet-5`, Protokoll `windowed`.

| Label | Support | GBERT | LayoutXLM |
|---|---:|---:|---:|
| UNIT_PRICE | 667 | 0.996 | 0.996 |
| DISCOUNT | 443 | 0.991 | 0.972 |
| BRAND | 606 | 0.924 | 0.933 |
| PRICE | 884 | 0.899 | 0.883 |
| OLD_PRICE | 521 | 0.892 | 0.854 |
| VALID | 96 | 0.866 | 0.974 |
| QUANTITY | 762 | 0.852 | 0.883 |
| PRODUCT | 1003 | 0.824 | 0.841 |
| APP_PRICE | 98 | 0.660 | 0.554 |
| **micro avg** | **5080** | **0.894** | **0.895** |

Über 43 Duplikat-Cluster gebootstrappt (10000 Ziehungen):

- GBERT **0.8938**, 95 % [0.8484, 0.9306]
- LayoutXLM **0.8952**, 95 % [0.8418, 0.9366]
- Differenz **−0.0014**, 95 % [−0.0164, +0.0108], **p = 0.843**

**Zum Layout-Vorteil ist kein Effekt nachweisbar, in keine Richtung.** Im
Vorlauf lag die Differenz bei +0.0132 (p = 0.435), jetzt bei −0.0014 – das
Vorzeichen hat gewechselt. Genau so verhält sich ein Effekt, dessen Intervall
die Null überdeckt. Der Negativbefund aus Woche 3 ist damit bestätigt, nicht
widerlegt.

Der Testsatz hat 100 Seiten, aber nur **43 unabhängige Einheiten**; der größte
Cluster umfasst 11 Seiten. Wer über Seiten resampelt, bekommt ein zu enges
Intervall. Praktische Nebenfolge: ein Fehler des Lehrers auf einer Seite im
großen Cluster zählt elffach.

Auffällig bleibt die **Streuung**: LayoutXLMs Intervall ist mit 0.095 Breite
deutlich weiter als GBERTs 0.082. Das layout-aware Modell ist über die
Vorlagen hinweg instabiler, und das verschluckt der Punktschätzer.

### Warum LayoutXLM den visuellen Fall nicht löst

Bei APP_PRICE erreicht LayoutXLM **0.554 gegen GBERTs 0.660** – schlechter,
obwohl nur es den blauen Kasten sehen könnte. Der Grund steht in der
Architektur, nicht in den Daten:

`image_feature_pool_shape` ist `[7, 7, 256]`, also **49 visuelle Token für die
ganze Seite**. Eine Gitterzelle deckt 142 × 251 px des Originals ab; der
App-Kasten (~230 × 80 px) fällt mit Produktfoto und Nachbarpreis in dieselbe
Zelle. Dazu hängen die 49 Token als *globale* Sequenz an – es gibt keine
Verknüpfung „dieses Wort steht auf blauem Grund".

Die naheliegende Vermutung, unsere 224-px-Bilder seien schlicht zu grob, ist
geprüft und falsch: `LayoutLMv2ImageProcessor` skaliert ohnehin auf 224 × 224;
`bundle.py` nimmt ihm das nur vorweg, mit demselben Filter. **Mehr Pixel
ändern nichts.** Wer den Layout-Arm verteidigen will, braucht eine Architektur
mit lokaler Wort-Bild-Verknüpfung.

## APP_PRICE: die Kennzeichnung ist Grafik, kein Text

Das ist der inhaltlich wichtigste Befund der Woche und er räumt eine ältere
Arbeitsannahme ab.

Penny zeichnet den App-Preis auf zwei Arten aus: mit dem Text „mit PENNY App"
daneben – der steht im Textlayer – oder mit einem türkisblauen Kasten samt
Logo und der Zeile „Nur mit App". **Der Kasten steht nicht im Textlayer.** Auf
`1347375_p5` liefert PyMuPDF an der Stelle `Aktion 1.99 1.69 1 Kernarm`; das
Wort „App" kommt auf der ganzen Seite nicht vor, obwohl `1.69` dort ein
App-Preis ist. Acht Seiten sind so.

Über alle 296 Seiten: bei **73 von 224 APP_PRICE-Spans (33 %)** steht „App"
nicht im Fenster ±8 Wörter. Für diese Fälle ist das Label aus dem Text
**prinzipiell nicht ableitbar** – weder von GBERT noch von einer Prompt- oder
Code-Regel. Das Labeling-Modell kann es, weil es das Seitenbild sieht. Das ist
eine strukturelle Obergrenze, keine Frage der Datenmenge.

### Was die Fußnotenregel wirklich getan hat

Penny markiert App-Preise auch mit einer hochgestellten Fußnotenziffer, deren
Legende auf der Seite steht. Die Regel dazu hat 67 Spans von PRICE auf
APP_PRICE umgewidmet, **alle in Train und Dev, keinen einzigen im Test**. Der
Grund ist banal: In KW32 steht die Ziffer meist *vor* dem Preis
(`-37% 1 0.99`), die Regel sucht sie dahinter.

Der Sprung von F1 0.234 auf 0.660 kommt also allein aus den zusätzlichen
Trainingsbeispielen (57 → 115), nicht aus einer veränderten Testreferenz. Das
ist sauberer als befürchtet: die Messlatte blieb liegen, nur das Training
wurde besser. Die Precision fiel dabei von 1.000 auf 0.630 – das Modell
überproduziert jetzt, unter anderem auf Aufzählungsziffern
(`2 Jahre Garantie`, `3 Paar`).

### Die Handprüfung

Da die Farbe im Bild das Merkmal trägt, das im Text fehlt, ist sie der
natürliche Vorsortierer – aber **kein Entscheider**. Ein automatisch
umgeschriebenes Label sähe in der Metrik aus wie eine Verbesserung und wäre
nur eine andere Heuristik. Deshalb: `magda audit APP_PRICE` sammelt Kandidaten,
ein Mensch urteilt unter `/audit`, und **kein Schritt schreibt dabei nach
`data/labeled/`**.

Verifiziert wurde der Ton an einer Stelle von Hand: **rgb(0, 124, 132)** im
Kasten gegen das Preisgelb **rgb(255, 212, 0)** direkt daneben. Ein grober
Test „Blaukanal über Rotkanal" reicht *nicht* – er fängt die hellblauen
Kacheln (196, 227, 248), und die stehen ausgerechnet neben „ohne PENNY App".
Gemessen wird am Rand der Wortbox, nicht in ihr, per Median: in der Box steht
Schrift.

Durchgesehen sind **374 von 374 Kandidaten in 267 Vorlagen** (ein Urteil gilt
für alle Regionalausgaben derselben Vorlage).

| Gruppe | Fälle | Urteil |
|---|---:|---|
| trägt bereits APP_PRICE | 224 | 223 bestätigt, **1 falsch** |
| PRICE auf App-Grund | 83 | **81 sind APP_PRICE**, 2 bleiben PRICE |
| OLD_PRICE auf App-Grund | 67 | **alle 67 bleiben OLD_PRICE** |

Drei Dinge folgen daraus:

**Sonnets Präzision auf diesem Label ist praktisch perfekt (223/224).** Der
eine Fehlgriff ist genau der vermutete Fall – `Aktion «1.99» 1 2 3`, eine
Aufzählungsziffer, die die Fußnotenregel für eine Fußnote hielt. Ein Fehler
unter 224 ist die Bestätigung der Regel, nicht ihre Widerlegung.

**Sonnets Recall ist es nicht: 81 App-Preise fehlen, also rund ein Viertel
(223 von 304).** Die fehlen alle in derselben Situation, nämlich im Kasten
ohne Text daneben.

**Die Prioritätsheuristik hat gehalten.** Die Vermutung war, dass der
durchgestrichene Preis im App-Kasten OLD_PRICE bleibt – 67 von 67 bestätigt.
Und die Farbe als Vorschlaggeber trifft in der Gruppe „fehlt vermutlich" zu
**97,6 % (81/83)**. Die beiden Ausreißer stehen beide neben „ohne PENNY App",
also der ausdrücklichen Verneinung.

### Wo die Urteile landen würden

| Split | Änderung |
|---|---|
| train | 72 PRICE → APP_PRICE, 1 APP_PRICE weg (115 → **186**) |
| dev | 9 PRICE → APP_PRICE (11 → **20**) |
| test | **keine** |

Der Testsatz enthält keinen einzigen Preis auf App-Grund, der nicht schon
APP_PRICE heißt. Damit gilt für eine Übernahme dasselbe wie für die
Fußnotenregel: **die Messlatte bleibt liegen, nur das Training wächst** – bei
APP_PRICE um 62 %. Das ist die methodisch günstigste Konstellation, die man
sich wünschen kann.

Eine Einschränkung, die der Bericht mittragen muss: Die Prüfung findet nur,
was **farblich** auffällt. Ein im Test fehlender App-Preis, der nur per Text
ausgezeichnet ist, wäre ihr entgangen. Eine Gegenprobe über die Textumgebung
hat im Test keinen solchen Fall ergeben, aber sie ist schwächer als die
Farbprüfung. Der Test-Recall der Referenz ist damit plausibel, nicht bewiesen.

### Was daraus folgt, ist offen

Zwei Wege, die verschiedene Fragen beantworten und einander nicht ersetzen:

**A – Referenz bereinigen.** Die 82 Urteile übernehmen. Macht die Zahlen
**ehrlicher, nicht besser**: Wenn jeder Kasten APP_PRICE wird, verlangt man
von GBERT eine Vorhersage über ein Merkmal, das in seiner Eingabe nicht
vorkommt. Ein Teil der heutigen 0.660 ist Zufallstreffer auf Textmustern.

**B – dem Modell das Merkmal geben.** Dieselbe Farbmessung als zusätzliche
Eingabe je Wort. Löst das Problem tatsächlich, weicht aber vom Proposal ab, wo
LayoutXLM den Layout-Anteil beisteuern soll.

Ohne A lässt sich nicht messen, was B gebracht hat. **Teamentscheidung**, weil
A die Referenzdefinition ändert und damit alle Zahlen davor.

## Modelloutput für den nächsten Schritt

Neu ist `magda predict`, weil das trainierte Modell für sich noch kein
Ergebnis ist – Bogdan und Kjell brauchen die gelabelten Tokens samt
Koordinaten, um daraus Angebote zusammenzusetzen.

`data/predictions/{gbert,layoutxlm}/` enthält je 100 Seiten plus `index.json`.
Je Wort: `i`, `text`, `bbox`, `label`, `confidence`; dazu die fertigen
`entities` je Seite.

| | GBERT | LayoutXLM |
|---|---:|---:|
| Wörter | 20952 | 20952 |
| Entitäten | 5479 | 5360 |
| abgeschnittene Seiten | 0 | 0 |

Für den Einsatzfall gibt es `magda predict gbert --all-words`: die ganze
Ernte, ohne Labels als Eingabe.

## Infrastruktur

- **`magda audit` und `/audit`.** Vorsortierung nach Hintergrundfarbe,
  Urteilsknöpfe, Fortschritt, Bündelung gleicher Vorlagen. Der
  Seitenausschnitt um den Span wird per CSS aus dem vorhandenen Seitenbild
  geschnitten – ohne Bild urteilt ein Mensch über dieselbe Information, die
  schon dem Textmodell fehlt. Einstieg versteckt auf der Datenseite, kein
  eigener Reiter: das Werkzeug gilt einem Label und ist zwischen zwei
  Messungen relevant, nicht dauerhaft.
- **Die API schreibt jetzt an vier Stellen** statt an dreien: `gold/`,
  `catalogs.json`, `data/runs/`, `data/audit/`. Erlaubnisliste, kein freier
  Schreibzugriff – `data/labeled/` ist ausdrücklich nicht dabei.
- **Trainingslauf.** RunPod, beide Varianten, Gesamtkosten 0,26 $. GBERT 96 s,
  LayoutXLM 254 s. detectron2 baut auf dem RunPod-PyTorch-Image ohne Eingriff
  durch; das Risiko aus Woche 3 ist erledigt.
- **`torch.cuda.is_available()` ist keine Prüfung.** Zwei Instanzen meldeten
  die GPU als verfügbar und brachen bei der ersten Allokation ab, während
  `nvidia-smi` 0 MiB belegt zeigte – ein Nachbarcontainer hielt die Karte. Das
  Bootstrap fasst sie deshalb wirklich an (`torch.zeros(8, device="cuda")`),
  sonst schlägt der Fehler erst nach zehn Minuten detectron2-Übersetzung auf.
- **`magda bundle` filtert `data/` heraus** und legt gezielt dazu, was die GPU
  braucht. Seit `data/` versioniert ist, zog `git ls-files` sonst die
  Original-PDFs mit: 1054 MB statt 17 MB.
- **Tests:** 263 Python, 124 Frontend, alle grün.

## Was offen ist

- **APP_PRICE, Weg A oder B** (siehe oben). Teamentscheidung, weil A die
  Referenz ändert. Die 82 Urteile liegen fertig in `data/audit/`.
- **Sortenangaben und Gebinde-Komposita.** Bei PRODUCT sind 106 von 135
  Fehlern Grenzfehler an Sortenzusätzen – das größte einzelne Fehlerbündel
  überhaupt. `50-ml-Fläschchen` ist 4× QUANTITY, `0,33-l-Dose` 6× gar nicht,
  `1-l-Sonderedition` war 8× ohne und 3× QUANTITY. Strukturell derselbe Fall,
  drei Behandlungen. Prüfen per Auszählung je Wortlaut über den Korpus, nicht
  seitenweise.
- **Sliding Window auch im Training?** In der Inferenz drin, +1,8 Punkte. Im
  Training wäre es Augmentierung, also eine Abwägung und keine Korrektur.
- **LiLT als dritter Arm?** LayoutXLM verliert konsistent, aber nicht
  nachweisbar. LiLT hat keinen visuellen Backbone und ist bei 175
  Trainingsseiten gutmütiger; ein Lauf würde den Negativbefund gegen den
  Einwand „falsche Layout-Architektur" absichern. Weicht vom Proposal ab.
- **Der Flair-Arm ist veraltet.** Der letzte Report steht über 4 Seiten und
  24 BRAND-Instanzen (F1 0.281) – das ist Rauschen. Muss über die 100
  Testseiten neu laufen, und jede berichtete Zahl daraus muss mitnennen, dass
  nur BRAND vergleichbar ist und Flair lange Seiten *nicht* kürzt, GBERT
  im `truncated`-Protokoll schon.

## Einordnung

Die Modelle sind an der **Konsistenzgrenze ihres Lehrers** angekommen, und das
ist der Satz, der die Priorisierung bestimmt. APP_PRICE hatte im Vorlauf F1
0.234 bei Precision 1.000 und **null reinen Falsch-Negativen** – das Modell
fand jeden App-Preis und nannte ihn nur anders. Die Handprüfung hat jetzt
gezeigt, woran das lag: an 81 fehlenden Labels in einer Situation, die im Text
gar nicht sichtbar ist.

Mehr Daten und größere Modelle bringen an dieser Stelle nichts, konsistentere
Labels schon. Und was mechanisch entscheidbar ist, gehört als Regel in den
Code statt in den Prompt – `labeling.trim_spans()` hat 179 und 322 Verstöße
über 196 Seiten auf null gesenkt, Werbewörter von 2,4 auf 0,06 je Seite. Eine
Prompt-Regel senkt die Fehlerrate, ein Guard setzt sie auf null.

Die Projektfrage bleibt Kosten, nicht Perfektion. **0,264 s je Seite gegen
44,8 s beim LLM-Labeling** – für eine Wochenernte über alle 44 Regionen 8,8
Minuten gegen 24,9 Stunden. F1 0.894 heißt deshalb nicht „89 % richtig",
sondern „89 % dessen, was das große Modell liefert, zum 170sten Teil der
Zeit". Neu ist gegenüber Woche 3 nur, dass hinter der Zahl jetzt ein
Konfidenzintervall steht.
