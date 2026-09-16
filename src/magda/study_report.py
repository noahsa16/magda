"""Berichtstext und Tabellen werden aus derselben gespeicherten Messung gebaut."""

from magda.evaluation_study import VARIANTS


def number(value):
    return "–" if value is None else f"{value:.4f}"


def interval(values):
    return "nicht bestimmt" if values is None else f"[{values[0]:+.4f}; {values[1]:+.4f}]"


def _comparisons(result):
    lines = ["| Differenz A − B | ΔF1 | 95-%-Intervall | Bonferroni-Intervall |",
             "|---|---:|---|---|"]
    for row in result["comparisons"]:
        lines.append(f"| {row['a']} − {row['b']} | {number(row['difference'])} | "
                     f"{interval(row['ci95'])} | {interval(row['ci_familywise'])} |")
    return lines


def _comparison_conclusion(study):
    rows = [row for key in ("ner_uncertainty", "offer_uncertainty")
            for row in study[key]["comparisons"]]
    if not rows or any(row["ci_familywise"] is None for row in rows):
        return "Nicht alle korrigierten Differenzintervalle sind bestimmbar; ein vollständiges statistisches Fazit ist daraus nicht möglich."
    separated = [row for row in rows if row["ci_familywise"][0] > 0 or row["ci_familywise"][1] < 0]
    if separated:
        names = ", ".join(f"{row['a']} − {row['b']}" for row in separated)
        return (f"Bei folgenden Vergleichen schließen die korrigierten Differenzintervalle null aus: {names}. "
                "Diese Unterschiede gelten innerhalb der bestehenden Referenz und beseitigen deren systematische Unsicherheit nicht.")
    return ("Die korrigierten Differenzintervalle schließen in den ausgewerteten Vergleichsfamilien null ein. "
            "Damit ist kein belastbarer Sieger nachgewiesen; ebenso wenig ist Gleichwertigkeit gezeigt.")


def _paragraphs(text):
    return [""] + text.strip().splitlines() + [""]


def _methods(study):
    pair = study["pair_model"]
    return _paragraphs(f"""
## 3. Untersuchte Verfahren: Welche Aufgabe löst welches Modell?

Ein **Modell** ist hier eine berechenbare Zuordnung von Eingaben zu Ausgaben. Beim **maschinellen Lernen (ML)** werden seine einstellbaren Zahlen, die Parameter oder Gewichte, anhand von Beispielen angepasst. Ein **neuronales Netz** verbindet dazu mehrere Rechenschritte in Schichten. Im Projekt gibt es zwei unterschiedliche Lernaufgaben: das Erkennen einzelner Angaben und das Zuordnen dieser Angaben zu Angeboten.

| Ansatz | Eingabe und Entscheidung | Rolle im Projekt |
|---|---|---|
| Textbasierte Entity-Erkennung: GBERT und XLM-R | Aus der Wortfolge den Typ jedes Wortes bestimmen | Trainierte Textmodelle als Vergleichsbasis |
| Layoutgestützte Entity-Erkennung: LiLT | Zusätzlich die Positionen der Wörter berücksichtigen | Prüfen, wie eine Architektur mit Layoutinformation abschneidet |
| Multimodale Entity-Erkennung: LayoutXLM | Text, Wortpositionen und Seitenbild gemeinsam verarbeiten | Trainiertes Dokumentmodell; Erkennung in der verglichenen lokalen Pipeline |
| Regelbasierte Gruppierung: Heuristik | Vorgegebene Regeln über Nähe und Seitenaufbau anwenden | Nachvollziehbare Vergleichsbasis für die Zuordnung |
| Gelernte Gruppierung: Paarmodell mit ILP | Für je zwei Angaben Zusammengehörigkeit bewerten und daraus Gruppen bilden | Eigener trainierter Gruppierer |
| Generative Extraktion: Vision-LLM | Aus dem Seitenbild direkt strukturierte Angebotsdatensätze erzeugen | Externer Blackbox-Vergleich mit Gemma, Qwen und Mistral |

Die vier Entity-Modelle gehören zur selben Methodenfamilie. Ihre Kombination mit Regeln, gelernter Gruppierung und generativer Extraktion schafft die methodische Breite der Untersuchung. Die **Baseline** ist jeweils das Vergleichsverfahren, an dem der Nutzen einer anderen Lösung eingeordnet wird: bei der Entity-Erkennung insbesondere GBERT, bei der Gruppierung die Heuristik.

### 3.1 Entity-Erkennung: Was bedeutet ein Wort?

**Named Entity Recognition (NER)** bezeichnet die Erkennung und Typisierung relevanter Textstellen. Unser eigenes Schema umfasst auch Preise und Mengen. Die Aufgabe lautet beispielsweise: „Butter“ ist PRODUCT, „250 g“ ist QUANTITY und „1,29“ ist PRICE. Der **Span** ist der zusammenhängende Wortbereich einer solchen Angabe; das **Label** ist ihr Typ.

Wir verwenden **Sequenzlabeling** beziehungsweise **Tokenklassifikation**: Das Modell versieht die Wörter einer Folge mit Labels und berücksichtigt dabei ihren Kontext. Im **BIO-Format** markiert B den Beginn einer Entity, I ihre Fortsetzung und O ein Wort außerhalb der gesuchten Angaben. Im erfundenen Beispiel „Frische Butter heute“ wäre eine mögliche Folge `B-PRODUCT I-PRODUCT O`. BIO hält Textgrenzen fest; welche Preisangabe zu diesem Produkt gehört, entscheidet erst die Gruppierung.

Ein **Transformer-Encoder** wandelt die Eingabe in Zahlenvektoren um, wobei sich die Wörter gegenseitig als Kontext beeinflussen. Diese Vektoren heißen Repräsentationen oder **Embeddings**. Ein **Klassifikationskopf** ist die abschließende Rechenschicht, die daraus die Labelbewertung erzeugt. GBERT ist auf deutsche Texte ausgerichtet; XLM-R ist mehrsprachig. LiLT ergänzt räumliche Information. LayoutXLM verbindet mehrere Eingabearten, sogenannte **Modalitäten**: Text, Layout und Bild. Die Architekturgrundlagen sind in [5–8] beschrieben.

**Vortraining** bezeichnet die allgemeine Vorbereitung dieser Modelle auf großen fremden Datensammlungen. Beim **Fine-Tuning** passen wir diese vorhandenen Gewichte mit unseren gelabelten Prospekten an die Angebotsaufgabe an. Der eigene Lernbeitrag besteht in dieser Anpassung und der zusätzlichen trainierten Gruppierung. Ein Vergleich der fertigen Architekturen kann deren Leistung zeigen; wegen ihrer unterschiedlichen Vortrainingsverfahren isoliert er nicht ausschließlich die Wirkung von Wortpositionen oder Bildern.

### 3.2 Wortteile, Training und Anwendung

Ein **Token** ist eine Verarbeitungseinheit des Modells. Ein PDF-Wort kann in mehrere **Subwords**, also Wortteile, zerlegt werden. **Alignment** bezeichnet die Zuordnung unserer Wortlabels zu diesen Teilen. Nur der erste Wortteil trägt das Trainingslabel; die folgenden Teile werden bei der Fehlerberechnung ignoriert. Dadurch wird ein langes Wort nicht allein wegen seiner Zerlegung mehrfach gewichtet.

Die **Verlustfunktion (Loss)** misst während des Trainings die Abweichung zwischen Labelvorhersage und Trainingslabel. Der Optimierer verändert die Gewichte, um diesen Verlust zu verringern. Ein **Checkpoint** ist ein gespeicherter Modellstand. Der Trainingscode wählt den Checkpoint anhand der Ergebnisse auf den Entwicklungsdaten aus. Diese Auswahl verwendet F1, dessen Bedeutung Abschnitt 4 erklärt.

**Inferenz** ist die spätere Anwendung der gelernten Gewichte auf ein Dokument. Lange Eingaben werden im Trainingscode gekürzt; die Inferenz unterstützt dagegen **Sliding Windows**, also überlappende Ausschnitte, deren Vorhersagen wieder zusammengeführt werden. Dieser Unterschied bleibt eine Einschränkung. Die gespeicherten historischen Vorhersagen belegen außerdem keine lückenlos rekonstruierbare Konfiguration jedes Trainingslaufs.

### 3.3 Heuristik: Zusammengehörigkeit durch Regeln

Eine **Heuristik** ist eine von Menschen festgelegte Entscheidungsregel. Unsere räumliche Gruppierung nutzt die Position und Anordnung der erkannten Angaben. Die Grundidee ist beispielsweise, benachbarte Produkt-, Mengen- und Preisangaben demselben Angebotsbereich zuzuordnen. Solche Regeln benötigen für sich kein Training und lassen sich anhand einzelner Entscheidungen nachvollziehen.

Die Schwierigkeit liegt im Prospektlayout: Ein Preis kann räumlich näher am Nachbarprodukt als am eigenen Produkt stehen. Nummerierte Legenden können Produkt und Preis sogar weit voneinander trennen. Nähe ist daher ein nützliches Signal, aber keine allgemeingültige Definition der Zusammengehörigkeit.

### 3.4 Paarmodell: Zusammengehörigkeit aus Beispielen lernen

Das **Paarmodell** betrachtet jeweils zwei bereits erkannte Entities. Seine Frage lautet: „Gehören diese beiden Angaben zum selben Angebot?“ Für das Butter-Beispiel wären dies unter anderem die Paare Produkt–Preis, Produkt–Menge und Menge–Preis. Auch Paare zwischen benachbarten Angeboten müssen bewertet werden.

Jedes Paar wird durch **Merkmale (Features)** beschrieben: beispielsweise die Typen beider Entities, ihr Abstand, ihre räumliche Überlappung und Eigenschaften ihres Textes. Das eingesetzte Modell verwendet {len(pair['feature_names'])} Merkmale aus den Bereichen Entity-Typen, grundlegende und zusätzliche Geometrie sowie Textmerkmale. Es verwendet in diesem Checkpoint keine Farbmerkmale. Diese Angaben stammen aus dem gespeicherten Modell, nicht nur aus den möglichen Optionen des Programms.

Aus Lehrergruppen entstehen Trainingsbeispiele: Zwei Entities derselben Gruppe bilden ein positives Beispiel, zwei Entities verschiedener Gruppen ein negatives. Das Paarmodell lernt, wie die Merkmale zusammen mit diesen Entscheidungen auftreten. Es ist ein **MLP (Multi-Layer Perceptron)**, also ein kleines neuronales Netz mit hintereinanderliegenden Rechenschichten. Die verdeckten Schichten enthalten hier {' und '.join(str(width) for width in pair['hidden'])} Recheneinheiten. „Verdeckt“ bedeutet lediglich, dass diese Zwischenschichten weder die Eingabe noch die fertige Ausgabe sind.

Das Ergebnis für ein Paar ist ein Wert zwischen 0 und 1. Ein hoher Wert spricht aus Sicht des Modells für Zusammengehörigkeit. Er ist keine Garantie und keine nachgewiesene Wahrscheinlichkeit, dass die Zuordnung im Alltag korrekt ist. Die gespeicherte **Schwelle** beträgt {study['pair_threshold']}: Sie legt im anschließenden Verfahren fest, ab welchem Paarwert eine Verbindung positiv gewichtet wird. Sie wird für diese Testauswertung unverändert übernommen. **Kalibrierung** bezeichnet im Projekt die Auswahl einer solchen Entscheidungsschwelle anhand zurückgehaltener Beispiele; sie ist nicht mit einem Nachweis zuverlässiger Wahrscheinlichkeiten gleichzusetzen.

### 3.5 Vom Paar zur Gruppe: Warum zusätzlich ILP?

Einzelne Paarurteile können sich widersprechen: Produkt A soll mit Preis B zusammengehören, B mit Menge C, A aber nicht mit C. Eine Angebotsgruppe muss trotzdem eine konsistente Menge von Angaben bilden. Einfach jede positive Verbindung zu übernehmen kann dadurch mehrere Angebote unbeabsichtigt zusammenziehen.

Der **Decoder**, also das Verfahren zum Zusammenbauen der Ausgabe, berücksichtigt deshalb mehrere Paarbewertungen gemeinsam. Verwendet wird **ILP (Integer Linear Programming, ganzzahlige lineare Optimierung)**. Vereinfacht sucht der Optimierer eine Gruppeneinteilung, die zu möglichst viel der gewichteten Paarinformation passt und die Bedingungen einer gültigen Einteilung einhält. Es entstehen keine widersprüchlichen Gruppenzugehörigkeiten. Der Code enthält Größenbegrenzungen und Rückfallwege für aufwendige Fälle; „ILP“ ist keine Garantie, dass jede denkbare Seite vollständig optimal gelöst wird.

Paarmodell und Decoder haben damit verschiedene Aufgaben: Das Modell **lernt die Bewertung einzelner Verbindungen**, der Decoder **baut daraus Gruppen**. Beide zusammen bilden den hier ausgewerteten gelernten Gruppierer. Eine hohe Gruppierungsqualität setzt weiterhin brauchbare erkannte Entities voraus.

Der Gruppierungscheckpoint nennt `{pair['provenance'].get('reference', 'unbekannt')}` als Trainingsreferenz und `{pair['provenance'].get('splits', 'unbekannt')}` als Trainingssplit. Diese gespeicherte Herkunft dokumentiert den Lauf. Ohne die historische Seitenliste samt Fingerabdruck ist sie kein vollständiger nachträglicher Beweis der Trainingszusammensetzung.

### 3.6 Generative Extraktion und die zwei Rollen des LLM

Ein **Large Language Model (LLM)** erzeugt Ausgaben anhand einer Aufgabenbeschreibung, dem **Prompt**. Ein Vision-LLM kann dabei Seitenbilder verarbeiten. **Generativ** heißt in unserem Vergleich: Das Modell formuliert direkt einen strukturierten Datensatz, statt jedes vorhandene PDF-Wort mit einem Label zu versehen. Die Ausgabe wird als **JSON**, einem maschinenlesbaren Format für Felder und Werte, gespeichert.

Als **Blackbox** betrachten wir diesen Dienst über seine Ein- und Ausgabe: Seitenbild hinein, Angebotsdaten heraus. Seine internen Gewichte werden im Projekt nicht trainiert. Die Anfrage erfolgt über eine **API**, eine Programmierschnittstelle zum externen Dienst. Verglichen werden die gespeicherten Antworten von Gemma, Qwen und Mistral.

Davon getrennt ist die Rolle des LLM als **Lehrer für die Trainingsannotation**. Hier erzeugt es automatisch Labels beziehungsweise Gruppierungsvorgaben, aus denen unsere eigenen Modelle lernen. Diese automatisch erzeugten Vorgaben heißen auch Pseudo-Labels. Fehler des Lehrers können sich auf die gelernten Modelle übertragen. Deshalb unterscheiden wir Ergebnisse gegen Lehrerlabels von Ergebnissen gegen die menschliche Referenz. Nach dem Training benötigt die lokale Pipeline zur Extraktion keine neue LLM-Antwort.
""")


