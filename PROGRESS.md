# PROGRESS — swing buy/sell indicator research

## 🇳🇱 Samenvatting (voor Carlos)

**Beste versie nu: v3.1** = de v3-signalen hieronder + één portfolioregel: **geld dat niet in een positie zit, parkeer
je in SPY zolang SPY boven zijn 200-daags gemiddelde staat (anders cash).** Dat gaf in alle 8 testcellen (4 groepen
aandelen × 2 periodes) 1–4% meer rendement per jaar bij een vergelijkbare Sharpe (E48). De tabel in het Pine-script
toont "Idle cash → SPY: YES/NO".

**De signalen (v3)**: een breakout-indicator met een "kwaliteitsfilter".
- **KOOP** als de slotkoers boven de hoogste koers van de vorige 20 dagen sluit, de koers boven het 200-daags
  gemiddelde staat, de dag sterk sluit (in de bovenste 30% van de dagrange) én het kwaliteitsmodel de breakout goed
  genoeg vindt. Het model is het positiefst over breakouts met veel volume, na een zwakke markt en na een rommelige,
  samengedrukte periode.
- **VERKOOP** als de koers onder de laagste koers van de vorige 20 dagen sluit, of als de trailing stop
  (hoogste koers sinds instap − 4×ATR) geraakt wordt. Gemiddeld houd je een trade ~5-7 weken vast.
- **TradingView** (handleiding: `indicator_lab/pine/README.md`):
  - `swing_v3_quality_model.pine` — de indicator: BUY/SELL, trailing stop, infotabel met positiegrootte en
    statistiek van het aandeel, waarschuwing vóór kwartaalcijfers, alerts. Model uitzetten = v2.
  - `swing_v3_strategy.pine` — zelfde regels als strategy → Strategy Tester van TradingView.
  - `swing_v3_watchlist_dashboard.pine` — 12 tickers in één tabel (BUY/SELL/LONG + stop).
  - Alles is **gecompileerd** met een Pine-compiler, en een Python-emulator bewijst dat de Pine-signalen exact
    dezelfde trades geven als de backtest (102 tickers).
- **Resultaat** (2021-2026, getest op data waarop niets is afgesteld): op SPY/QQQ/AAPL/MSFT/NVDA + 10 andere tickers
  een Sharpe van 1,23 tegenover 1,18 voor buy & hold, met een max drawdown van −15% in plaats van −26%. Minder
  rendement dan buy & hold (16% tegenover 21% per jaar), maar veel rustiger. Kosten en slippage zitten erin.
- **Eerlijke waarschuwing:** op een brede mand van 48 andere grote aandelen doet hij het duidelijk slechter dan buy &
  hold. **Gebruik hem op beweeglijke groei-/momentumaandelen** (NVDA, AMD, META, …), niet op saaie defensieve
  aandelen, nutsbedrijven of obligaties.
- **Praktische tips uit sessie 2:** gebruik op beweeglijke aandelen 10 posities in plaats van 5 (in 2021-26 even
  veel rendement als buy & hold, met minder dan de helft van de max daling), en open geen nieuwe positie in de week vóór
  de kwartaalcijfers van dat bedrijf. Shorten (breakdowns) werkt níet.
- **Hoe zeker is dit? (E60)** Het sterkste en meest zekere voordeel is een **veel kleinere maximale daling** dan
  buy & hold (in alle 6 testcellen kleiner, bv. −19% vs −33%). Op rendement wint buy & hold meestal nipt, en op
  Sharpe is het ongeveer gelijk. Zie dit dus als "rustiger beleggen met vergelijkbaar rendement", niet als een manier
  om de markt te verslaan.
- Van ~90 geteste ideeën hebben er 4 het gehaald (v1 → v2 → v3 → v3.1). De rest staat hieronder, met de reden waarom ze
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

---

## Session 2 (evening 2026-10-20) — working through the "next ideas" list

### E34 — 25%-size "probe" positions for breakouts the model rejects, re-tested on the fresh 48-ticker basket
v3 vs v3+probe on TRAIN_EXTRA (unseen by v3), 5-slot Sharpe IS/OOS 0.61/0.45 vs 0.56/0.38, 10-slot 0.64/0.45 vs 0.64/0.51.
**Rejected:** it does not hold up on fresh data. The +0.05 in E19 was noise, as suspected.

### E35 — A watchlist of volatile growth/momentum names (`data.VOLATILE`, 71 tickers, never used before)
TSLA, SHOP, ROKU, CRWD, PLTR, COIN, SMCI, MRNA, … deliberately including many that later crashed (PTON, ZM, SNAP, LYFT,
NIO, RIVN, LCID, CCL, PLUG, UPST, AFRM, DOCU, …) to limit survivorship bias. Delisted names are still missing, so
B&H here is flattered. B&H = equal weight over the names alive that day.

