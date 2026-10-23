# Swing v5 — phase 0: foundation and bugs (development data only)

Development data: 337 tickers (earlier development universe + the spent v4 holdout), entries 2015-01-01 .. 2024-10-21; every series is cut before 2024-10-22 and the 155 v5-holdout tickers are refused. Costs: 0.1% per side + 0.1% extra slippage on every breakout entry. Portfolio: max 10 positions of 10%; idle capital in SPY while SPY closed above its SMA200 the day before (switches cost 0.1%), otherwise in T-bills (^IRX); mean of 20 random orders of same-day signals.

## 1. The complete system vs SPY (development period)

| system | CAGR | max DD | MAR (range over orders) | Sharpe (excess) | beta | alpha / yr (t) | IR vs SPY | tracking error | in breakouts | in SPY (parked) |
|---|---|---|---|---|---|---|---|---|---|---|
| v4 complete (breakouts + SPY parking + regime) | 15.7% | -26.6% | 0.59 (0.51–0.72) | 0.89 | 0.61 | +6.7% (1.8) | +0.14 | 13.6% | 61% | 35% |
| v4 breakouts only (idle = T-bills) | 13.8% | -21.1% | 0.66 (0.47–0.92) | 0.91 | 0.41 | +7.1% (2.0) | -0.01 | 15.4% | 61% | 0% |
| v3 complete (no regime rule) | 14.5% | -26.2% | 0.56 (0.41–0.85) | 0.80 | 0.60 | +5.9% (1.4) | +0.06 | 14.6% | 92% | 4% |
| v3 breakouts only | 14.6% | -26.5% | 0.56 (0.42–0.83) | 0.83 | 0.55 | +6.5% (1.6) | +0.06 | 15.0% | 92% | 0% |
| SPY buy & hold | 13.2% | -33.7% | 0.39 | 0.69 | 1.00 | – | – | – | – | – |
| 60/40 SPY / T-bills | 8.9% | -21.3% | 0.42 | 0.69 | 0.60 | -0.0% (-2.1) | -0.69 | 7.1% | – | – |

Where the return comes from (annualised contribution to the portfolio return, mean of 20 orders):

| system | breakout positions | SPY parking (after switch costs) | T-bills | total |
|---|---|---|---|---|
| v4 complete (breakouts + SPY parking + regime) | +13.2% | +2.6% | +0.0% | +15.9% |
| v4 breakouts only (idle = T-bills) | +13.2% | +0.0% | +0.6% | +13.8% |
| v3 complete (no regime rule) | +14.8% | +0.0% | +0.0% | +14.9% |
| v3 breakouts only | +14.8% | +0.0% | +0.1% | +14.9% |

The breakout positions themselves (return per invested dollar, days with >5% invested): beta 0.70, alpha +7.2% per year on the invested capital.

Calendar-year returns (one random order for v4):

| year | v4 complete | SPY | 60/40 |
|---|---|---|---|
| 2015 | -1.6% | +1.2% | +1.0% |
| 2016 | +5.9% | +12.0% | +7.4% |
| 2017 | +21.8% | +21.7% | +13.0% |
| 2018 | +13.6% | -4.6% | -1.7% |
| 2019 | +61.0% | +31.2% | +18.9% |
| 2020 | +11.1% | +18.3% | +12.3% |
| 2021 | +20.2% | +28.7% | +16.6% |
| 2022 | -3.4% | -18.2% | -10.0% |
| 2023 | +23.8% | +26.2% | +17.5% |
| 2024 | +17.4% | +23.9% | +15.8% |

## 2. Pine engine: drawdown inside a trade on the entry bar

Before: on the fill bar the peak was the open and the low was compared with it (low-before-high), on later bars the high came first. Now every bar uses high-before-low (the fill bar's high counts, a stop inside the bar counts that bar's high first, an exit at the open does not), in Pine v3/v4, pine_sim and swing4.sim2; tests/test_pine_sim.py checks pine_sim = sim2 trade by trade. Trades and returns do not change.

