# Donchian 20-breakout met filters tegen valse signalen (NASDAQ, dagbars) — vooraf vastgelegde regels

Aanleiding: in `results/nasdaq_donchian.md` was de kale breakout per trade niet beter dan willekeurig (veel valse
uitbraken). Vraag van de gebruiker: minder valse signalen, op de daggrafiek. Dit bestand is gecommit vóór de eerste run.
Code: `indicator_lab/week/donchian_filters.py`. Rapport: `results/donchian_filters.md`.

## Basis (ongewijzigd)
Slot > hoogste hoog van de vorige 20 dagen; instap volgende open; één trade per aandeel; universum: NASDAQ, > $5,
> $20M/dag; 2015-2022 train, 2023-2026 test; kosten 0,05% + $0,02 per kant. Uitstappen DC (verkopen na een slot onder het
20-daagse laag) en DC+10 (+10% en eruit, anders DC).

## Filters (elk één regel op de signaaldag, waarden vooraf vast)
- **F1 trend**: slot > SMA200 en SMA50 > SMA200.
- **F2 volume**: volume >= 1,5 x het gemiddelde volume van de vorige 50 dagen.
- **F3 sterk slot**: slot in de bovenste 30% van de dagrange (IBS >= 0,7).
- **F4 markt**: QQQ sluit boven zijn SMA200.
- **F5 niet te ver**: slot hooguit 2 x ATR(14) boven het 20-daagse hoog (geen uitbraak die al te ver is doorgeschoten).
- Ter vergelijking: **jouw v4.1** (= breakout + F1-achtige trend + F3 + kwaliteitsmodel + SPY-regel), op dezelfde
  NASDAQ-aandelen.

## Keuze en oordeel
- "Valse signalen" = trades die met verlies sluiten (1 - winrate); daarnaast gemiddeld per trade en het verschil met
  willekeurige aandelen (5 per signaal, zelfde dag, zelfde uitstap, bootstrap over weken).
- Op **train (2015-2022)** wordt elk filter apart gemeten met uitstap DC. Een filter wordt gehouden als het verschil per
  trade met random op train hoger is dan bij de basis en er minstens 25% van de basistrades overblijft. De
  **combinatie** van de gehouden filters is de eindversie.
- Op **test (2023-2026)** wordt de eindversie één keer gemeten (beide uitstappen), plus als rekening (10 posities) tegen
  RND, SPY en QQQ. "Aantoonbaar beter" alleen als het hele 95%-interval boven 0 ligt.

## Nieuwe hypotheses (na het zien van resultaten; niet in de hoofdtabel)
_(nog geen)_
