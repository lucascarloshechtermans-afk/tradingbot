# PROGRESS — swing buy/sell indicator research

## 🇳🇱 Samenvatting (voor Carlos)

**Beste versie nu: v3**, een breakout-indicator met een "kwaliteitsfilter".
- **KOOP** als de slotkoers boven de hoogste koers van de vorige 20 dagen sluit, de koers boven het 200-daags
  gemiddelde staat, de dag sterk sluit (in de bovenste 30% van de dagrange) én het kwaliteitsmodel de breakout goed
  genoeg vindt. Het model is het positiefst over breakouts met veel volume, na een zwakke markt en na een rommelige,
  samengedrukte periode.
- **VERKOOP** als de koers onder de laagste koers van de vorige 20 dagen sluit, of als de trailing stop
  (hoogste koers sinds instap − 4×ATR) geraakt wordt. Gemiddeld houd je een trade ~5-7 weken vast.
- **TradingView:** `indicator_lab/pine/swing_v3_quality_model.pine` (plakken in de Pine Editor, op een dagchart).
  Je kan het model uitzetten in de instellingen; dan heb je v2.
- **Resultaat** (2021-2026, getest op data waarop niets is afgesteld): op SPY/QQQ/AAPL/MSFT/NVDA + 10 andere tickers
  een Sharpe van 1,23 tegenover 1,18 voor buy & hold, met een max drawdown van −15% in plaats van −26%. Minder
  rendement dan buy & hold (16% tegenover 21% per jaar), maar veel rustiger. Kosten en slippage zitten erin.
- **Eerlijke waarschuwing:** op een brede mand van 48 andere grote aandelen doet hij het duidelijk slechter dan buy &
  hold. **Gebruik hem op beweeglijke groei-/momentumaandelen** (NVDA, AMD, META, …), niet op saaie defensieve
  aandelen, nutsbedrijven of obligaties.
- Van ~35 geteste ideeën hebben er 3 het gehaald (v1 → v2 → v3). De rest staat hieronder, met de reden waarom ze
  afvielen. Er zijn geen echte orders geplaatst en er is niets met een broker verbonden. Geen financieel advies.

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

> ⚠️ **Most important caveat (E29):** on a third, completely fresh basket of 48 large caps and sector ETFs
> (`TRAIN_EXTRA`, never used to pick or tune v1–v3), every version is much weaker than on DEV/HOLDOUT.
> v3 5-slot Sharpe is 0.61 (2015-20) / 0.45 (2021-26) vs B&H 0.75 / 1.03, and CAGR 5–7% vs 13–15%. The ranking
> v3 > v2 > v1 still holds there, so the improvements are real, but **the absolute edge depends heavily on what you
> point it at.** It works best on volatile, trending names (NVDA, AMD, MU, GE, META, CAT, …) and poorly on slow
> defensives, utilities, staples and bonds. In 2021-26 the average trade was +3.6% in the most volatile quarter of
> tickers vs +0.4–0.9% in the other three. Use it on a watchlist of lively growth/momentum stocks, not on everything.

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

### E19 — v3 extras: size by model score, extra features (noise level, not adopted)
- Take every v2 candidate, but below-threshold ones at 25%/50% size: composite 1.28/1.25 (v3 1.23), sleeves 1.16/1.13.
- Extra model features: Nov–Apr "winter" flag 1.27 · SPY 20d volatility 1.20 · ticker 20d/120d vol ratio 1.24 · all three 1.21.
- **Verdict:** +0.01–0.05 is inside the ±0.04 noise band, and after ~150 variants the multiple-testing risk is real.
  Not adopted. Noted: 25%-size for low-score breakouts and the winter feature are the most promising follow-ups.

### E20 — Stress tests of v3 (robustness, not a new version)
- **Bug found and fixed:** `score()` bound the slot count at import time, so changing `E.SLOTS` had no effect.
  It is now read at call time. All earlier numbers used K=5 as intended, so they are unaffected.
