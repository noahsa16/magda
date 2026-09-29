"""Verdachtsfaelle in der LLM-Gruppierung: viele Preise, aber kaum Gruppen.

Kein Ersatz fuer eine Messung – nur ein Filter, der Seiten heraushebt, auf
denen die Zahl der Gruppen nicht zur Zahl der Preise passt. Beide Richtungen
sind gemeint: eine volle Seite mit einer Gruppe ist zu grob zusammengefasst,
deutlich mehr Gruppen als Preise deutet auf Fragmentierung.
"""
import json, pathlib, sys
from magda import config

groups_dir = pathlib.Path('data/offer_groups/claude-sonnet-5')
suspect = []
for f in sorted(groups_dir.glob('*.json')):
    payload = json.loads(f.read_text())
    labels = config.labeled_dir('sonnet-5') / f'{f.stem}.json'
    if not labels.is_file():
        continue
    tags = json.loads(labels.read_text())['tags']
    prices = sum(1 for t in tags if t in ('B-PRICE', 'B-APP_PRICE'))
    n = len(payload.get('groups', []))
    if prices >= 5 and n <= 1:
        suspect.append((f.stem, n, prices, 'zu grob'))
    elif n > prices + 3:
        suspect.append((f.stem, n, prices, 'fragmentiert?'))
print(f'{len(list(groups_dir.glob("*.json")))} Gruppierungen geprueft, {len(suspect)} verdaechtig')
for stem, n, prices, why in suspect:
    print(f'  {stem:<16} {n:>3} Gruppen / {prices:>3} Preise   {why}')