| | 2015-20 Sharpe / CAGR / MaxDD | 2021-26 Sharpe / CAGR / MaxDD | PF IS/OOS | avg trade IS/OOS |
|---|---|---|---|---|
| B&H | 1.41 / 41.5% / −42% | 0.56 / 14.3% / **−56%** | – | – |
| v1, 10 slots | 1.27 / 29.0% / −29% | 0.36 / 6.1% / −43% | 2.67 / 1.19 | +7.3% / +1.2% |
| v2, 10 slots | 1.09 / 23.3% / −32% | 0.58 / 11.8% / −33% | 2.37 / 1.24 | +6.1% / +1.5% |
| **v3, 10 slots** | 1.11 / 21.1% / −29% | **0.67 / 14.5% / −25%** | 2.63 / 1.25 | +6.3% / +1.5% |
| v3, 5 slots | 0.72 / 14.7% / −34% | 0.36 / 6.4% / −43% | | |
- **Verdict:** on volatile names in 2021-26, v3 matched B&H's return (14.5% vs 14.3%) with less than half the drawdown
  (−25% vs −56%) and a better Sharpe. In the 2015-20 tech boom, B&H of (surviving) volatile names was unbeatable.
  v3 > v2 > v1 holds again OOS. **With volatile names, use 10 slots, not 5:** concentration kills it.

### E36 — Equal-risk sizing (size = min(1, target ATR% / ATR%))
Target 2/3/4% ATR, VOLATILE 10-slot OOS Sharpe 0.69/0.68/0.68 (v3 0.67), with MaxDD −12/−17/−20% vs −25% and CAGR
7.5/10.6/12.8% vs 14.5%. DEV/HOLD composite 1.20/1.23/1.25.
**Verdict:** a pure risk dial. Drawdown and return scale down together, and the Sharpe is unchanged. Not a better
signal, but useful advice: on very volatile names, size so that every position carries similar risk.

### E37 — Short side: mirror of v2 on breakdowns (new `simulate_short`, stop above / trail from the lowest low)
Close < prior 20-day low, < SMA200, weak close (IBS ≤ 0.3); cover on close > prior 20-day high or 4×ATR trail.
- Composite −0.55 (PF 0.34–0.48). Only when SPY < SMA200: −0.34. Tighter trail 2.5: −0.31. 10-bar time stop: −0.29.
- v3 + short in shared slots: 0.53 (v3 alone 1.23).
- **Verdict: firmly rejected.** Stock breakdowns get run over by sharp short-covering rallies, even in bear phases.
  In this sample the best "bear mode" is the one v3 already has: no new longs below SMA200, so it sits in cash.

### E38 — Earnings awareness (Alpha Vantage quarterly report dates; 107 stocks cached, the free limit stopped the rest)
Pre-registered hypotheses, checked on v3's trades in DEV+HOLD, EXTRA and VOLATILE, IS and OOS (6 cells):
- **H1, breakouts on the earnings reaction day are better: rejected.** Mixed (+4.5 vs +3.9% DEV+HOLD IS, but +1.1 vs
  +2.7% OOS, and −0.6 vs +1.5% on EXTRA IS).
- **H2, entries ≤5 sessions before earnings are worse: confirmed in all 6 cells.** Avg trade: DEV+HOLD +2.6 vs +4.0% (IS),
  −0.2 vs +3.0% (OOS) · EXTRA +0.4 vs +1.4%, −0.2 vs +1.1% · VOLATILE +4.7 vs +9.0%, −0.4 vs +1.4%.
  This matches the scanner's existing `avoid_earnings` rule.
- As a filter (skip entries 3/5/7/10 sessions before earnings): composite 1.26/1.25/1.22/1.24 (v3 1.23). Worst cell
  0.96–1.01 (v3 0.88), OOS 1.09–1.16 (v3 1.06), sleeves 1.11–1.14 (v3 1.16). Fresh EXTRA IS/OOS 0.44–0.54 / 0.54–0.70
  (v3 0.61/0.45). VOLATILE 10-slot 0.99–1.17 / 0.61–0.70 (v3 1.11/0.67).
- **Verdict:** a clear per-trade effect, but at portfolio level it is mixed and inside the noise. A skipped breakout
  often never re-triggers, so the trade is lost entirely. **Not a rule. Adopted as advice:** don't open a new swing
  position in the week before a company's earnings. (The test used actual report dates. In practice those are
  announced weeks ahead, and TradingView exposes them as `earnings.future_time`.)
- Note: "held through earnings → +7% vs −2%" looks huge, but it is a look-ahead artefact. Trades that last long
  enough to reach earnings are the winners. Not usable.

### E39 — Pine: optional half-profit target (idea 4)
`swing_v3_quality_model.pine` has a new input, "Take half profit at +x ATR" (default 0 = off; E22 used 4). When on,
it draws the target line, marks "½" when it is hit and has its own alert. BUY/SELL logic is unchanged.

### Status after session 2
All 5 queued ideas are done: probe positions ✗ · volatile universe (✓ as usage advice: 10 slots on volatile names,
OOS ≈ B&H return at under half the drawdown) · short side ✗ · earnings (advice only) · Pine half-profit option ✓.
**v3 remains the best version.** Next ideas: a point-in-time (survivorship-free) volatile universe; the full Alpha
Vantage earnings history once the daily limit resets (27 names missing); and a regime switch between 5 and 10 slots.

### E40 — E38 re-run with fuller earnings data (131 of 134 stocks; DVN/OXY/HAL still missing)
- H2 per trade (entries ≤5 sessions before earnings vs the rest): DEV+HOLD +2.6 vs +3.9% (IS), +0.1 vs +3.1% (OOS) ·
  EXTRA +0.4 vs +1.4%, +0.1 vs +1.0% · VOLATILE +3.6 vs +6.9%, +1.0 vs +1.4%. **Still worse in all 6 cells.**
