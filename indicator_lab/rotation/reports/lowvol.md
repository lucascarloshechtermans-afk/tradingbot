# Lage-volatiliteitsanomalie (1237 holdout-aandelen, 2014-01-02 .. 2026-10-22)

Criterium (vooraf): Sharpe én MAR van de 30 rustigste aandelen boven SPY: **NIET GESLAAGD** (Sharpe 0.43 vs 0.72, MAR 0.18 vs 0.40).

| portefeuille                            | CAGR   | max DD   |   MAR |   Sharpe | volatiliteit/jaar   |
|:----------------------------------------|:-------|:---------|------:|---------:|:--------------------|
| 30 rustigste aandelen                   | 7.7%   | -42.3%   |  0.18 |     0.43 | 16%                 |
| 30 onrustigste aandelen                 | -11.1% | -94.4%   | -0.12 |    -0.15 | 39%                 |
| alle geschikte aandelen, gelijk gewogen | 3.7%   | -21.1%   |  0.18 |     0.21 | 11%                 |
| SPY kopen en vasthouden                 | 13.6%  | -33.7%   |  0.4  |     0.72 | 17%                 |

**Kanttekeningen (na het lezen toegevoegd):**
- De rij "alle geschikte aandelen" gebruikt een vaste verdeling over het maximale aantal geschikte aandelen; wanneer er
  minder geschikt zijn (vooral in de eerste jaren) staat het restant in T-bills. Die rij is dus te laag en alleen
  indicatief.
- Het verschil tussen de rustigste en de onrustigste 30 (+7,7% vs -11,1% per jaar) is het echte, robuuste signaal:
  beweeglijke aandelen waren als groep een slechte belegging, precies wat de literatuur zegt.
