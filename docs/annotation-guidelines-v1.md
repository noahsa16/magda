# Magda: Regeln für die unabhängige Kontrollannotation

Version 1, 15.09.2026. Arbeitsgrundlage für die neue Kontrollannotation.
Die bestehenden Gold-Dateien werden damit nicht automatisch geändert.
Beide Personen lesen diese Fassung vor Beginn. Offene Fälle kommen in die
Seitennotizen und werden erst nach Abgabe der getrennten Originalstände besprochen.

## Aufgabe und Einheit

Annotiert wird aus dem Seitenbild auf den vorgegebenen PDF-Wörtern. Indizes
und Wortreihenfolge bleiben unverändert. Ein Span umfasst einen zusammenhängenden
Bereich von Wortindizes; sein Endindex ist exklusiv. Kein Wort trägt zwei Labels.
Grafiken und Logos ohne auswählbares PDF-Wort können nicht als Span annotiert
werden. Solche Fälle in den Notizen nennen; keine Texte oder Indizes erfinden.

## Entity-Regeln

| Label | Einschließen | Ausschließen / Abgrenzung |
|---|---|---|
| PRODUCT | Produktbezeichnung mit konkreter Sorte, Geschmack oder Variante | Herkunftsprosa und allgemeine Werbeversprechen; Marke als BRAND |
| BRAND | Im Textlayer vorhandener Markenname | Händlername als Seitenkopf, reine Bildlogos ohne Wortindex |
| PRICE | Aktueller regulärer Kaufpreis, auch ausdrücklich „ohne PENNY App“ | App-Preis und durchgestrichener früherer Preis |
| OLD_PRICE | Tatsächlich gestrichener Vergleichspreis oder UVP-Zahlenwert | Aktueller Preis ohne App; das Wort „UVP“ selbst |
| APP_PRICE | Preis, der ausdrücklich an App-Nutzung gebunden ist; Bildhinweise beachten | Regulärer Preis; „mit App“ selbst |
| QUANTITY | Kaufmenge mit Einheit oder Stückzahl | Vorangestelltes „je“, „kaufen“, „entspricht“, Preisangaben |
| UNIT_PRICE | Ganze Grundpreisangabe, z. B. „(1 kg = 4.76)“ | Mengenangabe allein, Packungspreis |
| DISCOUNT | Explizite Rabattangabe, z. B. „-33%“ | Aktionsüberschriften, reine Kaufaufforderung „2 kaufen“ |
| VALID | Gültigkeitsdatum oder -zeitraum des Angebots bzw. der Seite | Andere Zahlen wie Druckkennung und Seitennummer |

Bei Preisen zuerst die Bedeutung im Bild bestimmen. Die kleinere Zahl ist
nicht automatisch PRICE: APP_PRICE kann niedriger sein. Doppelt gedruckte
Preisangaben werden an beiden Positionen annotiert, jeweils nach ihrer Bedeutung.
„Aktion“, „UVP“ und App-Texte gehören nicht in einen Preis-Span.

Produktvarianten werden gemäß der bestehenden Teamentscheidung vom 30.07.2026
mitgenommen. Bei „A oder B“ endet der erste Produkt-Span vor „oder“; der zweite
beginnt danach. Satzzeichen innerhalb eines unteilbaren PDF-Wortes bleiben erhalten.

### Gebinde-Komposita: Vorschlag für eine einheitliche Entscheidung

Die bisherige Konvention ist an dieser Stelle offen. Vorschlag für den Abgleich:
Ein einzelnes Wort mit ausdrücklicher Menge und Einheit, etwa „250-g-Schale“,
„0,33-l-Dose“ oder „50-ml-Fläschchen“, wird vollständig QUANTITY. Dasselbe gilt
für „1-l-Sonderedition“. Ein Wort darf bei der Annotation nicht intern aufgeteilt
werden. „Familienpackung“ ohne Zahlenmenge wird nicht QUANTITY.

Beide Personen müssen sich vor der Kontrollannotation auf diese Regel oder
eine dokumentierte Alternative einigen. Eine Änderung erzeugt eine neue
Regelfassung und ein neues Prüfpaket; alte Urteile bleiben der alten Fassung zugeordnet.

### Mehrfachkäufe und Stückpreise

„2 Stück“ ist QUANTITY; „2 kaufen“ allein ist eine Aktionsbedingung und wird
in den Notizen festgehalten. Ein ausdrücklich ausgerechneter Preis je Stück
ist keine Menge. Ist er ein echter alternativ nutzbarer Einzelkaufpreis, wird
er PRICE; ist er nur aus dem Mehrfachkauf abgeleitet, den Fall notieren und
im Abgleich entscheiden. Die derzeitige Angebotsprojektion kann solche
Kaufbedingungen nicht vollständig ausdrücken. Diese Grenze wird im Bericht
genannt, statt unterschiedliche Kaufbedingungen still gleichzusetzen.

## Gruppierungsregeln

Alle Entities eines gemeinsamen Angebots erhalten dieselbe Angebotsnummer.
Eine Entity wird vollständig einer Gruppe zugeordnet. Die Nummer selbst
hat keine Bedeutung. Varianten mit gemeinsamem Preis bleiben gemeinsam,
sofern das Bild sie als ein Angebot zeigt. Unterschiedliche Preisvarianten
dürfen gemeinsam bleiben; die anschließende Projektion bildet je PRICE-Wert
einen Eintrag. Globale Seiten-Gültigkeit bleibt ohne Angebotszuordnung.

Eine reine Werbeseite kann leere Spans und Gruppen haben und trotzdem fertig
sein. Fehlende Textlayer-Wörter und unsichere Kaufbedingungen werden notiert.
Eine fehlende reguläre Preisangabe darf nicht durch Umbenennen eines App-Preises
„repariert“ werden.

## Unabhängigkeit und Abgabe

Jede Person nutzt ihre eigene Datei `review-a.html` bzw. `review-b.html`.
Während der Bearbeitung keine Goldlabels, Lehrerlabels, Modellausgaben oder
Abgabe der anderen Person öffnen. Frühere Einsicht ehrlich angeben. Der
Editor fragt dies beim Export ab; die Erklärung ist keine technische Garantie.

Beide unveränderten Originalabgaben aufbewahren. Das Auswertungsskript misst
Entity-Übereinstimmung und Wortgruppen-Übereinstimmung und erstellt eine Liste
der Unterschiede. Übereinstimmung ist keine Richtigkeit. Anschließend prüft
das Team Unterschiede und die zusätzliche regelbasierte Prüfliste am Bild.

Korrekturen an der Referenz brauchen Seite, alte/neue Annotation, Begründung,
prüfende Person und Zeitpunkt. Alle Fälle derselben geklärten Regel werden
systematisch geprüft. Modelle und Schwellen bleiben dabei eingefroren. Danach
neuen Referenzstand sichern und die vorhandenen Ausgaben erneut auswerten.