| ticker (v4, full data) | code | trades | worst drawdown in a trade | average | PF (unchanged) |
|---|---|---|---|---|---|
| NVDA | before | 17 | -18.1% | -11.0% | 6.36 |
| NVDA | after | 17 | -18.1% | -11.1% | 6.36 |
| AAPL | before | 13 | -9.1% | -7.2% | 3.48 |
| AAPL | after | 13 | -9.1% | -7.2% | 3.48 |
| JPM | before | 14 | -7.9% | -5.8% | 4.21 |
| JPM | after | 14 | -7.9% | -5.9% | 4.21 |


## 3. Double counting of the regime: the model without spy_roc63 / spy_up

Evaluated on the 10657 base candidates that pass the regime rule (each traded on its own with the v3 exits).

| model | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | mean AUC | Q5 − Q1 exp R | Q5 win |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v4 model (17 features) | 0.561 | 0.586 | 0.630 | 0.483 | 0.557 | 0.573 | 0.642 | 0.659 | 0.435 | 0.702 | 0.583 | +0.268 | 54.7% |
| without spy_roc63/spy_up (15; rs63 keeps SPY inside) | 0.552 | 0.551 | 0.650 | 0.497 | 0.482 | 0.427 | 0.639 | 0.575 | 0.463 | 0.708 | 0.554 | +0.107 | 49.5% |
| no SPY at all: also without rs63 (14) | 0.551 | 0.549 | 0.651 | 0.496 | 0.477 | 0.423 | 0.626 | 0.549 | 0.481 | 0.714 | 0.552 | +0.104 | 49.7% |
| no SPY at all (14), trained on regime-passing breakouts | nan | 0.511 | 0.641 | 0.511 | 0.493 | 0.524 | 0.639 | 0.513 | 0.474 | 0.789 | 0.566 | +0.168 | 51.5% |
| no SPY at all: also without rs63 (14): sign-stable subset (2) | 0.563 | 0.548 | 0.625 | 0.527 | 0.492 | 0.415 | 0.655 | 0.565 | 0.464 | 0.758 | 0.561 | +0.150 | 49.6% |
| no SPY at all (14), trained on regime-passing breakouts: sign-stable subset (7) | nan | 0.530 | 0.645 | 0.513 | 0.482 | 0.509 | 0.683 | 0.525 | 0.485 | 0.776 | 0.572 | +0.210 | 52.2% |

The same models as the v4 entry filter (candidate & regime & top 75% of the model), complete system:

| model | trades | win | exp R [95% CI] | exp % | PF | CAGR | max DD | MAR | alpha | IR |
|---|---|---|---|---|---|---|---|---|---|---|
| v4 model (17 features) | 2737 | 49.0% | 0.328 [0.28, 0.38] | 4.11% | 2.46 | 15.7% | -26.6% | 0.59 | +6.7% | +0.14 |
| without spy_roc63/spy_up (15; rs63 keeps SPY inside) | 2641 | 48.8% | 0.323 [0.27, 0.37] | 3.91% | 2.37 | 15.6% | -26.8% | 0.58 | +6.5% | +0.14 |
| no SPY at all: also without rs63 (14) | 2625 | 48.5% | 0.320 [0.27, 0.37] | 3.90% | 2.36 | 15.8% | -26.9% | 0.59 | +6.6% | +0.14 |
| no SPY at all (14), trained on regime-passing breakouts | 2163 | 52.3% | 0.423 [0.36, 0.48] | 5.25% | 2.85 | 15.9% | -27.7% | 0.57 | +6.9% | +0.15 |
| no SPY at all: also without rs63 (14): sign-stable subset (2) | 2653 | 49.1% | 0.334 [0.28, 0.39] | 4.23% | 2.48 | 15.5% | -27.7% | 0.56 | +6.4% | +0.12 |
| no SPY at all (14), trained on regime-passing breakouts: sign-stable subset (7) | 2184 | 52.4% | 0.422 [0.36, 0.48] | 5.27% | 2.85 | 15.3% | -27.3% | 0.56 | +6.4% | +0.11 |

Coefficients x100 per walk-forward year — no SPY at all: also without rs63 (14):

