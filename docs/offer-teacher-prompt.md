# Der Gruppierungs-Prompt des Teachers

`offer_teacher.PROMPT_VERSION` ist eine Nummer ohne Text — der Prompt, mit
dem `data/offer_groups/claude-sonnet-5/` entstand, lebte nur in der
Konversation. Damit ist die Referenz nicht reproduzierbar und ein zweiter
Lauf nicht vergleichbar. Diese Datei schließt die Lücke ab Version 2.

## Version 2 (29.08.2026)

Verwendet für die Zweitannotation `claude-opus-5` auf 26 Dev-Seiten, je
eine pro Duplikat-Cluster, für die Teacher-gegen-Teacher-Deckenmessung.

> **Was ein Angebot ist:**
>
> - Ein Angebot ist ein beworbenes Produkt mit allem, was preislich und
>   beschreibend dazugehört: Marke, Produktname, Menge, Preis,
>   Streichpreis, Grundpreis, Rabatt, App-Preis, Gültigkeit.
> - Maßgeblich ist die visuelle Kachel: Was in einem Rahmen, auf einer
>   gemeinsamen Hintergrundfläche oder unter einem gemeinsamen Produktfoto
>   steht, gehört zusammen.
> - **Größenvarianten eines Produkts bleiben ein Angebot**, auch wenn sie
>   mehrere Mengen und mehrere Preise haben („Pfanne: 20 cm 9.99 / 24 cm
>   14.99"). Ebenso Sortenvarianten mit gemeinsamem Preis.
> - Mehrere Produktnamen in einer Gruppe sind also erlaubt und kommen vor.
> - **Nicht jede Entity gehört zu einem Angebot.** Seitenkopf,
>   Kleingedrucktes („Abgabe nur in haushaltsüblichen Mengen"),
>   Öffnungszeiten, allgemeine Gültigkeitsangaben der ganzen Seite: solche
>   Entities werden weggelassen.
> - Achte besonders auf **Legendenlayouts**: nummerierte Produkte („④
>   Pflanztopf-Set") mit einer Preisliste an anderer Stelle der Seite. Dort
>   entscheidet die Nummer, nicht die Nähe.
> - Preise stehen bei Penny oft in einem gelben Kasten, der räumlich näher
>   am Nachbarangebot liegt als am eigenen Produktnamen. Geh nach der
>   Kachel, nicht nach dem kürzesten Abstand.

Dazu die Sperre, ohne die die Messung wertlos wäre: Der Zweit-Annotator
darf `data/offer_groups/claude-sonnet-5/` nicht ansehen, weder direkt noch
über `offers-teacher view` oder die Reports in `data/eval/`. Wer die erste
Gruppierung kennt, ankert daran, und die gemessene Übereinstimmung ist dann
eine Aussage über das Ankern.

## Zweite Lücke: die Version steht nicht in den Daten

`PROMPT_VERSION` ist eine Modulkonstante und nicht pro Lauf setzbar. Die mit
Version 2 erzeugten `claude-opus-5`-Dateien tragen deshalb
`prompt_version: 1`. Wer die Läufe auseinanderhalten will, geht über
`provenance.model`. Ein Feld, das die Version nennt und sie nicht kennt, ist
schlechter als keines — das gehört behoben, sobald jemand den Teacher
ohnehin anfasst.

## Einschränkung dieser Messung

Version 1 ist unbekannt. Die Zweitannotation verwendet also einen anderen
Prompt *und* ein anderes Modell — gemessen wird die Übereinstimmung zweier
Annotatoren, nicht der Modellunterschied allein. Für eine **Obergrenze** der
erreichbaren Übereinstimmung ist das konservativ: ein abweichender Prompt
senkt sie eher, als dass er sie hebt.
