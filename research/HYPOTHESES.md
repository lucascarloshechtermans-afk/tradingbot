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

---

# Round 6 — complete trading systems (written 2026-09-26, parameters fixed from the literature before running)

Goal: compare whole systems the user could run, not single signals. All execute at the next
open, 10 bp cost per side, uninvested cash earns the 13-week T-bill (^IRX). Reported for
1999–2007 (ETF systems only), 2008–2021 and 2022–2026; stock systems also per ticker half.
Benchmarks: SPY buy-and-hold and SPY with the 200-day filter. No parameter is tuned; the
listed neighbours are only reported as robustness.

- S1 CURRENT SCANNER: LEADER DIP, 10-session hold, 0.5% risk (0.25% below SPY 200d), max 10.
- S2 DIP + TREND: LEADER DIP only while SPY > 200d, 20-session hold.
- S3 MOMENTUM PORTFOLIO: month-end, top 20 of the eligible universe by 12-1 month return,
  equal weight, invested only if SPY > 200d SMA (else cash). Neighbours: top 10/50, 6-1 month.
- S4 SECTOR ROTATION: month-end, the 3 of the 9 original sector SPDRs with the best average
  of 3/6/12-month return, each held only if above its own 200d SMA (else that third in cash).
  Neighbours: top 2/4.
- S5 TREND BREAKOUT: close at a 50-day closing high while SPY > 200d; initial stop 2.5 ATR;
  exit when the close falls below the 20-day lowest close; 0.5% risk per trade, max 20
  positions, heat ≤ 10%. Control: the same exits on random entries.
- S6 INDEX RSI(2): SPY (and QQQ) close > SMA200 and RSI(2) < 10 → buy next open; sell next
  open after a close > SMA5.

---

# Round 7 — breakouts inside momentum leaders (written 2026-09-29, before running)

Question from the user: they trade breakouts. Plain breakouts were ≤ random (rounds 4–5).
Does a breakout help when it happens in a stock that is already a momentum leader?

Leader on day t = top 50 of the eligible universe by 12-1 month return (close t−21 / close t−252).
Only while SPY > its 200-day SMA. Entry next open, initial stop 2.5 ATR.
- B1 LEADER_50D_BREAKOUT: first close above the highest close of the prior 50 sessions.
- B2 LEADER_20D_BREAKOUT_VOL: close above the prior 20-session closing high, volume > 1.5× 20d avg.
Exits: (a) trend exit — next open after a close below the lowest close of the prior 20 sessions;
(b) fixed 20-session time exit.
Controls, same exits, same days/regime:
- C1 a random leader (top 50) that is NOT breaking out — does the breakout TIMING add anything
  over simply owning a leader?
- C2 a random eligible stock (same-day baseline).
Pass: B beats C1 by > 0 with t ≥ 2 in DEV (research ≤2021) and keeps the sign in VAL-T, VAL-U
and FINAL. Then it goes into the scanner as a breakout setup; otherwise the scanner says so.

---

# Round 10 — robustness and refinements of the dip-free plan (written 2026-09-30, before running)

Rule for adopting any change: it must beat the current default in DEV (research half,
2008–2021) AND not be worse in any of VAL-T, VAL-U, FINAL (Sharpe for the momentum book,
mean R per trade and one-account CAGR/maxDD for breakouts). Otherwise the default stays;
neighbouring values are reported to show whether the default sits on a plateau.

Momentum book (month-end unless stated, SPY > 200d filter):
- M-N: top 10 / 20 (default) / 30
- M-BUF: buffer — keep a holding while it is in the top 40, buy new names from the top 20
- M-SEC: at most 5 names per GICS sector
- M-VOL: inverse-volatility weights (63-day)
- M-2W: rebalance every 10 sessions instead of monthly

Leader breakout (trailing exit, one open trade per ticker):
- leader list top 30 / 50 (default) / 100
- breakout lookback 20 / 50 (default) / 100 sessions
- trailing exit 10 / 20 (default) / 50 sessions
- initial stop 2 / 2.5 (default) / 3.5 ATR

## Round 10 results (momentum + breakout parameters)
No variant beat the defaults in DEV and in every validation cell; defaults kept
(top 20 monthly; leader top 50, 50-day breakout, 20-day trailing exit, 2.5 ATR stop).
A 50-day trailing exit raised R per trade in all cells but also max drawdown in all cells.

# Round 10b — market filter and volatility targeting for the momentum book (written before running)
Filters (evaluated at each month-end): F0 none · F1 SPY > 200d SMA (default) · F2 SPY > its
10-month SMA of month-end closes · F3 SPY 12-month return > T-bill 12-month yield (absolute momentum).
Vol targeting (on top of F1): V1 scale the book to 20% annualised volatility using the
book's own 126-day realised volatility (weight ≤ 1, no leverage) · V2 same with 63 days.
Same adoption rule as round 10 (Sharpe, all four cells).

## Round 10b results
Vol targeting (20%, 63d) cut max drawdown in all four cells but tied the default Sharpe in
DEV → not adopted (offered as an option). Filters F0/F2/F3 not adopted.