- As a filter, skip 3/5/7/10 sessions: composite 1.25/1.24/1.22/1.24 (v3 1.23). EXTRA OOS 0.50–0.69 (v3 0.45), but
  VOLATILE 10-slot OOS 0.46–0.60 (v3 0.67) is worse.
- **Verdict unchanged:** a real per-trade effect, no robust portfolio gain. Keep it as advice, not a rule.

## Where this ends (2026-10-21)
I am stopping the optimisation here on purpose. After ~40 idea families, the last ~22 have not produced a robust
improvement over v3, and every extra test on the same 2015-2026 data raises the chance that a "winner" is luck.
The highest-value next step is no longer another backtest. It is **checking v3 in reality**:
1. Paste `indicator_lab/pine/swing_v3_quality_model.pine` into TradingView and check that the BUY/SELL marks match
   the Python signals on a few charts (e.g. NVDA, AAPL in 2024). The Pine code has not been compiled in TradingView.
2. Paper-trade it for 2–3 months on a watchlist of ~20–40 volatile names, with 10 positions, without trading in the
   week before earnings, and compare with these backtest numbers.


---

## Session 3 (2026-10-21) — the Pine Script itself

Focus moved from finding new rules to making the TradingView script the user will actually run correct and useful.

### E41 — Is the Pine script correct?
- **Compilation:** all Pine files (v1, v2, v3 indicator, v3 strategy) were compiled with an external Pine compiler
  (TextToQuant `validate_indicator`) and linted: 0 errors, 0 warnings. The validator is real: it rejects, for example,
  duplicate declarations, which caught one bug in the first draft of the strategy file. v3 also compiles as `@version=6`.
- **Logic parity:** `indicator_lab/pine_emulator.py` re-implements the Pine script bar by bar with Pine semantics.
  On 102 tickers (DEV+HOLDOUT+VOLATILE), its BUY/SELL marks reproduce the research engine's trades **exactly**
  (32 differences, all positions still open on the last data day, which the engine does not log). Pine's
  `ta.percentrank` (which excludes the current bar) changes 4 of 3,246 signals (0.1%).
  `tests/test_pine_emulator.py` guards both the signals and the per-trade returns on synthetic data (runs in CI, no
  network). `tests/test_pine_model_sync.py` checks that both Pine files embed exactly `v3_model.json`.
- Runtime check on real bars was not possible: the TextToQuant free plan runs crypto only, and its preview output
  was truncated. Compile + emulator parity is the strongest check available here.

### E42 — Pine features added (signal logic unchanged, so parity holds)
- `swing_v3_strategy.pine`: the same rules as a TradingView **strategy** (next-open market orders, the trail as a stop
  order from the next bar, gaps fill at the open, 0.10% per side, no re-entry on an exit bar). The Strategy Tester
  works on any ticker.
- Indicator v3: an **info table** (status, breakout quality, stop, risk to stop, bars in trade, next earnings, trend,
  **position size** at a chosen account/risk %, daily-chart check, and **this chart's trade statistics** since 2015
  with costs) · an **earnings window** via `earnings.future_time` (yellow dot on a BUY within 7 days, optional block;
  live bars only) · a dynamic `alert()` with estimated stop, quality and size · a **status plot** for TradingView's
  **Pine Screener** to scan a whole watchlist (1 = BUY today, −1 = SELL) · optional ½-profit target.
- Model check: retraining the embedded model on DEV+EXTRA (48 more tickers) is not clearly better on the fresh
  VOLATILE names (5 slots better, 10-slot OOS 0.60 vs 0.67), so the Pine file keeps the validated v3 fit.
- Dutch user guide: `indicator_lab/pine/README.md`.

### E43 — Bug fix: indicator cache keyed on `id(df)`
`strategies.C` cached indicators by `id(df)`. After a DataFrame is freed, Python can reuse its id for a new frame,
which would then get the old frame's indicators. This surfaced in the new synthetic-data Pine tests (a test passed
alone but failed in the full suite). The cache now keeps the frame and checks identity. **Research results are
unaffected:** every backtest used frames held for the whole run in `evaluate._DATA`, so ids were never reused. Re-run
after the fix: v3 composite 1.23 and v2 1.18, identical to before. Lesson: the commit before this one was pushed with
a failing test because `pytest | tail` hid the exit code. Checks now look at the exit code.

### E44 — Pine watchlist dashboard
`swing_v3_watchlist_dashboard.pine` (Pine v6) runs the full v3 state machine for 12 user-chosen symbols via
`request.security`, with SPY requested in a nested call inside each symbol's context, and shows a table: BUY today /
SELL today / LONG with the current stop and risk % / flat, plus breakout quality. It compiles (validated) and is meant
for users without TradingView's Pine Screener. The default list is volatile momentum names, as advised in E35.


---

## Session 4 (2026-10-21) — autonomous backtesting for more profit

New safeguard: `data.LOCKBOX` holds 50 never-used stocks (DECK, AXON, FICO, VRT, APP, MELI, …), downloaded but not
looked at until a final confirmation. Development universe this session: BIG = ALL + TRAIN_EXTRA + VOLATILE
(~150 names), 10 slots.

