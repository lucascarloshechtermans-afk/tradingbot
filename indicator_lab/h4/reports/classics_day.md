# Bekende swingstrategieën, dagbars, 1667 NASDAQ-aandelen, 2015-01-01 .. 2024-10-21

Regels zoals ze bekend zijn (long only), max 1 BUY per aandeel per 2 weken, liquiditeitsvloer, kosten 0,1%/kant + 0,1% slippage, rekening max 10 posities van 10%.

| strategie                                                                  | trades   | winrate   | gem. winst   | gem. verlies   | gem. trade   | PF   | hold (dagen)   | CAGR (10 pos.)   | max DD   |   Sharpe |
|:---------------------------------------------------------------------------|:---------|:----------|:-------------|:---------------|:-------------|:-----|:---------------|:-----------------|:---------|---------:|
| 1 RSI(2) < 10 (Connors), uit: slot > SMA5                                  | 25005.0  | 60%       | 3.2%         | -4.9%          | -0.03%       | 0.99 | 4              | -10.6%           | -78.7%   |    -0.32 |
| 2 Cumulatieve RSI(2) 2 dagen < 35, uit: RSI(2) > 65                        | 25907.0  | 62%       | 3.3%         | -5.3%          | 0.04%        | 1.02 | 5              | -9.4%            | -75.2%   |    -0.24 |
| 3 Double 7s: 7-daags laagste slot, uit: 7-daags hoogste                    | 32718.0  | 64%       | 4.3%         | -7.2%          | 0.11%        | 1.04 | 9              | 1.3%             | -57.7%   |     0.18 |
| 4 IBS < 0.2, uit: slot > high van gisteren                                 | 47905.0  | 61%       | 3.3%         | -5.3%          | -0.03%       | 0.98 | 5              | -7.1%            | -71.0%   |    -0.13 |
| 5 Bollinger: slot < onderband, uit: slot > middenband                      | 8821.0   | 67%       | 5.4%         | -9.0%          | 0.69%        | 1.23 | 14             | -3.6%            | -53.3%   |    -0.01 |
| 6 Stochastic %K kruist 20 omhoog, uit: %K > 80                             | 11517.0  | 69%       | 6.5%         | -12.0%         | 0.68%        | 1.18 | 21             | 4.8%             | -61.1%   |     0.31 |
| 7 MACD kruist signaal omhoog, uit: kruist omlaag                           | 22279.0  | 35%       | 9.0%         | -5.0%          | -0.18%       | 0.95 | 11             | -6.4%            | -71.3%   |    -0.13 |
| 8 EMA 9/21 kruist omhoog, uit: kruist omlaag                               | 22267.0  | 30%       | 16.0%        | -6.9%          | -0.04%       | 0.99 | 23             | -9.1%            | -77.5%   |    -0.28 |
| 9 Supertrend(10,3) draait long, uit: draait short                          | 15371.0  | 38%       | 17.4%        | -10.2%         | 0.20%        | 1.03 | 35             | -6.7%            | -76.5%   |    -0.14 |
| 10 Donchian 20-breakout + sterke slot (v2), uit: 20-laagste of 4xATR-trail | 12363.0  | 36%       | 15.0%        | -8.4%          | 0.14%        | 1.03 | 28             | -6.7%            | -63.7%   |    -0.2  |
| SPY kopen en vasthouden                                                    | –        | –         | –            | –              | –            | –    | –              | 13.2%            | -33.7%   |     0.79 |