# Round 11 — execution and diversification, technicals only (written 2026-09-30, before running)
- X1 CLOSE ENTRY: leader breakouts bought at the CLOSE of the breakout day (+0.05% slippage;
  in practice a market-on-close order when price is above the level ~10 min before the close)
  instead of the next open. Same stop distance (2.5 ATR from the fill) and trailing exit.
  Compare R per trade and one-account CAGR/maxDD per cell with the next-open default.
- E1 ETF LEADER BREAKOUTS: universe = 24 ETFs (SPY QQQ IWM DIA MDY EFA EEM TLT IEF SHY GLD DBC
  VNQ + 11 sector SPDRs). Leader = top 8 by 12-1 month return; 50-day closing-high breakout;
  NO SPY filter (bonds/gold must be able to trade in bear markets); 2.5 ATR stop; 20-day
  trailing exit; 0.5% risk, max 8. Periods 2006–2014 / 2015–2021 / 2022–2026. Compared with
  (a) random entries in the same ETFs with the same exits and (b) as a third sleeve next to
  the stock plan (does it lower drawdown / raise Sharpe?).

## Round 11 results
- X1 close entry: one-account CAGR higher and max drawdown lower in all four cells
  (DEV 7.4 vs 7.2%, VAL-T 19.2 vs 17.1%, VAL-U 13.0 vs 12.2%, FINAL 13.4 vs 10.9%); R per trade
  mixed. Adopted as the recommended execution (buy near the close when above the level).
- E1 ETF leader breakouts: better than random ETF entries in 2006-14 and 2022-26, worse in
  2015-21; 1-4%/yr at account level. Not adopted.

# Round 12 — improving the momentum-only book (written 2026-09-30, before running)
Default: month-end top 20 by 12-1 return, SPY > 200d at month-end, equal weight.
Adoption rule as round 10 (Sharpe better in DEV, not worse in VAL-T / VAL-U / FINAL).
Scores: S1 6-1 month · S2 composite 3/6/12 months (skip 1) · S3 12-1 divided by 252-day vol ·
S4 close / 252-day high (52-week-high proximity) · S5 average rank of 12-1 return and share of
up days over 12 months ("smooth momentum").
Rules: R1 buy only names above their 50-day SMA at the rebalance · R2 daily crash exit: SPY
closes below its 200d → whole book to cash at the next open until the next month-end ·
R3 per-stock exit: close below its 20-day lowest close → that slot to cash until month-end ·
R4 two tranches (half rebalanced at month-end, half mid-month, ~10 sessions later).

# Round 13 — resistance and chart patterns as a filter (written 2026-09-30, before running)
The user sees picks running into resistance and wants proper chart analysis. Test on:
(a) every momentum pick (month-end top 20 per ticker half, SPY > 200d), outcome = return to the
next month-end MINUS the average of that month's 20 picks (same-month comparison);
(b) every leader breakout (trailing exit), outcome = R.
Features at the signal close (data up to that close only; analysis.chart_read.find_zones on
the last 500 bars, analysis.patterns.detect_patterns):
- ROOM = (low of the nearest resistance zone above the close − close) / ATR; "open sky" if none.
- H1 AT_RESISTANCE: ROOM ≤ 1 ATR → predicted worse than the other picks.
- H2 OPEN_SKY: no zone above → predicted better.
- H3 PATTERN: a bullish pattern whose trigger is within 5% above the close or was cleared in the
  last session → predicted better.
Pass: sign as predicted with |t| ≥ 2 in DEV (research ≤2021) and the same sign in VAL-T, VAL-U,
FINAL. A passing feature becomes a rule (skip / replace the pick); otherwise it is shown on the
dashboard as information only.

# Round 14 — NICHE momentum: does it work, and do the two filters help? (written 2026-10-04, before running)
The user wants lesser-known names (e.g. CDNA) instead of SNDK / MU. Live rule: month-end top 10 by
12-1 return over US common stocks outside the S&P 500, price >= $10, >= $10M/day, SPY > 200d at
month-end, equal weight; niche-only filters F1 close >= 0.75 x 252-day high, F2 best single day
< 1/3 of the 12-1 month log gain.
Data: today's NASDAQ Trader listings (~5,100 names), daily since 2010 (yfinance). Two biases, in
opposite directions: delisted names are missing (flatters every small-cap result, raw momentum
the most: it buys run-ups that later collapse), and today's S&P 500 members were often small
before (excluding them historically would remove the biggest winners). So "niche at date t" is
defined point-in-time: NOT among the 500 largest by 20-day dollar volume at t (proxy for the
S&P 500). Costs 0.30% per side for niche books (wider spreads), 0.10% for the large-cap book.
Periods: DEV 2011-07..2018-12 · VAL 2019-01..2022-12 · OOS 2023-01..2026-09.
Variants: N0 raw niche top 10 · N1 + F1 · N2 + F2 · N3 + F1 + F2 (live default) · N4 = N3 top 20.
Benchmarks: B0 SPY · B1 equal-weight all eligible niche stocks (the "random niche stock"),
monthly · B2 the same 12-1 top 20 over the 500 largest (large-cap momentum, same data).
Questions and pass rules (Sharpe, per period):
- Q1 Is niche momentum better than a random niche stock? N3 Sharpe > B1 in DEV, and not lower in
  VAL and OOS → otherwise the niche list is labelled "no edge" on the dashboard.