def _metric_guide(study):
    hits, predicted, reference = study["offer_uncertainty"]["systems"]["layoutxlm_pair_model"]["counts"]
    precision, recall = hits / predicted if predicted else 0, hits / reference if reference else 0
    f1 = study["offer_uncertainty"]["systems"]["layoutxlm_pair_model"]["f1"]
    return _paragraphs(f"""
## 4. Wie wird Qualität gemessen?

### 4.1 Precision, Recall und F1

Eine Bewertung braucht zuerst eine festgelegte Einheit: eine Entity, ein zusammengehöriges Paar, eine ganze Gruppe oder ein Angebotseintrag. Die folgenden Größen beziehen sich immer auf diese Einheit und auf die gewählte Referenz.

- **True Positive (TP, Treffer):** Eine vorhergesagte Einheit stimmt nach der jeweiligen Bewertungsregel mit einer Referenzeinheit überein.
- **False Positive (FP, zusätzliche oder falsche Ausgabe):** Für eine vorhergesagte Einheit gibt es keinen passenden Referenzeintrag.
- **False Negative (FN, übersehener Eintrag):** Ein Referenzeintrag hat keine passende Vorhersage.

**Precision** beantwortet: „Wie viel von dem, was das System ausgibt, trifft die Referenz?“ **Recall** beantwortet: „Wie viel von dem, was laut Referenz vorhanden ist, findet das System?“ Ein System kann wenige sehr verlässliche Einträge ausgeben und viel übersehen, oder sehr viel ausgeben und dabei zahlreiche zusätzliche Fehler produzieren. Deshalb werden beide Größen berichtet.

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 × Precision × Recall / (Precision + Recall)
          = 2 × TP / (2 × TP + FP + FN)
```

**F1** ist das harmonische Mittel von Precision und Recall. Es wird hoch, wenn beide Größen hoch sind. Es liegt zwischen 0 und 1; 1 bedeutet vollständige Übereinstimmung nach der verwendeten Regel. F1 ist weder der Anteil richtiger Wörter noch automatisch der Anteil vollständig korrekter Angebote. Fälle ohne bewertbare Einheiten werden in den Ergebnisdateien gesondert behandelt; ein Vergleich ohne Referenzeinträge und ohne Ausgaben gilt nicht als perfekte Leistung.

**Rechenbeispiel aus dieser Studie:** Die lokale Pipeline gibt {predicted:g} auswertbare Angebotseinträge aus. Die Referenz enthält {reference:g}; {hits:g} Einträge werden einander als Treffer zugeordnet. Daraus folgen {predicted-hits:g} zusätzliche Ausgaben und {reference-hits:g} nicht getroffene Referenzeinträge. Precision beträgt {hits:g}/{predicted:g} = **{number(precision)}**, Recall {hits:g}/{reference:g} = **{number(recall)}** und F1 **{number(f1)}**. Das Beispiel betrifft ausschließlich Angebotsname und regulären Preis.

Bei **Micro-F1** werden die Treffer- und Fehlerzahlen über alle betrachteten Einheiten zuerst addiert; daraus wird anschließend F1 berechnet. Es wird also nicht der Durchschnitt einzelner Seiten-F1 gebildet. Häufige Entity-Typen beeinflussen den Gesamtwert stärker als seltene. Deshalb berichten wir zusätzlich Ergebnisse je Typ und den **Support**, hier die Anzahl der jeweiligen Referenzentities.

### 4.2 SemEval: Wann ist eine Entity richtig erkannt?

Wir übernehmen vier Bewertungsschemata aus SemEval-2013 Task 9.1 [1]. **SemEval ist hier die Herkunft der Bewertungsregeln.** Unsere Messung verwendet die eigenen Prospektseiten, nicht den ursprünglichen biomedizinischen SemEval-Datensatz. Die Schemata unterscheiden, wie streng Textgrenzen und Typ einer Entity übereinstimmen müssen.

| Schema | Bedingung für einen vollständigen Treffer | Zweck |
|---|---|---|
| **Strict** | Wortgrenzen und Typ stimmen exakt | Hauptmetrik für die genaue Extraktion |
| **Exact** | Wortgrenzen stimmen exakt; der Typ wird ignoriert | Unterscheiden zwischen Grenz- und Typfehlern |
| **Partial** | Exakte Grenzen geben einen ganzen Treffer; bloße Überlappung einen halben; der Typ wird ignoriert | Zeigen, ob wenigstens ein Teil der Textstelle gefunden wurde |
| **Type** | Passender Typ und mindestens ein gemeinsames Wort | Zeigen, ob die richtige Art von Angabe ungefähr lokalisiert wurde |

Ein erfundenes Beispiel verdeutlicht den Unterschied: Die Referenz markiert „Frische Butter“ als PRODUCT, das Modell nur „Butter“ als PRODUCT. Strict und Exact zählen dies nicht als richtigen Entity-Treffer; Partial vergibt einen halben Treffer, Type einen ganzen. Würde das Modell den vollständigen Text als BRAND markieren, wäre Exact erfüllt, Strict dagegen nicht. Höhere Werte der lockeren Schemata stammen somit aus einer anderen Bewertungsregel, nicht aus einer verbesserten Modellvorhersage.

**Strict bleibt die vorab für diese ergänzende Rechnung festgelegte Hauptmetrik.** Die vier Schemata werden nebeneinander berichtet. Technisch verwenden wir `nervaluate` in Version 1.2.1 [4] und prüfen Strict unabhängig mit `seqeval` gegen. Die Endindizes werden zwischen den Bibliotheken umgerechnet; unser Adapter zählt schon ein gemeinsames Wort als Überlappung. Dadurch werden auch lange Spans nach derselben Wortregel bewertet.

### 4.3 Paar-F1, Gruppen-F1 und Angebots-F1 messen Verschiedenes

**Paar-F1** bewertet, welche Entity-Paare demselben Angebot zugeordnet sind. Eine Referenzgruppe aus Produkt, Menge und Preis enthält beispielsweise die Beziehungen Produkt–Menge, Produkt–Preis und Menge–Preis. Wird die Menge abgetrennt, bleibt die Beziehung Produkt–Preis korrekt, während die beiden anderen fehlen. Größere Gruppen tragen mehr Paare bei; Paar-F1 ist deshalb keine Gleichgewichtung der Angebote.

**Exakte Gruppen-F1** verlangt dagegen dieselbe komplette Gruppe von zuordenbaren Entities. Eine falsche zusätzliche Entity oder eine fehlende Entity kann den Treffer der gesamten Gruppe verhindern. „Exakt“ bezieht sich auf die jeweilige Entity-Grundmenge. Fehlen schon bei der Erkennung Entities, können sie in einer anschließenden reinen Gruppierungsbewertung nicht unverändert als vorhandene Eingabe vorausgesetzt werden. Nicht zuordenbare Entities werden deshalb gesondert ausgewiesen. Ein hoher Gruppierungswert allein beweist keine gute vollständige Pipeline.

**Angebots-F1** bewertet hier fertige Einträge aus Name und regulärem Preis. Dieser Vergleich ist zwischen lokaler Pipeline und Blackbox möglich, obwohl die Blackbox keine Wortpositionen ausgibt. Die genaue Regel und die ausgeschlossenen Felder stehen in Abschnitt 5.4. Entity-F1, Paar-F1 und Angebots-F1 haben unterschiedliche Nenner und dürfen nicht wie dieselbe Kennzahl verglichen werden.

### 4.4 Unsicherheit: Wie stabil ist eine beobachtete Differenz?

Ein einzelner F1-Wert ist eine **Punktschätzung** für die ausgewählten Seiten. Andere Seiten können zu anderen Werten führen. Ein **Bootstrap** nähert diese Stichprobenunsicherheit an: Aus den vorhandenen Daten werden wiederholt Einheiten mit Zurücklegen gezogen und die Kennzahlen neu berechnet. Wir verwenden {study['ner_uncertainty']['resamples']} Ziehungen. Der **Seed** {study['ner_uncertainty']['seed']} ist der Startwert des Zufallszahlengenerators und macht diese Ziehungen reproduzierbar.

Die Ziehungseinheit ist ein **Vorlagencluster**, also eine Gruppe ähnlicher Regionalvarianten einer Seite. Diese Cluster sind von den Angebotsgruppen auf einer einzelnen Seite zu unterscheiden. Viele fast gleiche Seiten dürfen keine scheinbar große unabhängige Stichprobe erzeugen. Die Cluster werden im vollständigen Testsplit bestimmt; die feste Vergleichsliste wird darauf abgebildet.

Das **95-%-Konfidenzintervall (KI)** beschreibt einen Unsicherheitsbereich des Schätzverfahrens. Hier verwenden wir die mittleren 95 % der Bootstrap-Werte als näherungsweises Intervall. Es ist keine Garantie für das Ergebnis auf einer neuen Woche und keine nachträgliche Wahrscheinlichkeit, dass ein Modell besser ist.

Bei einem **gepaarten Vergleich** erhalten beide Systeme in jeder Ziehung dieselben Seiten. Gemessen wird dann ihre Differenz **ΔF1 = F1(A) − F1(B)**. Positive Werte sprechen im jeweiligen Vergleich für A, negative für B. Enthält das Differenzintervall null, liefern diese Daten unter diesem Verfahren keinen eindeutigen Nachweis eines Unterschieds. Gleichwertigkeit ist damit ebenfalls nicht bewiesen.

Mehrere Vergleiche erhöhen die Möglichkeit eines zufällig auffälligen Ergebnisses. Die **Bonferroni-Korrektur** verwendet deshalb strengere, breitere Intervalle. Wir behandeln die vier NER-Vergleiche und die drei Blackbox-Vergleiche als zwei getrennte, explorative Vergleichsfamilien mit jeweils 5 % nominalem Familienfehlerniveau. Die Interpretation hängt weiterhin von den Annahmen und der Näherung des Bootstrap ab [2]. Die Intervalle messen weder Referenzfehler noch die Streuung über neu trainierte Modellstände.
""")