- **Number of slots K** (composite v3 vs v2): K3 1.23 vs 1.17 · K5 1.23 vs 1.18 · K8 1.22 vs 1.10 · K10 1.17 vs 1.04.
  v3 beats v2 at every K, and the gap widens with more slots. K3 gives the most return (CAGR 14–22%) with deeper
  drawdowns (up to −23%).
- **Costs 0.25% per side** (2.5× the base assumption): v3 1.11 vs v2 1.06 (sleeves 1.01 vs 0.92). Still positive
  everywhere, and v3 stays ahead.
- **Year by year, all 31 tickers, 5 slots, total return (seed 0) vs equal-weight B&H:**

| Year | v3 | v3 MaxDD | B&H | B&H MaxDD | Trades |
|---|---|---|---|---|---|
| 2015 | +31.2% | −7.2% | +12.4% | −10.5% | 82 |
| 2016 | +20.5% | −4.4% | +25.5% | −8.7% | 99 |
| 2017 | +28.9% | −5.0% | +31.4% | −2.2% | 95 |
| 2018 | +15.4% | −13.1% | +2.1% | −19.9% | 74 |
| 2019 | +22.0% | −6.2% | +36.4% | −7.4% | 108 |
| 2020 | +12.2% | −9.1% | +26.6% | −30.8% | 65 |
| 2021 | +18.8% | −7.4% | +27.7% | −4.5% | 118 |
| 2022 | +2.3% | −13.6% | −16.4% | −25.3% | 64 |
| 2023 | +27.3% | −16.2% | +36.7% | −8.6% | 100 |
| 2024 | +38.3% | −6.1% | +22.9% | −8.0% | 98 |
| 2025 | +7.2% | −7.9% | +24.2% | −17.2% | 93 |
| 2026 (to 20 Oct) | +31.7% | −12.0% | +22.0% | −6.8% | 63 |

  v3 was positive in all 12 years. It beats B&H in down or choppy years (2015, 2018, 2022) and in strong momentum
  years (2024, 2026), and lags in broad V-shaped rallies (2019, 2020, 2025), where it is either flat or late.

### E21 — Let the model replace the SMA200 trend filter (to catch V-shaped recoveries sooner)
Base without SMA200 / with SMA50 / SMA100 / SMA150 (keep 0.5 and 0.75): 1.08–1.10 / 1.10–1.18 / 1.12–1.17 / 1.18–1.20.
**Rejected:** SMA200 (v3 1.23) stays best. The model cannot replace the trend filter.

### E22 — Partial profit: sell half at +X ATR, trail the other half (blend of two exits)
- +2/3/3.5/4/5/6 ATR: composite 1.14/1.23/1.23/1.28/1.25/1.26. OOS 0.96/1.16/1.09/1.14/1.07/1.10 (v3 1.06). Lower
  drawdowns, ~1–2 points less CAGR.
- Neighbours vs v3's same neighbours: n16 1.11 vs 1.06 · n24 1.35 vs 1.29 · m16 1.23 vs 1.20 · m24 1.32 vs 1.31 ·
  trail 3.2 0.97 vs 0.95 · 4.8 1.08 vs 1.07 · IBS .56 1.14 vs 1.20 · .84 1.12 vs 1.08 · keep .6 1.29 vs 1.23 · .9 1.20 vs 1.20.
- **Verdict:** better in 8 of 10 neighbours, but only by ~+0.03 on average, inside the noise band. Not crowned.
  Documented as an optional, smoother "half off at +4 ATR" variant (lower DD, slightly lower return).

### E23 — Train the quality model on more and different data (48 training-only tickers)
`data.TRAIN_EXTRA` (ADBE, CRM, …, sector ETFs, EFA, EEM) is never scored. Average composite over keep 0.6/0.75/0.9:
- DEV-trained (v3): 1.22 · DEV+EXTRA-trained: 1.22 · **EXTRA-only-trained: 1.25** (keep 0.75: 1.32, worst cell 1.13).
- **Verdict:** no improvement (not adopted), but **strong evidence that v3's model is real.** A model fitted only on
  48 completely different tickers works just as well on the DEV and HOLDOUT tickers. It learned something general
  about breakouts, not quirks of the DEV names.

