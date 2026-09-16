# Blackbox gegen Handreferenz: Vorprüfung

**Historischer Zwischenstand.** Die offenen Abschlüsse sind inzwischen erledigt;
der vollständige Vergleich steht in [Blackbox gegen Gold](2026-09-15-blackbox-gold.md).
Die folgenden Befunde dokumentieren die Situation vor dem Abschluss.

Stand: 15.09.2026. Abgabe: `origin/gold`, Commit
`c606a17` (einschließlich der bereits dort vorgenommenen Span-Normalisierung
durch `scripts/merge_gold_spans.py`). Auswertungsbranch:
`codex/blackbox-gold-comparison`.

## Ergebnis

Die Abschlussmessung ist noch nicht freigegeben durch den Datenstand:
Alle 42 Seiten der eingefrorenen Vergleichsliste haben fertige Handspans
mit passenden Wortlisten-Hashes; 38 haben auch ladbare fertige Gruppen.
Zusätzlich ist eine als fertig markierte Gruppierung inhaltlich leer.

| Seite | Offener Punkt |
|---|---|
| `1364390_p15` | Handspans fertig und leer; Gruppendatei fehlt. Bewusst angebotsfreie Seite bestätigen und leere Gruppierung abschließen. |
| `1364390_p23` | Handspans fertig und leer; Gruppendatei fehlt. Bewusst angebotsfreie Seite bestätigen und leere Gruppierung abschließen. |
| `1364390_p25` | Vorhandene Gruppen stehen auf `in_progress`; menschlichen Abschluss bestätigen. |
| `1364420_p8` | Vorhandene Gruppen stehen auf `in_progress`; menschlichen Abschluss bestätigen. |
| `1364390_p3` | Gruppen stehen auf `done`, aber `groups: []`, trotz Produkt- und Preisspans. Im Seitenbild sind Angebote sichtbar; Gruppierung nachtragen. |

### Gegenprüfung nach erneutem Abruf

`git fetch origin` liefert weiterhin `c606a17` als Spitze von `origin/gold`.
Die Historie aller lokal verfügbaren Branches enthält keine spätere fertige
Fassung der betroffenen Gruppendateien.

- Die Seitenbilder von `1364390_p15` und `1364390_p23` zeigen tatsächlich
  reine Werbung ohne konkrete Preisangebote. Die leeren Handspans sind damit
  plausibel; es fehlen die ausdrücklich gespeicherten leeren Gruppendateien.
- `1364420_p8` war in `191ec9e` bereits fertig. `4ec9714` änderte nur Status,
  Annotator und Zeitstempel; die Gruppen blieben unverändert.
- `1364390_p25` war zunächst fertig markiert, enthielt aber sämtliche Wörter
  in einer einzigen Gruppe. `e2ca8e0` teilte diese in einzelne Gruppen auf
  und setzte den Status auf `in_progress`.
- `1364390_p3` wurde bereits in `d547f76` mit `groups: []` und `status: done`
  angelegt. In der verfügbaren Historie liegt keine nichtleere Fassung.

Zur Wiederholung der historischen Gegenprüfung:

```bash
git log --all --oneline -- gold/offers/1364390_p3.json \
  gold/offers/1364390_p15.json gold/offers/1364390_p23.json \
  gold/offers/1364390_p25.json gold/offers/1364420_p8.json
git show 4ec9714 -- gold/offers/1364420_p8.json
git show e2ca8e0 -- gold/offers/1364390_p25.json
git show d547f76:gold/offers/1364390_p3.json
```

Es wurden keine Annotationen verändert. Der vollständige Gemma-Replay-Aufruf
bricht vor der Berechnung mit „Handannotation unvollständig“ ab. Es gibt daher
keine neue Blackbox-F1 und keine verkleinerte Teilmessung.

## Bereits geprüft

- Gespeicherte Vorhersagen für GBERT, XLM-R, LiLT und LayoutXLM decken die
  Vergleichsliste ab und passen zu den Wortlisten.
- Der lokale Paarmodell-Checkpoint ist vorhanden.
- Die gespeicherten Gemma-, Qwen- und Mistral-Läufe enthalten dieselbe
  angeforderte Seitenmenge. Historisch fehlgeschlagene Antworten bleiben
  beim Replay als fehlende Ausgaben in der Bewertung: Gemma auf 5 Seiten,
  Mistral auf 3, Qwen auf keiner.
- 54 Tests für Blackbox-Matching, Gold-Replay, Entity-Goldbewertung und
  Gold-Lader/Gruppierung bestanden.

Die Vorprüfung lässt sich reproduzieren:

```bash
.venv/bin/python scripts/check_blackbox_gold.py \
  > data/eval/blackbox_gold_preflight_2026-09-15.json
.venv/bin/python -m pytest tests/test_blackbox_eval.py \
  tests/test_blackbox_eval_gold.py tests/test_gold_evaluation.py \
  tests/test_gold.py tests/test_offers_gold.py -q
```

## Nach Abschluss der offenen Gruppierungen

Aus dem Projektroot auf dem Auswertungsbranch ausführen:

```bash
for model in gemma-4-31b-it qwen3.6-35b-a3b mistral-medium-3.5-128b; do
  .venv/bin/magda blackbox-eval \
    --pages data/eval/test_cluster_pages.txt \
    --reference-groups gold --predictions layoutxlm --grouper pair-model \
    --blackbox-from "data/eval/blackbox_test_${model}_pair-model_ref-teacher.json"
done
```

Die Befehle benötigen keine API-Aufrufe. Es gelten das eingefrorene
`offer-price-v2`-Matching und die unveränderte Seitenliste. Primärmetrik ist
Angebots-F1 über Name und Aktionspreis; Zusatzfelder sind nicht eingeschlossen.
Details: `docs/evaluation-protocol.md`.