def _requirements():
    return _paragraphs("""
## 8. Abgleich mit dem Projektantrag

Der [Projektantrag](../../../docs/proposal/IE_ProjectProposal_Magda.pdf) nennt auf Seite 3 fünf Anforderungen in den Stufen Minimum, Good und Excellent. Die folgende Zuordnung hält fest, wodurch jede Anforderung bearbeitet wurde und welche Reichweite der Nachweis hat. Die Stufen sind Anforderungen des Antrags, keine vorweggenommene Benotung.

| Stufe und Anforderung | Umsetzung und Nachweis | Einordnung |
|---|---|---|
| **Minimum: Prospekt hinein, strukturierte Angebote heraus, mit selbst trainiertem Modell** | Durchgängige Verarbeitung in `src/magda/pipeline.py`: PDF-Wörter und Positionen, trainierte Entity-Erkennung, Paarmodell und Angebotsausgabe; Ausgabe als JSON, CSV oder SQLite | Für PDFs mit nutzbarem Textlayer umgesetzt. Die Abschlussauswertung verwendet gespeicherte Vorhersagen; sie ist kein neuer Laufzeitbenchmark des PDF-Eingangs. |
| **Minimum: dokumentiertes Entity-F1** | Abschnitt 5.1: Strict Entity-Precision, Recall und F1 für alle vier Modelle; Strict-Gegenprüfung mit seqeval | Erfüllt; Referenzumfang und Einschränkungen sind benannt. |
| **Good: Layoutmodell gegen Textbaseline vergleichen** | GBERT und XLM-R gegenüber LiLT und LayoutXLM, ergänzt durch gepaarte Intervalle | Vergleich durchgeführt. Der Nutzen wird empirisch eingeordnet; unterschiedliche Vortrainingsverfahren erlauben keine isolierte kausale Layoutaussage. |
| **Good: häufige Fehler analysieren** | Abschnitt 6: fehlende Entities, Typfehler, abweichende Grenzen, Typauflösung und konkrete Referenzprobleme | Erfüllt; Unterschiede gegenüber der Referenz werden von nachgewiesenen Modellfehlern unterschieden. |
| **Excellent: eigenes Modell gegen LLM-Blackbox; Qualität, Kosten und lokaler Betrieb gegenüber API diskutieren** | Abschnitt 5.4 vergleicht die lokale Pipeline mit drei gespeicherten Vision-LLM-Läufen; Abschnitt 7 diskutiert Betriebs- und Kostenfaktoren | Vergleich und Diskussion durchgeführt. Vergleichsmodelle gegenüber dem Gemini-Prototyp geändert; Kosten qualitativ eingeordnet, kein gemessener Kostensieg. |

Auch die im Antrag beschriebenen technischen Bausteine sind umgesetzt: eigenes Entity-Schema, LLM-gestützte Trainingslabels, BIO-Kodierung, Subword-Alignment mit Maskierung der Fortsetzungen, Klassifikationskopf, Fine-Tuning des Dokumentmodells und trainierte GBERT-Baseline. XLM-R, LiLT, der Vergleich von Heuristik und Paarmodell sowie die erweiterte Unsicherheitsanalyse ergänzen den geplanten Umfang.

**Anpassungen gegenüber dem ursprünglichen Plan:** Der als OCR bezeichnete Schritt liest bei Penny tatsächlich den vorhandenen PDF-Textlayer aus. OCR würde Schrift erst aus Bildpixeln erkennen; das wird für diese Daten nicht benötigt und für reine Bild-PDFs nicht nachgewiesen. Der ursprüngliche Gemini-Prototyp wird durch gespeicherte Gemma-, Qwen- und Mistral-Läufe als Blackbox-Vergleich vertreten. Der Vergleich beantwortet damit die geplante Systemfrage, reproduziert aber keinen identischen historischen Gemini-Lauf. Die Zielgröße „bis zu mehreren tausend Angeboten“ war eine Planungsgröße; Seiten- und Entity-Zahlen dürfen nicht ohne Gruppierungsdefinition als Zahl korrekt extrahierter Angebote ausgegeben werden.

Damit werden alle fünf ausdrücklich genannten Anforderungspunkte in der dokumentierten Reichweite adressiert. Die beschriebenen Anpassungen und Referenzgrenzen gehören zum Ergebnis dieser Umsetzung.
""")


