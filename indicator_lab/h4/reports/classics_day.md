# Bekende swingstrategieën, dagbars, 24 NASDAQ-aandelen, 2015-01-01 .. 2024-10-21

Regels zoals ze bekend zijn (long only), max 1 BUY per aandeel per 2 weken, liquiditeitsvloer, kosten 0,1%/kant + 0,1% slippage, rekening max 10 posities van 10%.

| strategie                                                                  | trades   | winrate   | gem. winst   | gem. verlies   | gem. trade   | PF   | hold (dagen)   | CAGR (10 pos.)   | max DD   |   Sharpe |
|:---------------------------------------------------------------------------|:---------|:----------|:-------------|:---------------|:-------------|:-----|:---------------|:-----------------|:---------|---------:|
| 1 RSI(2) < 10 (Connors), uit: slot > SMA5                                  | 519.0    | 60%       | 3.4%         | -5.5%          | -0.17%       | 0.92 | 4              | -0.8%            | -16.4%   |    -0.08 |
| 2 Cumulatieve RSI(2) 2 dagen < 35, uit: RSI(2) > 65                        | 531.0    | 62%       | 3.4%         | -5.8%          | -0.08%       | 0.97 | 5              | -0.2%            | -14.9%   |     0.01 |
| 3 Double 7s: 7-daags laagste slot, uit: 7-daags hoogste                    | 627.0    | 64%       | 5.1%         | -8.9%          | 0.12%        | 1.04 | 9              | 0.5%             | -31.0%   |     0.1  |
| 4 IBS < 0.2, uit: slot > high van gisteren                                 | 967.0    | 62%       | 3.5%         | -6.1%          | -0.19%       | 0.92 | 5              | -1.8%            | -30.1%   |    -0.13 |
| 5 Bollinger: slot < onderband, uit: slot > middenband                      | 160.0    | 71%       | 6.2%         | -12.1%         | 0.93%        | 1.27 | 14             | 1.7%             | -15.2%   |     0.25 |
| 6 Stochastic %K kruist 20 omhoog, uit: %K > 80                             | 230.0    | 63%       | 6.6%         | -13.7%         | -0.79%       | 0.84 | 22             | -2.4%            | -37.3%   |    -0.12 |
| 7 MACD kruist signaal omhoog, uit: kruist omlaag                           | 433.0    | 34%       | 11.5%        | -4.7%          | 0.80%        | 1.26 | 11             | 3.4%             | -15.1%   |     0.42 |
| 8 EMA 9/21 kruist omhoog, uit: kruist omlaag                               | 443.0    | 31%       | 15.6%        | -7.8%          | -0.49%       | 0.91 | 24             | -2.7%            | -47.1%   |    -0.12 |
| 9 Supertrend(10,3) draait long, uit: draait short                          | 333.0    | 38%       | 18.0%        | -11.4%         | -0.21%       | 0.97 | 33             | -0.3%            | -33.8%   |     0.06 |
| 10 Donchian 20-breakout + sterke slot (v2), uit: 20-laagste of 4xATR-trail | 249.0    | 40%       | 15.9%        | -10.5%         | 0.04%        | 1.01 | 27             | -0.7%            | -28.8%   |    -0.01 |
| SPY kopen en vasthouden                                                    | –        | –         | –            | –              | –            | –    | –              | 13.2%            | -33.7%   |     0.79 |
