# Pro-swingmethodes, 4H-bars, 1795 NASDAQ-aandelen, 2024-07-03 .. 2026-10-23

Max 1 BUY per aandeel per 2 weken, liquiditeitsvloer, kosten 0,1%/kant + 0,1% slippage, rekening max 10 posities van 10%, lege kas 0%. 'markt-uptrend' = alleen kopen als SPY gisteren boven SMA200 sloot.

| strategie                                                             | trades   | winrate   | gem. winst   | gem. verlies   | gem. trade   | PF   | hold (4H-bars)   | CAGR (10 pos.)   | max DD   |   Sharpe |
|:----------------------------------------------------------------------|:---------|:----------|:-------------|:---------------|:-------------|:-----|:-----------------|:-----------------|:---------|---------:|
| P1 Minervini trend template + VCP-breakout                            | 519.0    | 30%       | 18.4%        | -6.4%          | 0.99%        | 1.22 | 29               | 15.3%            | -18.7%   |     0.76 |
| P1 Minervini trend template + VCP-breakout + markt-uptrend            | 502.0    | 29%       | 17.9%        | -6.4%          | 0.73%        | 1.16 | 29               | 11.6%            | -17.1%   |     0.6  |
| P2 Qullamaggie momentum-breakout                                      | 559.0    | 23%       | 15.0%        | -5.1%          | -0.48%       | 0.88 | 6                | -10.0%           | -32.7%   |    -0.35 |
| P2 Qullamaggie momentum-breakout + markt-uptrend                      | 530.0    | 23%       | 14.7%        | -5.1%          | -0.50%       | 0.87 | 6                | -9.2%            | -32.6%   |    -0.32 |
| P3 Qullamaggie episodic pivot (gap >= 10%, 3x volume)                 | 712.0    | 22%       | 19.9%        | -7.7%          | -1.53%       | 0.75 | 5                | -16.8%           | -60.1%   |    -0.11 |
| P3 Qullamaggie episodic pivot (gap >= 10%, 3x volume) + markt-uptrend | 655.0    | 21%       | 17.7%        | -7.6%          | -2.21%       | 0.63 | 5                | -25.1%           | -67.8%   |    -0.32 |
| P4 Raschke Holy Grail (ADX > 30, pullback EMA20)                      | 2753.0   | 25%       | 10.4%        | -4.5%          | -0.73%       | 0.78 | 9                | -24.3%           | -61.2%   |    -0.53 |
| P4 Raschke Holy Grail (ADX > 30, pullback EMA20) + markt-uptrend      | 2644.0   | 25%       | 10.1%        | -4.4%          | -0.74%       | 0.77 | 9                | -31.2%           | -66.4%   |    -0.87 |
| P5 Raschke Turtle Soup (valse 20-bar-low-break)                       | 11162.0  | 38%       | 6.9%         | -4.9%          | -0.43%       | 0.86 | 5                | -60.1%           | -89.0%   |    -1.86 |
| P5 Raschke Turtle Soup (valse 20-bar-low-break) + markt-uptrend       | 10342.0  | 38%       | 6.8%         | -4.9%          | -0.46%       | 0.85 | 5                | -55.2%           | -86.2%   |    -1.8  |
| P6 Weinstein stage-2-breakout (30-weeks lijn)                         | 2251.0   | 23%       | 40.9%        | -11.2%         | 0.63%        | 1.07 | 60               | -25.9%           | -55.0%   |    -0.85 |
| P6 Weinstein stage-2-breakout (30-weeks lijn) + markt-uptrend         | 2216.0   | 22%       | 41.4%        | -11.2%         | 0.38%        | 1.04 | 59               | -24.8%           | -52.5%   |    -0.73 |
| P7 Pocket pivot (Morales & Kacher)                                    | 7499.0   | 26%       | 12.8%        | -4.9%          | -0.31%       | 0.91 | 22               | -24.0%           | -50.8%   |    -0.99 |
| P7 Pocket pivot (Morales & Kacher) + markt-uptrend                    | 7222.0   | 26%       | 12.2%        | -4.8%          | -0.48%       | 0.87 | 22               | -20.2%           | -45.8%   |    -0.86 |
| P8 Anchored-VWAP-pullback (Shannon)                                   | 4870.0   | 15%       | 17.9%        | -4.4%          | -0.95%       | 0.74 | 25               | -32.9%           | -65.5%   |    -1.37 |
| P8 Anchored-VWAP-pullback (Shannon) + markt-uptrend                   | 4419.0   | 14%       | 16.4%        | -4.3%          | -1.36%       | 0.63 | 23               | -30.6%           | -64.2%   |    -1.23 |
| P9 NR7-insidebar-breakout (Crabel)                                    | 6608.0   | 24%       | 9.0%         | -3.2%          | -0.33%       | 0.87 | 9                | -12.7%           | -45.8%   |    -0.37 |
| P9 NR7-insidebar-breakout (Crabel) + markt-uptrend                    | 6380.0   | 23%       | 8.9%         | -3.2%          | -0.35%       | 0.86 | 9                | -21.8%           | -53.3%   |    -0.8  |
| SPY kopen en vasthouden                                               | –        | –         | –            | –              | –            | –    | –                | 16.5%            | -18.8%   |     1.02 |
| SPY alleen boven SMA200 (anders cash 0%)                              | –        | –         | –            | –              | –            | –    | –                | 11.9%            | -10.0%   |     0.99 |
