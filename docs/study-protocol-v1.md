# Protokoll der Magda-Fallstudie

Festgelegt am 15.09.2026 vor Berechnung der ergänzenden Gold-/Intervallauswertung.
Die bisherigen Blackbox-Punktwerte und einzelne Testseiten waren bereits bekannt.
Dieses Protokoll ist deshalb keine Präregistrierung und macht den Test nicht
nachträglich unberührt. Historische Ergebnisdateien bleiben erhalten.

## Ergänzung zum Studienumfang vom 16.09.2026

Nach Sichtung der ersten ergänzenden Ergebnisse wurde der Umfang auf die
bestehenden Annotationen begrenzt: keine weitere Labelrunde, keine zusätzliche
unabhängige Doppelannotation und keine systematische Adjudikation. Diese
Entscheidung ist nachträglich und keine vorab festgelegte Auswertungsregel.
Seitenliste, Modelle, Matchingregeln und Referenz bleiben unverändert. Die
unklare Angebotsabgrenzung und Referenzfehler werden als Limitationen berichtet.
Die ursprünglich vorgesehene Kontrollannotation ist kein Abschlusskriterium
mehr. Das vorbereitete, unbenutzte Prüfpaket bleibt nachvollziehbar erhalten;
es ist kein Beleg für durchgeführte Annotation oder gemessene Übereinstimmung.

## Fragen

1. Wie genau erkennen die eingefrorenen GBERT-, XLM-R-, LiLT- und LayoutXLM-
   Ausgaben Entities gegenüber der derzeitigen menschlichen Referenz?
2. Wie gut gruppieren Heuristik und Paarmodell bei gegebenen Goldentities;
   wie verändert sich die Gruppierung bei LayoutXLM-Entities?
3. Wie unterscheiden sich die lokale Pipeline und die gespeicherten LLM-Läufe
   bei der gemeinsamen Aufgabe, Angebotsname und regulären Preis auszugeben?

Das Projekt ist ein Architektur- und Systemvergleich. Unterschiedliche
Vortrainingsverfahren erlauben keine isolierte kausale Aussage „Layout hilft
um X“ oder „Bildinformation erklärt den gesamten Unterschied“.

## Eingaben und Referenz

Die Liste `data/eval/test_cluster_pages.txt`, `data/splits/split.json`,
Vorhersagen, Paarmodell und Blackbox-Antworten bleiben eingefroren. Alle IDs
müssen zum Test gehören; Schnittmengen mit Train/Dev führen zum Abbruch.
Die Vorlagen werden mit dem bestehenden Jaccard-Kriterium 0.7 im gesamten
Testsplit gebildet und anschließend auf die Vergleichsliste projiziert.
Es werden keine Seiten anhand ihrer Ergebnisse ausgesondert.

Das Skript speichert Datei- und Quellenhashes, Paketversionen, Seitenlisten,
Gruppenzähler und verwendete Schwellen. Historischen NER-Ausgaben ohne
gespeicherten Checkpoint-Hash wird kein heutiger Checkpoint zugeschrieben.

Die Referenzprüfung liest keine Modellausgaben. Strukturelle Fehler stoppen
die Rechnung. Inhaltliche Hinweise werden vollständig als diagnostischer
Anhang ausgegeben. Sie bleiben nicht adjudiziert und sind keine gemessene
Fehlerrate. Bekannte Referenzfehler werden ausdrücklich als solche beschrieben.
Es wird keine Inter-Annotator-Übereinstimmung berichtet.

Als Angebot zählt für die Messung je gespeicherter Gruppe ein Name aus BRAND
und PRODUCT zusammen mit jedem unterschiedlichen PRICE-Wert. Gemeinsame
Preise ergeben innerhalb einer Gruppe einen Eintrag, unterschiedliche Preise
mehrere; fehlender Name oder PRICE ergibt ein Fragment. Diese Projektion ist
eine operative Bewertungseinheit. Sie entscheidet nicht allgemeingültig,
welche Varianten, Mehrfachkäufe oder benachbarten Textangaben inhaltlich zu
einem Angebot gehören. Die Unsicherheit alternativer Gruppierungen wird
nicht empirisch quantifiziert.

## Metriken

