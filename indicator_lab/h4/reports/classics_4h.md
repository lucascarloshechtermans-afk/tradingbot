# Bekende swingstrategieën, 4H-bars, 1795 NASDAQ-aandelen, 2024-07-03 .. 2026-10-23

Regels zoals ze bekend zijn (long only), max 1 BUY per aandeel per 2 weken, liquiditeitsvloer, kosten 0,1%/kant + 0,1% slippage, rekening max 10 posities van 10%.

| strategie                                                                  | trades   | winrate   | gem. winst   | gem. verlies   | gem. trade   | PF   | hold (4H-bars)   | CAGR (10 pos.)   | max DD   |   Sharpe |
|:---------------------------------------------------------------------------|:---------|:----------|:-------------|:---------------|:-------------|:-----|:-----------------|:-----------------|:---------|---------:|
| 1 RSI(2) < 10 (Connors), uit: slot > SMA5                                  | 13183.0  | 58%       | 2.9%         | -4.3%          | -0.09%       | 0.95 | 4                | -27.5%           | -61.9%   |    -0.44 |
| 2 Cumulatieve RSI(2) 2 dagen < 35, uit: RSI(2) > 65                        | 13880.0  | 60%       | 3.0%         | -4.6%          | -0.09%       | 0.95 | 5                | -35.6%           | -69.5%   |    -0.68 |
| 3 Double 7s: 7-daags laagste slot, uit: 7-daags hoogste                    | 16641.0  | 63%       | 4.1%         | -6.9%          | 0.01%        | 1.00 | 9                | -14.5%           | -60.0%   |    -0.09 |
| 4 IBS < 0.2, uit: slot > high van gisteren                                 | 21003.0  | 59%       | 3.0%         | -5.0%          | -0.29%       | 0.86 | 5                | -46.8%           | -81.6%   |    -1.56 |
| 5 Bollinger: slot < onderband, uit: slot > middenband                      | 5282.0   | 65%       | 5.4%         | -8.6%          | 0.51%        | 1.17 | 15               | 6.6%             | -36.4%   |     0.33 |
| 6 Stochastic %K kruist 20 omhoog, uit: %K > 80                             | 7615.0   | 64%       | 6.3%         | -11.6%         | -0.04%       | 0.99 | 23               | 14.0%            | -57.7%   |     0.19 |
| 7 MACD kruist signaal omhoog, uit: kruist omlaag                           | 12276.0  | 33%       | 8.7%         | -4.9%          | -0.45%       | 0.86 | 11               | -27.6%           | -64.5%   |    -0.52 |
| 8 EMA 9/21 kruist omhoog, uit: kruist omlaag                               | 14820.0  | 27%       | 14.6%        | -6.9%          | -1.04%       | 0.79 | 22               | -41.1%           | -73.3%   |    -1.15 |
| 9 Supertrend(10,3) draait long, uit: draait short                          | 11963.0  | 33%       | 15.7%        | -10.0%         | -1.55%       | 0.77 | 31               | -43.5%           | -76.3%   |    -1.23 |
| 10 Donchian 20-breakout + sterke slot (v2), uit: 20-laagste of 4xATR-trail | 8390.0   | 33%       | 13.2%        | -7.5%          | -0.71%       | 0.86 | 24               | -26.2%           | -60.5%   |    -0.86 |
| SPY kopen en vasthouden                                                    | –        | –         | –            | –              | –            | –    | –                | 16.5%            | -18.8%   |     1.02 |
