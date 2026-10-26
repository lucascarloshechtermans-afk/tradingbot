# Klassieke swingstrategieën op grote aandelen — ontwikkeling (2878 aandelen, top 300 op dollarvolume per dag, 2015-01-01 .. 2024-10-21)

Rekening max 10 posities van 10%, lege kas in SPY zolang SPY > SMA200 (anders T-bills). Criterium (vooraf): Sharpe én MAR boven beide benchmarks, ook in beide tickerhelften.

| strategie                                                                  |   trades | winrate   | gem. trade   | in aandelen   | in SPY   | CAGR   | max DD   |   Sharpe |   MAR | Sharpe helften   | voldoet   |
|:---------------------------------------------------------------------------|---------:|:----------|:-------------|:--------------|:---------|:-------|:---------|---------:|------:|:-----------------|:----------|
| 1 RSI(2) < 10 (Connors), uit: slot > SMA5                                  |    17409 | 61%       | +0.05%       | 85%           | 10%      | -0.1%  | -48.4%   |     0    | -0    | -0.11 / -0.26    | nee       |
| 2 Cumulatieve RSI(2) 2 dagen < 35, uit: RSI(2) > 65                        |    17997 | 63%       | +0.14%       | 87%           | 8%       | -1.4%  | -53.5%   |    -0.05 | -0.03 | 0.02 / -0.11     | nee       |
| 3 Double 7s: 7-daags laagste slot, uit: 7-daags hoogste                    |    23153 | 66%       | +0.29%       | 96%           | 2%       | 9.7%   | -43.0%   |     0.45 |  0.23 | 0.31 / 0.39      | nee       |
| 4 IBS < 0.2, uit: slot > high van gisteren                                 |    34244 | 62%       | +0.09%       | 98%           | 1%       | -0.3%  | -52.1%   |     0.01 | -0    | 0.16 / -0.15     | nee       |
| 5 Bollinger: slot < onderband, uit: slot > middenband                      |     6582 | 69%       | +0.83%       | 83%           | 11%      | 3.3%   | -46.4%   |     0.18 |  0.07 | 0.32 / 0.24      | nee       |
| 6 Stochastic %K kruist 20 omhoog, uit: %K > 80                             |     8141 | 71%       | +0.87%       | 92%           | 4%       | 8.5%   | -39.1%   |     0.41 |  0.23 | 0.29 / 0.27      | nee       |
| 7 MACD kruist signaal omhoog, uit: kruist omlaag                           |    15869 | 36%       | +0.11%       | 96%           | 2%       | 1.5%   | -42.0%   |     0.08 |  0.04 | 0.37 / 0.13      | nee       |
| 8 EMA 9/21 kruist omhoog, uit: kruist omlaag                               |    14004 | 34%       | +0.97%       | 98%           | 1%       | 8.4%   | -39.7%   |     0.42 |  0.22 | 0.38 / 0.40      | nee       |
| 9 Supertrend(10,3) draait long, uit: draait short                          |    10544 | 42%       | +1.41%       | 97%           | 1%       | 5.4%   | -42.7%   |     0.28 |  0.13 | 0.24 / 0.52      | nee       |
| 10 Donchian 20-breakout + sterke slot (v2), uit: 20-laagste of 4xATR-trail |     8602 | 40%       | +0.88%       | 95%           | 2%       | 4.7%   | -30.2%   |     0.26 |  0.16 | -0.03 / 0.56     | nee       |

Benchmarks:

| strategie                               | CAGR   | max DD   |   Sharpe |   MAR |
|:----------------------------------------|:-------|:---------|---------:|------:|
| SPY kopen en vasthouden                 | 13.2%  | -33.7%   |     0.69 |  0.39 |
| SPY alleen boven SMA200, anders T-bills | 10.4%  | -18.1%   |     0.76 |  0.58 |