### E45 — Choosing among signals by model quality; cross-sectional momentum filter (BIG, 10 slots)
- v3 baseline: IS 1.33 / 20.3% / −18% · OOS 0.60 / 10.1% / −28% (B&H: 1.25 / 27.0% / −35% · 0.77 / 16.4% / −37%).
- Highest model quality first when slots are full: IS 1.14, OOS 0.54. **Worse.**
- Only breakouts in the top 50/30/20% of 126-day momentum across the universe: OOS 0.68/0.62/0.68, IS 1.12/1.10/1.36.
  Not monotonic, so noise. **Rejected.**

### E46 — Lookback × trail × number of slots on BIG
Breakout 20/30/40/55 × trail 3/4/5 × slots 10/15/20 (36 combinations). Robust pattern: **15–20 slots beat 10** on a
~150-name watchlist (n=20, trail 4: OOS 0.60 → 0.69 → 0.76). Lookback 20 stays best OOS. Trail 5 is slightly better
on BIG but was worse on DEV (E7 neighbours), so v3 keeps trail 4.
**Advice:** with a large watchlist hold more, smaller positions (≈ watchlist size / 8, at 5–10% each).

### E47 — LOCKBOX confirmation (50 fresh stocks; the lockbox is now spent)
| 2015-20 / 2021-26, Sharpe (CAGR) | 5 slots | 7 slots | 10 slots | PF IS/OOS |
|---|---|---|---|---|
| v1 | 0.97 (17.6%) / 0.41 (6.9%) | 1.14 / 0.56 | 1.23 / 0.48 | 2.10 / 1.69 |
| v2 | 0.92 / 0.55 | 1.25 / 0.53 | 1.37 / 0.46 | 2.11 / 1.64 |
| **v3** | 0.85 / **0.76** | 1.20 / **0.78** | 1.32 (20.6%) / **0.73 (12.7%)** | 2.05 / **1.71** |
| B&H (survivors, flattered) | 1.40 (34.8%) / 0.88 (21.4%) | | | |
**v3's out-of-sample edge over v1/v2 is confirmed on completely fresh stocks.** It still trails B&H of today's
survivors.

### E48 — Park idle cash in SPY while SPY > SMA200 → **NEW BEST v3.1 (portfolio rule)**
Idle slot capital earns SPY's return when SPY closed above its SMA the day before; otherwise 0%.
| | no parking | SPY>SMA200 | SPY>SMA100 | QQQ>SMA200 |
|---|---|---|---|---|
| DEV/HOLD composite (Sharpe) | 1.23 | 1.23 | 1.23 | 1.19 |
| OOS mean Sharpe | 1.06 | 1.13 | 1.16 | 1.17 |
| CAGR per cell DEV-IS/DEV-OOS/HOLD-IS/HOLD-OOS | 15.9/15.9/16.4/12.2% | **18.9/18.0/19.9/16.1%** | 17.1/17.9/19.0/17.0% | 18.0/19.4/21.2/18.7% |
| BIG 10-slot IS/OOS CAGR | 20.3/10.1% | 22.3/10.8% | 22.3/10.5% | 22.3/11.2% |
| LOCKBOX 10-slot IS/OOS CAGR (Sharpe) | 20.6 (1.32) / 12.7% (0.73) | 21.7 (1.26) / 14.9% (0.79) | 21.2 / 15.2% | 21.6 / 16.7% |
- More return in **all 8 universe×period cells** at about the same Sharpe; MaxDD a few points deeper (DEV-IS −10 → −19%).
  The SMA length and the parking ETF don't matter much, so it is robust. SPY>SMA200 is the plainest version.
- HOLD 2021-26 now about equals B&H's return (16.1% vs 16.3%) with a smaller drawdown (−19% vs −24%). DEV 2021-26 is
  18.0% vs 21.4% for B&H.
- Why it works: v3 is only ~70% invested. In uptrends the idle part now earns the market. In downtrends
  (SPY < SMA200) it stays in cash, so the bear-market protection is kept.
- Pine: the info table and the dashboard show "Idle cash → SPY: YES/NO".

### E49 — v3.1 robustness checks
- Slots 3/5/8/10, composite Sharpe without → with parking: 1.23→1.24 · 1.23→1.23 · 1.22→1.22 · 1.17→1.17. CAGR rises
  in every cell at every slot count (+2.5 to +6 points per year; the more slots, the more idle cash to park).
- With realistic cash (3-month T-bill rate on the part that is neither invested nor parked): v3.1 CAGR DEV 17.8→17.9%
  (IS) / 17.7→18.1% (OOS) · HOLD 20.3→20.3% / 16.2→16.5% (single seed). Small but positive.
  (A first run showed lower numbers. That was a bug in the throwaway script, `~` on an object dtype, caught because
  adding interest cannot lower returns.)

### E50 — Dynamic position size (bigger positions when few signals are open)
Each open position gets 1/max(open positions, min) of equity, up to 10 positions, with SPY parking:
min 3: composite 1.18, OOS 0.99, BIG OOS 0.70 (v3.1 10-slot 0.63), LOCKBOX 0.99/0.69 (v3.1 1.26/0.79) ·
min 5: 1.22, OOS 1.09, BIG 0.67, LOCKBOX 1.13/0.73. Better on BIG, worse on DEV/HOLD OOS and on the lockbox.
**Rejected.** Fixed equal slots + SPY parking (v3.1) stays the rule.

