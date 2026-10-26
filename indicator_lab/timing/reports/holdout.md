# Markttiming — holdout (eenmalig)

Gekozen variant (vooraf, op ontwikkeldata): **T5 volatiliteitsdoel 15%**. Beter dan kopen en vasthouden (MAR hoger én Sharpe minstens gelijk) in 2 van de 4 perioden: **NIET GESLAAGD** (nodig: 3 van 4).

## SPY 1993-02-01 .. 2011-12-30 — gekozen variant beter

| variant                               | CAGR   | max DD   |   MAR |   Sharpe | gem. belegd   |   wissels/jaar |
|:--------------------------------------|:-------|:---------|------:|---------:|:--------------|---------------:|
| kopen en vasthouden                   | 7.7%   | -55.2%   |  0.14 |     0.31 | 100%          |              0 |
| T1 SMA200                             | 7.0%   | -23.7%   |  0.3  |     0.36 | 67%           |              7 |
| T2 SMA200 met 2%-band                 | 8.9%   | -19.1%   |  0.47 |     0.5  | 66%           |              1 |
| T3 Faber 10-maands SMA                | 9.6%   | -21.0%   |  0.45 |     0.53 | 68%           |              1 |
| T4 absoluut momentum (12m vs T-bills) | 10.1%  | -19.0%   |  0.53 |     0.54 | 68%           |              0 |
| T5 volatiliteitsdoel 15%              | 6.8%   | -44.8%   |  0.15 |     0.32 | 85%           |              0 |
| T6 SMA200 x vol-doel                  | 6.8%   | -19.3%   |  0.35 |     0.38 | 62%           |              7 |
| T7 SMA200-band x vol-doel             | 8.1%   | -14.8%   |  0.55 |     0.49 | 61%           |              1 |

## ^GSPC 1960-01-04 .. 1992-12-31 — gekozen variant NIET beter

| variant                               | CAGR   | max DD   |   MAR |   Sharpe | gem. belegd   |   wissels/jaar |
|:--------------------------------------|:-------|:---------|------:|---------:|:--------------|---------------:|
| kopen en vasthouden                   | 6.2%   | -48.2%   |  0.13 |     0.05 | 100%          |              0 |
| T1 SMA200                             | 8.5%   | -17.5%   |  0.48 |     0.24 | 66%           |              5 |
| T2 SMA200 met 2%-band                 | 7.2%   | -34.2%   |  0.21 |     0.12 | 67%           |              1 |
| T3 Faber 10-maands SMA                | 7.2%   | -33.2%   |  0.22 |     0.12 | 65%           |              1 |
| T4 absoluut momentum (12m vs T-bills) | 6.7%   | -33.2%   |  0.2  |     0.07 | 56%           |              1 |
| T5 volatiliteitsdoel 15%              | 6.3%   | -40.1%   |  0.16 |     0.05 | 95%           |              0 |
| T6 SMA200 x vol-doel                  | 8.3%   | -16.7%   |  0.49 |     0.23 | 64%           |              5 |
| T7 SMA200-band x vol-doel             | 7.3%   | -26.6%   |  0.27 |     0.12 | 65%           |              1 |

## ^NDX 1987-01-02 .. 2011-12-30 — gekozen variant beter

| variant                               | CAGR   | max DD   |   MAR |   Sharpe | gem. belegd   |   wissels/jaar |
|:--------------------------------------|:-------|:---------|------:|---------:|:--------------|---------------:|
| kopen en vasthouden                   | 11.7%  | -82.9%   |  0.14 |     0.4  | 100%          |              0 |
| T1 SMA200                             | 10.5%  | -40.9%   |  0.26 |     0.41 | 71%           |              8 |
| T2 SMA200 met 2%-band                 | 11.0%  | -38.0%   |  0.29 |     0.43 | 71%           |              2 |
| T3 Faber 10-maands SMA                | 12.2%  | -39.9%   |  0.31 |     0.48 | 70%           |              1 |
| T4 absoluut momentum (12m vs T-bills) | 11.6%  | -46.7%   |  0.25 |     0.44 | 70%           |              1 |
| T5 volatiliteitsdoel 15%              | 11.4%  | -39.7%   |  0.29 |     0.52 | 71%           |              0 |
| T6 SMA200 x vol-doel                  | 7.9%   | -29.9%   |  0.27 |     0.35 | 55%           |              5 |
| T7 SMA200-band x vol-doel             | 8.2%   | -29.5%   |  0.28 |     0.37 | 55%           |              1 |

## SPY 2024-10-22 .. 2026-10-23 — gekozen variant NIET beter

| variant                               | CAGR   | max DD   |   MAR |   Sharpe | gem. belegd   |   wissels/jaar |
|:--------------------------------------|:-------|:---------|------:|---------:|:--------------|---------------:|
| kopen en vasthouden                   | 15.5%  | -18.8%   |  0.82 |     0.71 | 100%          |              0 |
| T1 SMA200                             | 9.5%   | -11.5%   |  0.82 |     0.5  | 89%           |              3 |
| T2 SMA200 met 2%-band                 | 8.7%   | -9.6%    |  0.91 |     0.43 | 90%           |              2 |
| T3 Faber 10-maands SMA                | 7.4%   | -10.0%   |  0.74 |     0.33 | 87%           |              2 |
| T4 absoluut momentum (12m vs T-bills) | 15.5%  | -18.8%   |  0.82 |     0.71 | 100%          |              0 |
| T5 volatiliteitsdoel 15%              | 11.1%  | -15.5%   |  0.72 |     0.55 | 94%           |              0 |
| T6 SMA200 x vol-doel                  | 8.8%   | -10.7%   |  0.83 |     0.45 | 87%           |              3 |
| T7 SMA200-band x vol-doel             | 7.7%   | -9.1%    |  0.85 |     0.36 | 88%           |              2 |
