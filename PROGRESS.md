# PROGRESS — swing buy/sell indicator research

## ⭐ CURRENT BEST VERSION: v1 — Donchian 20/20 breakout + 4×ATR trail

- **Rule:** BUY when the close is above the highest high of the prior 20 days AND above the 200-day SMA.
  SELL when the close is below the lowest low of the prior 20 days (exit at the next open), or when the
  chandelier trailing stop (highest high since entry − 4×ATR14) is touched.
- **Code:** `indicator_lab/strategies.py::donchian_breakout {"n":20,"m":20,"trail":4.0}`
- **Pine (TradingView):** `indicator_lab/pine/swing_v1_donchian.pine`
- **Reproduce:** `python -m indicator_lab.run best`

| Cell (5-slot portfolio) | Sharpe | CAGR | MaxDD | Trades | Win% | PF | Avg hold |
|---|---|---|---|---|---|---|---|
| DEV 2015-20 (in-sample) | 1.26 | 16.1% | -13.4% | 330 | 51% | 2.31 | 35 d |
| DEV 2021-26 (OOS) | 0.99 | 13.0% | -17.6% | 287 | 47% | 1.92 | 34 d |
| HOLDOUT 2015-20 | 1.16 | 14.8% | -16.7% | 300 | 45% | 2.17 | 35 d |
| HOLDOUT 2021-26 (OOS) | 0.69 | 9.6% | -18.0% | 314 | 42% | 1.47 | 28 d |
| **Buy & hold** (equal weight, DEV OOS / HOLD OOS) | 1.18 / 1.06 | 21.4% / 16.3% | -26.5% / -24.2% | – | – | – | – |

Composite (mean 5-slot Sharpe over 4 cells) **1.03**, worst cell 0.69. Baseline v0 (repo pullback): 0.15.
**Honest read:** v1 has a much smaller drawdown than buy & hold, but it does NOT beat B&H on return or
Sharpe in 2021-26. Beating a 2015-2026 bull market on Sharpe with a long-only timing signal is the bar to clear.

---

## Test protocol (fixed, so every idea is judged the same way)

- **Data:** yfinance daily, split/dividend-adjusted, 2012-2026 (2012-14 warm-up only).
- **Tickers:** DEV (used while designing) = SPY QQQ AAPL MSFT NVDA IWM DIA AMZN GOOGL META JPM XOM JNJ HD KO.
  HOLDOUT (never used to design or tune) = CAT UNH V AMD COST PG NFLX BA DIS INTC WMT GS XLE XLU TLT GLD.
- **Periods:** in-sample 2015-2020, out-of-sample 2021-2026 (to 2026-10-20). Plus an anchored walk-forward
  (re-tune on all data before each year 2018-2026, score only the next year) for anything with tuned params.
- **Execution:** signal on the close, fill at the next open. Stops are checked intrabar, a gap through the stop
  fills at the open, and stop wins if stop and target are both inside one bar. **Costs 0.10% per side**
  (0.05% commission + 0.05% slippage), on every fill.
- **Portfolio ("5-slot"):** how the indicator would actually be traded on a watchlist. At most 5 open positions,
  each 1/5 of equity, cash at 0%. A signal with all slots full is skipped, and same-day ties are broken randomly.
  Stats are averaged over 5 seeds. "Sleeves" = 1/N fixed per ticker, also reported.
- **"Better" means all of:** higher composite (mean 5-slot Sharpe of DEV/HOLD × IS/OOS) AND OOS not worse
  AND ≥30 trades per cell AND ±20% parameter nudges don't collapse it (robustness table) AND, if tuned,
  the walk-forward doesn't fall apart. Otherwise the idea is logged as overfit or rejected.
- **Choices I made without being able to ask (noted per the brief):**
  - The repo had no Pine file, and the brief's `[bestandsnaam/map]` was left unfilled. The baseline (v0) is
    therefore the repo's own scanner "Bullish Pullback" setup turned into a stand-alone indicator, with the
    scanner's own exits. Each new best version also gets a Pine v5 port in `indicator_lab/pine/`.
  - "Swing" = average hold from a few days up to ~2 months. Longer-hold variants are noted but not crowned.
  - Long only (the original scanner is long only; shorting stocks adds borrow cost that isn't modelled).

---

## Experiment log (newest at the bottom)

### E0 — Baseline v0: repo "Bullish Pullback" as indicator
Close > SMA50 > SMA200, |close−EMA21| ≤ 1.5%, 35 ≤ RSI14 ≤ 58. Exits: 2 ATR stop, 3.35 ATR target, 5-bar time stop.
- DEV IS 0.36 / DEV OOS 0.16 / HOLD IS 0.36 / **HOLD OOS −0.27** (5-slot Sharpe). ~1000 trades/cell, PF 0.91–1.12.
- **Verdict:** barely positive before 2021 and loses money out of sample on unseen tickers. Weak baseline.

### E1 — RSI(2) mean reversion in uptrend (Connors style)
Buy RSI2 < 10 and close > SMA200; sell close > SMA5 or RSI2 > 90.
- 5-slot Sharpe 0.60 / 1.07 / 0.57 / 0.52, ~650–700 trades/cell, win 63–67%, PF 1.29–1.64.
- In-sample grid (DEV IS only): the best was RSI2 < 20 with an SMA10 exit (IS 0.92), but HOLD OOS dropped to 0.30.
- **Verdict:** a real but modest edge. Better than v0, worse than the trend ideas. Keep it as a candidate component.

### E2 — EMA crossover trend (fast/slow, SMA200 filter, optional trail)
- 20/50 + 3 ATR trail: 0.98 / 0.83 / 0.67 / 0.12. 10/50 no trail: 1.20 / 0.40 / 1.35 / 0.43 (holds 45–63 days).
- **Verdict:** unstable across cells (HOLD OOS weak). Rejected.

### E3 — Donchian breakout (n-day high entry, m-day low exit, ATR trail) → **NEW BEST v1**
- Default 55/20/3 ATR: 0.84 / 0.85 / 0.65 / 0.73.
- In-sample grid on DEV IS: top were 20/40 without a trail (IS 1.43, but 124-day holds and DEV OOS 0.16, which is
  NOT swing and NOT stable) and 20/40 or 20/20 with a 4 ATR trail.
- **20/20/4 ATR: 1.26 / 0.99 / 1.16 / 0.69 → composite 1.03**, the smallest IS→OOS drop of all variants.
- Robustness (DEV, 2015-26, sleeves Sharpe; base 1.07): n 16/24 → 1.07/1.05; m 16/24 → 1.01/1.08;
  trail 3.2/4.8 → 0.89/1.11. No cliff. ✅
- Walk-forward (sleeves, 2018-26): DEV 1.04 re-tuned vs 0.97 fixed; HOLD 0.68 re-tuned vs 0.68 fixed. Re-tuning
  adds nothing, so the fixed params are not curve-fit. ✅
- **Verdict:** new best. Committed with Pine port.