## Where session 4 ends
**v3.1 is the best version:** the v3 signals (unchanged, Pine-verified) plus parking idle cash in SPY while
SPY > SMA200. Practical settings, from the evidence: a watchlist of volatile growth/momentum names; about 1 position
per 8 names on the list (5–10% each); no new entries in the week before earnings; idle cash in SPY when the table says
YES. Signal rules, filters, exits, sizing and ranking have now been searched broadly (50 experiment families), and
the remaining ideas test as noise.


---

## Session 5 (2026-10-21) — code review of the indicator

A line-by-line review of the Pine scripts and the Python behind them turned up 3 real issues and 3 usability gaps.
All are fixed, and the backtest numbers are unchanged (v3 composite 1.23).

### E51 — Fixes
1. **Look-ahead on non-US charts (real bug):** the model read SPY's close of the SAME date. Euronext closes ~4.5 h
   before New York, so on a European chart historical signals used SPY information that did not exist yet, and live
   signals changed with SPY intraday. Fix: on charts whose exchange timezone isn't New York, use the previous SPY close
   (indicator, strategy, dashboard).
2. **Training-label contamination (small bug):** the exported live model also trained on 23 trades (0.6%) that were
   still open, labelled with unrealised P&L. `candidate_table` now drops trades still open on the last bar. Refit:
   3,633 closed breakouts, threshold 39.26 → 39.30%. Walk-forward backtests were unaffected: they only train on trades
   closed before each test year.
3. **No protection on the entry day:** the stop only existed from the bar after the fill. Added an initial stop at
   fill − 4×ATR(signal bar) from the fill bar onward (engine `stop: 4.0`, Pine indicator/strategy/dashboard, emulator).
   It was never hit in 2015-26, so the results are identical, but it covers an entry-day crash. In the strategy file
   it is attached at entry via `strategy.exit(loss=…)`.
4. **Intraday flicker:** BUY/SELL can appear while the daily bar is still forming. Unconfirmed signals now show as faded
   "BUY?" / "SELL?". Only the confirmed ones count (alerts already fired once per bar close).
5. **Threshold in logit units → "Min breakout quality %"** in all three files, so it can be read directly. The table
   shows quality only on breakout days ("no breakout today" otherwise).
6. **Model refresh was manual and error-prone:** new `python -m indicator_lab.export_pine` refits the model and writes it
   into all three v3 files (`--check` verifies sync; `tests/test_pine_model_sync.py` now covers the dashboard too).
   While building it, a first version truncated a file before reading it (open-for-write evaluated first). It was
   caught immediately and restored from git, and the tool now renders every file before writing any.
- Verification: 407 tests pass (a new test crashes a bar right after entry and checks that engine and Pine logic stop
  out at the same price). 102-ticker parity holds (0 unexplained differences; 6 of ~3,250 signals differ only through
  `ta.percentrank`). All three Pine files compile.

---

## Session 6 (2026-10-21, autonomous) — more searching, against v3.1

New safeguard: `data.LOCKBOX2`, 53 never-used names (AMP, AZO, BKNG, CME, CTAS, …; ANSS dropped as delisted).
Baseline for comparisons: v3.1 (v3 signals + SPY parking). All runs include the entry-day stop.

### E52 — Entry-day stop on volatile names
Hit 4 times on BIG (~150 names) and 0 on LOCKBOX. BIG 10-slot Sharpe IS/OOS with vs without the stop: 1.43/0.55 vs
1.34/0.63, VOLATILE 1.18/0.75 vs 1.16/0.74, LOCKBOX identical. Four trades moving the BIG portfolio ±0.08 is
slot path-dependence (a freed slot changes every later pick), not an edge either way. **Kept for safety.**
Lesson: BIG 10-slot differences under ~0.1 are noise.

### E53 — Trail on ATR 10/20/50, chandelier from the highest close, skip big gap-ups at the fill
Composite (v3.1 1.23): ATR10 1.16 · ATR20 1.15 · ATR50 1.08 · trail from close 1.16 (3.5 ATR: 1.11) · skip if the
fill opens > 0.5/1/2 ATR above the signal close 1.16/1.22/1.24 (BIG OOS 0.88/0.49/0.55, not monotonic). **All rejected.**

### E54 — Pyramiding (one add-on unit per trade) vs CONTROLS
- Add on a new v3 signal once the trade is +1/+2/+3 ATR up: composite 1.25/1.23/1.32, OOS 1.18/1.21/1.25, BIG OOS
  0.84/1.00/0.92 (v3.1 0.55), VOLATILE OOS 0.83/0.98/0.85 (0.75). It looked like a big win.
- **Controls:** add unconditionally after 5/10/20 bars: composite 1.31/1.26/1.16, BIG OOS 0.91/0.91/0.78, VOL OOS
  0.79/0.92/0.99. Add when +2/+3 ATR without a new breakout: 1.18/1.29.
- **Verdict:** the controls do as well. The gain is not "adding to winners". It is simply more capital in v3 trades
  instead of SPY (a v3 trade beats SPY on average) plus more single-name concentration. **Not adopted as a rule.**
  Takeaway: when only a few v3 positions are open, a larger position per trade (up to ~2 slots) adds return at the
  cost of concentration. E50 (dynamic sizing) tested the clean version of that idea and was mixed.