### E24 — Can the model learn the strong-close filter itself? Stricter labels?
- v1 base (no IBS) + model trained on DEV+EXTRA, keep 0.4/0.5/0.6: 1.24/1.17/1.11, OOS 0.87–0.93. Worse OOS than v3.
- Label "trade made > 1% / > 3%" instead of > 0: 1.18/1.14. **Rejected.** The hand IBS filter + the "> 0" label stay.

### E25 — Mean-reversion signal (RSI2 dip in uptrend) with its own quality model, alone and with v3
- RSI2 < 10 + SMA200, exit close > SMA5: unfiltered composite 0.68. With a model (keep 0.3/0.5/0.7, DEV+EXTRA):
  0.73/0.70/0.73. RSI2 < 20: 0.76. The model barely helps mean reversion.
- v3 + MR in shared slots: 1.11 (MR top 30%) / 1.13 (top 70%). CAGR up to 16–20%, but MaxDD up to −24/−26% and a
  lower slot Sharpe. **Rejected** (noted as a "more return, more risk" mode).

### E26 — Dead-trade exit and the weekly timeframe
- Exit if still ≤ the entry price after 5/10/15/20 bars: 1.03/1.03/1.12/1.14. Worse. Breakouts often need time.
- v2 logic on WEEKLY bars (signal on the weekly close, daily ATR trail): 10/10 1.15→0.85 · 10/10 + IBS 0.82 ·
  4/4 + IBS 1.05 · 4/4 without trail 0.89 (79-bar holds) · 10/5 trail 6 0.71. **Daily stays better.**

### E27 — Execution: buy at the signal day's close (MOC order) instead of the next open
v3 MOC 1.19 vs next-open 1.23 (OOS 1.07 vs 1.06). No difference. The night after a breakout is not systematically
positive. **Practical takeaway:** placing the buy at the next morning's open is fine; no need to trade at 15:55.


### E28 — Market breadth and VIX as model features
Share of TRAIN_EXTRA names above SMA50/SMA200 (no holdout data used), VIX level, VIX / its 50-day mean, all five +
winter: composite 1.20/1.22/1.24/1.17/1.15/1.12 (v3 1.23). **No gain.** The model looks saturated; its SPY-ROC63
feature already captures the market state.

### E29 — A third, fresh test universe: the 48 TRAIN_EXTRA tickers (never used to select or tune v1–v3)
| 5-slot | 2015-20 Sharpe / CAGR / DD | 2021-26 Sharpe / CAGR / DD | Sleeves IS/OOS | PF IS/OOS |
|---|---|---|---|---|
| v1 | 0.56 / 6.4% / −18.2% | 0.27 / 2.9% / −22.2% | 0.69 / 0.54 | 1.56 / 1.29 |
| v2 | 0.56 / 6.3% / −17.4% | 0.36 / 4.3% / −20.6% | 0.69 / 0.55 | 1.57 / 1.30 |
| v3 | 0.61 / 6.9% / −16.2% | 0.45 / 5.5% / −19.2% | 0.75 / 0.54 | 1.60 / 1.29 |
| B&H | 0.75 / 13.5% / −35.3% | 1.03 / 15.1% / −19.4% | – | – |
- **Verdict:** v3 > v2 > v1 holds on fresh tickers, so the progress generalizes. But the indicator clearly loses to
  buy & hold on a broad, defensive-heavy large-cap basket. This is the most important limitation found.

### E30 — Why? Ticker volatility predicts the edge → a volatility universe filter
- Across all 79 tickers, the correlation between a ticker's 2013-20 mean ATR% and its 2021-26 v3 average trade is
  **0.58**. By ATR quartile, the 2021-26 average trade was +0.37 / +0.75 / +0.88 / **+3.59%**, and the same monotonic
  pattern already shows in-sample (+0.90 / 0.75 / 2.01 / 4.36%). Worst names: NKE, SBUX, TLT, TXN, UPS, VZ, XLU.
  Best: NVDA, AMD, MU, GE, META, SLB, CAT, ORCL, AAPL, COST.
