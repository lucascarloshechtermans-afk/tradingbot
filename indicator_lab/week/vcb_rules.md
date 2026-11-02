# Volatility compression breakout (VCB) — vooraf vastgelegde regels

Vraag van de gebruiker: de "volatility compression breakout"-strategie backtesten. Dit bestand is gecommit vóór de
eerste run. Code: `indicator_lab/week/vcb.py`. Rapport: `results/vcb.md`.

## Strategie (dagbars, alleen long)
- **Compressie**: op de dag vóór het signaal is de Bollinger-bandbreedte (4 x stdev(20) / SMA20) kleiner dan of gelijk
  aan haar 20e percentiel van de voorgaande 252 dagen (de rustigste 20% van het jaar).
- **Uitbraak**: slot > hoogste hoog van de vorige 20 dagen.
- **V1** = compressie + uitbraak. **V2** = V1 + trendfilter (slot > SMA200 en SMA50 > SMA200; dat filter hielp de kale
  breakout op train in `results/donchian_filters.md`).
- Instap op de open van de volgende dag; één trade per aandeel.
- Uitstappen (zoals de Donchian-test): **DC** verkopen op de open na een slot onder het 20-daagse laag; **DC+10** +10% en
  eruit (limiet), anders DC. Max 250 dagen. Kosten 0,05% + $0,02 per kant.

## Data en vergelijking
- NASDAQ-aandelen, > $5, > $20M/dag, 2015-2022 train, 2023-2026 test; alleen aandelen die op 2026-10-23 genoteerd
  waren (survivorship bias).
- Vergeleken met: de kale 20-daagse breakout (zelfde uitstap), willekeurige aandelen (5 per signaal, zelfde dag),
  en als rekening (10 posities) met RND, SPY en QQQ (bootstrap 95%-intervallen). Niets wordt gekozen op de test.

## Nieuwe hypotheses (na het zien van resultaten; niet in de hoofdtabel)
_(nog geen)_