### E55 — Non-linear quality model (squares and pairwise products of the 6 sign-stable features)
17 linear + 21 polynomial terms, l2 100/300/1000: composite 1.21/1.24/1.25 (v3.1 1.23), BIG OOS 0.62/0.58/0.51 (0.55),
VOLATILE OOS 0.68/0.64/0.65 (0.75). Polynomial on the 6 stable features only: 1.23, BIG 0.51, VOL 0.67.
**Rejected.** The linear model is as good on DEV/HOLD and better on the volatile names.

### E56 — How much of "volatile names work better" is real edge vs. just bigger swings? (all ~150 names, v3 trades)
| 1-year mean ATR% at signal | ≤1.5 | 1.5–2 | 2–2.5 | 2.5–3 | 3–4 | >4 |
|---|---|---|---|---|---|---|
| avg trade 2015-20 / 2021-26 | +0.9 / +0.4% | +1.1 / +0.6% | +2.6 / +0.8% | +2.6 / +1.2% | +3.2 / +1.6% | +15.9 / +2.5% |
| avg in risk units (R = 4×ATR) 2015-20 / 2021-26 | 0.19 / 0.08 | 0.16 / 0.08 | 0.30 / 0.08 | 0.23 / 0.10 | 0.23 / 0.12 | 0.72 / 0.11 |
- Most of the % difference is scale: volatile names move more, so trades are bigger in both directions. The edge per
  unit of risk rises only modestly in 2021-26 (0.08 → 0.10–0.12 R from about 2.5% ATR). 2015-20 is flat except the
  >4% bucket (the NVDA/AMD booms).
- **Pine:** a new table row, "Volatility 1y (ATR%)", marks ≥2.5% "good fit", 1.5–2.5% "ok fit" and <1.5% "weak fit".
  This is guidance, not a filter: E30 showed a hard filter does not improve the portfolio.

### E57 — Live model trained on the broad universe (DEV+EXTRA+VOLATILE, ~135 names) instead of DEV only
HOLDOUT 2021-26 5-slot Sharpe 1.11 vs 1.03 (better); LOCKBOX 10-slot 2021-26 0.65 vs 0.79 (worse). Not clearly better,
so the Pine model stays DEV-trained.

### E58 — Dual-momentum parking (idle cash in the stronger of SPY/QQQ(/IWM) if above SMA200)
Composite 1.15 (126d) / 1.11 (63d) / 1.10 (with IWM) vs 1.23 for plain SPY>SMA200. **Rejected.**

### E59 — Correlation guard (skip a signal that is >0.8/0.7/0.6 correlated over 60 days with a holding)
Mean 5-slot Sharpe 1.24/1.22/1.24 (1.23). BIG and LOCKBOX move both ways (LOCKBOX OOS 0.75/0.66/0.60 vs 0.79).
**Rejected.**

### E60 — How certain are the main conclusions? (circular block bootstrap, 21-day blocks, 2,000 resamples, one slot path)
| | DEV 15-20 | DEV 21-26 | HOLD 15-20 | HOLD 21-26 | LOCK1 15-20 | LOCK1 21-26 |
|---|---|---|---|---|---|---|
| P(v3 Sharpe > v2 Sharpe) | 0.26 | 0.42 | 0.78 | 0.29 | 0.17 | **1.00** |
| P(v3.1 Sharpe > B&H) | 0.60 | 0.47 | 0.67 | 0.45 | 0.26 | 0.41 |
| P(v3.1 return > B&H) | 0.15 | 0.21 | 0.47 | 0.48 | 0.04 | 0.22 |
| P(v3.1 max drawdown smaller than B&H) | **0.91** | **0.79** | **0.82** | 0.48 | **0.78** | 0.51 |
| actual MaxDD v3.1 vs B&H | −18.7 vs −32.7% | −18.3 vs −26.5% | −18.2 vs −29.3% | −19.0 vs −24.2% | −24.1 vs −41.7% | −33.4 vs −37.4% |
- **Honest bottom line:** the version-to-version gains (v2 → v3) are real on average across universes but not
  statistically clear in most single cells. v3.1 vs buy & hold is a coin flip on Sharpe and usually behind on raw
  return. The one robust property is **a much smaller drawdown**: smaller in all 6 cells, and with ≥78% confidence in
  4 of 6. What this indicator really offers is buy-and-hold-like risk-adjusted returns with a smoother ride, not a
  way to beat the market on return.

## Status (end of session 6)
v3.1 remains the best version. Since E18, ~40 further idea families (signals, filters, exits, sizing, ranking, models,
portfolio overlays) have been tested. Only the SPY parking rule (E48) passed every check. New tests now mostly measure
noise, which E52 and E60 quantify.

---

## Session 7 (2026-10-22) — reliability round (no new edge; the signal logic only changes where a step says so)

Test tickers for before/after: NVDA, AAPL, JPM (+ KO and ASML.AS for parity). Chart statistics come from
`indicator_lab/pine_sim.py`, a bar-by-bar simulation of the Pine indicator with a switch per step. Pine was
compile-validated after every change; it cannot be run on real bars from here.

### R1 — Pine ↔ Python feature parity (`indicator_lab/pine_parity.py`, `pine_ta.py`)
`pine_ta.py` re-implements TradingView's `ta.*` exactly (RMA seeded with an SMA, percentrank over the PREVIOUS n values,
population stdev, …). `pine_parity.py` computes all 17 features plus score and quality as the Pine code defines them
and compares them with `meta.feature_frame` (the training features) on 20 random dates per ticker. Max |diff| in z-units:
- **US, original Pine:** all < 0.05 z after warm-up (worst `bbw_pct` 0.014 z, from percentrank: previous 252 vs window
  incl. current). `ta.stdev` biased = pandas `ddof=0`: identical. Score diff ≤ 0.0006 logit.