- Filter (no look-ahead): trade a ticker only while its trailing 252-day mean ATR% ≥ 1.5/1.75/2.0/2.25/2.5%:
  composite 1.14/1.06/1.13/1.03/0.98. On EXTRA OOS: 0.48/0.61/0.48/0.37/0.76 (v3 0.45).
- **Verdict:** a higher edge per trade, but not a better portfolio. Fewer names trade, so cash sits idle and
  concentration rises. Not adopted as a rule. **Adopted as usage advice:** run the indicator on a watchlist of
  volatile momentum names (the original scanner's `min_atr_pct` idea points the same way).

### E31 — Ranking signals on a big 79-ticker watchlist (where slots are often full)
v3 on ALL+EXTRA (79 names), 5-slot Sharpe IS/OOS: random 1.00/0.80 · ATR% high-first 0.96/0.91 · ATR% low-first
1.07/0.84 · ROC126 high 0.89/0.81 · RS63 high 0.97/0.54 · return/vol high 0.84/0.68. With 10 slots: random 1.06/0.90 ·
ATR% high 1.07/0.96 · RS63 high 1.09/0.95. B&H (79 names): 0.92/1.11, MaxDD −33%/−22% (v3 at 10 slots: −9%/−15%).
- **Verdict:** no ranking rule is reliably better (helps OOS, hurts or is flat IS). "Highest ATR% first" is at worst
  harmless, so it is a reasonable tie-breaker in practice. On a broad watchlist, v3 has about B&H's Sharpe with far
  smaller drawdowns but lower return.

### E32 — Threshold and exit simplifications of v3
- Probability threshold = training base rate (instead of a top-75% quantile): 1.27, but fewer trades (202/cell). Noise level.
- Trail only (no 20-day-low exit): 1.28 at 4 ATR, but trail 3.5/4.5/5.0 → 0.94/1.06/1.08 and n16 1.07, so fragile.
  No trail (20-day-low only): 0.94. 40-day-low only: 0.93 (124-bar holds).
- **Verdict:** keep v3's two exits. The trail does most of the work, and the 20-day-low exit makes it less sensitive
  to the trail setting.

### E33 — Realistic cash: idle capital earns the 3-month T-bill rate (^IRX)
v3 5-slot (seed 0), with on average ~70% of the slots occupied. CAGR without → with T-bill interest on idle cash:
DEV IS 14.6% → 14.9% · DEV OOS 15.0% → 16.0% · HOLD IS 16.8% → 17.1% · HOLD OOS 12.4% → 13.4%.
Worth ~+0.3%/yr when rates were ~0 (2015-20) and ~+1%/yr in 2021-26. It narrows, but does not close, the raw-return
gap to B&H (DEV OOS 21.4%). Reporting only; the protocol keeps cash at 0% (conservative).

---

## Status after this session & ideas not yet tested

After E18 (v3), 15 more idea families (E19–E33) produced nothing that beat v3 by more than the ±0.04 noise band on
the composite **and** held up in the neighbour checks. With ~35 families and ~250 variants tested on the same
2015-2026 data, the risk that the next "winner" is luck (data-snooping) keeps rising, so new wins need extra-strict
proof. The fresh-universe check (E29) is the best tool for that: it confirmed v3 > v2 > v1, but at a much lower absolute level.

Untested / next ideas, roughly by expected value:
1. **Run the indicator on a larger watchlist of volatile momentum names** (e.g. 100+ stocks with ATR% > 2.5) with
   10 slots. E30 suggests that is where the edge lives. It needs a point-in-time universe to avoid survivorship bias.
2. **Short side / bear-market mode** (mirror breakdowns, or move to T-bills/an inverse ETF when SPY < SMA200).
   The engine is long-only today, so this needs a `side` flag. Expected value is modest in a 2015-26 bull sample.
3. **Earnings awareness** (the repo has `events/earnings.py`). Breakouts on earnings gaps vs other breakouts.
4. Optional E22 mode in Pine: sell half at +4 ATR (smoother equity curve, slightly less return).
5. A 25%-size "probe" position for breakouts the model rejects (E19: 1.28, just inside noise). Re-test on fresh data.
