# Post-earnings drift — onafhankelijke bevestiging (446 nooit gebruikte NYSE/AMEX-aandelen, publicaties 2013-01-01 .. 2026-07-15)

Vooraf vastgelegd (zie `confirm.py`). Alleen E1 en E2 worden beoordeeld.

| regel                                                       |   trades |   aandelen | winrate   | gem. 60d   | boven SPY   |    t | boven alle publicaties   | CAGR   | max DD   |   Sharpe |   MAR | oordeel       |
|:------------------------------------------------------------|---------:|-----------:|:----------|:-----------|:------------|-----:|:-------------------------|:-------|:---------|---------:|------:|:--------------|
| E1 winstverrassing >= +10%                                  |     3227 |        310 | 55%       | 2.75%      | -0.89%      | -2.9 | +0.43%                   | 11.7%  | -44.1%   |     0.53 |  0.27 | niet geslaagd |
| E2 koersreactie >= +5% t.o.v. SPY (en positieve verrassing) |     1528 |        260 | 57%       | 3.31%      | -0.38%      | -0.8 | +0.93%                   | 10.0%  | -46.7%   |     0.45 |  0.21 | niet geslaagd |
| E3 beide                                                    |     1073 |        243 | 58%       | 3.81%      | 0.10%       |  0.2 | +1.41%                   | 10.3%  | -45.6%   |     0.47 |  0.23 | –             |
| (alle publicaties, ter vergelijking)                        |     7568 |        343 | 54%       | 1.82%      | -1.31%      | -6.9 | +0.00%                   | 8.8%   | -44.3%   |     0.41 |  0.2  | –             |

Benchmarks:

| regel                                   | CAGR   | max DD   |   Sharpe |   MAR |
|:----------------------------------------|:-------|:---------|---------:|------:|
| SPY kopen en vasthouden                 | 14.9%  | -33.7%   |     0.81 |  0.44 |
| SPY alleen boven SMA200, anders T-bills | 12.1%  | -18.1%   |     0.88 |  0.67 |