- **Early history (first ~400 bars of PLTR/COIN/RIVN/ABNB), original Pine:** `atr_pct` up to **14.6 z**, `rsi14` 3.8 z,
  `brk_atr` 5.6 z, `range_atr` 2.0 z. `ta.rma` seeds with an SMA, but pandas `ewm(adjust=False)` (the training) seeds
  with the first value. The gap only dies out after a few hundred bars, and ATR also drives the stops. `dist52` and
  `bbw_pct` were na for 52/153 bars where Python already had values (`min_periods` 200/100).
- **Fix (Pine now follows Python):** `f_rma_py` reproduces pandas' ewm for ATR and RSI; `dist52` uses a ≤252-bar high
  with ≥200 bars; `bbw_pct` is a rank incl. the current bar (average ties, ≥100 values) via `f_rank_incl`. Result:
  **US 0.000 z on every feature, including the first 400 bars after an IPO.**
- **Remaining, explained:** (a) Python fills RSI with 100 for the first 14 bars; Pine keeps na. (b) Python computes SPY's
  SMA200/ROC63 on the *ticker's* bars, so `spy_up` = 0 for a new listing's first 200 bars, a Python quirk. Neither
  can produce a signal (SMA200 trend needs 200 bars). (c) **Euronext (ASML.AS):** `spy_roc63` 0.35–0.69 z and
  `spy_up` up to 5 z, quality up to 1.7–3.2 %-pt. Pine deliberately uses the PREVIOUS SPY close outside New York;
  following Python there would mean using a close that doesn't exist yet at the Euronext close (look-ahead). Python
  never trained or tested on non-US stocks.
- **Debug mode:** input "Debug: show the raw model features in the Data Window" plots all 17 features + the logit score.
- **Structure:** the feature/model/debug code is now generated (`python -m indicator_lab.export_pine`) into
  `// <<GEN:...>>` regions of all three v3 files. `tests/test_pine_model_sync.py` fails if a region drifts.
- **Effect on NVDA/AAPL/JPM:** none (identical trades). These have history since 2012, so the warm-up differences are long gone.

### R2 — OOS chart statistics (walk-forward fits in Pine)
- `meta.export_yearly()` → `pine/v3_model_yearly.json`: the 12 walk-forward fits (2015–2026) the research engine used,
  each trained only on DEV breakouts whose trade closed before 1 Jan of that year (coefs, mu/sd, threshold, n_train).
- `export_pine.py` generates `scoreYear = switch year(time)` with one arm per fit + `thrYear`; bars after TRAIN_END
  (2026-10-20, the last bar the final fit saw) use the final fit. Generated, never by hand; a test evaluates every
  generated expression against the JSON. One term is skipped on purpose: `spy_up` in the 2015 fit was constant in
  training (sd 1e-9, weight exactly 0), so it contributes nothing in Python either (instead of dividing by 0.000000).
- `minQual` keeps its meaning: on OOS bars the same shift vs the final threshold is applied to that year's threshold.
- The indicator's state machine is now a function `f_machine(entryOk)` that runs twice with its own `var` state:
  with the OOS quality (the signals you see) and with the in-sample quality (statistics only). Table row is
  **"OOS since 2015"**; input "Also show the in-sample statistics" adds an **"In-sample (final fit) — optimistic"** row.
- Strategy and dashboard use the same OOS score for their signals (same generated MODEL region).
- Pine note: `switch` cannot sit inside a ternary; it is generated as its own variable. Compile-validated.

| ticker | in-sample (final fit) n / win / PF / avg | OOS (walk-forward) n / win / PF / avg | PF OOS − IS |
|---|---|---|---|
| NVDA | 38 / 57.9% / 5.30 / 12.4% | 37 / 59.5% / 5.87 / 13.1% | +0.56 |
| AAPL | 32 / 59.4% / 4.24 / 5.7% | 29 / 58.6% / 4.27 / 5.1% | +0.03 |
| JPM  | 36 / 44.4% / 2.31 / 2.3% | 36 / 44.4% / 2.26 / 2.2% | −0.05 |

Wider check (all trades pooled): DEV 15 tickers IS PF 2.37 → OOS 2.45; HOLDOUT 16: 1.84 → 1.97; LOCKBOX 50: 1.87 → 1.86.
**Conclusion:** the in-sample statistics were NOT materially inflated: the model is heavily regularised (l2 100) and
only removes the weakest 25%, so the final fit and the yearly fits pick nearly the same trades. The OOS row is
still the honest one to show, and it is now the default.

### R3 — inputs pinned to the model
- New generated region `TRAIN` (from `v3_model.json "params"`, now exported by `meta.export_final`): `TRAIN_N 20`,
  `TRAIN_M 20`, `TRAIN_TRAIL 4`, `TRAIN_IBS 0.7`, `TRAIN_TREND 200` (training also used the SMA200 trend filter), and
  `FINAL_THR 0.393009` with its source (25th percentile of the final fit's predictions on its own 3633 training
  breakouts, keep 0.75). The inputs default to these constants; `minQual` defaults to `FINAL_THR * 100` (39.3009).