| feature | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | + | − |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| er20 | -15.0 | -20.2 | -18.7 | -16.1 | -19.0 | -21.2 | -19.2 | -17.4 | -16.5 | -15.4 | 0 | 10 |
| rvol | 6.9 | 9.4 | 6.0 | 10.5 | 13.9 | 13.1 | 7.3 | 7.9 | 9.7 | 11.2 | 10 | 0 |
| roc63 | -8.7 | -5.7 | -5.8 | -13.8 | -12.4 | -14.0 | -9.5 | -8.3 | -6.0 | 3.0 | 1 | 9 |
| atr_pct | 5.1 | 8.3 | 15.5 | 8.8 | -3.8 | -0.1 | 12.6 | 13.4 | 9.6 | 7.4 | 8 | 2 |
| rsi14 | -6.4 | -3.1 | -3.6 | 11.5 | 8.1 | 8.3 | 4.0 | 4.2 | 5.9 | 3.1 | 7 | 3 |
| roc126 | -7.8 | 1.5 | 5.1 | 2.9 | 6.0 | 3.5 | -2.8 | -6.1 | -5.7 | -6.7 | 5 | 5 |
| ibs | 7.9 | 7.3 | 7.4 | 0.4 | -0.9 | -3.7 | -4.3 | -4.1 | -4.6 | -2.5 | 4 | 6 |
| gap | 7.9 | 6.1 | 4.7 | 4.9 | 5.9 | 3.0 | -0.0 | -0.4 | -0.7 | -0.8 | 6 | 4 |
| roc21 | 2.1 | -5.5 | -1.6 | -2.9 | -5.7 | -5.5 | -5.4 | -2.6 | -2.0 | 0.3 | 2 | 8 |
| bbw_pct | 8.2 | 2.5 | 6.7 | -2.1 | -2.7 | -0.1 | -2.7 | 1.2 | -2.5 | -4.3 | 4 | 6 |
| ext50 | 4.9 | 4.2 | -3.6 | -6.0 | -1.5 | -2.2 | 0.1 | -1.6 | -3.5 | -3.9 | 3 | 7 |
| brk_atr | -2.1 | -3.7 | -1.9 | -0.6 | 0.6 | 1.2 | 3.6 | 3.4 | 3.5 | 3.1 | 6 | 4 |
| range_atr | -8.5 | -6.0 | -0.3 | -1.4 | -1.6 | 0.8 | 1.8 | -0.1 | 0.1 | -2.8 | 3 | 7 |
| dist52 | -3.7 | -1.8 | 2.2 | 3.1 | -1.9 | -0.1 | 2.1 | 0.0 | 2.7 | -3.1 | 5 | 5 |

Coefficients x100 per walk-forward year — no SPY at all (14), trained on regime-passing breakouts:

| feature | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | + | − |
|---|---|---|---|---|---|---|---|---|---|---|---|
| er20 | -14.6 | -15.7 | -14.0 | -16.6 | -15.8 | -15.9 | -16.1 | -13.2 | -14.7 | 0 | 9 |
| ext50 | -2.2 | -8.5 | -11.7 | -14.7 | -15.7 | -14.0 | -14.0 | -11.7 | -8.4 | 0 | 9 |
| roc126 | 13.7 | 13.7 | 11.4 | 13.2 | 7.7 | 9.5 | 9.3 | 6.5 | 2.5 | 9 | 0 |
| rvol | 6.2 | 5.3 | 8.5 | 11.2 | 8.9 | 5.8 | 5.9 | 8.9 | 10.4 | 9 | 0 |
| atr_pct | 7.3 | 10.0 | 5.0 | 0.9 | 1.0 | 8.6 | 8.8 | 3.9 | 3.3 | 9 | 0 |
| range_atr | -4.1 | 0.6 | -2.4 | -2.9 | -4.7 | -7.7 | -7.7 | -6.0 | -6.6 | 1 | 8 |
| bbw_pct | -9.4 | -3.9 | 2.8 | 4.4 | 3.5 | 3.9 | 3.6 | -3.5 | -6.2 | 5 | 4 |
| roc21 | -9.4 | -2.1 | -0.3 | 0.2 | 2.2 | 5.9 | 6.2 | 5.7 | 7.6 | 6 | 3 |
| rsi14 | 0.8 | -4.7 | -1.1 | -2.8 | -4.8 | -6.5 | -6.5 | -4.3 | -4.5 | 1 | 8 |
| roc63 | 0.4 | 5.1 | 2.3 | 2.1 | 2.3 | 2.7 | 2.5 | 2.0 | 9.6 | 9 | 0 |
| gap | -2.6 | -2.4 | -3.0 | -1.6 | -2.5 | -2.5 | -2.3 | -1.8 | -0.0 | 0 | 9 |
| ibs | 2.5 | 5.6 | 2.4 | 1.0 | 0.3 | 0.5 | 0.7 | 1.4 | 2.7 | 9 | 0 |
| brk_atr | -1.5 | 0.4 | 0.0 | -2.9 | -2.2 | -1.2 | -1.5 | -1.5 | -3.4 | 2 | 7 |
| dist52 | 0.5 | -0.6 | 2.4 | -0.1 | 0.9 | 0.7 | 0.8 | 5.5 | -1.9 | 6 | 3 |

