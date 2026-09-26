# Research round 4 — pre-registered hypotheses (written 2026-09-26, before any result)

## Data and cells (fixed before looking)
- 966 US stocks (S&P 500 + S&P MidCap 400 + scanner lists), daily, split+dividend
  adjusted, 2007-01 → 2026-09 (`research/bigdata.py`). Benchmarks SPY/QQQ/IWM/VIX/sector ETFs.
- Tickers split once, seeded, stratified by sector: RESEARCH (486) / HOLDOUT (480).
- Time split: ≤ 2021-12-31 / ≥ 2022-01-01.
- Cells: DEV = research × ≤2021 (all exploration happens here) · VAL-T = research × ≥2022 ·
  VAL-U = holdout × ≤2021 · FINAL = holdout × ≥2022 (looked at ONCE, at the very end).

## Common rules
- Signal on the close of day t, entry at the open of t+1 (+0.05% slippage), no look-ahead.
- Eligible on day t: close ≥ $5, 20-day average dollar volume ≥ $10M, ≥ 260 bars of history.
- Stop 2.5 ATR(14) below the entry (checked from the entry bar itself); exits: time exit at
  the close after H ∈ {3, 5, 10, 20} bars; one open trade per ticker per hypothesis.
- Metric: R per trade; EXCESS R = trade R minus the mean R of ALL eligible days of the same
  ticker in the same calendar month with the same exit (a same-stock, same-time baseline);
  t-stat computed on day-averaged excess (trades on the same day are not independent);
  share of calendar years with positive excess; results split by market regime.
- A hypothesis "passes DEV" if excess > 0 with t ≥ 3 and ≥ 70% of DEV years positive.

## Hypotheses (signal on day t)
Short-term reversal / dips
- H01 LEADER_DIP: composite momentum rank ≥ 80, 5-day move ≤ −1 ATR
- H02 LEADER_DIP_DEEP: H01 and close ≤ EMA21 − 1 ATR
- H03 IBS_UPTREND: close > SMA200 and IBS = (close−low)/(high−low) < 0.15
- H04 RSI2_UPTREND: close > SMA200 and RSI(2) < 10
- H05 DOWN3_UPTREND: 3 consecutive lower closes and close > SMA200
- H06 GAPDOWN_REVERSAL: open < prior low − 0.5 ATR, close > open, close > SMA200
- H15 CAPITULATION: 5-day move ≤ −3 ATR and volume ≥ 2× 20-day average
- H16 LEADER_PANIC_DAY: momentum rank ≥ 80 and 1-day move ≤ −2 ATR
Momentum / breakout
- H07 HIGH_52W: close at a 252-day closing high
- H08 BREAKOUT_20D_VOL: close at a 20-day closing high and volume > 1.5× average
- H09 MOMENTUM_TOP_DECILE: momentum rank ≥ 90 (sampled every 5th day)
- H10 POCKET_PIVOT: up day with volume > max down-day volume of the prior 10 days, close > SMA50
- H11 SQUEEZE_BREAKOUT: Bollinger width in the lowest 10% of 120 days (at t−1) and close > 20-day high
- H12 NR7_INSIDE_UPTREND: narrowest range of 7 days and inside day, close > SMA50 (entry next open)
Relative strength / sector
- H13 RS_LEADS_PRICE: stock/SPY ratio at a 63-day high while close is ≥ 1 ATR below its 63-day high
- H14 SECTOR_LEADER_DIP: stock's sector ETF in the top 3 by 1-month return and 5-day move ≤ −1 ATR
Event proxies / calendar
- H17 TURN_OF_MONTH_LEADERS: last trading day of the month and momentum rank ≥ 80
- H18 GAP_UP_DRIFT: gap up > 2 ATR on volume ≥ 3× average, close in the top 25% of the day's range
- H19 BASELINE: every 5th eligible day (the unconditional drift, for reference)

## Afterwards (only for hypotheses that pass DEV)
Confirmations, exits and stops refined on DEV only; parameter neighbourhoods; then VAL-T and
VAL-U; the FINAL cell once; then a portfolio simulation (one account, max positions, daily
ranking) and a block-bootstrap Monte Carlo.

---

# Round 4b — earnings-event hypotheses (written 2026-09-26, before the earnings data was looked at)

Motivation (from DEV so far, recorded before 4b): price-only dip signals carry a real but
small edge; within a day, which dip you pick barely matters (per-feature spread ≈ ±0.01R),
while the market regime dominates. A different information source is needed, so we test
the best-documented swing effect in the literature: post-earnings drift.

## Data
- Earnings dates, time of day and EPS surprise % from Yahoo (`research/earnings_data.py`).
- Same stocks, same cells (DEV/VAL-T/VAL-U/FINAL), same common rules and metrics as above.
  Extra hold: 40 bars (drift is documented over 1–3 months).

## Reaction day E (fixed rule)
- report hour ≥ 16:00 NY → E = next session; hour < 09:30 → E = the report date's session;
  any other hour (incl. unknown 00:00) → whichever of {date, next session} has the larger
  |open gap| in ATR.
- EAR = (close_E − close_{E−1}) / ATR_{E−1}  (earnings-announcement return in ATR units).
- All signals are on the close of E or later; entry is the next open (the gap is never traded).

