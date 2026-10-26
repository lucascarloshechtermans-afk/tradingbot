# Relatieve-sterkte-rotatie — ontwikkeling (1667 NASDAQ-aandelen, 2015-01-01 .. 2024-10-21)

Elke 10 handelsdagen de N sterkste liquide aandelen, gelijk gewogen; vullen op de volgende open; 0,1%/kant + 0,1% slippage op kopen; lege kas in T-bills. Criterium (vooraf): Sharpe én MAR boven SPY, ook in beide tickerhelften.

| variant                                               | CAGR   | max DD   |   Sharpe |   MAR | posities   | winrate posities   | top-10 posities = % winst   | omzet/jaar   | Sharpe helften   | voldoet   |
|:------------------------------------------------------|:-------|:---------|---------:|------:|:-----------|:-------------------|:----------------------------|:-------------|:-----------------|:----------|
| 12-1 momentum, top 10                                 | -7.3%  | -76.5%   |     0.03 | -0.09 | 656.0      | 43%                | 25%                         | 15.6x        | 0.13 / 0.21      | nee       |
| 12-1 momentum, top 10, alleen SPY > SMA200            | -20.2% | -90.1%   |    -0.4  | -0.22 | 610.0      | 39%                | 29%                         | 14.3x        | -0.26 / -0.19    | nee       |
| 12-1 momentum, top 20                                 | 0.8%   | -76.5%   |     0.17 |  0.01 | 1172.0     | 47%                | 19%                         | 14.1x        | 0.27 / 0.35      | nee       |
| 12-1 momentum, top 20, alleen SPY > SMA200            | -11.9% | -81.2%   |    -0.25 | -0.15 | 1102.0     | 44%                | 22%                         | 12.9x        | -0.06 / -0.03    | nee       |
| IBD-RS, top 10                                        | -18.5% | -91.8%   |    -0.21 | -0.2  | 743.0      | 37%                | 34%                         | 17.0x        | -0.27 / 0.05     | nee       |
| IBD-RS, top 10, alleen SPY > SMA200                   | -21.8% | -92.8%   |    -0.36 | -0.23 | 692.0      | 36%                | 40%                         | 15.7x        | -0.43 / -0.16    | nee       |
| IBD-RS, top 20                                        | -12.1% | -86.2%   |    -0.16 | -0.14 | 1323.0     | 38%                | 29%                         | 15.2x        | -0.01 / 0.11     | nee       |
| IBD-RS, top 20, alleen SPY > SMA200                   | -17.0% | -86.4%   |    -0.37 | -0.2  | 1233.0     | 36%                | 32%                         | 14.0x        | -0.23 / -0.10    | nee       |
| SPY kopen en vasthouden                               | 13.2%  | -33.7%   |     0.69 |  0.39 | –          | –                  | –                           | –            | –                | –         |
| QQQ kopen en vasthouden                               | 18.3%  | -35.1%   |     0.8  |  0.52 | –          | –                  | –                           | –            | –                | –         |
| SPY alleen boven SMA200, anders T-bills               | 10.4%  | -18.1%   |     0.76 |  0.58 | –          | –                  | –                           | –            | –                | –         |
| gemiddeld liquide aandeel (gelijk gewogen, survivors) | 6.0%   | -48.8%   |     0.29 |  0.12 | –          | –                  | –                           | –            | –                | –         |