Coefficients x100 per walk-forward year — no SPY at all: also without rs63 (14): sign-stable subset (2):

| feature | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | + | − |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| er20 | -16.6 | -23.2 | -21.6 | -16.3 | -19.0 | -21.1 | -22.1 | -19.3 | -18.3 | -18.0 | 0 | 10 |
| rvol | 4.0 | 6.9 | 8.6 | 12.4 | 13.7 | 13.9 | 10.1 | 10.1 | 11.8 | 12.3 | 10 | 0 |

Coefficients x100 per walk-forward year — no SPY at all (14), trained on regime-passing breakouts: sign-stable subset (7):

| feature | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | + | − |
|---|---|---|---|---|---|---|---|---|---|---|---|
| er20 | -17.8 | -17.7 | -13.8 | -16.8 | -16.2 | -15.7 | -15.9 | -13.7 | -15.5 | 0 | 9 |
| ext50 | -4.6 | -9.8 | -11.0 | -15.0 | -16.4 | -14.8 | -14.8 | -11.9 | -7.8 | 0 | 9 |
| roc126 | 13.6 | 14.4 | 11.9 | 13.0 | 7.8 | 9.9 | 9.6 | 8.5 | 5.7 | 9 | 0 |
| atr_pct | 4.9 | 9.8 | 5.1 | 1.5 | 1.9 | 11.3 | 11.5 | 3.8 | 6.4 | 9 | 0 |
| rvol | 5.0 | 5.5 | 7.9 | 9.7 | 6.8 | 2.7 | 2.7 | 6.6 | 8.0 | 9 | 0 |
| gap | -3.8 | -2.5 | -3.2 | -2.8 | -3.6 | -3.5 | -3.4 | -2.9 | -1.3 | 0 | 9 |
| ibs | 2.4 | 5.8 | 2.4 | 0.9 | 0.1 | 0.1 | 0.4 | 1.0 | 2.3 | 9 | 0 |

## 4. Statistical power of the new holdout (computed before any test)

- v4 takes 0.87 trades per ticker-year (development), SD of a trade result 1.36R.
- Expected trades: ticker holdout (155 tickers x 9.8 y) ≈ **1329**; ticker + time holdout (2 y) ≈ **271**.
- ticker holdout: minimal detectable expectancy vs 0 (80% power, 5% two-sided): 0.104R; difference between two independent systems of that size: 0.148R (much less when v5 and v4 share most trades and the difference is tested pairwise).
- ticker + time holdout: minimal detectable expectancy vs 0 (80% power, 5% two-sided): 0.231R; difference between two independent systems of that size: 0.327R (much less when v5 and v4 share most trades and the difference is tested pairwise).
- Portfolio over 9.8 years: alpha vs SPY is only detectable if it exceeds ≈ 12.2% per year (tracking error 13.6%), i.e. an information ratio of 0.89.
- Portfolio over 2 years: alpha vs SPY is only detectable if it exceeds ≈ 27.0% per year (tracking error 13.6%), i.e. an information ratio of 1.98.

Trials logged in swing5/experiments.csv: 10.
