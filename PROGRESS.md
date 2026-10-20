# PROGRESS — swing buy/sell indicator research

## ⭐ CURRENT BEST VERSION: v2 — Donchian 20/20 breakout + strong close + 4×ATR trail

- **Rule:** BUY when the close is above the highest high of the prior 20 days AND above the 200-day SMA AND the
  close is in the top 30% of the day's range (IBS ≥ 0.7, a "strong close"). SELL when the close is below the
  lowest low of the prior 20 days (exit at the next open), or when the chandelier trailing stop (highest high
  since entry − 4×ATR14) is touched.
- **Code:** `indicator_lab/strategies.py::breakout {"n":20,"m":20,"trail":4.0,"ibs_min":0.7}`
- **Pine (TradingView):** `indicator_lab/pine/swing_v2_strong_close.pine`
- **Reproduce:** `python -m indicator_lab.run best`

| Cell (5-slot portfolio) | Sharpe | CAGR | MaxDD | Trades | Win% | PF | Avg hold |
|---|---|---|---|---|---|---|---|
| DEV 2015-20 (in-sample) | 1.33 | 16.4% | -13.9% | 306 | 51% | 2.46 | 35 d |
| DEV 2021-26 (OOS) | 1.16 | 14.8% | -14.9% | 264 | 49% | 2.23 | 35 d |
| HOLDOUT 2015-20 | 1.36 | 16.9% | -12.7% | 275 | 47% | 2.29 | 36 d |
| HOLDOUT 2021-26 (OOS) | 0.88 | 12.0% | -19.1% | 287 | 42% | 1.48 | 28 d |
| **Buy & hold** (equal weight, DEV OOS / HOLD OOS) | 1.18 / 1.06 | 21.4% / 16.3% | -26.5% / -24.2% | – | – | – | – |

Composite (mean 5-slot Sharpe over 4 cells) **1.18** (v1 1.03, baseline v0 0.15), worst cell 0.88, OOS 1.02.
**Honest read:** v2 roughly matches buy & hold on Sharpe on the DEV tickers OOS (1.16 vs 1.18) with about half the
drawdown and ~45% time in the market. It still trails B&H on raw return and on the holdout tickers OOS.

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

### E4 — Filters on v1: market regime, relative strength, ADX, volume, "don't chase"
Composite (mean 5-slot Sharpe) vs v1 1.03:
- SPY > SMA200/100/50 regime: 0.83 / 0.91 / 0.94. **Worse.** The per-ticker SMA200 filter already does this job,
  and the extra filter mostly delays re-entry after corrections.
- RS vs SPY (126/63/252-day): 0.87 / 0.99 / 0.81. Worse. Regime+RS: 0.67.
- ADX ≥ 20/25: 0.86 / 0.77. Worse.
- Breakout-day volume ≥ k×SMA50: k 0.8/1.0/1.1/1.2/1.3/1.4/1.5 → 0.99/1.02/1.12/1.10/1.05/0.99/0.94. A bumpy hill:
  the average over the plateau (≈1.06) is within noise of v1. **Not adopted.**
- Max extension above SMA50 (ATR): 2/2.5/3/3.5/4/5 → 0.84/0.98/1.05/1.12/1.06/0.99. Same story, noise level.
  Volume 1.2 + extension 3 together: 0.76 (too few trades). **Rejected.**

### E5 — Two signal types in one indicator: v1 breakout + RSI2 mean reversion (shared 5 slots)
- With RSI2<10/SMA5 exit: composite 0.95, CAGR up (13–19%), but MaxDD −18…−23%. RSI2<5: 0.98. RSI2<20/SMA10: 0.78.
- **Verdict:** more return but more drawdown, and a lower Sharpe. Rejected under the Sharpe-first rule.
  Noted as an option for a "max return" variant.

### E6 — Exit and sizing variants on v1
Composite: initial stop 2/3 ATR 0.97/0.97 · breakeven after +2/+3 ATR 1.07/1.03 · time stop 20/40 bars 0.79/0.95 ·
exit on close < EMA10/EMA20 0.70/0.85 · fixed 3 ATR stop without trail 0.84 · volatility-scaled size
(target ATR% 1.5/2/3) 0.98/0.99/1.01.
- **Verdict:** the plain 4 ATR chandelier + 20-day-low exit is already a good exit. Tighter exits cut the winners.
  Breakeven +2 ATR is within noise. None adopted.

### E7 — Strong-close filter on the breakout day (IBS = (close−low)/(high−low)) → **NEW BEST v2**
- IBS ≥ 0.4/0.5/0.6/0.65/**0.7**/0.75/0.8/0.85/0.9 → composite 1.06/1.08/1.13/1.13/**1.18**/1.10/1.06/0.93/0.82.
  A broad plateau from 0.5 to 0.8 where every value beats v1, so it is not a single lucky value.
- v2 cells 1.33 / 1.16 / 1.36 / 0.88. **All four cells beat v1** (1.26 / 0.99 / 1.16 / 0.69), and MaxDD is
  lower in 3 of 4.
- Neighbours (5-slot composite): n 16/24 → 0.99/1.20 · m 16/24 → 1.16/1.12 · trail 3.2/4.8 → 0.94/1.03.
  Sleeves robustness (DEV 2015-26, base 1.15): every ±20% nudge stays within 0.96–1.16. No cliff. ✅
- Walk-forward (grid incl. IBS 0/0.5/0.7): re-tuning picks IBS 0.5 or 0.7 in 17 of 18 years, so the filter is chosen
  out of sample. WF sleeves Sharpe DEV 1.00 / HOLD 0.66 (v1 WF 1.04 / 0.68), so on sleeves the gain is ≈0.
  The improvement shows mostly in the realistic 5-slot portfolio: fewer, better breakouts compete for slots. ✅
  (A modest but consistent improvement.)
- **Verdict:** new best. Pine port `swing_v2_strong_close.pine`. Also fixed both Pine files so they never re-enter
  on the bar of an exit, which matches the engine.