## Hypotheses
- E01 EARNINGS_GAP_UP: EAR ≥ +2 and close_E in the upper half of E's range
- E02 SURPRISE_POSITIVE: surprise ≥ +10% and EAR ≥ 0
- E03 SURPRISE_AND_GAP: surprise ≥ +10% and EAR ≥ +1
- E04 LEADER_EARNINGS_FLUSH: EAR ≤ −2 and momentum rank (at E−1) ≥ 80  (overreaction fade)
- E05 PRE_EARNINGS_RUNUP: enter the open 5 sessions before E, exit at the close of E−1
  (only for reports whose date was already in the data ≥ 10 sessions earlier is NOT checkable
  with this data → accepted look-ahead on the date only; flagged as such)
- E06 DRIFT_AFTER_HOLD: E03 and close_{E+5} ≥ close_E → signal on the close of E+5
- E07 NEGATIVE_SURPRISE (sanity, expected < 0): surprise < 0 and EAR ≤ −1
Pass criterion unchanged (excess > 0, t ≥ 3, ≥ 70% DEV years positive).

---

# Round 4c — findings that changed the plan, and the market-state hypothesis (written before VAL/FINAL)

1. **Baseline bias found in our own metric.** The same-stock/same-month baseline contains the
   event's own move (a dip lowers that month's mean, a breakout raises it), so it biased dip
   setups UP and breakout/earnings-gap setups DOWN. Re-scored against a same-day
   cross-sectional baseline (`engine2.day_baseline`: mean R of all eligible stocks entering
   the same day), NO price or earnings hypothesis (H01–H18, E01–E07) beats a random stock bought
   the same day (|excess| ≤ 0.02R; breakouts H08 significantly negative, t −5).
2. The dips' absolute edge is therefore **market timing**: they fire after market selloffs.
   A random stock bought in DEV when SPY > SMA200, VIX ≥ 15 and SPY's 5-day return < 0 earned
   R10 +0.156 / R20 +0.255 (85% of years positive) vs ≈ 0.01–0.06 in the other bull states.
3. Cross-sectional characteristics (same-day quintiles, DEV) add only ±0.02–0.07R/20d; the
   most consistent: less extended (EMA21/SMA50 distance, RSI14), lower ATR%, further below the
   52-week high → slightly better (≈70% of years).

## M1 MARKET_STATE (pre-registered here; tested on periods never used for its choice)
State "GO" on the close of day t: SPY close > SMA200(SPY) AND VIX close ≥ 15 AND
SPY close < SPY close 5 sessions earlier.
Prediction: SPY forward 10- and 20-session returns (entry next open) are higher in GO than in
all other days, in each of: 1993–2007 (never looked at), 2022–2026 (VAL-T time span), and for
the random-stock basket in VAL-T, VAL-U and FINAL. Neighbourhood check: VIX 13–20, lookback 3–10.

---

# Round 5 — technicals only, three new angles (written 2026-09-26, before any round-5 data was looked at)

Metric for everything below: excess R vs the SAME-DAY, SAME-HALF random eligible stock
(`engine2.day_baseline` logic); pass = excess > 0, t ≥ 3, ≥ 70% of DEV years positive, then
the same sign in VAL-T, VAL-U and finally FINAL. Entry next open, 2.5 ATR stop, time exits.

## A. Small caps (S&P SmallCap 600, new dataset `small.pkl`, own seeded research/holdout split)
Less-followed stocks may keep technical inefficiencies. Run H01–H19 unchanged, holds 5/10/20/40.

## B. Longer horizons (both universes), holds 20/40/60
- H07 HIGH_52W, H09 MOMENTUM_TOP_DECILE, H13 RS_LEADS_PRICE re-run at 40/60 bars
- L01 TREND_TEMPLATE (weekly sample): close > SMA50 > SMA150 > SMA200, SMA200 higher than 21
  sessions ago, close ≥ 1.25 × 52w low and ≥ 0.75 × 52w high, momentum rank ≥ 70
- L02 GOLDEN_CROSS: SMA50 crosses above SMA200
- L03 EMA200_RECLAIM: close crosses above EMA200 after ≥ 20 sessions below it
- L04 WEEKLY_26W_BREAKOUT: last session of the week, close ≥ highest close of the prior 126 sessions
- L05 EMA_STACK_PULLBACK: EMA9 > EMA21 > EMA50 > EMA200 and low ≤ EMA21 ≤ close
- L06 TIGHT_NEAR_HIGH: close ≥ 0.95 × 52w high and Bollinger-width percentile (120d) ≤ 0.20

## C. The user's own multi-timeframe style (1h bars → 4H bars 09:30/13:30 NY; ~2 years only)
Daily signal on day t (entry next open):
- M01 D200_HOLD_4H200_BREAK: daily close > daily EMA200 AND a 4H bar on day t closes above the
  4H EMA200 after ≥ 6 consecutive 4H closes below it
- M02 same 4H break while the daily close < daily EMA200 (control: "not holding the DTF 200")
- M03 D200_RETEST: daily close within 1 ATR above the daily EMA200 AND last 4H close > 4H EMA200
Only ~2 years exist, so cells are the ticker halves only (research = dev, holdout = validation);
low power is accepted and reported.
