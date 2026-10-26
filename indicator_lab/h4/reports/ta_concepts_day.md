# TA-concepten, dagbars, 1667 NASDAQ-aandelen, 2015-01-01 .. 2024-10-21

GEX > 0 op 89% van de handelsdagen in deze periode. Max 1 BUY per aandeel per 2 weken, liquiditeitsvloer, kosten 0,1%/kant + 0,1% slippage, rekening max 10 posities van 10%.

| strategie                                                     | trades   | winrate   | gem. winst   | gem. verlies   | gem. trade   | PF   | hold (dagen)   | CAGR (10 pos.)   | max DD   |   Sharpe |
|:--------------------------------------------------------------|:---------|:----------|:-------------|:---------------|:-------------|:-----|:---------------|:-----------------|:---------|---------:|
| A EMA-pullback (21>50>200, raakt EMA21)                       | 14420.0  | 25%       | 15.2%        | -4.8%          | 0.26%        | 1.07 | 19             | -4.4%            | -62.5%   |    -0.1  |
| A EMA-pullback (21>50>200, raakt EMA21) + GEX > 0             | 13695.0  | 25%       | 15.2%        | -4.8%          | 0.27%        | 1.08 | 19             | -0.9%            | -60.2%   |     0.06 |
| B EMA21-reclaim (EMA50>EMA200)                                | 25397.0  | 27%       | 7.9%         | -3.1%          | -0.13%       | 0.94 | 8              | -5.2%            | -72.7%   |    -0.13 |
| B EMA21-reclaim (EMA50>EMA200) + GEX > 0                      | 23188.0  | 27%       | 7.7%         | -3.0%          | -0.12%       | 0.94 | 8              | -2.3%            | -65.4%   |    -0.01 |
| C Resistance-breakout (2x geraakt, 1.5x volume)               | 7187.0   | 30%       | 12.2%        | -6.2%          | -0.79%       | 0.82 | 13             | -11.5%           | -79.0%   |    -0.35 |
| C Resistance-breakout (2x geraakt, 1.5x volume) + GEX > 0     | 6745.0   | 30%       | 12.2%        | -6.2%          | -0.74%       | 0.83 | 13             | -10.0%           | -76.5%   |    -0.31 |
| D Support-retest na breakout                                  | 4267.0   | 29%       | 10.0%        | -5.0%          | -0.63%       | 0.82 | 11             | -13.0%           | -80.4%   |    -0.55 |
| D Support-retest na breakout + GEX > 0                        | 3875.0   | 29%       | 9.9%         | -5.0%          | -0.68%       | 0.81 | 11             | -10.2%           | -75.9%   |    -0.43 |
| E Marktstructuur: hogere bodem + break of structure           | 19747.0  | 32%       | 13.4%        | -6.7%          | -0.33%       | 0.93 | 18             | -8.3%            | -76.8%   |    -0.24 |
| E Marktstructuur: hogere bodem + break of structure + GEX > 0 | 18959.0  | 32%       | 13.3%        | -6.7%          | -0.35%       | 0.92 | 18             | -5.3%            | -77.1%   |    -0.12 |
| SPY kopen en vasthouden                                       | –        | –         | –            | –              | –            | –    | –              | 13.2%            | -33.7%   |     0.79 |