- Q2 Do the filters help? N1, N2, N3 each vs N0: Sharpe higher in DEV and not lower in VAL / OOS
  → filter kept; otherwise removed (default off).
- Q3 Top 10 vs top 20 (N3 vs N4): the one with the higher DEV Sharpe that is not lower in VAL /
  OOS; tie → top 20 (more spread).
Because of survivorship, absolute CAGRs are not trusted; only same-data comparisons count, and
even those favour N0 (it would have held more of the missing collapses).
- Q4 Do the dashboard's chart warnings matter? For every pick of B2 (large-cap top 20) and N3
  (niche top 10) at each month-end with SPY > 200d, run ta.engine.analyze on the daily data up to
  that close (light mode, same code as the live dashboard) and record the warnings of
  ui/portfolio.chart_flags: W1 resistance zone within 1 ATR above, W2 daily trend down,
  W3 trend exhausted/overextended, plus the 0-100 technical score. Outcome = return from the next
  open to the next month-end close MINUS the average of that month's picks of the same book.
  Pass: flagged picks worse with |t| >= 2 in DEV and the same sign in VAL and OOS (score: rank
  correlation > 0 with the same rule) → the warning becomes a rule (skip the name); otherwise the
  dashboard says the warning had no measurable effect.

## Round 14 results (Q1-Q3; Q4 below when run)
- Q1 FAILED: niche momentum (F1+F2, top 10) Sharpe 0.25 / 0.14 / 0.53 vs random niche
  0.44 / 0.25 / 0.16 (DEV lower) -> dashboard: niche list = VOLGEN (follow), "no edge".
- Q2: F1 vs N0 0.31>0.30, 0.40>-0.06, 0.19>-0.53 -> kept. F2 vs N0 0.26<0.30 -> off.
- Q3: N4 vs N3 DEV 0.30>0.25 but VAL 0.01<0.14; N3 lower in DEV -> undecided -> top 20.
- Q4 FAILED: no warning worse with |t| >= 2 in DEV. Large caps W1 resistance +0.69 / +1.04 /
  +1.29% (better, n.s.), W2 downtrend +0.62 / +0.85 / +0.22, W3 exhausted -0.15 / -4.95 / -0.75
  (DEV t -0.1); score IC 0.000 / -0.025 / +0.057. Niche: score IC +0.071 (t 2.2) / -0.084 / +0.094
  -> sign flips in VAL, fails. Dashboard: warnings grey, "no measurable effect".
- Post-hoc diagnostic (not pre-registered): the main rule on the 900 most traded stocks chosen
  point-in-time: 0.48 / 0.33 / 0.56; today's S&P members within it 0.60 / 0.93 / 1.14; the
  rest 0.43 / 0.10 / 0.07 -> the main list's edge is tied to today's S&P membership.

# Round 15 — the main list with POINT-IN-TIME S&P 500 membership (written 2026-10-04, before running)
Round 14 showed the main list's edge is tied to today's S&P membership. Point-in-time S&P 500
membership is rebuilt from Wikipedia's change table (revision of 2026-05-23, 395 changes; the
reconstruction gives 503-511 members every year since 2010, so it is near complete), undoing
every change after each month-end. Prices of names removed since 2010 are fetched from
yfinance; a removed ticker counts only if its data covers its removal date (a reused ticker
belongs to another company). Coverage = share of point-in-time members with prices at each
month-end, reported. Rule as live: month-end top 20 by 12-1 return, price >= $5, >= $10M/day,
SPY > 200d at month-end, equal weight, 0.10% per side. Periods as round 14.
- P0 today's S&P 500 members (hindsight) · P1 point-in-time S&P 500 members with prices.
- Survivorship estimate = P0 minus P1 (CAGR, Sharpe).
- Pass ("the momentum edge is real"): P1 Sharpe >= SPY Sharpe in at least 2 of the 3 periods.
  Fail → the dashboard and README say the plan did not beat SPY once hindsight is removed.
(S&P 400 has no usable change history here, so this tests the S&P 500 part only.)

## Round 15 results
- Coverage of point-in-time members with prices: DEV 75%, VAL 89%, OOS 96% (delisted names missing).
- SPY 0.80 / 0.66 / 1.40 · P0 today's members 0.98 / 0.67 / 1.33 · P1 point-in-time 0.48 / 0.22 / 0.78.
- FAILED (0 of 3 periods): the momentum edge does not survive point-in-time membership.
  Survivorship estimate P0-P1: 12.2 / 10.8 / 27.5 %-points CAGR per year.
