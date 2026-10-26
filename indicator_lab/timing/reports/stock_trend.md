# Trendregel per aandeel (395 NYSE/AMEX-aandelen, 2013-01-02 .. 2026-10-23)

Criterium (vooraf): mediane max daling <= 0,75 x vasthouden én hogere MAR op >= 60% van de aandelen.

- **aandeel > SMA200: NIET GESLAAGD** (mediane max daling 0.80 x die van vasthouden; hogere MAR op 41% van de aandelen)
- **aandeel > SMA200 en SPY > SMA200: NIET GESLAAGD** (mediane max daling 0.76 x die van vasthouden; hogere MAR op 42% van de aandelen)

## Per aandeel

| regel                            |   aandelen | mediaan CAGR   | mediaan max DD   | hogere MAR dan vasthouden   |
|:---------------------------------|-----------:|:---------------|:-----------------|:----------------------------|
| kopen en vasthouden              |        395 | 5.3%           | -74%             | –                           |
| aandeel > SMA200                 |        395 | 2.0%           | -59%             | 41% van de aandelen         |
| aandeel > SMA200 en SPY > SMA200 |        395 | 2.0%           | -56%             | 42% van de aandelen         |

## Portefeuille van alle aandelen

| gelijk gewogen portefeuille      | CAGR   | max DD   |   MAR |   Sharpe |
|:---------------------------------|:-------|:---------|------:|---------:|
| kopen en vasthouden              | 29.1%  | -44.0%   |  0.66 |     0.69 |
| aandeel > SMA200                 | 6.7%   | -17.2%   |  0.39 |     0.59 |
| aandeel > SMA200 en SPY > SMA200 | 6.1%   | -16.2%   |  0.38 |     0.54 |
| SPY kopen en vasthouden          | 14.8%  | -33.7%   |  0.44 |     0.8  |

**Let op (na het lezen toegevoegd):** de gelijk-gewogen portefeuille wordt dagelijks herbalanceerd over alle aandelen,
ook kleine met ruizige koersen; dat geeft een kunstmatige "herbalanceringswinst" (zie het eerdere 65%-artefact in
`h4/reports/nasdaq_daily.md`). De 29,1% van "kopen en vasthouden" is daarom niet betrouwbaar. Het oordeel steunt op
de mediane cijfers per aandeel.