- NER: Strict Entity-Micro-F1 primär, Precision/Recall und Labelauflösung.
  Ergänzend Exact, Partial und Type nach SemEval-2013 Task 9.1, implementiert
  mit `nervaluate==1.2.1`. Exklusive Magda-Endindizes werden in inklusive
  Evaluator-Endindizes umgerechnet. Strict wird gegen seqeval gegengeprüft.
  Ein expliziter Adapter verlangt bei Überlappung mindestens ein gemeinsames
  Wort. Er ersetzt die Bibliotheksvorgabe von mindestens einem Prozent, damit
  das SemEval-Kriterium auch für Spans über hundert Wörter gilt. Die übrigen
  Zuordnungsregeln bleiben unverändert; Randfälle sind separat getestet.
  Die historische Implementierung `matching.py` bleibt erhalten.
- Gruppierung: Paar-F1 und exakte Gruppen-F1 auf der ausdrücklich angegebenen
  Entity-Grundmenge. Nicht zuordenbare Entities und Referenzgruppen ohne
  überlebende Entity werden mitgezählt und gesondert berichtet. Diese
  Gruppierungswerte sind bedingt auf die Entities und kein vollständiges E2E-F1.
- Angebote: unverändertes `offer-price-v2`: exakter PRICE, symmetrische
  Zeichenähnlichkeit des Namens >= 0.6, maximales Eins-zu-eins-Matching.
  Das ist keine semantische Ähnlichkeit. Alle weiteren Felder bleiben außerhalb
  des Hauptscores; Fragmente werden ausgewiesen. Fehlerhafte API-Seiten zählen
  mit leerer Ausgabe. Kein Weglassen schlechter oder fehlgeschlagener Seiten.

## Unsicherheit

10 000 Cluster-Bootstrap-Ziehungen mit Seed 42. Pro Ziehung dieselben
Vorlagen für alle Systeme, Summieren der Zähler vor Berechnung von Micro-F1.
Marginale 95-%-Perzentilintervalle sowie gepaarte Differenzintervalle.

Zwei ausdrücklich explorative Vergleichsfamilien:

- NER: XLM-R minus GBERT, LiLT minus XLM-R, LayoutXLM minus LiLT,
  LayoutXLM minus GBERT.
- Angebote: jede der drei LLM-Blackboxes minus LayoutXLM mit Paarmodell.

Zusätzlich Bonferroni-Intervalle mit Familienfehlerniveau 5 % innerhalb
jeder Familie. Ein Intervall über null belegt keine Gleichwertigkeit.
Bootstrap erfasst weder Seed-Streuung noch systematische Referenzfehler,
Selektionsverzerrung oder Übertragbarkeit auf andere Wochen. Undefinierte
Resamples werden ausgewiesen; mit nur einem Cluster gibt es kein Intervall.

## Modellarbeit und Geltungsbereich

Keine Optimierung, Nachtrainierung oder Schwellenwahl anhand dieser
Gold-Testauswertung. Ein methodisch guter Bericht kann auch fehlende Vorteile
oder Grenzen zeigen. Falls weitere Modellverbesserung erforderlich ist:
Hypothese zuerst dokumentieren, nur an Train/Dev arbeiten, neuen Lauf separat
speichern und danach auf einer künftig erhobenen, unberührten Woche prüfen.
Der bestehende Split wird dafür nicht neu gewürfelt.

Der Vergleich betrifft einen Händler und eine Testwoche. Unterschiede der
Eingaben werden offengelegt: PDF-Text/Koordinaten und teilweise Seitenbilder
bei den lokalen Modellen, Seitenbilder bei der Blackbox. Reine Bildlogos
können außerhalb der spanbasierten Referenz liegen. Preisbedingungen und
vollständige Angebotsdatensätze werden nur eingeschränkt abgebildet.

Replay verursacht keine neuen Modellaufrufe. Kosten und lokaler Betrieb
werden qualitativ diskutiert. Laufzeit- oder Kostensieg erfordert einen
zusätzlichen gemeinsamen Benchmark mit identischen Seiten und dokumentierter
Hardware, Startzustand, API-Wartezeit und Wiederholungen.

## Quellen

- [SemEval-2013 Task 9, Abschnitt 3.1](https://aclanthology.org/S13-2056/)
- [nervaluate: Quellcode und Beschreibung](https://github.com/MantisAI/nervaluate)
- [Dror et al. (2018): Signifikanztests in NLP](https://aclanthology.org/P18-1128/)
- [Bender & Friedman (2018): Data Statements](https://aclanthology.org/Q18-1041/)
