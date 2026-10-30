# Jouw strategie "support + EMA-tap + lage RSI" — vooraf vastgelegde regels

Jouw beschrijving: wachten tot de koers een support-zone raakt; dan een daily close boven die zone; er moet een EMA-tap
zijn boven de support-zone waar de koers doorheen breekt, liefst een hoge EMA (50 / 100 / 200); de RSI moet laag zijn.

Dit bestand is gecommit vóór de eerste run. Na het zien van de testresultaten worden de regels niet meer veranderd.
Code: `indicator_lab/week/support_ema.py`. Rapport: `results/support_ema.md`.

## 1. Vertaling naar exacte regels (beslist op het slot van dag t, dagbars)
- **Support-zone**: de dichtstbijzijnde support onder het slot uit `indicator_lab/sr.py` (point in time: pivots tellen
  pas mee als ze bevestigd zijn) met sterkte >= 2 (dus minstens twee aanrakingen of het 52-weekse hoog, geen losse
  ronde getallen). Zone = [onderkant `sup_lo`, bovenkant = `sup` + (`sup` - `sup_lo`)] (sr.py bewaart het midden en
  de onderkant van de zone).
- **Zone geraakt**: de laagste koers van dag t-2 .. t komt in of onder de bovenkant van de zone.
- **Daily close boven de zone**: slot van dag t > bovenkant van de zone.
- **EMA-tap boven de zone met doorbraak**: voor minstens één EMA uit de set geldt op dag t: EMA > bovenkant van de zone,
  laag van dag t <= EMA en slot van dag t > EMA (de koers tikt de EMA aan en sluit erboven).
  - E1: EMA 50, 100 of 200.   E2: alleen EMA 100 of 200 ("liefst een hoge").
- **RSI laag**: de laagste RSI(14) (Wilder) van dag t-4 .. t is <= 30 / 35 / 40 (drie varianten; jij noemde geen getal).
- **Instap**: de open van dag t+1.
- **Stop**: onder de support-zone (`mfe.std_stop` met de zone-onderkant: onderkant - 0,25 ATR, minstens 1 ATR,
  hooguit 8% onder de instap).

## 2. Uitstap (jij noemde er geen; daarom de drie uit de exit-test, `exit_test_rules.md`)
- (a) eruit bij +10%, anders vrijdag bij het slot (max 3 nieuwe posities per week);
- (b) eruit bij +20%, anders na 20 handelsdagen bij het slot;
- (c) trailing stop 2 x ATR(14) onder het hoogste slot sinds instap, max 60 handelsdagen.
- Rekening: max 3 posities tegelijk, elk 1/3 van de rekening; instappen op elke dag zodra er een plek vrij is
  (modus M2 "doorlopend"); bij meer signalen dan plekken op één dag een willekeurige keuze (20 runs, gemiddeld).
- Kosten: 0,05% + $0,02 per kant.

## 3. Universum, data, controles
- Twee universa op de signaaldag: **U4** = slot > $5, 50-daagse dollaromzet > $20M, ADR(20) > 4% (zelfde als de
  vorige tests) en **UL** = slot > $5, dollaromzet > $20M (alle liquide aandelen, geen ADR-eis).
- Data: Swing 20/21-cache 2015-01 .. 2026-10-23, alleen aandelen die op 2026-10-23 genoteerd waren (geen gedelistte
  aandelen: survivorship bias).
- **RND-controle** per universum en exit: willekeurig aandeel uit hetzelfde universum op dezelfde manier (elke dag een
  vaste willekeurige steekproef van max. 60 aandelen uit het universum, waaruit de vrije plekken willekeurig gevuld
  worden), instap volgende open, stop onder de dichtstbijzijnde support, dezelfde exit.
- **SPY** kopen en vasthouden (dividend-gecorrigeerd) in dezelfde weken.

## 4. Train / test en statistiek
- Varianten: 2 universa x 2 EMA-sets x 3 RSI-grenzen x 3 exits = 36 (+ 6 RND-controles).
- Train = weken t/m 2022-12-31: per universum x exit wordt de variant (EMA-set, RSI-grens) met het hoogste gemiddelde
  weekrendement gekozen (★). Test = 2023-01 .. 2026-10: alleen rapporteren, alle varianten getoond.
- Per testweek het verschil met RND (zelfde universum en exit) en met SPY; gemiddeld verschil met 95%-interval uit een
  moving-block bootstrap (blokken van 4 weken, 10.000 trekkingen). "Beter dan random / SPY" alleen als het hele
  interval boven 0 ligt.
- Daarnaast per variant de trades zonder rekening-beperking (elk signaal): aantal, winrate, gemiddeld per trade, en
  hetzelfde voor willekeurige instappen op dezelfde dagen in hetzelfde universum.
- Geen advies om (papier) te traden, tenzij een variant in de test aantoonbaar beter is dan SPY.

## Nieuwe hypotheses (na het zien van resultaten; niet in de hoofdtabel)
_(nog geen)_
