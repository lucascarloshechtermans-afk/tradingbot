# Pro-swingmethodes, dagbars, 1667 NASDAQ-aandelen, 2015-01-01 .. 2024-10-21

Max 1 BUY per aandeel per 2 weken, liquiditeitsvloer, kosten 0,1%/kant + 0,1% slippage, rekening max 10 posities van 10%, lege kas 0%. 'markt-uptrend' = alleen kopen als SPY gisteren boven SMA200 sloot.

| strategie                                                             | trades   | winrate   | gem. winst   | gem. verlies   | gem. trade   | PF   | hold (dagen)   | CAGR (10 pos.)   | max DD   |   Sharpe |
|:----------------------------------------------------------------------|:---------|:----------|:-------------|:---------------|:-------------|:-----|:---------------|:-----------------|:---------|---------:|
| P1 Minervini trend template + VCP-breakout                            | 753.0    | 29%       | 13.4%        | -6.5%          | -0.71%       | 0.84 | 29             | -3.0%            | -34.1%   |    -0.15 |
| P1 Minervini trend template + VCP-breakout + markt-uptrend            | 704.0    | 29%       | 13.1%        | -6.5%          | -0.72%       | 0.84 | 29             | -3.2%            | -35.1%   |    -0.18 |
| P2 Qullamaggie momentum-breakout                                      | 1105.0   | 23%       | 11.2%        | -4.7%          | -1.03%       | 0.72 | 6              | -8.5%            | -58.5%   |    -0.62 |
| P2 Qullamaggie momentum-breakout + markt-uptrend                      | 967.0    | 22%       | 10.8%        | -4.7%          | -1.28%       | 0.65 | 6              | -9.7%            | -63.8%   |    -0.8  |
| P3 Qullamaggie episodic pivot (gap >= 10%, 3x volume)                 | 965.0    | 24%       | 17.5%        | -7.4%          | -1.35%       | 0.76 | 6              | -9.0%            | -66.9%   |    -0.37 |
| P3 Qullamaggie episodic pivot (gap >= 10%, 3x volume) + markt-uptrend | 810.0    | 23%       | 16.1%        | -7.2%          | -1.98%       | 0.65 | 6              | -12.0%           | -76.2%   |    -0.67 |
| P4 Raschke Holy Grail (ADX > 30, pullback EMA20)                      | 3857.0   | 27%       | 11.9%        | -5.0%          | -0.47%       | 0.87 | 10             | -9.5%            | -68.9%   |    -0.32 |
| P4 Raschke Holy Grail (ADX > 30, pullback EMA20) + markt-uptrend      | 3504.0   | 27%       | 11.8%        | -4.8%          | -0.35%       | 0.90 | 10             | -7.6%            | -66.7%   |    -0.28 |
| P5 Raschke Turtle Soup (valse 20-bar-low-break)                       | 16089.0  | 41%       | 6.9%         | -5.2%          | -0.27%       | 0.91 | 4              | -30.6%           | -97.3%   |    -1.09 |
| P5 Raschke Turtle Soup (valse 20-bar-low-break) + markt-uptrend       | 12632.0  | 41%       | 6.5%         | -5.0%          | -0.36%       | 0.88 | 5              | -28.0%           | -96.3%   |    -1.25 |
| P6 Weinstein stage-2-breakout (30-weeks lijn)                         | 2881.0   | 26%       | 33.9%        | -12.0%         | 0.14%        | 1.02 | 68             | -2.8%            | -51.1%   |     0    |
| P6 Weinstein stage-2-breakout (30-weeks lijn) + markt-uptrend         | 2710.0   | 26%       | 33.3%        | -11.8%         | 0.10%        | 1.01 | 68             | -1.9%            | -64.3%   |     0.02 |
| P7 Pocket pivot (Morales & Kacher)                                    | 11267.0  | 28%       | 13.5%        | -5.3%          | -0.01%       | 1.00 | 23             | 1.5%             | -47.2%   |     0.17 |
| P7 Pocket pivot (Morales & Kacher) + markt-uptrend                    | 10185.0  | 28%       | 13.6%        | -5.2%          | 0.12%        | 1.03 | 23             | 4.4%             | -44.5%   |     0.32 |
| P8 Anchored-VWAP-pullback (Shannon)                                   | 6509.0   | 17%       | 24.3%        | -4.9%          | -0.01%       | 1.00 | 30             | -5.2%            | -70.3%   |    -0.12 |
| P8 Anchored-VWAP-pullback (Shannon) + markt-uptrend                   | 5020.0   | 15%       | 20.8%        | -4.8%          | -0.89%       | 0.78 | 27             | -10.3%           | -79.3%   |    -0.48 |
| P9 NR7-insidebar-breakout (Crabel)                                    | 6744.0   | 24%       | 9.9%         | -3.4%          | -0.24%       | 0.91 | 9              | -2.3%            | -54.2%   |    -0.01 |
| P9 NR7-insidebar-breakout (Crabel) + markt-uptrend                    | 6257.0   | 23%       | 9.6%         | -3.3%          | -0.29%       | 0.89 | 9              | -4.4%            | -55.6%   |    -0.15 |
| SPY kopen en vasthouden                                               | –        | –         | –            | –              | –            | –    | –              | 13.2%            | -33.7%   |     0.79 |
| SPY alleen boven SMA200 (anders cash 0%)                              | –        | –         | –            | –              | –            | –    | –              | 10.1%            | -19.8%   |     0.88 |
