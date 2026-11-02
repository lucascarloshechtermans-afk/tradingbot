# Swing v4.2 verbeteren — I1-I3 (kosten 0,5%/kant)

## Conclusie

1. **Geen van de drie filters maakt v4.2 aantoonbaar beter.** Zonder model (I1) is even goed als met model (DEV MAR
   0,47 vs 0,42; holdout-tickers 0,8% vs 0,3% per jaar; laatste 2 jaar iets slechter). De andere twee filters vielen
   op DEV af volgens de vooraf vastgelegde regel.
2. **Compressie leek op DEV een grote verbetering** (MAR 0,81, max daling -15%), **maar faalt op alle drie de
   holdout-cellen** (PF 0,52-0,82, verliesgevend). Een schoolvoorbeeld van overfitting: goed dat de regel hem tegenhield.
3. **Jouw plan blijft onder SPY:** DEV 11,2% vs 13,2%, holdout-tickers 4,6% vs 13,2%, laatste 2 jaar -2,6% / 2,7% vs 15,5%.
4. **Advies:** v4.2 laten zoals hij is; eventueel "Use quality model" uitzetten (eenvoudiger, even goed).


Regels: docstring van `indicator_lab/swing4/v42_improve.py` (vooraf gecommit). Keuze alleen op DEV; de holdout-cellen zijn al eerder gezien en worden alleen gerapporteerd.

## Keuze op DEV

| variant                               |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   | gehouden   |
|:--------------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|:-----------|
| I1 zonder model (regels + marktregel) |     2857 | 46.1%     | +3.57%       |      0.257 | 2.13 | 11.4%  | -24.8%   |  0.47 | 63%        |            |
| I2 + compressie                       |      810 | 46.0%     | +3.21%       |      0.294 | 2.05 | 12.4%  | -15.2%   |  0.81 | 49%        | nee        |
| I3 + SMA50 > SMA200                   |     2078 | 45.3%     | +3.37%       |      0.258 | 2.06 | 10.1%  | -24.3%   |  0.42 | 60%        | nee        |

## Alle cellen: v4.1 tegen de eindversie

**DEV (253, 2015-2024/10)**

| variant                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:----------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| v4.1 (met model)                  |     2778 | 45.7%     | +3.47%       |      0.251 | 2.11 | 10.6%  | -25.9%   |  0.42 | 62%        |          |
| v4.2+ = zonder model              |     2857 | 46.1%     | +3.57%       |      0.257 | 2.13 | 11.4%  | -24.8%   |  0.47 | 63%        |          |
| SPY kopen & houden (total return) |          |           |              |            |      | 13.2%  | -33.7%   |  0.39 | 100%       |     0.79 |

Jouw plan (1% risico, max 10%, vrij geld in SPY > SMA200):

| jouw plan            | CAGR   | max DD   |   MAR |   Sharpe |
|:---------------------|:-------|:---------|------:|---------:|
| v4.1                 | 10.9%  | -23.4%   |  0.47 |     0.82 |
| v4.2+ = zonder model | 11.2%  | -23.6%   |  0.48 |     0.84 |

**TICKER-holdout (84, 2015-2024/10)**

| variant                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:----------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| v4.1 (met model)                  |      974 | 42.0%     | +0.23%       |      0.031 | 1.08 | 0.3%   | -23.9%   |  0.01 | 50%        |          |
| v4.2+ = zonder model              |      990 | 42.2%     | +0.29%       |      0.036 | 1.09 | 0.8%   | -24.0%   |  0.04 | 51%        |          |
| SPY kopen & houden (total return) |          |           |              |            |      | 13.2%  | -33.7%   |  0.39 | 100%       |     0.79 |

Jouw plan (1% risico, max 10%, vrij geld in SPY > SMA200):

| jouw plan            | CAGR   | max DD   |   MAR |   Sharpe |
|:---------------------|:-------|:---------|------:|---------:|
| v4.1                 | 4.1%   | -24.0%   |  0.17 |     0.38 |
| v4.2+ = zonder model | 4.6%   | -23.7%   |  0.19 |     0.42 |

**TIME-holdout (253, 2024/10-nu)**

| variant                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:----------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| v4.1 (met model)                  |      568 | 37.7%     | +0.96%       |     -0.008 | 1.2  | -4.0%  | -23.7%   | -0.17 | 55%        |          |
| v4.2+ = zonder model              |      580 | 36.9%     | +0.75%       |     -0.019 | 1.15 | -5.5%  | -23.8%   | -0.23 | 55%        |          |
| SPY kopen & houden (total return) |          |           |              |            |      | 15.5%  | -18.8%   |  0.83 | 100%       |     0.95 |

Jouw plan (1% risico, max 10%, vrij geld in SPY > SMA200):

| jouw plan            | CAGR   | max DD   |   MAR |   Sharpe |
|:---------------------|:-------|:---------|------:|---------:|
| v4.1                 | -1.0%  | -17.8%   | -0.05 |    -0    |
| v4.2+ = zonder model | -2.6%  | -19.4%   | -0.13 |    -0.12 |

**TICKER+TIME (84, 2024/10-nu)**

| variant                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:----------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| v4.1 (met model)                  |      203 | 35.0%     | +0.55%       |     -0.029 | 1.14 | -0.1%  | -14.6%   | -0    | 48%        |          |
| v4.2+ = zonder model              |      204 | 34.8%     | +0.72%       |     -0.021 | 1.18 | -1.8%  | -16.7%   | -0.1  | 48%        |          |
| SPY kopen & houden (total return) |          |           |              |            |      | 15.5%  | -18.8%   |  0.83 | 100%       |     0.95 |

Jouw plan (1% risico, max 10%, vrij geld in SPY > SMA200):

| jouw plan            | CAGR   | max DD   |   MAR |   Sharpe |
|:---------------------|:-------|:---------|------:|---------:|
| v4.1                 | 3.3%   | -14.1%   |  0.24 |     0.32 |
| v4.2+ = zonder model | 2.7%   | -14.9%   |  0.19 |     0.27 |


## Nieuwe hypothese H1 (na de run, NIET vooraf gekozen): zonder model + compressiefilter

Op DEV viel dit filter af op de regel (gemiddelde per trade 3,21% < 3,57%), maar het had een veel hogere MAR (0,81 vs 0,47). Ter informatie op alle cellen; dit is geen bewijs (de holdout is al eerder gezien).

| cel                               |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   | jouw plan CAGR / DD   |
|:----------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|:----------------------|
| DEV (253, 2015-2024/10)           |      810 | 46.0%     | +3.21%       |      0.294 | 2.05 | 12.4%  | -15.2%   |  0.81 | 49%        | 14.2% / -19.2%        |
| TICKER-holdout (84, 2015-2024/10) |      284 | 39.4%     | -0.58%       |     -0.051 | 0.82 | -1.9%  | -25.3%   | -0.08 | 28%        | 5.4% / -26.4%         |
| TIME-holdout (253, 2024/10-nu)    |      123 | 23.6%     | -2.73%       |     -0.294 | 0.52 | -15.7% | -30.7%   | -0.51 | 33%        | -5.3% / -18.3%        |
| TICKER+TIME (84, 2024/10-nu)      |       46 | 34.8%     | -0.93%       |     -0.133 | 0.75 | -2.1%  | -8.3%    | -0.26 | 19%        | 6.2% / -13.6%         |

