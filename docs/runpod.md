# Training auf einer fremden GPU (RunPod)

Beide Modellvarianten laufen auch lokal. Auf einen Pod gehört das Training
aus einem einzigen Grund: **Arbeitsspeicher.** LayoutXLM bringt 368 Mio.
Parameter plus den detectron2-Backbone mit, und auf einer 8-GB-Maschine
landet das im Swap – die Kiste wird unbenutzbar, ohne dass das Training
nennenswert schneller fertig wäre.

Der Datensatz ist klein (rund 200 Seiten). Beide Varianten sind auf jeder
aktuellen GPU in Minuten durch. **Nimm die billigste Karte, die du bekommst**
(RTX A4000/A5000). Eine H100 rechnet dasselbe in derselben Minute und kostet
das Zehnfache.

## 1. Bündel bauen

```bash
magda bundle --labels-from sonnet-5
```

Ergebnis: `data/magda-training.tgz`, rund 25 MB. Darin stecken

- der Code im Stand von `HEAD` – **auch nicht gepushte Commits**, es wird
  `git ls-files` benutzt, kein `git clone`,
- die Labels des gewählten Modellordners,
- `data/splits/split.json` – ohne den würfelt der Pod einen eigenen Split
  und die Zahlen wären nicht mit den lokalen vergleichbar,
- die Seitenbilder, auf 224×224 vorskaliert,
- `bootstrap.sh`.

Die Bilder werden mit demselben Filter verkleinert, den
`LayoutLMv2ImageProcessor` ohnehin anwendet (bilinear, 224 px). Aus 390 MB
werden 20 MB, ohne dass sich am Modelleingang ein Pixel ändert.

## 2. Hochladen

Über RunPods eigenes Werkzeug (kein SSH-Schlüssel nötig):

```bash
runpodctl send data/magda-training.tgz     # gibt einen Code aus
```

Auf dem Pod:

```bash
runpodctl receive <code>
```

Alternativ per `scp`, wenn SSH eingerichtet ist.

## 3. Laufen lassen

```bash
mkdir magda && tar xzf magda-training.tgz -C magda && cd magda
bash bootstrap.sh
```

Das Skript installiert die Abhängigkeiten, übersetzt detectron2 (dauert ein
paar Minuten), trainiert beide Varianten, evaluiert auf dem Test-Split und
packt am Ende `ergebnisse.tgz`.

Schlägt die detectron2-Installation fehl, läuft GBERT trotzdem durch und nur
LayoutXLM wird übersprungen – das Skript bricht nicht ab.

## 4. Zurückholen

```bash
runpodctl send ergebnisse.tgz              # auf dem Pod
runpodctl receive <code>                   # zu Hause
tar xzf ergebnisse.tgz                     # legt data/eval und checkpoints/ ab
```

Danach zeigt die Evaluationsseite im Frontend beide Varianten.

## Was schiefgehen kann

- **`nvidia-smi` zeigt keine GPU** – dann trainiert PyTorch stillschweigend
  auf der CPU und du zahlst GPU-Stunden für nichts. Einmal prüfen:
  `python -c "import torch; print(torch.cuda.is_available())"`.
- **detectron2 braucht passende CUDA-Header.** Auf den offiziellen
  RunPod-PyTorch-Images ist das der Fall; auf minimalen Images nicht.
- **Der Pod löscht sich beim Beenden.** `ergebnisse.tgz` vorher herunterladen,
  sonst ist die Rechenzeit weg.
- **`data/splits/split.json` nicht überschreiben.** Der Split ist eingefroren,
  damit alle im Team auf denselben Testseiten messen.