def render(study, review_status, command):
    audit, ner = study["reference_audit"], study["ner"]
    layout_score = ner["layoutxlm"]["matching_schemes"]["strict"]["f1"]
    baseline_score = ner["gbert"]["matching_schemes"]["strict"]["f1"]
    offer_score = study["offer_uncertainty"]["systems"]["layoutxlm_pair_model"]["f1"]
    lines = _paragraphs(f"""
# Magda: Von Prospektseiten zu strukturierten Angeboten

Semesterprojekt Information Extraction · SoSe 2026 · Leuphana

Bogdan Roth · Kjell Lavezzari · Noah Samel

## Redaktionshinweis für Bogdan und Kjell: Aufbau der Abgabefassung

**Arbeitsnotiz für die gemeinsame Fertigstellung; vor der Abgabe entfernen.** Die wissenschaftliche Einleitung und der Abschnitt zu verwandten Arbeiten werden von Bogdan und Kjell ergänzt. Der folgende Bericht liefert die technische und empirische Materialgrundlage. Die bisherigen Abschnittsnummern sind noch nicht die endgültige Paper-Gliederung.

Als strukturelle Vorlage dient der Bericht **„Erkennung von Schreibaktivität anhand der IMU-Daten einer Apple Watch“** (`ML4SCS (~4900 words).pdf`). Er führt von der Einleitung über verwandte Arbeiten, Datenerhebung, Methodik und Evaluation zu Ergebnissen, Diskussion, einem eigenen Abschnitt zu Limitationen und dem Fazit. Besonders hilfreich ist sein Unterabschnitt „Einordnung der vorliegenden Arbeit“ am Ende der verwandten Arbeiten: Dort wird aus dem Literaturvergleich die Position des eigenen Projekts hergeleitet. Für Magda lässt sich dieser Aufbau wie folgt übertragen:

| Teil der Abgabefassung | Was hineingehört | Vorhandenes Material |
|---|---|---|
| **Abstract / Kurzfassung** | Problem, Vorgehen, wichtigstes Ergebnis und zentrale Einschränkung knapp zusammenfassen; nach Fertigstellung des Haupttextes überarbeiten | Aktuelle Kurzfassung |
| **1. Einleitung** | Problem und Relevanz der Angebotsextraktion erklären, wissenschaftlich einordnen, die konkrete Projektfrage und den eigenen Beitrag benennen; mit einem kurzen Überblick über den Aufbau enden | Aktueller Abschnitt 1 als Ausgangspunkt; wissenschaftliche Einordnung durch euch ergänzen |
| **2. Verwandte Arbeiten** | Ausgewählte relevante Arbeiten vorstellen und vergleichen; mit einem Unterabschnitt „Einordnung von Magda“ abschließen | Eigenen Abschnitt ergänzen; Literaturverzeichnis als Einstieg |
| **3. Daten und Aufgabendefinition** | Prospekte, Annotation, Entity-Schema, Angebotsdefinition, Datenaufteilung und Herkunft der Referenz beschreiben | Aktueller Abschnitt 2 |
| **4. Methodik** | Datenweg und untersuchte Verfahren erklären: Entity-Erkennung, Text/Layout/Bild, Heuristik, Paarmodell mit Gruppierung und LLM-Blackbox; Auswahl der Verfahren begründen | Aktuelle Abschnitte 1.1 und 3 |
| **5. Versuchsaufbau und Evaluation** | Festlegen, was zwischen den Systemen vergleichbar ist, welche Referenz verwendet wird und wie Precision, Recall, F1 und Unsicherheit berechnet werden | Aktueller Abschnitt 4 und Versuchsbedingungen aus Abschnitt 5 |
| **6. Ergebnisse und Fehleranalyse** | Messwerte entlang der Forschungsfragen präsentieren und typische Abweichungen anhand konkreter Fälle erklären | Aktuelle Abschnitte 5 und 6 |
| **7. Diskussion** | Forschungsfragen beantworten, Ergebnisse auf verwandte Arbeiten beziehen und praktische Abwägungen erläutern | Aktuelle Abschnitte 7.1 und 7.2; Rückbezug auf eure Literatur ergänzen |
| **8. Limitationen** | Referenzqualität, unklare Angebotsabgrenzung, Testhistorie und begrenzte Übertragbarkeit zusammenhängend einordnen | Aktueller Abschnitt 7.3 und entsprechende Hinweise in der Daten- und Fehleranalyse |
| **9. Fazit und Ausblick** | Den belegten Beitrag und die wichtigsten Erkenntnisse bündeln, danach mögliche Folgearbeiten nennen | Aktueller Abschnitt 9 |
| **Literatur und Anhang** | Vollständige Quellen; technische Nachweise, Reproduktionsbefehle und Proposal-Abgleich gesammelt nachweisen; tatsächliche Teambeiträge sowie Code- und Datenverfügbarkeit angeben | Literaturverzeichnis sowie aktuelle Abschnitte 8 und 10; Beiträge gemeinsam korrekt zuordnen |

**Tipp für „Verwandte Arbeiten“:** Wie in der Vorlage einige besonders relevante Arbeiten so vorstellen, dass Aufgabe, Daten, Verfahren und Evaluation verständlich werden. Sinnvolle Themen für Magda sind (a) Entity-Erkennung und Sequenzlabeling, (b) Dokumentextraktion mit Layout und Bild, (c) LLMs als Annotatoren beziehungsweise direkte Extraktoren und (d) die Zuordnung erkannter Angaben zu Datensätzen. Einzelne Arbeiten können eigene Unterabschnitte erhalten oder thematisch zusammengefasst werden. Jeweils erklären: Worin ähnelt oder unterscheidet sich Magda? Welche Entscheidung unseres Projekts wird dadurch verständlich? Im abschließenden Unterabschnitt „Einordnung von Magda“ diese Verbindungen bündeln und zur eigenen Aufgabe überleiten. Die vorhandenen Modellquellen sind ein Ausgangspunkt, keine abgeschlossene Literaturrecherche. Aussagen mit den gelesenen Originalarbeiten belegen; eine Forschungslücke oder Überlegenheit nur behaupten, wenn die Quellen beziehungsweise unsere Messungen sie tragen.

**Roter Faden:** Einleitung und verwandte Arbeiten sollen zu den drei Fragen „Erkennen, Zuordnen, Vergleichen“ hinführen. Methodik erklärt, wie wir diese Fragen untersuchen; Ergebnisse beantworten sie mit Daten; Diskussion ordnet die Antworten und ihre Grenzen ein. ML-Begriffe weiterhin beim ersten Gebrauch verständlich erklären. Beim Umstellen die Querverweise aktualisieren und Dopplungen zwischen Einleitung, Methodik und Diskussion kürzen. Der Proposal-Abgleich kann als Nachweis im Anhang bleiben, damit der Haupttext der wissenschaftlichen Argumentation folgt. Es ist keine weitere Annotation vorgesehen.

---

## Kurzfassung

Supermarktprospekte verteilen Produktnamen, Mengen und Preise über die Seite. Magda überführt diese Angaben in strukturierte Angebotsdatensätze. Dazu vergleichen wir mehrere trainierte Verfahren zur Erkennung der Angaben, eine regelbasierte und eine gelernte Methode für ihre Zuordnung sowie große Sprachmodelle, die Angebote direkt aus dem Bild ausgeben.

Die eigene Pipeline lernt aus automatisch erzeugten Trainingslabels und kann anschließend lokal ohne neue Anfrage an einen Sprachmodelldienst arbeiten. Gegen die bestehende menschliche Referenz erreicht ihre Entity-Erkennung mit LayoutXLM **{number(layout_score)} Strict-F1**; die Textbaseline GBERT erreicht **{number(baseline_score)}**. Die vollständige Ausgabe von Angebotsname und regulärem Preis erreicht **{number(offer_score)} F1**. F1 verbindet den Anteil passender Ausgaben mit dem Anteil gefundener Referenzeinträge; die genaue Rechnung wird in Abschnitt 4 erklärt.

**Abgeschlossene explorative Fallstudie mit bestehender Referenz.** „Explorativ“ bedeutet, dass die Untersuchung Unterschiede und Fehlerbilder im vorhandenen Material beschreibt. Sie liefert keine allgemeingültige Rangliste der Modelle. Mehrdeutige Angebotsgrenzen, bekannte Referenzfehler und fehlende unabhängige Doppelannotation begrenzen die Aussagen. Für diesen Studienabschluss erfolgt keine weitere Labelrunde.

## 1. Aufgabe und Forschungsfragen

**Information Extraction (IE)** macht gezielt gesuchte Informationen aus Dokumenten als einzelne Felder weiterverarbeitbar. Ein erfundenes Beispiel: Aus den Angaben „Beispielmarke“, „Frische Butter“, „250 g“ und „1,29 €“ soll ein Datensatz mit Marke, Produkt, Menge und Preis entstehen. Auf einer Prospektseite stehen viele solcher Angaben nebeneinander. Das System muss daher sowohl ihre Bedeutung als auch ihre Zusammengehörigkeit bestimmen.

Wir trennen drei Fragen:

1. **Erkennen:** Wie zuverlässig finden Text-, Layout- und Bildmodelle die einzelnen Angaben?
2. **Zuordnen:** Wie gut bilden feste Regeln beziehungsweise ein gelerntes Paarmodell daraus Angebote?
3. **Vergleichen:** Wie schneidet die lokale Pipeline gegenüber einem großen Sprachmodell ab, das fertige Angebote direkt aus dem Bild erzeugt?

Der eigene Beitrag umfasst die auf Prospektdaten angepassten Modelle, den trainierten Gruppierer, die durchgängige Verarbeitung und die gemeinsame Auswertung. Die folgenden Abschnitte erläutern zunächst den Datenweg und die Begriffe, danach die Ergebnisse. Abschnitt 8 ordnet die Nachweise den Anforderungen des Projektantrags zu.

### 1.1 Der Datenweg im Überblick

```mermaid
flowchart LR
    PDF[Prospekt als PDF] --> W[Wörter und Positionen]
    W --> N[Trainierte Erkennung der Angaben]
    PDF --> I[Seitenbild]
    I --> N
    N --> H[Heuristische Zuordnung]
    N --> P[Paarmodell und Gruppierung]
    H --> O[Strukturierte Angebote]
    P --> O
    I --> B[Vision-LLM als Blackbox]
    B --> L[Strukturierte Vergleichsausgabe]
```

Heuristik und Paarmodell sind alternative Gruppierer. Die in der Haupttabelle verwendete lokale Pipeline kombiniert LayoutXLM mit dem Paarmodell und seinem Gruppierungsverfahren. Von den lokalen Erkennungsmodellen nutzt LayoutXLM zusätzlich das Bild; GBERT und XLM-R nutzen Text, LiLT Text und Wortpositionen. Das Diagramm zeigt die Anwendung nach dem Training. Die LLM-Erzeugung der Trainingslabels ist ein vorgelagerter Arbeitsschritt.

## 2. Daten, Labels und Referenz

Ein **Datensatz** ist die Sammlung der Beispiele für Training oder Auswertung. Die Penny-PDFs enthalten bereits einen **Textlayer**, also gespeicherte Wörter samt Positionen. PyMuPDF liest daraus Wörter und ihre rechteckigen Bereiche auf der Seite, die **Bounding Boxes**. Zusätzlich stehen gerenderte Seitenbilder zur Verfügung. **OCR** würde dagegen Zeichen aus einem reinen Bild erkennen; eine solche OCR-Leistung wird hier nicht gemessen.

**Annotation** oder **Labeling** bedeutet, Beispielen die gesuchten Kategorien und Zuordnungen zu geben. Trainingslabels entstehen im Projekt mit LLM-Unterstützung. Für die Abschlussmessung verwenden wir die vorhandenen menschlichen Entity-Annotationen und Angebotsgruppen. Diese **Referenz**, häufig **Goldstandard** genannt, legt fest, welche Ausgabe die Messung als richtig zählt. „Gold“ bezeichnet ihre Rolle in der Bewertung und garantiert keine Fehlerfreiheit.

| Label | Bedeutung |
|---|---|
| PRODUCT | Produktname einschließlich erfasster Variante |
| BRAND | Marke |
| PRICE | Aktueller regulärer Kaufpreis ohne App-Bedingung |
| OLD_PRICE | Früherer beziehungsweise durchgestrichener Vergleichspreis |
| APP_PRICE | Preis unter der Bedingung der App-Nutzung |
| QUANTITY | Menge, Gewicht oder Stückzahl |
| UNIT_PRICE | Grundpreis, etwa je Kilogramm |
| DISCOUNT | Explizite Rabattangabe |
| VALID | Gültigkeitszeitraum |

### 2.1 Warum Training, Entwicklung und Test getrennt werden

Beim **Training** werden Modellgewichte anhand von Beispielen angepasst. **Entwicklungsdaten (Dev)** dienen zur Auswahl von Modellständen und Einstellungen. **Testdaten** dienen zur abschließenden Bewertung. Ein **Split** ist diese Aufteilung. Würde ein Modell auf denselben Beispielen lernen und gemessen, könnte bloßes Wiedererkennen einen scheinbaren Erfolg erzeugen.

Der eingefrorene Split enthält **{study['split']['train']} Trainings-, {study['split']['dev']} Entwicklungs- und {study['split']['test']} Testseiten**. Die feste menschlich referenzierte Vergleichsliste umfasst **{len(study['pages'])} Seiten in {len(study['clusters'])} ausgewerteten Vorlagenclustern**. Die Rechnung prüft, dass die verwendeten Seiten zum Test gehören und die drei Splits keine gemeinsamen Seiten-IDs enthalten.

Penny veröffentlicht ähnliche regionale Ausgaben. Wir berücksichtigen deshalb Vorlagenähnlichkeit statt jede Regionalvariante als unabhängiges Beispiel zu behandeln. Das bestehende Verfahren bildet Cluster über die Wortmengenähnlichkeit nach **Jaccard**: gemeinsame Wörter im Verhältnis zur Vereinigungsmenge der Wörter. Der verwendete Schwellenwert ist 0,7. Eine solche Gruppierung verringert das Problem von Beinahe-Duplikaten; sie beweist keine vollständige statistische Unabhängigkeit.

Die Testseiten waren bereits in früheren Entwicklungs- und Vergleichsarbeiten betrachtet worden. Die ergänzende Auswertung macht sie nicht nachträglich zu einem unberührten Test. Für diesen Abschluss wurden Modelle, Schwellen, Seitenliste und Referenz unverändert übernommen. Die Studie begründet keine nachträgliche Optimierung auf diesen Testseiten.
""")
    if review_status["status"] == "not_performed":
        lines += _paragraphs("""
### 2.2 Was über die Qualität der Referenz bekannt ist

Eine **unabhängige Doppelannotation** würde dieselben Beispiele von zwei Personen getrennt bearbeiten lassen. Ihre **Inter-Annotator-Übereinstimmung** beschreibt, wie häufig ihre Urteile zusammenpassen. **Adjudikation** bedeutet, Unterschiede anschließend begründet aufzulösen. Eine zusätzliche systematische Doppelannotation und Adjudikation wurden für diese Studie nicht durchgeführt; eine entsprechende Übereinstimmungszahl wird daher nicht angegeben.

Die Herkunft der Entity- und Gruppierungsannotation steht je Seite in `reference-audit.json`. Menschlich geprüfte KI-Vorschläge gelten nicht als unabhängige Blindannotation. Eine Bestätigung der Angebotsgruppen belegt außerdem nicht, dass alle zugrunde liegenden Entity-Labels nochmals semantisch geprüft wurden. Die Wortlisten werden durch **Hashes**, rechnerische Dateifingerabdrücke, an ihre Annotationen gebunden. Das schützt vor unbemerkten technischen Änderungen, nicht vor inhaltlich falschen Labels.
""")
    else:
        lines += _paragraphs(f"""
### 2.2 Zusätzliche Kontrollannotation

Status des optionalen getrennten Prüfpakets: `{review_status['status']}`. Es verändert die Referenz nicht automatisch. Übereinstimmung wird ausschließlich aus tatsächlich vorliegenden Originalabgaben berechnet; der gemeinsame Abgleich bleibt eine eigene Entscheidung. Die Herkunft der vorhandenen Referenz wird in `reference-audit.json` dokumentiert.
""")
    lines += _paragraphs("""
### 2.3 Was in dieser Studie als Angebot zählt

Für die Rechnung gilt die gespeicherte Zuordnung von Wörtern zu Angebotsgruppen. Aus jeder Gruppe werden BRAND- und PRODUCT-Texte zum Namen zusammengesetzt. Je unterschiedlichem auswertbaren PRICE-Wert entsteht ein Eintrag mit diesem Namen. Varianten innerhalb einer Gruppe mit gemeinsamem Preis bilden damit einen Eintrag; unterschiedliche Preise erzeugen mehrere. Eine Gruppe ohne Namen oder PRICE ist ein **Fragment** und liegt außerhalb des Angebotsscores.

Diese **operative Definition** legt die Bewertungseinheit fest. Sie entscheidet jedoch nicht jede inhaltliche Mehrdeutigkeit: Ein gemeinsames Preisfeld kann mehrere Produkte oder Sorten betreffen, räumlich benachbarte Angaben können zu verschiedenen Angeboten gehören, und Mehrfachkäufe oder App-Bedingungen verändern die Kaufbedingungen. Eine andere plausible Abgrenzung verändert Referenzeinträge und Treffer. Mangels alternativer unabhängiger Gruppierungsreferenz wird dieser Einfluss nicht empirisch quantifiziert.
""")
    lines += _methods(study) + _metric_guide(study)
    lines += _paragraphs("""
## 5. Ergebnisse und ihre Bedeutung

### 5.1 Erkennung der einzelnen Angaben

Alle folgenden Entity-Werte beziehen sich auf dieselben menschlich referenzierten Vergleichsseiten. Precision und Recall werden für Strict angegeben; die weiteren Spalten sind F1-Werte der jeweiligen SemEval-Regel.

| Modell | Precision strict | Recall strict | F1 strict | Exact-F1 | Partial-F1 | Type-F1 | Strict 95-%-KI |
|---|---:|---:|---:|---:|---:|---:|---|
""")
    lines.pop()
    for variant in VARIANTS:
        schemes = ner[variant]["matching_schemes"]
        strict = schemes["strict"]
        lines.append(f"| {variant} | {number(strict['precision'])} | {number(strict['recall'])} | "
                     + " | ".join(number(schemes[s]["f1"]) for s in ("strict", "exact", "partial", "type"))
                     + f" | {interval(study['ner_uncertainty']['systems'][variant]['ci95'])} |")
    lines += ["", "Die folgende Tabelle vergleicht die Systeme direkt. Das Intervall der Differenz ist hierfür aussagekräftiger als das bloße Nebeneinander ihrer einzelnen Intervalle.", ""]
    lines += _comparisons(study["ner_uncertainty"])
    lines += _paragraphs(f"""

**Einordnung:** GBERT erreicht {number(baseline_score)}, LayoutXLM {number(layout_score)} Strict-F1. Diese Punktwerte allein erlauben keine Entscheidung über einen verlässlichen Architekturvorteil. Die korrigierten Differenzintervalle stehen daneben, damit sowohl Größe als auch Unsicherheit sichtbar bleiben. Dass eine komplexere Eingabe verfügbar ist, garantiert keinen höheren Wert in jedem Entity-Typ.

### 5.2 Welche Angaben sind schwierig?

Die Typauflösung zeigt, wo sich der Gesamtwert zusammensetzt. Die Anzahl der Referenzentities ist der Support; seltene Typen lassen sich weniger präzise beurteilen.

| Typ | Referenzentities | GBERT | XLM-R | LiLT | LayoutXLM |
|---|---:|---:|---:|---:|---:|
""")
    lines.pop()
    labels = sorted({label for report in ner.values() for label in report["matching_schemes_per_label"]})
    for label in labels:
        rows = [ner[v]["matching_schemes_per_label"].get(label, {}).get("strict", {}) for v in VARIANTS]
        lines.append(f"| {label} | {rows[0].get('possible', 0)} | " + " | ".join(number(r.get("f1")) for r in rows) + " |")
    lines += _paragraphs(f"""

**Einordnung:** Bei LayoutXLM beträgt Strict-F1 für PRICE {number(ner['layoutxlm']['matching_schemes_per_label']['PRICE']['strict']['f1'])}, für PRODUCT {number(ner['layoutxlm']['matching_schemes_per_label']['PRODUCT']['strict']['f1'])} und für QUANTITY {number(ner['layoutxlm']['matching_schemes_per_label']['QUANTITY']['strict']['f1'])}. Besonders Produktnamen und Mengen verdienen damit Aufmerksamkeit. Uneinheitliche Referenzgrenzen können zu den Abweichungen beitragen; aus der Tabelle lässt sich ihr Anteil nicht bestimmen.

### 5.3 Zuordnung zu Angeboten: Heuristik gegenüber Paarmodell

Die ersten beiden Zeilen verwenden **dieselben Goldentities**, also die aus der Referenz übernommenen Angaben. Dadurch wird ihre Erkennung zunächst vorausgesetzt und die Zuordnung untersucht. Die dritte Zeile verwendet die von LayoutXLM erkannten Entities und bewertet damit eine andere Grundmenge. Nicht zuordenbare Entities und Referenzgruppen ohne verbleibende Entity werden separat gezählt.

| Eingabe / Gruppierer | Paar-F1 | 95-%-KI | Exakte Gruppen-F1 | 95-%-KI | Nicht zuordenbare Entities | Referenzgruppen ohne Entity |
|---|---:|---|---:|---|---:|---:|
""")
    lines.pop()
    for name, result in study["grouping"].items():
        pair, group = result["systems"]["pair"], result["systems"]["exact_group"]
        lines.append(f"| {name} | {number(pair['f1'])} | {interval(pair['ci95'])} | "
                     f"{number(group['f1'])} | {interval(group['ci95'])} | "
                     f"{result['totals']['unassignable']} | {result['totals']['ref_groups_without_entities']} |")
    heuristic = study["grouping"]["heuristic_on_gold"]["systems"]
    learned = study["grouping"]["pair_model_on_gold"]["systems"]
    lines += _paragraphs(f"""

**Einordnung:** Auf Goldentities erreicht die Heuristik {number(heuristic['pair']['f1'])} Paar-F1, der gelernte Gruppierer {number(learned['pair']['f1'])}. Auch exakte Gruppen werden häufiger getroffen: Gruppen-F1 beträgt {number(heuristic['exact_group']['f1'])} beziehungsweise {number(learned['exact_group']['f1'])}. Das ist ein deutlicher Unterschied der beobachteten Punktwerte auf derselben Eingabegrundlage. Diese Tabelle enthält einzelne Bootstrap-Intervalle, keinen zusätzlich berechneten gepaarten Signifikanztest der Gruppierer. Aus der dritten Zeile darf kein Vorteil fehlerhafter Modellentities gegenüber Goldentities abgeleitet werden: Die bedingt bewertete Grundmenge verändert sich.

### 5.4 Fertige Angebote: lokale Pipeline gegenüber LLM-Blackbox

Hier wird die gemeinsame Aufgabe auf **Name und regulären Preis** begrenzt. Der feste Score `offer-price-v2` verlangt exakt denselben Preis und eine symmetrische Zeichenähnlichkeit des Namens von mindestens 0,6. Zeichenähnlichkeit vergleicht Buchstabenfolgen und ist keine Prüfung gleicher Bedeutung. Ein **maximales Eins-zu-eins-Matching** ordnet die Ausgaben so zu, dass möglichst viele gültige Treffer entstehen, jeder Eintrag aber höchstens einmal zählt.

Die Blackbox liefert keine Wortpositionen. SemEval-Spanregeln lassen sich deshalb ohne eine zusätzliche, fehleranfällige Zuordnung zu PDF-Wörtern nicht unmittelbar auf ihre Ausgabe anwenden. Für diesen Systemvergleich wird daher das beschriebene Angebotsmaß verwendet.

| System | Treffer | Ausgaben | Referenzeinträge | Precision | Recall | F1 | 95-%-KI | Fehlende Antworten |
|---|---:|---:|---:|---:|---:|---:|---|---:|
""")
    lines.pop()
    for name, row in study["offer_uncertainty"]["systems"].items():
        hits, predicted, reference = row["counts"]
        failures = len(study["replays"].get(name, {}).get("missing_responses", []))
        lines.append(f"| {name} | {hits:g} | {predicted:g} | {reference:g} | "
                     f"{number(hits/predicted if predicted else 0)} | {number(hits/reference if reference else 0)} | "
                     f"{number(row['f1'])} | {interval(row['ci95'])} | {failures} |")
    lines += _paragraphs(f"""

{len(study['reference_fragments'])} Referenzfragmente und {len(study['own_fragments'])} Fragmente der lokalen Pipeline besitzen keinen auswertbaren Namen oder PRICE. Sie stehen vollständig in `study.json`. Altpreis, App-Preis, Menge, Grundpreis, Rabatt, Gültigkeit und Kaufbedingungen sind außerhalb dieses Hauptscores, auch wenn die Systeme solche Felder ausgeben können. Angebots-F1 misst damit keine vollständige Feldgenauigkeit.

**Replay** bedeutet, gespeicherte Antworten erneut zu bewerten. Alle angeforderten Seiten bleiben im Vergleich; fehlgeschlagene API-Seiten zählen als leere Ausgaben. So bleibt die Zuverlässigkeit des ursprünglich ausgeführten Gesamtablaufs Teil der Messung. Neue API-Aufrufe werden nicht durchgeführt.
""")
    lines += _comparisons(study["offer_uncertainty"])
    qwen_score = study["offer_uncertainty"]["systems"]["qwen3.6-35b-a3b"]["f1"]
    lines += _paragraphs(f"""

**Einordnung:** Die lokale Pipeline erreicht {number(offer_score)} Angebots-F1, Qwen {number(qwen_score)}. Die nahe beieinanderliegenden Punktwerte zeigen, dass eine spezialisierte lokale Pipeline in diesem Datensatz praktisch relevante Ausgaben liefern kann. Die Differenzintervalle erlauben keine Gleichwertigkeitsbehauptung. Die fehlenden Antworten einzelner Blackboxes begrenzen zudem deren gemessenen Gesamtablauf; die Tabelle isoliert keine reine Modellqualität ohne Dienstfehler.

## 6. Fehleranalyse: Was wurde nicht passend extrahiert?

Eine **Fehlertaxonomie** ordnet Abweichungen in nachvollziehbare Kategorien. Wir unterscheiden zunächst drei Fälle für nicht exakt getroffene Referenzentities. Zusätzliche Vorhersagen werden über Precision und die vollständigen Zähler erfasst. Bei einer fehlerhaften Referenz ist eine Abweichung nicht automatisch ein Fehler des Modells.

| Modell | Keine überlappende Vorhersage | Falscher Typ bei exakten Grenzen | Grenzen / Zusammenfassung abweichend |
|---|---:|---:|---:|
""")
    lines.pop()
    for name, errors in study["error_analysis"].items():
        counts = errors["counts"]
        lines.append(f"| {name} | {counts.get('missing', 0)} | {counts.get('type_at_exact_boundary', 0)} | {counts.get('boundary_or_merge', 0)} |")
    lines += _paragraphs(f"""

Die Kategorien erklären unterschiedliche Schwierigkeiten: eine ganz übersehene Angabe, ein falsch zugewiesener Typ oder eine Textstelle mit anderer Abgrenzung. Bei LayoutXLM steigt F1 von {number(layout_score)} unter Strict auf {number(ner['layoutxlm']['matching_schemes']['type']['f1'])} unter Type. Das zeigt die Bedeutung der Grenzanforderung; Type bewertet allerdings bereits jede passende Typzuordnung mit Wortüberlappung großzügig. Die Differenz ist deshalb keine direkte Quote bloß harmloser Grenzfehler.

### 6.1 Referenzdiagnostik und ein konkreter Fehler

Eine regelbasierte Prüfung verwendet ausschließlich Referenzdateien und Quellwörter. Ihre Zahlen sind **Hinweise, keine bestätigten Fehlerquoten**. Ein Fall kann mehrere Hinweise auslösen. Alle Fälle mit Text und Wortindizes stehen in `reference-audit.json` und `reference-diagnostics.md`.

| Hinweis | Anzahl |
|---|---:|
""")
    lines.pop()
    issue_names = {
        "numeric_without_digit": "Numerisches Label ohne Ziffer",
        "quantity_prefix": "Vorangestelltes ›je‹ in einer Mengenangabe",
        "quantity_campaign_text": "Aktions- oder Preistext in einer Mengenangabe",
        "regular_price_marked_old": "Preis nach ›ohne PENNY App‹ als Altpreis markiert",
        "entity_not_fully_grouped": "Entity nicht vollständig einer Gruppe zugeordnet",
        "entity_crosses_groups": "Entity über mehrere Gruppen verteilt",
        "product_group_without_regular_price": "Produktgruppe ohne regulären Preis",
        "price_group_without_name": "Preisgruppe ohne auswertbaren Namen",
    }
    lines += [f"| {issue_names.get(code, code)} | {count} |" for code, count in sorted(audit["issue_counts"].items())]
    regular_price_cases = [row for row in audit["issues"] if row["code"] == "regular_price_marked_old"]
    if regular_price_cases:
        case = regular_price_cases[0]
        lines += _paragraphs(f"""

Ein konkreter Fall ist Seite **{case['page_id']}**, Wort {case['start']}: „{case['text']}“ nach „ohne PENNY App“ trägt OLD_PRICE. Hier wird ein regulärer Preis als Altpreis behandelt. Hat die zugehörige Gruppe keinen PRICE, fällt das Angebot aus der Referenzprojektion heraus. Eine inhaltlich passende Systemausgabe kann dann als False Positive gezählt werden. Dieser bekannte Referenzfehler bleibt im ausgewerteten Datenstand erhalten.
""")
    lines += _paragraphs("""
Die Hinweise werden für diesen Studienabschluss nicht nachannotiert. Unbestätigte Hinweise bleiben von dem konkret erkannten Referenzfehler getrennt. Eine bereinigte Fehlerquote und eine Leistung auf einer fehlerfreien Referenz lassen sich daraus nicht ableiten. Die offene Frage, welche Angaben zu einem Angebot gehören, bleibt eine Grenze der Messung.

## 7. Diskussion: Erkenntnisse, Betrieb und Grenzen

### 7.1 Was die Kombination der Verfahren zeigt

**Erkennung und Zuordnung sind getrennte Probleme.** Ein korrekt erkanntes Produkt und ein korrekt erkannter Preis ergeben erst dann einen nutzbaren Datensatz, wenn beide richtig verbunden werden. Die getrennten Messungen machen diesen Unterschied sichtbar. Der höhere beobachtete Wert des Paarmodells auf derselben Gold-Eingabe ist ein konkretes Ergebnis der zusätzlich gelernten Zuordnung.

**Komplexere Eingaben sind eine zu prüfende Hypothese.** Das Seitenbild kann beispielsweise Schriftbild und Preisgestaltung zugänglich machen. Ob die jeweilige Architektur diese Information für die Aufgabe nutzt, muss sich in den Messwerten zeigen. Unser Vergleich erlaubt eine Einordnung der fertigen Systeme, keine isolierte Ursache-Wirkungs-Aussage über eine einzelne Modalität.

**Eine lokale Pipeline ist als Gesamtsystem realisiert.** Ihr Nutzen liegt in der trainierten Verarbeitungskette und den auswertbaren strukturierten Ausgaben. Der Blackbox-Vergleich zeigt ihre Stellung innerhalb derselben begrenzten Aufgabe. Die dokumentierte Referenzqualität begrenzt die Genauigkeit dieser Einordnung.

### 7.2 Qualität, Kosten und Betriebsform

| Gesichtspunkt | Lokale trainierte Pipeline | LLM-Blackbox über API |
|---|---|---|
| Vorbereitung | Datensammlung, Trainingsannotation, Fine-Tuning und Pflege der Komponenten | Prompt und Schnittstellenintegration; im Projekt kein eigenes Training der Blackbox |
| Laufender Einsatz | Eigene Rechenressourcen, Speicher und Wartung; nach Bereitstellung der Gewichte keine LLM-Anfrage je Seite | Externer Dienst, Netzverbindung, Kontingente und gegebenenfalls nutzungsabhängige Gebühren |
| Kontrolle | Modellstand, Entity-Schema und Verarbeitungsschritte liegen im Projekt | Anbieter und bereitgestellter Modellstand beeinflussen Verfügbarkeit und Verhalten |
| Datenweg | Verarbeitung kann nach Einrichtung auf eigener Infrastruktur erfolgen | Seitenbilder werden zur Verarbeitung an den Dienst übertragen |
| Qualitätsnachweis | Mehrstufige Diagnose und derselbe Angebotsvergleich | Gemeinsamer Angebotsvergleich; keine direkt ausgegebenen Wortspans |

Die Kostenabwägung ist **qualitativ**. Ein akademischer Zugang kann direkte Gebühren reduzieren, macht Rechenleistung und Betreuung aber nicht ressourcenfrei. Ob sich der Trainings- und Wartungsaufwand gegenüber wiederholten API-Anfragen lohnt, hängt unter anderem von Nutzungsmenge, Hardware und Dienstkonditionen ab. Eine einheitlich gemessene Kostenrechnung liegt nicht vor. Aus den gespeicherten Antworten werden keine neuen Kosten- oder Laufzeitwerte abgeleitet; die Zeit nur einer Gruppierungsstufe belegt keinen Geschwindigkeitsvorteil der gesamten PDF-Verarbeitung.

### 7.3 Reichweite der Ergebnisse
""")
    lines += [f"- {item}" for item in study["limitations"]] + [""]
    lines += _paragraphs("""
Die fehlende unabhängige Doppelannotation und mehrdeutige Angebotsdefinition begrenzen die **Validität**, also wie gut die Messung die eigentlich interessierende Extraktionsqualität abbildet. **Reproduzierbarkeit** bedeutet dagegen, dass sich die Rechnung mit denselben Eingaben nachvollziehen lässt. Die Studie verbessert Letzteres durch gespeicherte Ausgaben, feste Regeln und Fingerabdrücke; dadurch verschwinden inhaltliche Referenzprobleme nicht. Neue Händler oder Wochen können zudem anders aussehen als die untersuchten Daten. Diese Übertragbarkeit wird hier nicht nachgewiesen.
""")
    lines += _requirements()
    lines += _paragraphs(f"""
## 9. Fazit und Ausblick

Magda verbindet mehrere IE-Techniken zu einem ausführbaren System: automatische Trainingsannotation, trainierte Text- und Dokumentmodelle, regelbasierte und gelernte Zuordnung sowie einen generativen Vergleichsarm. Die Untersuchung erklärt damit nicht nur einen Gesamtwert, sondern zeigt, an welcher Stufe Unterschiede entstehen und welche Art von Fehler die Bewertung beeinflusst.

Der gelernte Gruppierer erzielt auf denselben Goldentities höhere beobachtete Zuordnungswerte als die Heuristik. Die lokale Pipeline liefert auf der gemeinsamen Aufgabe aus Angebotsname und Preis einen Punktwert nahe dem Qwen-Vergleichslauf. Zugleich bleibt die exakte Abgrenzung von Textstellen und Angeboten ein zentrales Problem. {_comparison_conclusion(study)}

Der wissenschaftliche Beitrag liegt in der nachvollziehbaren Umsetzung, dem Vergleich und der begrenzten empirischen Einordnung. Der vereinbarte Umfang des 5-CP-Projekts endet mit der bestehenden Referenz und ihren dokumentierten Limitationen. Eine weitere Labelrunde ist kein verbleibender Arbeitsschritt.

Mögliche Folgestudien könnten die Wirkung alternativer Angebotsabgrenzungen untersuchen oder eine neue, bislang unberührte Prospektwoche auswerten. Weitere Modellverbesserungen würden zunächst anhand einer konkreten Hypothese auf Train/Dev entwickelt und als eigener Lauf gespeichert. Ein Gewinn nach Anpassung auf bereits betrachteten Testseiten wäre kein unabhängiger Nachweis.

## 10. Reproduzierbarkeit und technische Nachweise

Der folgende Befehl erzeugt Tabellen und Bericht aus vorhandenen Daten. Er verwendet gespeicherte Vorhersagen und Blackbox-Antworten, verändert keine Trainingslabels oder Gewichte und löst keine neue Labelrunde aus.

```bash
{command}
```

`study.json` enthält Zähler, Ausgaben, Intervalle, Vorlagencluster, Referenzhinweise und Laufmetadaten. Die Quelldateien der Blackbox-Antworten werden durch Hashes referenziert. Der Quellcodehash schließt lokale Änderungen ein; der Commit allein beschreibt bei uncommittierter Arbeit noch nicht die vollständige Fassung. `scripts/check_study_completion.py` prüft die unveränderten Messwerte und Referenzdateien gegenüber dem vorherigen Studienstand.

| Baustein | Nachweis im Repository |
|---|---|
| PDF-Verarbeitung und strukturierter Export | `src/magda/pipeline.py`, `src/magda/cli/extract_pdf.py` |
| BIO und Wortteilzuordnung | `src/magda/labels.py`, `src/magda/dataset.py` |
| Training und Vorhersage | `src/magda/cli/train.py`, `src/magda/predict.py` |
| Räumliche Heuristik | `src/magda/offers.py` |
| Paarmerkmale, Lernen und Gruppenbildung | `src/magda/offer_pairs.py`, `src/magda/offer_model.py`, `src/magda/offer_ilp.py` |
| SemEval- und Gold-Auswertung | `src/magda/semeval.py`, `src/magda/gold_evaluation.py` |
| Bootstrap und Studienrechnung | `src/magda/resampling.py`, `src/magda/evaluation_study.py` |
| Blackbox und Angebotsvergleich | `src/magda/blackbox.py`, `src/magda/blackbox_eval.py` |

- Quellcode-Commit: `{study['code']['git_revision']}`
- Quellcode-SHA256 einschließlich lokaler Änderungen: `{study['code']['source_sha256']}`
- Split-SHA256: `{study['split_sha256']}`
- Referenzinventar-SHA256: `{audit['reference_sha256']}`
- Paarmodell-SHA256: `{study['pair_checkpoint_sha256']}`

## Literatur

1. [Segura-Bedmar et al. (2013): SemEval-2013 Task 9](https://aclanthology.org/S13-2056/), Abschnitt 3.1: Entity-Bewertungsschemata.
2. [Dror et al. (2018): The Hitchhiker’s Guide to Testing Statistical Significance in NLP](https://aclanthology.org/P18-1128/): Einordnung statistischer Vergleiche.
3. [Bender & Friedman (2018): Data Statements for NLP](https://aclanthology.org/Q18-1041/): Datenherkunft und Geltungsbereich; relevant für die Dokumentation in Abschnitt 2 und 7.
4. [nervaluate: Implementierung der Entity-Metriken](https://github.com/MantisAI/nervaluate), verwendete Version 1.2.1.
5. [Chan et al. (2020): German’s Next Language Model](https://aclanthology.org/2020.coling-main.598/): GBERT.
6. [Conneau et al. (2020): Unsupervised Cross-lingual Representation Learning at Scale](https://aclanthology.org/2020.acl-main.747/): XLM-R.
7. [LiLT: A Simple yet Effective Language-Independent Layout Transformer for Structured Document Understanding (2022)](https://aclanthology.org/2022.acl-long.534/).
8. [Xu et al. (2021): LayoutXLM: Multimodal Pre-training for Multilingual Visually-rich Document Understanding](https://arxiv.org/abs/2104.08836).
""")
    if review_status.get("scores") is not None:
        score = review_status["scores"]["matching_schemes"]["strict"]
        lines += _paragraphs(f"""
## Anhang: Zusätzliche Kontrollannotation

Entity-Übereinstimmung Strict-F1: {number(score['f1'])}. Status des Abgleichs: `{review_status['status']}`. Dies ist Übereinstimmung zwischen getrennten Abgaben und keine gemessene Genauigkeit gegenüber einer fehlerfreien Referenz.
""")
    return "\n".join(lines).strip() + "\n"