- `brkAtr` used a hard-coded 20: now `TRAIN_N`. It is a feature definition and must stay at the training lookback even
  if the user changes n (before, it was also fixed at 20, so behaviour is identical; it is now explicit and tied to the JSON).
- With the model on and n/m/trail/ibsMin/trendLen ≠ training values: a yellow row
  "⚠ model getraind op n=20/m=20/trail=4/ibs=0.7/SMA200: quality + stats not valid for these settings"
  (indicator table; a one-cell table in the strategy; a merged row in the dashboard).
- Effect on NVDA/AAPL/JPM at default settings: none (identical trades); it only warns when settings drift.

### R4 — missing data: no silent imputation
- Pine `f_z` no longer wraps in `nz()`: if any of the 17 features is na, score and quality are na and `qualityOk` is
  false, so no BUY. The table shows "te weinig historie (x/252 bars)" (or "model feature missing" after 252 bars,
  e.g. a data gap; the Debug input shows which one). The dashboard shows "n/a (history)". A na quality no longer
  draws a "rejected breakout" cross.
- **Did Python do the same?** Training: yes, `candidate_table(...).dropna()` drops rows instead of imputing, and it
  dropped **0 of 3656** DEV candidates (the SMA200 trend condition already needs 200 bars, by which time every feature
  exists). Prediction: no. `YearlyModels.prob/take` use `np.nan_to_num(z)` (a missing feature counts as the training
  mean). But that never mattered: **0 imputed features among 2035 DEV, 1870 HOLDOUT, 5017 LOCKBOX, 6129 LOCKBOX2 and
  4690 VOLATILE signals taken since 2015**. Python was left as is (changing it changes no trade).
- Effect (pine_sim, na-block on vs off): NVDA/AAPL/JPM 102 → 102 trades, VOLATILE 1553 → 1553, LOCKBOX 1524 → 1524,
  identical returns. It only protects charts with short history or gaps.

### R5 — honest statistics: half-profit booked 50/50, drawdown and holding time per trade
- With `tpMult > 0` the chart statistics booked the WHOLE position at the final exit, although the indicator tells you
  to sell half at the target. Now `f_machine` books the half at the target (or the open on a gap above it, each half
  with its own exit cost): trade return = 50% half + 50% rest.
- New table row **"OOS per trade"**: max drawdown inside the trade (peak since the fill to a later low; intrabar order
  unknown, so a bar's high is assumed to come before its low, i.e. conservative), worst and average, plus the
  average holding period in bars. Comment added: when stop and target are both touched on one bar, the stop wins.
- `pine_sim` mirrors this exactly (`half_book`, `stats()["mae"/"dd_avg"/"bars"]`).

| ticker | tpMult 4, before: n / win / PF / avg | tpMult 4, after (50/50): n / win / PF / avg | default tpMult 0 (unchanged) |
|---|---|---|---|
| NVDA | 37 / 59.5% / 5.87 / 13.1% | 37 / 59.5% / **4.41 / 9.2%** | 37 / 59.5% / 5.87 / 13.1% |
| AAPL | 29 / 58.6% / 4.27 / 5.1% | 29 / 58.6% / **3.59 / 4.1%** | 29 / 58.6% / 4.27 / 5.1% |
| JPM  | 36 / 44.4% / 2.26 / 2.2% | 36 / 44.4% / **2.05 / 1.9%** | 36 / 44.4% / 2.26 / 2.2% |

New row values (default settings): max drawdown in trade worst / avg, avg hold: NVDA −19.7% / −11.5% / 36 bars,
AAPL −11.5% / −7.2% / 38 bars, JPM −8.5% / −6.2% / 37 bars. Taking half at +4 ATR costs PF on all three: the
table used to hide that.

### R6 — strategy companion with identical fills (`swing_v3_strategy.pine`)
- The strategy already used next-open market entries, `strategy.exit(stop=...)` for the trail, the entry-bar
  protective stop via `loss`, `strategy.close` on close < m-day low (fills next open), commission 0.1%,
  `process_orders_on_close=false`, and no re-entry on an exit bar; it now also shares the OOS model (R2), the na rule
  (R4) and the settings warning (R3). Added `margin_long = 0` (no margin call when the next open gaps above the signal
  close with 100% of equity) and a header documenting every fill rule. `strategy()` only takes constants, so
  commission cannot follow the `costPct` input: the header says to change both together.
- **Verification** (TradingView cannot be run from here): `pine_sim.run_strategy` emulates the strategy script as an
  order book under TradingView's broker rules, independently from `pine_sim.run` (the indicator's state machine) and
  from the research engine (`evaluate.run_ticker(BEST)`).

| ticker | indicator table n / avg | strategy (TV rules) n / avg | Python engine n / avg | same entry+exit dates |
|---|---|---|---|---|
| NVDA | 37 / 13.061% | 37 / 13.074% | 37 / 13.061% | all 37 |
| AAPL | 29 / 5.136% | 29 / 5.141% | 29 / 5.136% | all 29 |
| JPM  | 36 / 2.235% | 36 / 2.237% | 36 / 2.235% | all 36 |

  Tolerance asked: 1 trade / 0.1 %-pt. Result: 0 trades, ≤ 0.013 %-pt (TradingView takes commission on the traded
  value on both sides; the engine divides by entry × (1 + cost)). The indicator table and the engine agree exactly.
  `tests/test_pine_sim.py` locks this in (AAPL, JPM).
