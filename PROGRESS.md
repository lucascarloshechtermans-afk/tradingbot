# PROGRESS — swing buy/sell indicator research

## ⭐ CURRENT BEST VERSION: v3 — v2 breakout + logistic "breakout quality" model (meta-labeling)

- **Rule:** the v2 candidate (close > prior 20-day high, close > SMA200, close in the top 30% of the day's range) is
  only taken when a small logistic-regression model scores it in the top 75% of breakout quality. The model uses 17
  features known at that close. The most stable ones: higher relative volume is better; a strong SPY over the last
  3 months, an already "smooth" 20-day trend (efficiency ratio), a large 6-month gain and wide Bollinger bands are
  worse. SELL is unchanged from v2: close below the prior 20-day low (exit next open), or the 4×ATR chandelier stop.
- **No look-ahead in the test:** the model was refit before every calendar year only on breakouts whose trades had
  already closed, using DEV tickers only. Every year scored below is therefore unseen by the model that traded it.
- **Code:** `indicator_lab/meta.py::meta_breakout {"n":20,"m":20,"trail":4.0,"ibs_min":0.7,"keep":0.75,"l2":100}`
- **Pine (TradingView):** `indicator_lab/pine/swing_v3_quality_model.pine` holds the latest fit, with coefficients
  in `v3_model.json`. It has a switch to fall back to v2 and an orange ✕ for breakouts the model rejected.
- **Reproduce:** `python -m indicator_lab.run best`

| Cell (5-slot portfolio) | Sharpe | CAGR | MaxDD | Trades | Win% | PF | Avg hold |
|---|---|---|---|---|---|---|---|
| DEV 2015-20 | 1.40 | 15.9% | -9.6% | 273 | 52% | 2.76 | 36 d |
| DEV 2021-26 | **1.23** | 15.9% | -15.4% | 260 | 49% | 2.23 | 35 d |
| HOLDOUT 2015-20 | 1.42 | 16.4% | -14.5% | 250 | 48% | 2.57 | 36 d |
| HOLDOUT 2021-26 | 0.88 | 12.2% | -18.0% | 276 | 43% | 1.58 | 28 d |
| **Buy & hold** (equal weight, DEV OOS / HOLD OOS) | 1.18 / 1.06 | 21.4% / 16.3% | -26.5% / -24.2% | – | – | – | – |

Composite **1.23** (v2 1.18, v1 1.03, baseline v0 0.15). Worst cell 0.88, OOS 1.06, sleeves Sharpe 1.16 (v2 1.06).
**Honest read:** on the DEV tickers in 2021-26, v3 now edges buy & hold on Sharpe (1.23 vs 1.18) with about 60% of
its drawdown, while invested ~44% of the time. It still makes less raw return than B&H (15.9% vs 21.4% CAGR), and on
the unseen HOLDOUT tickers in 2021-26 it trails B&H (0.88 vs 1.06). The step from v2 to v3 is real but modest.

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

### E8 — More v2 variants: stop only on a close, other trend filters, gap and squeeze filters
Composite vs v2 1.18:
- Trailing stop only on a CLOSE below it (exit next open): 4/3.5/3 ATR → 0.97/1.06/1.03. Worse. The intraday stop
  protects better.
- Breakout of the highest CLOSE instead of the highest high: 1.10. Trend MA 50/100/150 instead of 200: 1.14/1.06/1.14.
  SMA200 rising over 20 bars: 0.97. 12-month / 6-month momentum > 0: 1.02/1.12. None better.
- Skip breakouts that gapped up > 1/2 ATR: 1.09/1.11. Worse.
- Bollinger squeeze (BB width ≤ 20th/35th percentile of the last year within the last 10 bars): 1.06/1.09. Composite
  lower, BUT OOS 1.10/1.09 and worst cell 0.79/0.99 (v2: 0.88), so it is stronger in 2021-26 and weaker in 2015-20.
  **Interesting, not adopted** (fails the composite rule, and fewer trades: 167-204/cell).

### E9 — Buy the first pullback after a breakout (instead of the breakout itself)
A strong-close breakout within the last 5/10/20 bars, then RSI2 < 10/20/30 → composite 0.79–0.89, HOLD OOS 0.41–0.66.
Combined with v2 in the same slots: 1.03. **Rejected:** dips after breakouts are often failed breakouts.

### E10 — Breakout lookback and weekly-timeframe filters
- n = 30/40/55/100/252: 1.09/1.09/1.06/0.96/0.70 (52-week-high breakouts are clearly worse). 40/40: 1.14. 55/30: 1.04.
- Weekly close > weekly EMA10/EMA20: 1.12/1.22. Weekly MACD histogram > 0: 1.02. Within 5/10% of the 52-week high: 1.01/1.03.
- **Verdict:** weekly EMA20 at 1.22 is +0.04 vs v2, but its neighbour EMA10 is 1.12, so this is noise. Not adopted.

### E11 — Diagnosis: where does v2 lose? → volatility and trend-quality filters
Per ticker, the losers in OOS are low-volatility defensives: TLT (PF 0.03), XLU, V, PG, KO, BA, DIS.
- Minimum ATR% 1.0/1.25/1.5/2.0: 1.13/1.12/1.07/0.85. Noise to worse.
- Kaufman efficiency ratio ≥ 0.2/0.3/0.4 (50 bars): 0.84/0.62/0.32. ER(20) ≥ 0.3/0.4: 1.01/0.94. **Clearly worse:**
  requiring an already "clean" trend means buying late.

### E12 — Which signal gets the last free slot? (ranking same-day signals)
Ranked by ROC21/63/126/252, RS vs SPY, ATR%, RSI14, IBS, extension, RVOL, return/vol (high-first or low-first)
→ composite 1.14–1.22 vs random 1.18. **No effect.** With the strong-close filter the 5 slots are rarely full. This also
gives the noise level of the composite: about ±0.04.

### E13 — Exit tightening after a big gain, volume dry-up, range-expansion and NR breakouts
- Trail tightens to 2.5/3 ATR after +4/+6/+8 ATR: 1.05/1.05(2.5)/1.11(6→3)/1.20(8→3). The best is within noise,
  and its neighbour is worse.
- Volume dried up before the breakout (10/50 vol ≤ 0.8/0.9/1.0): 0.89/0.91/0.98. Range ≥ 1.0/1.3 ATR on the breakout
  bar: 1.14/1.01. NR4/NR7 before the breakout: 0.71/0.72. **All rejected.**

### E14 — Ensemble of breakout lookbacks: the ARTEFACT case (important lesson)
- 10/20/55 as three independent parts, each able to take its own slot: composite **1.30**, CAGR 19–27%. It looked
  like a big win, BUT one ticker could fill up to 3 slots (60% of equity), so this is concentration and leverage,
  not a better signal. The 20/40 two-part version: 1.09, HOLD OOS 0.46, DD −34%.
- Fair version: ONE position per ticker, sized by the fraction of parts that are long (1/3, 2/3, 1):
  10/20/55 1.06 · 10/20/40 1.08 · 15/20/30 1.04 · 20/55 1.09 · 10/20 1.12 · trail 3/4/5 0.98. **No improvement.**
- Fix to the protocol: the composite now also prints the sleeves Sharpe (per ticker, no slot interaction),
  and a new best must not lower it.

### E15 — Classic indicator families as the entry (all with v2's exits)
Composite (without / with the IBS ≥ 0.7 strong-close filter): Supertrend(10,3) 0.99/0.69 · Keltner(20, 2 ATR) 0.89/1.08 ·
MACD cross above 0 0.62/0.57 · Ichimoku (above cloud, TK cross) 1.08/1.08 · Aroon-up hits 100 1.06/1.20 ·
close > upper BB 0.95/1.03 · ROC20 crosses 10% 0.93/0.80.
- **Verdict:** none beat v2. Aroon+IBS (1.20) is in effect a 25-day breakout, the same signal as v2. The Donchian
  breakout + strong close family is the strongest.

### E16 — Close-based exits, fresh vs continuation breakouts, seasonality
- Exit on a close below the lowest CLOSE of 20/15 bars: 1.05/1.14 (sleeves 0.99 < v2 1.06). Exit below SMA50/SMA20: 1.07/0.94.
- "Fresh" breakout (no breakout in the prior 20/40 bars): 0.90/0.83. Continuation only (a breakout in the prior 10/20 bars): 0.87/0.99.
- Entries only Nov–Apr: 1.00. Only May–Oct: 0.80. Skip Sep–Oct: 1.13 (sleeves 0.98). The seasonality effect is real
  (May–Oct is clearly weaker), but excluding months removes trades and does not lift the composite. Not adopted.

### E17 — Meta-labeling: a logistic model decides which breakouts to take (walk-forward)
Setup: every candidate bar of the base breakout gets 17 features (IBS, log RVOL, ROC21/63/126, ATR%, RSI14,
extension over SMA50, RS63 vs SPY, distance to the 52-week high, Bollinger-width percentile, gap, SPY > SMA200,
SPY ROC63, range/ATR, breakout size/ATR, ER20). The label is whether the trade with the base exits made money. An L2
logistic regression is refit before each year on DEV candidates whose trade had already closed. A candidate is taken
if its probability is in the top `keep` share of that year's training predictions. Numpy only; Pine-portable.
- Univariate first look (2013-20 candidates, avg return by quintile): ATR% top quintile +3.6% vs +1.3%; RSI14 low
  better; extension low better; ER20 high **bad** (+0.1%); SPY ROC63 low (after market dips) **good** (+3.9%).
- On the v1 base (no IBS): keep 0.3/0.5/0.7 → 1.08/1.13/1.04. l2 1/100 → 1.16/1.18. The sleeves Sharpe rose to 1.15,
  but OOS fell (0.75–0.85). Small 6-feature model: 1.09–1.10. **Not better than v2.**

### E18 — Meta-labeling on top of v2 (IBS ≥ 0.7 base) → **NEW BEST v3**
- keep 0.6/0.7/0.75/0.8/0.9 (l2 100): composite 1.23/1.26/1.23/1.25/1.20, sleeves 1.13/1.16/1.16/1.15/1.12.
  l2 30/100/300/1000 (keep 0.75): 1.21/1.23/1.20/1.20. **Every setting beats v2** (1.18, sleeves 1.06). Plateau, no spike.
- Neighbours of n/m/trail/IBS with the model on vs v2's same neighbours: n16 1.06 vs 0.99 · n24 1.29 vs 1.20 ·
  m16 1.20 vs 1.16 · m24 1.31 vs 1.12 · trail 3.2 0.95 vs 0.94 · trail 4.8 1.07 vs 1.03. The model layer helps in
  every variant. ✅
- Sleeves robustness (DEV 2015-26, base 1.22): all ±20% nudges 1.02–1.23 (only trail 3.2 drops, as for v1/v2). ✅
- Coefficient stability across the 13 yearly refits: rvol (+), spy_roc63 (−), er20 (−) keep their sign every year;
  bbw_pct (−), rs63 (+), rsi14 (+) almost every year; ibs, gap, range_atr, roc21/63 flip sign (noise, small weights).
- 4-feature model with only sign-stable features (rvol, spy_roc63, er20, bbw_pct): 1.18–1.23, sleeves 1.09–1.16.
  Close to, but slightly below, the full model. Kept as a documented simpler fallback.
- **Interpretation:** take breakouts with volume behind them that come after the market has been weak and after a
  choppy, coiled period. Skip breakouts that are the n-th leg of an already smooth, extended run during a hot market.
- **Verdict:** new best v3 (keep 0.75, l2 100, the centre of the plateau). Pine port generated from the final fit
  (`export_final`, trained on all 3656 DEV candidates). Note: TradingView's SPY is not dividend-adjusted unless that
  chart setting is on, so the market features there differ marginally from the backtest.