def render_audit(audit):
    lines = ["# Diagnostischer Anhang zur bestehenden Referenz", "", audit["interpretation"], "",
             "Diese Hinweise dokumentieren Einschränkungen der ausgewerteten Referenz. "
             "Sie wurden nicht systematisch adjudiziert und führen in dieser Studie "
             "zu keiner weiteren Labelrunde. Die vorhandenen Labels und Gruppen bleiben "
             "unverändert. Die Liste ist keine bestätigte Fehlerzählung und keine Aufgabenliste.", ""]
    for issue in audit["issues"]:
        location = f"Wörter {issue['start']}–{issue['end']}" if "start" in issue else f"Gruppe {issue.get('group', '–')}"
        lines += [f"## {issue['page_id']} · {issue['code']} · {issue['id']}", "",
                  f"{location}. {issue['detail']}", "", issue.get("text", ""), "",
                  "Status: nicht adjudizierter Hinweis; bestehende Referenz unverändert ausgewertet.", ""]
    lines += ["## Gleicher Text mit verschiedenen Typen", "",
              "Kontext kann Unterschiede erklären. Alle Vorkommen stehen im JSON.", ""]
    lines += [f"- {row['text']}: {', '.join(row['labels'])}" for row in audit["text_label_conflicts"]]
    return "\n".join(lines) + "\n"
