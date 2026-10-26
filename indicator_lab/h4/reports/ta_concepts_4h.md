# TA-concepten, 4H-bars, 1795 NASDAQ-aandelen, 2024-07-03 .. 2026-10-23

GEX > 0 op 97% van de handelsdagen in deze periode. Max 1 BUY per aandeel per 2 weken, liquiditeitsvloer, kosten 0,1%/kant + 0,1% slippage, rekening max 10 posities van 10%.

| strategie                                                     | trades   | winrate   | gem. winst   | gem. verlies   | gem. trade   | PF   | hold (4H-bars)   | CAGR (10 pos.)   | max DD   |   Sharpe |
|:--------------------------------------------------------------|:---------|:----------|:-------------|:---------------|:-------------|:-----|:-----------------|:-----------------|:---------|---------:|
| A EMA-pullback (21>50>200, raakt EMA21)                       | 8080.0   | 25%       | 13.8%        | -4.6%          | -0.12%       | 0.97 | 19               | -13.2%           | -44.7%   |    -0.38 |
| A EMA-pullback (21>50>200, raakt EMA21) + GEX > 0             | 8041.0   | 24%       | 13.8%        | -4.6%          | -0.13%       | 0.96 | 19               | -13.1%           | -43.7%   |    -0.34 |
| B EMA21-reclaim (EMA50>EMA200)                                | 12284.0  | 26%       | 7.5%         | -3.0%          | -0.27%       | 0.88 | 8                | -23.5%           | -50.0%   |    -0.78 |
| B EMA21-reclaim (EMA50>EMA200) + GEX > 0                      | 12103.0  | 26%       | 7.4%         | -3.0%          | -0.32%       | 0.86 | 8                | -24.4%           | -52.4%   |    -0.84 |
| C Resistance-breakout (2x geraakt, 1.5x volume)               | 5653.0   | 25%       | 13.8%        | -6.4%          | -1.33%       | 0.72 | 11               | -47.2%           | -78.0%   |    -1.1  |
| C Resistance-breakout (2x geraakt, 1.5x volume) + GEX > 0     | 5572.0   | 25%       | 13.9%        | -6.3%          | -1.29%       | 0.73 | 11               | -46.0%           | -76.5%   |    -1.28 |
| D Support-retest na breakout                                  | 3173.0   | 26%       | 10.4%        | -4.8%          | -0.81%       | 0.77 | 10               | -31.6%           | -64.0%   |    -1.01 |
| D Support-retest na breakout + GEX > 0                        | 3125.0   | 26%       | 10.4%        | -4.8%          | -0.82%       | 0.77 | 10               | -34.1%           | -65.7%   |    -1.18 |
| E Marktstructuur: hogere bodem + break of structure           | 12693.0  | 29%       | 12.4%        | -6.2%          | -0.85%       | 0.81 | 17               | -43.6%           | -74.2%   |    -1.52 |
| E Marktstructuur: hogere bodem + break of structure + GEX > 0 | 12524.0  | 29%       | 12.2%        | -6.2%          | -0.92%       | 0.79 | 17               | -42.8%           | -74.8%   |    -1.57 |
| SPY kopen en vasthouden                                       | –        | –         | –            | –              | –            | –    | –                | 16.5%            | -18.8%   |     1.02 |
