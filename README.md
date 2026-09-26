# Swing-Trade Scanner

A multi-signal swing-trading scanner for US stocks: technicals, price action,
market regime, sector rotation, relative strength, earnings-awareness, risk
management, and an event-driven backtester — with every score fully explainable
and no look-ahead bias in the backtesting engine.

## ⚠️ Not financial advice

This tool ranks and explains setups based on historical price/volume data. It
does **not** predict the future, does not guarantee profit, and a high score is
not investment advice. Read the "Reasons" and "Risks" for every setup before
acting on it, and never risk money you can't afford to lose.

## Optimization-phase audit (latest — supersedes the performance numbers further down)

An adversarial "why would this scanner pick bad trades tomorrow?" audit. Every
number below comes from full-universe backtests (134 tickers, 5 years), each
assembled from four merged chunk runs, and every change was checked separately
in both halves of the sample (split at the median entry date). Metrics are
reported **risk-adjusted** (R = $ P&L / $ risked at entry) and profit factor is
$-weighted — the older "% expectancy" ignores position sizing and flattered the
system.

### Bugs found in the validation pipeline (the old numbers were too optimistic)

- **Stops filled at the stop price even when the market gapped through it.**
  Now filled at the (worse) open. Alone this cut the reported profit factor from
  1.21 to 1.07.
- **15% of the score was fake in every backtest.** The backtester never passed
  SPY/sector data to the context, so `relative_strength` (weight 10) and `sector`
  (weight 5) were pinned at neutral for every trade. Fixed with walk-forward-safe,
  per-date benchmark truncation and sector ranks. The score is now monotonic:
  50-55 → -0.04%, 60-65 → +0.13%, 70-75 → +0.24%, 75+ → +0.41% per trade (this
  resolves the old "score above ~65 doesn't predict quality" puzzle below).
- **The EPS-growth gate is look-ahead-contaminated** (today's fundamentals filter
  2021-era trades). Documented and warned at runtime; its old A/B is not clean.
- `load_config(None)` falls back to `config/config.example.yaml`, so "default"
  runs include that file's gates.

### Changes that survived validation

| Variant (full universe, 5y) | Trades | Win | PF | Mean R | Max losing streak |
|---|---|---|---|---|---|
| A. Original (5-day hold, tight structure stops) | 7460 | 45.4% | 1.06 | -0.016R | 15 |
| B. + 7-day hold for Momentum/Trend Continuation | 7202 | 45.3% | 1.07 | -0.008R | 15 |
| C. + stops never tighter than the 2-ATR stop | 6783 | 50.2% | 1.09 | +0.031R | 11 |
| D. + no-chase entry (skip if it opens >0.5 ATR above the signal close) — **current default** | 6469 | **50.6%** | **1.11** | **+0.038R** | — |

Each step improved in both halves (D: +0.034R early / +0.042R late, PF 1.10 / 1.12;
net P&L $8,370 (A) → $11,166 (D) despite ~1,000 fewer trades).

- **No-chase entry.** When the session after a signal opened >0.5 ATR above the
  signal close, those trades lost money in both halves (worst for dip-buying
  setups, where the gap erases the favorable entry). The entry is now a buy-limit
  at close + 0.5 ATR (`gates.max_entry_gap_atr`); the scanner and dashboard show
  that "max entry" price.

- **Per-setup holding period.** 5-day vs 7-day caps: Momentum Continuation and
  Trend Continuation improved with 7 days in both halves; Bullish Pullback got
  worse; the rest were mixed. Only the consistent group was extended
  (`risk.holding_days_by_strategy`).
- **Minimum stop distance.** Structure stops sat a median 0.87 ATR from entry;
  the tightest quintile (<0.71 ATR) was the only losing one (-0.22R). In every
  one of the six strategies, stops <1.9 ATR had negative R and wider stops
  positive R. Tight stops also got the largest positions and the highest R:R,
  so the `risk_reward` score category was rewarding the worst trades. Support
  Bounce (100% structure stops, median 0.74 ATR) went from 38.8% to 49.7% wins.
- **Late-entry penalty for breakouts** (>2.5 ATR past the trigger). Only changes
  the displayed confidence/score — nothing in the engine gates on it — so it
  does not change backtest trade selection.

### Tested and rejected (kept as-is on purpose)

- **Cutting stale trades early** (exit on day 2-3 if still below entry): worse in
  every variant and every strategy (+0.025R → +0.007..0.014R).
- **Named indicator combos** (EMA+RS+RVOL, BB squeeze+ADX rising, RSI divergence
  + liquidity sweep, ...): 4 of 5 did worse than trades without the combo.
- **Holding through earnings:** higher mean R (+0.18 vs -0.02) but twice the
  gap-through-stop rate (20% vs 10%) and a worst-1% of -23% vs -12%, and the
  higher mean is plausibly survivorship-inflated. The live scanner keeps
  avoiding earnings as tail-risk control.
- **Tighter R:R gate:** raising `min_risk_reward` above ~1.5 made results worse
  (2.0 → negative expectancy). 1.2 sits on a flat, robust plateau, as does the
  RS-percentile gate (30-70).

### Remaining weaknesses

- The edge is thin: +0.031R per trade. Treat the scanner as a candidate filter
  with explanations, not a signal to trade blindly.
- Survivorship bias is structural: failed names (e.g. SIVB, FRC) have no
  retrievable yfinance history, and some dead tickers (SBNY, SI) are now reused
  by unrelated companies.
- Support Bounce is still ~0R after the stop fix — the largest-volume setup with
  no demonstrated edge; a candidate for removal that has not been A/B-tested yet.
- Mean Reversion lost money in BULLISH regimes and Bullish Pullback in NEUTRAL
  regimes (both halves, legacy stops) — regime-specific gating not yet tested.

### Research tooling added (`research/`)

`capture_trades` (per-trade feature snapshots, `--workers`, A/B overrides),
`merge_captures`, `report_from_pickle` (R and $ metrics), `feature_importance`
(importance, redundancy, interactions, per-regime), `exit_sweep`,
`stop_comparison`, `walk_forward_screener`, `parameter_robustness`,
`data_integrity`, `false_positive_log` (loser database with failure reasons).
Run long captures in ~34-ticker chunks: this container kills long-lived
background processes.

## Chart patterns + "ready to boom" list

`analysis/patterns.py` detects every bullish pattern the same way (trigger,
invalidation, measured-move target, lines to draw): falling wedge,
descending channel, descending triangle, ascending triangle, symmetric
triangle, double bottom, inverse head & shoulders, cup & handle, bull flag,
flat base, horizontal range, VCP, channel up (bounce and strong breakout).

`research/pattern_backtest.py` backtests each one on its breakout day
(5y, 190 tickers, entry next open, 2-4 ATR stop at the invalidation,
2-4R target, 10-day time exit, gap-through fills): 9,419 breakouts.

| pattern | n | win % | mean R | PF | H1 / H2 |
|---|---|---|---|---|---|
| descending triangle | 58 | 60.3 | +0.34 | 2.42 | +0.08 / +0.67 |
| VCP | 220 | 55.0 | +0.15 | 1.44 | +0.09 / +0.23 |
| channel up strong breakout | 422 | 54.5 | +0.15 | 1.54 | +0.14 / +0.16 |
| descending channel | 446 | 58.7 | +0.12 | 1.49 | +0.13 / +0.12 |
| bull flag | 1070 | 51.5 | +0.12 | 1.33 | +0.15 / +0.09 |
| cup & handle | 645 | 56.1 | +0.11 | 1.35 | +0.09 / +0.13 |
| ascending triangle | 646 | 55.4 | +0.10 | 1.40 | +0.15 / +0.05 |
| double bottom | 869 | 54.3 | +0.10 | 1.39 | +0.14 / +0.05 |
| falling wedge | 409 | 52.1 | +0.09 | 1.29 | +0.09 / +0.09 |
| inverse head & shoulders | 291 | 51.5 | +0.07 | 1.21 | +0.12 / +0.01 |
| flat base | 1306 | 54.5 | +0.07 | 1.26 | +0.08 / +0.05 |
| horizontal range | 728 | 52.7 | +0.07 | 1.27 | +0.15 / −0.02 |
| symmetric triangle | 872 | 48.1 | +0.06 | 1.15 | +0.10 / +0.02 |
| channel up bounce | 1437 | 46.6 | −0.02 | 0.95 | −0.04 / −0.00 |

Context that helps (all patterns pooled): above the daily 200 EMA +0.106R
vs +0.054R below it; two or more patterns breaking out together +0.111R;
EMA 21>50>200 stacked + ATR% >= 3 + breakout volume > 1.5x: +0.153R, PF 1.60,
both halves.

`python -m analysis.setup_finder --top 15 --html boom.html` scans the
universe for patterns that broke out today / 1-3 days ago (still < 1.5 ATR
above the trigger) or are READY (within min(3%, 1 ATR) under the trigger),
scores them on the pattern's own edge plus that context (and momentum rank,
efficiency, tight coil, room to the next resistance zone) and writes an
annotated chart per setup with trigger (buy-stop), stop and target.
Channel up bounce never makes the list.

### Second round: out-of-sample, entries, exits, the 4H 200 EMA

`research/pattern_research.py` re-ran every pattern walk-forward on the 190
scanner tickers AND on 163 other liquid US stocks that were never used to
build or tune anything (out-of-sample), 2021-2026:

- **Most of the in-sample pattern edge did not survive.** Pooled breakouts:
  +0.095R in-sample vs +0.026R out-of-sample (PF 1.09, second half
  negative). The first round's numbers were flattered by a universe picked
  with hindsight (2023-26 growth leaders).
- **Held up in both samples and all four halves**: descending channel
  (+0.124 / +0.117R), bull flag (+0.118 / +0.116R), channel up strong
  breakout (+0.146 / +0.096R). Positive in both but weaker: inverse H&S,
  double bottom, ascending triangle, falling wedge (+0.03..+0.07R out).
- **Failed out-of-sample**: VCP (−0.04R), cup & handle (0.00), descending
  triangle (−0.04), flat base (0.00), horizontal range (−0.04), symmetric
  triangle (−0.02). They no longer appear in the ready-to-boom list.
- **The first score did not rank**: higher score buckets were not better,
  in or out of sample. Its above-200/stacked/coil/room/multi-pattern
  points helped in-sample only (or not at all) and were dropped.
- **4H 200 EMA** (in-sample, last 2y where 1h data exists): breakouts
  above it +0.095R (n=4,204), below it −0.055R (n=648, PF 0.86). Now
  +15 / −20 points.
- **Held up in both samples**: breakout volume > 1.5x (+0.10/+0.06R vs
  +0.09/+0.02R), ATR% >= 3 (+0.10/+0.06 vs +0.09/+0.01).
- **Hold longer**: 20-day holds beat 10 and 5 in both samples (+0.145 vs
  +0.095R in, +0.053 vs +0.026R out); target choice (2R/3R/measured) barely
  matters.
- **Entry**: buying on a close above the trigger (next open) was a bit
  better than a buy-stop at the trigger in-sample (+0.095 vs +0.076R),
  equal out-of-sample.

The re-weighted score is built from these results and has not itself been
tested on data it wasn't derived from yet -- forward-test it before
sizing up.

## Chart read: EMAs on two timeframes, zones, wedges, the plan

Every setup the scanner lists now also gets a trader-style chart read
(`analysis/chart_read.py`), shown in the terminal, the JSON and the
dashboard with an annotated chart (`ui/chart_svg.py`):

- daily EMA 9/21/50/200 and a fresh cross of the **DTF 200 EMA**
- the **4H 200 EMA** (1h bars resampled to the 09:30/13:30 New York 4h
  candles, as TradingView draws them)
- **support/resistance zones** (price bands from clustered swing highs and
  lows, not single lines) and a breakout out of one
- **falling wedge / descending channel / descending triangle / bull flag**
  since the last major peak, and a breakout above the upper line
- the plan in chart language: `IF IT CAN HOLD <level> AND BREAK THROUGH
  <4H 200 EMA / zone> @<price> -> NEXT RESISTANCE <zone>`, plus what
  invalidates it

For any ticker, with an HTML page of annotated charts:

    python -m analysis.chart_read SYNA AMD --html charts.html

It is a READ, not (yet) a filter or score input: whether wedge breakouts or
4H-200-EMA reclaims add edge on top of the gates still needs a backtest.

Daily history in the cache is now also refreshed when it is missing the
last completed US session, not only after `cache_ttl_hours`: a scan on
2026-09-26 had been served Thursday's closes from a Friday-evening cache.

## Scanner comparison: uploaded "Explosive Breakout" scanner vs this one

`alt_scanners/explosive_breakout_scanner.py` is an externally supplied scanner,
kept verbatim (cross-sectional composite momentum 63/126/252d, top 10%,
EMA9>EMA21 + EMA300 trend filter, 30-day efficiency ratio >= 0.35, VIX
16–25, 1.5-ATR stop capped at 8%, 50% off at 1R + breakeven + 1.5-ATR
trail, max 5 days). `research/compare_scanners.py` runs its own signal
code on our price data and replays it under a ladder of rule sets, one
assumption changed per step, then under **exactly our engine's rules**
(next-open entry, gap-through fills, one position per ticker, same costs
and sizing). Window 2023-01-04 → 2026-09-23 (their scanner needs 320 bars
of history), 5y data, same window for both.

**Their published numbers reproduce** on their own watchlist (99 of 102
tickers still have data — ZI and CYBR are gone): 899 trades, +1.28%/trade,
54.5% win vs. their stated +1.43%, 55.5%, 853 trades.

| Universe | Scanner (engine rules) | trades | win % | mean R | PF (R) | H1 / H2 mean R | 1 account CAGR / max DD |
|---|---|---|---|---|---|---|---|
| ours (134) | theirs | 387 | 56.6 | **+0.167** | **1.42** | +0.175 / +0.163 | 8.6% / 13.3% |
| ours (134) | ours | 5,874 | 51.4 | +0.052 | 1.15 | +0.065 / +0.036 | **14.9% / 20.1%** |
| theirs (99) | theirs | 253 | 52.2 | **+0.176** | **1.37** | **+0.002** / +0.254 | 5.9% / 8.4% |
| theirs (99) | ours | 4,070 | 49.2 | +0.060 | 1.17 | +0.077 / +0.040 | **17.7% / 21.9%** |

"1 account" replays each trade list through one $10k account (0.5% risk,
20% max position, 6% max heat, same-day candidates by our score / their
momentum rank). Reading it:

- **Per trade theirs is ~3× better** (+0.17R vs +0.05–0.06R), but it
  fires ~70–100×/yr vs ~1,100–1,600×/yr, so in one account it leaves
  capital idle and makes less money; risk-adjusted (CAGR/maxDD) the two are
  close (theirs 0.64–0.70, ours 0.74–0.81).
- **Theirs is less stable**: 2023 was −0.31R on their watchlist, the whole
  first half ~0R; t-stat 2.7 vs 4.4 for ours; APP alone is 12 of its 65 R on
  our universe. Their "walk-forward" fits nothing per window, and top-10%/
  VIX 16–25 are the peak of a narrow ridge: top 5% +0.10R, top 15% +0.07R,
  no VIX filter +0.09R, VIX 14–27 +0.11R (our universe, engine rules).
- **Their robust ingredient is the efficiency ratio**: rises steadily with
  the threshold (none +0.09R → 0.25 +0.13 → 0.35 +0.17 → 0.45 +0.22R) and
  every threshold is positive in both halves. EMA300 and
  the EMA9/21 trend filter add nothing (±0.01R).
- Of their gap-through assumptions, "stop fills at the stop" hides 17–28%
  of stop-outs that gapped through (worst trade −8.5% on paper, −47.8% real).

Their exit (50% at 1R + breakeven + 1.5-ATR trail) replayed on our own
entries is worse (+0.052R → −0.001R), so it was not taken over.

### Adopted: their momentum rank + efficiency ratio as gates on our scanner

`gates.min_momentum_percentile` (composite 63/126/252-day momentum,
last 5 days skipped, percentile vs. the whole scanned universe) and
`gates.min_efficiency_ratio` (30-day Kaufman ER) now run before scoring,
for every strategy. Real gated backtests (not post-hoc filtering; each
chunk ranked against the full universe via `capture_trades
--rank-tickers`), same window and rules as above:

| Universe | Variant | trades/wk | win % | mean R | PF (R) | H1 / H2 mean R | mean R 2023 / 24 / 25 / 26 | 1 account CAGR / max DD |
|---|---|---|---|---|---|---|---|---|
| ours | before (no gates) | 30.4 | 51.4 | +0.052 | 1.15 | +0.065 / +0.036 | +0.04 / +0.07 / +0.08 / +0.00 | 14.9% / 20.1% |
| ours | momentum 90 only | 4.5 | 52.4 | +0.097 | 1.27 | +0.059 / +0.138 | −0.00 / +0.13 / +0.14 / +0.14 | 11.3% / 13.1% |
| ours | **momentum 80 + ER 0.25 (default)** | 4.5 | 52.8 | **+0.122** | 1.35 | +0.139 / +0.105 | +0.09 / +0.18 / +0.09 / +0.12 | 14.8% / **9.7%** |
| ours | momentum 90 + ER 0.25 | 2.5 | 55.1 | +0.185 | 1.51 | +0.208 / +0.159 | +0.13 / +0.31 / +0.11 / +0.19 | 12.3% / 5.6% |
| ours | momentum 90 + ER 0.35 | 1.6 | 56.6 | +0.207 | 1.56 | +0.171 / +0.246 | +0.01 / +0.36 / +0.25 / +0.19 | 8.7% / 4.3% |
| theirs | before (no gates) | 21.0 | 49.2 | +0.060 | 1.17 | +0.077 / +0.040 | +0.09 / +0.06 / +0.07 / −0.01 | 17.7% / 21.9% |
| theirs | momentum 90 only | 3.3 | 50.7 | +0.147 | 1.43 | +0.081 / +0.221 | −0.00 / +0.21 / +0.30 / +0.03 | 12.8% / 14.3% |
| theirs | **momentum 80 + ER 0.25 (default)** | 3.3 | 54.5 | **+0.189** | 1.52 | +0.214 / +0.163 | +0.28 / +0.21 / +0.12 / +0.13 | 16.9% / **7.1%** |
| theirs | momentum 90 + ER 0.25 | 1.9 | 53.6 | +0.244 | 1.69 | +0.166 / +0.326 | +0.20 / +0.24 / +0.36 / +0.10 | 12.0% / 5.8% |
| theirs | momentum 90 + ER 0.35 | 1.2 | 51.7 | +0.249 | 1.65 | +0.184 / +0.315 | +0.04 / +0.43 / +0.29 / +0.12 | 8.7% / 5.5% |
| theirs | *their own scanner (engine rules)* | 1.3 | 52.2 | +0.176 | 1.37 | +0.002 / +0.254 | −0.31 / +0.27 / +0.23 / +0.35 | 5.9% / 8.4% |

Every variant with the efficiency gate beats both "before" and their own
scanner in both halves on both universes, and the neighbourhood is smooth
(80/90, 0.25/0.35), so the gain isn't one lucky threshold. Momentum alone is
weaker (flat 2023 on both universes). The default, 80 + 0.25, was picked
from that neighbourhood for the ~3–4.5 setups/week a person can actually
follow: about the same one-account return as before at half the drawdown.
Caveats: the thresholds were compared on this same 2023–2026 window;
Bullish Pullback and Support Bounce contribute little inside the gated set
(Support Bounce almost never qualifies); the single worst trade is still a
~−43% gap, so earnings avoidance and small sizing still matter. The live
scan needs `data.period` >= 2y for the 252-day horizon (now the default)
and, with the gate on, lists setups by momentum rank first.

The backtest has no universe filter, the live scan does. Inside the gated
set the `min_atr_pct: 3` part of it helps, checked point-in-time on ATR% at
entry: our universe ATR% < 3 −0.005R (339 trades) vs >= 3 +0.202R (538);
theirs +0.15R (64) vs +0.19R (584). The first live scan with the old
134-ticker list (2026-09-26) had only 45/134 pass the universe filter and
gave 1 setup, so on request:

- `DEFAULT_UNIVERSE` now also holds their watchlist (minus ZI/CYBR): 190 tickers.
- `universe.max_market_cap` ($200B) is off — it removed 8 of the 27
  strongest-momentum names (AMD, MU, AMAT, LRCX, PANW, ARM, MRVL, INTC) and
  can't be backtested (only today's market cap is known).

Gated backtest on the 190-ticker list (ranked against all 190), same window:

| | trades/wk | win % | mean R | PF (R) | H1 / H2 | mean R 2023 / 24 / 25 / 26 | 1 account CAGR / max DD |
|---|---|---|---|---|---|---|---|
| all gated trades | 6.2 | 51.4 | +0.109 | 1.29 | +0.096 / +0.122 | +0.10 / +0.10 / +0.13 / +0.10 | 16.8% / 13.7% |
| ATR% >= 3 at entry (≈ live) | 4.5 | 53.3 | +0.143 | 1.39 | +0.142 / +0.144 | +0.17 / +0.15 / +0.13 / +0.12 | 16.6% / 11.0% |

The live scan still applies `min_price` 10 and `min_market_cap` $2B, which
drop some of the added small caps (OCGN, BBAI, ...) that the backtest kept.

    # our scanner on their watchlist (gates off = the "before" rows), then the comparison
    python -m research.capture_trades --period 5y --tickers <their watchlist> --min-momentum-pct -1 --min-efficiency -1 --out ours_on_theirs.pkl
    python -m research.compare_scanners --universe theirs --ours-pickle ours_on_theirs.pkl
    # a gated chunk, ranked against the full universe (repeat per chunk, then merge_captures)
    python -m research.capture_trades --period 5y --tickers <chunk> --rank-tickers default --out chunk1.pkl

## Overnight session summary (autonomous build) — earlier, superseded numbers

This section is the executive summary requested at the end of an unattended,
overnight build/test/validate session. Its performance numbers were produced by
the pre-audit backtester (fills at the stop through gaps, RS/sector scored as
neutral) and are superseded by the section above.

### WHAT I BUILT

The full system described in this README: a `DataProvider` abstraction over
`yfinance` with disk caching; a universe filter (price band, market cap floor
*and* ceiling, dollar-volume, Corwin-Schultz spread estimate, ATR% floor);
trend/momentum/volatility/volume/trend-strength indicators (EMA 8/21/50 with
slope and spread, SMA 20/50/100/200, RSI14/7 with regular+hidden divergence,
MACD with histogram acceleration and zero-line/divergence, ADX/+DI/-DI with
slope, ATR/ATR%, Bollinger Bands with squeeze/expansion, RVOL, OBV +
Accumulation/Distribution with divergence); market structure (HH/HL/LH/LL,
Break of Structure/Change of Character, liquidity sweeps); support/resistance
with touch-count strength and ATR-normalized distance-to-resistance;
Fibonacci retracement as confluence only (never a standalone trigger);
anchored VWAP; gap classification (breakaway/continuation/exhaustion); market
regime (SPY/QQQ/IWM/VIX multi-factor); sector rotation (11 SPDR ETFs) and
relative strength vs. SPY *and* the scanned universe (a separate, later-added
percentile gate); 8 strategy modules (Breakout, Pullback, Trend Continuation,
Support Bounce, Momentum Continuation, Mean Reversion, Volatility Contraction,
Episodic Pivot — the last two currently non-tradeable, see below); an 11-
category weighted scoring engine with an explicit indicator-redundancy design
(capped combined momentum/volume "votes" instead of counting correlated
indicators as independent evidence) and a multi-category confluence bonus;
hard sequential NO-TRADE gates applied *before* scoring (RS-vs-universe
percentile, market regime, min R:R, resistance proximity, bearish weekly
trend, extreme overextension, EPS-growth quality); risk management (ATR/
structure stop selection, position sizing with correct rounding, horizon-
capped targets); an event-driven backtester with no look-ahead (signal on bar
t, fill at bar t+1's open) plus walk-forward-window infrastructure; a
structured per-candidate trade explanation (why it passed / why it could
fail / structure / momentum / volume / context / levels / risk); and a
single-file static HTML dashboard. 398 automated tests, all passing.

### WHAT I TESTED

Every gate, strategy tightening, and scoring change in this session was run
through a real backtest before being trusted — `backtest_screener.py --period
5y` across the full 134-ticker universe (~7,500-9,000 closed trades per run,
5 years, 2021-2026) was the primary validation tool, with `--period 2y` used
tonight specifically as an out-of-sample check (see below). Tests included:
A/B comparisons of the RS-vs-universe gate threshold (50 vs. 70), the
target-horizon multiplier (1.2 vs. 1.5), Support Bounce's touch-count/trend
filter, a min-ATR% universe floor at three different levels, a new EPS-
growth quality gate, an RS-top-decile scoring bonus, a multi-category
confluence bonus, re-enabling both non-tradeable strategies on a wider
universe, and — tonight — a full out-of-sample run on the most recent 2
years only (2433 trades) to check whether the accumulated tuning generalizes
beyond the single 5-year window every prior decision was validated against.

### WHAT FAILED

- **Target-multiplier tightening (1.5 -> 1.2) and Support Bounce tightening
  (min_touches 2 -> 3 + hard bearish-trend gate)**: both achieved their
  stated proximate goal (target-hit-rate roughly doubled; Support Bounce
  trade count fell 22%) but a controlled backtest showed the COMBINED effect
  made the system worse on the metrics that matter (profit factor 1.15 ->
  1.09, expectancy +0.20% -> +0.13%/trade). Reverted.
- **Volatility Contraction strategy**: re-enabled as tradeable five separate
  times across this project's history (including once tonight, on the wider
  136-ticker universe) hoping a bigger sample would resolve its instability.
  Every single time: 20-64 trades total (vs. hundreds-to-thousands for every
  other strategy) with expectancy that flips sign between runs
  (+0.52%, +0.40%, +0.39%, -0.05%, -0.37% across five tests). Confirmed
  `tradeable = False` — the setup fires too rarely to trust as a primary
  entry trigger regardless of universe size.
- **Episodic Pivot strategy (new tonight)**: a Qullamaggie-style catalyst-gap
  setup. Best expectancy of all 8 strategies on its first test (+0.73%), but
  only 12 trades — thinner than Volatility Contraction's already-disqualified
  sample. Built, tested, kept in the codebase (it can still contribute
  price-action confirmation), but set `tradeable = False` for the same
  small-sample reason.
- **Confluence bonus and RS-top-decile scoring bonus**: both mechanically
  push more setups into the 70+ score range (worked as designed — see "score
  bucket" note below) but neither shows a validated POSITIVE correlation with
  actual trade outcomes; if anything, both the original 5y validation and
  tonight's 2y out-of-sample check show *negative* expectancy in the 70-79
  and 80+ score buckets. Kept (they don't gate any trades by default, so
  there's no downside to keeping them), but flagged prominently below.

### WHAT I CHANGED

In roughly chronological order this session: fixed a Corwin-Schultz spread
threshold that was wrongly excluding liquid high-beta names; loosened the
RS-vs-universe gate 70 -> 50 (evidence-based, see "Hard entry gates" above);
fixed a real bug where `scanner.py --preset` only relabeled the config
without reapplying its actual thresholds; fixed a real bug where
`backtest_screener.py`'s score calculation silently omitted market-regime and
risk/reward from the score (the reason the score-bucket report showed
literally zero trades above 70 for most of this project, despite live scans
regularly landing there); widened the universe from 103 to 136 tickers;
recalibrated the score-label thresholds (90/80/70/60 -> 78/72/65/55) against
the real achievable distribution once the above bug was fixed; added
`min_atr_pct` (now 3.0, was tested at 5.0 and 4.0), `max_price`/`min_price`
(added, then explicitly disabled per a later request), and `max_market_cap`
(200B, excludes mega-caps) as universe filters; added an EPS-growth quality
gate (validated: cut trades ~17%, raised profit factor 1.17 -> 1.21 and
expectancy +0.28% -> +0.33%); added and then reverted Volatility Contraction
and Episodic Pivot as tradeable strategies (see "What failed").

### CURRENT PERFORMANCE

**In-sample (5y, 134 tickers, current full config, 7491 trades):** 45.7% win
rate, profit factor 1.21, expectancy +0.33%/trade, avg win/loss 4.56%/-3.22%,
max 15 consecutive losses, avg hold 5.5 days.

**Out-of-sample (2y, most recent data only, same config, 2433 trades):**
45.1% win rate, profit factor **1.25**, expectancy **+0.37%/trade**, avg
hold 5.2 days. Performance on the most recent, unseen-during-tuning period is
not degraded — if anything slightly better — which is real (if not
airtight, single-check) evidence against the system being overfit to stale
historical patterns.

**Per-strategy (5y, current config):** Bullish Breakout +0.71%, Mean
Reversion +0.42%, Support Bounce +0.36% (highest trade count, worst per-trade
loss rate at 61%, still net positive on R:R asymmetry), Momentum Continuation
+0.35%, Bullish Pullback +0.27%, Trend Continuation +0.14%.

### REMAINING RISKS

- **Score above ~65 does not reliably predict better outcomes, and the reason
  why remains unexplained.** Confirmed in two independent backtests (5y full
  period and a 2y OOS check): the 70-79 and 80+ score buckets show
  *flat-to-negative* expectancy, not better. The leading hypothesis —
  overextended, "already-chased" setups score highly on many categories at
  once but underperform — was tested directly (a new `print_overextension_report`
  bucketing trades by `stretched_reference_count` at entry) and **rejected**:
  overextension count correlates *positively* with expectancy in this
  system (0 refs: +0.25%, 4 refs: +0.84%, monotonically increasing), the
  opposite of the "buying exhaustion" theory. Use the score to find
  candidates worth reading the reasons/risks for, never as a standalone
  conviction signal — this is now empirically demonstrated, not just a
  disclaimer, and the mechanism behind it is still an open question.
- **Mean Reversion and Bullish Breakout flipped negative in the 2y OOS-only
  window** (-0.12% and -0.43% respectively, vs. +0.42%/+0.71% over the full
  5y) on samples of 94-118 trades. Could be real regime-sensitivity (both
  are the lowest-trade-count strategies, so more exposed to whatever the
  last 2 years specifically looked like) or could be noise — not enough
  evidence either way to act on, but worth watching, not ignoring.
- **Survivorship bias**: the backtest universe is today's liquid tickers,
  not a point-in-time historical membership list (see "Scope & honest
  limitations" below) — structurally inflates backtest results somewhat.
- **The RS-top-decile bonus and confluence bonus are unvalidated as
  positive contributors** (see "What failed") — kept because they cause no
  harm to trade selection, not because they're proven to help.
- **Data source reliability**: `yfinance` intermittently returns transient
  errors (HTTP 401 "Invalid Crumb", timeouts) that the retry logic absorbs,
  but two tickers (CFLT, EXAS) failed to return any history across every run
  this session — likely a data-provider-side issue with those specific
  symbols, not a code bug, but unconfirmed.
- **Walk-forward window infrastructure exists** (`backtesting/walk_forward.py`)
  but is wired into the single-strategy `backtest.py`, not the full
  multi-strategy `backtest_screener.py` that every validation in this
  project actually uses — tonight's out-of-sample check (`--period 2y`) is a
  practical substitute (recent-data-only, not seen as a whole in prior
  tuning) but isn't a true sequential walk-forward across multiple windows.
  A real next step, not silently skipped.

### HOW TO RUN IT

```bash
pip install -r requirements.txt
cp config/config.example.yaml config.yaml   # optional, has sensible defaults
python scanner.py                            # live scan, prints + writes dashboard.html
python scanner.py --min-score 55             # include the Watchlist tier too
python backtest_screener.py --period 5y      # full validation backtest
python backtest_screener.py --period 2y      # out-of-sample check
python -m pytest -q                          # 398 tests, all passing
```

## Network access note (important for this environment)

If you're running this in a sandboxed environment where `query1.finance.yahoo.com`
is not reachable, `python scanner.py` will fail to fetch real data. Two ways to
verify the tool works anyway:

- `python scanner.py --dry-run` runs the entire pipeline (universe filtering,
  indicators, strategies, scoring, risk, dashboard generation) against built-in
  synthetic data — no network needed. This proves the wiring is correct.
- Once you have network access to `query1.finance.yahoo.com` (yfinance's data
  endpoint), drop `--dry-run` and it fetches real data.

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.11+.

## Configuration

Copy `config/config.example.yaml` to `config.yaml` in the project root and adjust
as needed. Every value has a sensible default — you only need to override what you
want to change. See the comments in `config.example.yaml` for every option:
universe filters/preset, data caching, risk management, scoring weights and
thresholds, earnings-avoidance buffer, backtesting costs, and alert triggers.

Universe presets (`universe.preset` in config):

| Preset | Min price | Min avg $ volume | Min market cap |
|---|---|---|---|
| CONSERVATIVE | $20 | $20M | $10B |
| BALANCED (default) | $10 | $5M | $2B |
| AGGRESSIVE | $3 | $1M | $300M |
| CUSTOM | uses only what you set in config.yaml | | |

## Holding period: this scanner targets ~1 trading week

Every trade plan is built for a **5-trading-day hold** by default
(`risk.max_holding_days` in config, default `5`):

- **Targets are capped** to what's realistically reachable within that many
  trading days, estimated from ATR scaled by `sqrt(holding_days)` — a target that
  would historically take weeks to hit is pulled in, not just computed from a fixed
  R:R multiple that ignores time entirely (`risk/stops_targets.py:cap_target_to_horizon`).
- **The backtester force-closes any open trade** once it's been held for
  `max_holding_days` bars, even if neither the stop nor the target has been hit yet
  (`backtesting/engine.py`, exit reason `"time_exit"`). This is what actually lets
  you verify whether a strategy works within a week, instead of a backtest quietly
  letting winning trades run for months.
- Change the horizon with `risk.max_holding_days` in `config.yaml`, or per-run with
  `python backtest.py --max-holding-days 10 ...`.
- **Per-setup horizon** (`risk.holding_days_by_strategy`): Momentum Continuation
  and Trend Continuation are held **7** days, everything else the default 5. A
  full-universe 5-day vs 7-day A/B, split at the median entry date, showed those
  two trend-following setups improving with the longer hold in *both* halves,
  while Bullish Pullback got worse and the others were mixed — momentum persists,
  pullback/mean-reversion moves are short-lived. The horizon drives both the
  target cap and the forced time exit, in the live scanner and the backtester.

## Running the scanner

```bash
python scanner.py                          # full scan, default config
python scanner.py --preset AGGRESSIVE       # override the universe preset
python scanner.py --min-score 65            # only print setups scoring >= 65
python scanner.py --dry-run                 # synthetic data, no network required
```

Output: a ranked console list —

```
1. NVDA — Score 91 — Bullish Breakout
2. AMD — Score 87 — Bullish Pullback
```

— followed by the detailed table (`RANK | TICKER | SCORE | SETUP | ENTRY | STOP |
TARGET | R:R | TREND | RVOL | RSI | MARKET`), plus two files written to disk:

- `dashboard.html` — a self-contained dashboard (Dashboard / Scanner / Watchlist
  tabs; click any scanner row to expand the full reasons/risks/score breakdown and
  a price sparkline). Open it directly in a browser.
- `scan_results.json` — the raw ranked results.

## Managing the watchlist

```bash
python watchlist_cli.py add AAPL --notes "watching for a pullback to the 50MA"
python watchlist_cli.py list
python watchlist_cli.py status AAPL READY
python watchlist_cli.py remove AAPL
```

Status values: `SETUP FORMING` → `READY` → `TRIGGERED`, or `INVALIDATED` at any
point (see `watchlist/status.py` for the exact transition rules).

## Backtesting a strategy

```bash
python backtest.py --ticker AAPL --strategy breakout --period 3y
python backtest.py --ticker AAPL --strategy pullback --walk-forward
python backtest.py --dry-run --strategy breakout      # synthetic data, no network
```

Strategy slugs: `breakout`, `pullback`, `trend_continuation`, `support_bounce`,
`momentum_continuation`, `mean_reversion`, `volatility_contraction`.

Reports: trade count, total return & CAGR (vs. buy-and-hold), win rate, avg
win/loss, profit factor, expectancy, max drawdown, Sharpe & Sortino ratios, average
holding period, largest win/loss, and consecutive win/loss streaks.

`--walk-forward` runs **walk-forward validation**: the same fixed strategy is
tested across sequential out-of-sample windows (default 252 train days / 63 test
days), so you see how it performs across different market periods instead of one
aggregate number. This is validation, not optimization — it does not re-fit any
parameters per window. See "Scope & honest limitations" below.

## Backtesting the whole screener across a universe

```bash
python backtest_screener.py --period 5y                          # full DEFAULT_UNIVERSE (~100 tickers)
python backtest_screener.py --period 5y --tickers AAPL,MSFT,NVDA
python backtest_screener.py --dry-run
```

Runs all 7 strategies together (whichever matches with the highest confidence
wins the bar — the same rule the live scanner uses, via
`strategies.best_tradeable_signal`) across every ticker in the universe, and
reports an aggregate win rate plus a per-strategy and per-ticker breakdown. Each
bar's indicators are computed once and shared across signal/stop/target
evaluation (`SharedContextCache`), which is what makes a 100+-ticker, 5-year
backtest finish in tens of minutes instead of hours.

This is genuinely how the strategies/scoring here were tuned: a 5-year,
102-ticker run surfaced that the original bare-squeeze Volatility Contraction
strategy was the only net-losing strategy of the 7, that Mean Reversion had the
best expectancy but fired far too rarely, and that max_holding_days=5 combined
with 1% risk/trade could produce a ~20% drawdown from one losing streak alone —
all three are now fixed (see `strategies/volatility_contraction.py`'s docstring,
`strategies/mean_reversion.py`'s comment, and `risk.risk_per_trade_pct` in
`config.example.yaml`).

`backtest_screener.py` also reports, on every run (required, not optional, per
an explicit instruction that a backtest must analyze losers, not just an
aggregate win rate): a **losing-trade analysis** (average score/R:R at entry
for losers vs. winners, losers broken down by exit reason/strategy/regime —
surfacing patterns worth fixing, not just a single win-rate number) and a
**performance-per-regime breakdown** (win rate/expectancy bucketed by the
market regime active at entry, testing whether the same rule set actually
performs consistently across regimes rather than assuming it does).

**Latest full validation** (5y, 103 tickers, every gate/fix in this README
applied, including the NO-TRADE engine and deep-scan additions below): 5768
trades, 44.7% win rate, profit factor 1.14, expectancy +0.22%/trade, max 14
consecutive losses, all 6 tradeable strategies individually net positive except
Bullish Breakout (essentially flat at -0.00%, likely pulled down by the new
resistance-too-close gate disproportionately filtering breakout setups, which
by definition often sit near a level — not yet root-caused, noted here rather
than silently accepted). This followed several rounds of empirical
back-and-forth, each one only kept after a fresh backtest confirmed it helped:
the hard gates (RS/regime/min-R:R) initially made things worse for Mean
Reversion/Support Bounce specifically because those strategies deliberately buy
weakness, which the counter-trend exemption then fixed; Momentum Continuation
and Support Bounce needed tighter volume/magnitude conditions after showing up
as high-trade-count, low-edge outliers; and Volatility Contraction went back to
`tradeable=False` after three runs showed its win/loss sign flipping on a
26-31-trade sample. A lower overall win rate (44.7% vs. an earlier 46.5%
pre-gate baseline) paired with a HIGHER profit factor and expectancy is the
point, not a regression — see "Hard entry gates" below.

Two findings from the new per-regime and losing-trade reports worth flagging
rather than silently noting: **trades entered during a NEUTRAL regime show
slightly negative expectancy (-0.09%)** while BULLISH (+0.21%) and BEARISH —
counter-trend trades only, since the regime gate blocks everyone else —
(+0.64%) are both positive; extending the regime gate to also block NEUTRAL
for trend-following strategies is a plausible next tightening, but per the
"don't add complexity without proof it helps" rule below, this needs its own
dedicated before/after backtest before being adopted, not just a plausible
story. Separately, **losing trades have a HIGHER average R:R at entry than
winners** (3.33 vs. 2.88) — counter-intuitive at first, but a wider nominal
target is also a harder one to actually reach within 5 trading days, so a
high R:R doesn't automatically mean a better expected outcome once you account
for how often that far a target is realistically hit; worth keeping in mind
when reading the R:R number alone as "better."

**Update: the NEUTRAL-regime idea above was checked and rejected, and a
different gate was loosened instead based on real evidence.** A quick
significance check on the NEUTRAL finding (~881 trades, -0.09% expectancy)
gave a t-statistic of ~0.2 — indistinguishable from pure noise (need roughly
2+ for a credible signal) — so no gate was added on it; that would have been
exactly the overfitting trap this document warns about elsewhere. Instead, a
live scan surfaced a real, actionable question: `min_rs_percentile: 70` was
rejecting the large majority of tickers on a given day (54 of 66 rejections in
one live run), so it was A/B tested directly — 70 vs. 50, same 5-year,
103-ticker backtest. Lowering to 50 produced **22.6% more trades** (5768 ->
7070) at essentially the same profit factor (1.14 -> 1.15) and expectancy
(+0.22% -> +0.20%, within noise), a *higher* win rate, and specifically fixed
Bullish Breakout's flat expectancy (-0.00% -> +0.24%) — while the score-bucket
monotonicity that originally justified the RS gate held up just as well at 50
as at 70. `min_rs_percentile` is now 50 by default: 70 wasn't wrong, just
needlessly strict — it discarded real, working setups without adding quality.

## Hard entry gates (before scoring)

A weighted 0-100 composite score alone lets a setup make up for a real weakness
with strength in unrelated categories — e.g. a laggard stock in a downtrending
market can still score reasonably if its chart pattern and volume look good.
Research on systems with a documented, replicated edge (Minervini's Trend
Template, CANSLIM, academic momentum studies) consistently gates entries on hard,
sequential pass/fail conditions FIRST, and only scores/ranks what's left.
`config.gates` (`GatesConfig` in `config/schema.py`) implements three such gates,
applied in both `scanner.py` and `backtest_screener.py` before a ticker is even
scored:

1. **RS rank vs. the scanned universe** (`min_rs_percentile`, default 50 — see
   the A/B-tested update below): a ticker's trailing 60-day return must rank in
   at least this percentile among the OTHER tickers being scanned — an
   IBD/Minervini-style "RS Rating" pre-filter,
   not a scored input. `relative_strength.compute_universe_rs_ranks` (live) and
   `universe_rs_rank_series` (walk-forward, no look-ahead — every date's rank uses
   only that date's trailing data) implement this.
2. **Market regime gate** (`regime_gate_enabled`, default on): entries are blocked
   outright while the market regime is BEARISH or HIGH_VOLATILITY
   (`blocked_regime_labels`). The backtest uses `classify_market_regime_series`, a
   vectorized walk-forward version of the live regime classifier — every date's
   label depends only on data through that date.
3. **Minimum risk/reward** (`min_risk_reward`, default 1.2): a setup whose
   horizon-capped R:R doesn't clear this bar is rejected outright rather than just
   scoring lower in one of ten categories — this is what actually makes a win rate
   below 50% still add up to a profitable system (`risk/stops_targets.py:plan_trade_levels`
   is the shared stop/target/R:R pipeline both the scanner and the backtest use).

These are deliberately configurable and can be disabled
(`backtest_screener.py --no-regime-gate` / `--no-rs-gate`, or `min_risk_reward: 0`
in config) — research on regime filters specifically warns they can be a source of
overfitting themselves ("perfect in backtest, worse live"), so the honest approach
is to validate their effect empirically rather than assume they help. See
"Backtesting the whole screener" above for how to compare with/without.

**Counter-trend exemption.** The RS-vs-universe and market-regime gates both
require the stock/market to already be STRONG — which is the opposite of what
Mean Reversion and Support Bounce look for (they deliberately buy a dip / a bounce
off support). A 5-year backtest confirmed the mismatch is real, not theoretical:
once those two strategies were subjected to the same gates as the trend-following
ones, their expectancy flipped from solidly positive (+0.30-0.33%/trade) to
negative. `Strategy.counter_trend` (`strategies/base.py`) marks them, and both
`scanner.py`'s `build_trade_plan` and `backtest_screener.py`'s `signal_fn` check
`best.strategy in COUNTER_TREND_STRATEGY_NAMES` before applying the RS/regime
gates — a setup from either strategy is exempt from both, but still has to clear
the (strategy-agnostic) minimum R:R gate.

## The NO-TRADE engine

`build_trade_plan` (`scanner.py`) is explicitly a rejection engine, not just a
plan builder: a high composite score can never override one of its hard gates,
because every gate runs and can reject the setup BEFORE scoring happens at all.
Each rejection is a specific, named reason — never a silent `None` — collected
into `ScanRun.no_trade` (ticker → reason) and printed as a breakdown by category
(`print_no_trade_summary`), the same way universe-filter exclusions already were.
The gates, in the order they run:

1. Insufficient data (ATR/stop unavailable)
2. Weak market regime / weak relative strength / bearish higher-timeframe weekly
   trend (skipped for counter-trend setups — see above)
3. Earnings too close (`config.earnings.avoid_earnings` + `buffer_days` — this
   was previously COMPUTED via `EarningsWarning.should_avoid` but never actually
   enforced, just shown as a risk note; now it actually blocks)
4. Extreme overextension (all 5 distance references from
   `risk/overextension.py` agree at once — `config.gates.block_extreme_overextension`)
5. Resistance too close (`config.gates.min_distance_to_resistance_atr`, default
   0.5 ATR — virtually no room for the trade to work)
6. Poor risk/reward (`config.gates.min_risk_reward`)

`backtest_screener.py`'s `signal_fn` mirrors gates 2 (except the weekly-trend
check, which would need a resampled weekly context built per-bar — not done
here, so that one gate is live-scan-only for now), 4, 5 and 6, so the backtest
and the live scanner reject setups on the same grounds wherever the backtest has
the data to check.

## How scoring works

Every ticker gets a 0-100 composite score from 11 weighted categories (weights
configurable in `config.yaml`, must sum to ~100). Trend and Market Structure are
deliberately SEPARATE categories, not merged — a stock can be in a clean
moving-average uptrend while its swing-point structure is quietly breaking down
(or the reverse, a fresh higher-low forming before the MAs catch up), and folding
them into one number would hide exactly that kind of divergence from the scanner
output:

| Category | Default weight | What it measures |
|---|---|---|
| Trend | 8% | MA alignment, ADX(+slope)/DI, EMA 8/21/50 stack/cross, anchored VWAP — direction & strength only |
| Market Structure | 7% | HH/HL vs. LH/LL swing-point pattern, Break of Structure / Change of Character — the swing-point pattern itself, independent of the MA-based trend read above |
| Price Action | 15% | Best-matched *tradeable* strategy setup, candlestick confluence, liquidity sweeps, S/R confluence, gap type |
| Momentum | 10% | RSI/MACD-histogram/ROC (capped combined "core momentum" vote — see below), MACD cross/zero-line/acceleration, regular + hidden RSI divergence, extension-from-EMA21 |
| Volume | 10% | Relative volume, OBV + Accumulation/Distribution (capped combined vote), OBV divergence |
| Volatility | 10% | ATR% in a healthy range, squeeze detection, squeeze→expansion |
| Relative Strength | 10% | 1M/3M performance vs SPY (distinct from the RS-vs-universe hard gate below, which ranks against peers, not the index) |
| Market Regime | 10% | SPY/QQQ/IWM/VIX-based regime (see below) |
| Risk/Reward | 10% | Computed R:R ratio, distance to resistance in ATRs |
| Sector | 5% | Sector ETF's relative-strength rank (1-11) |
| Multi-Timeframe | 5% | Weekly/Daily trend confluence |

Thresholds (configurable): **78-100 Exceptional · 72-77 Strong · 65-71 Interesting
· 55-64 Watchlist · <55 Ignore**. `scanner.py`'s CLI output defaults to
`--min-score 65` (Interesting and above) rather than 55 — the goal here is a
short list of high-conviction setups, not maximizing how many tickers get
printed; pass `--min-score 55` or lower to also see the Watchlist tier.

**These thresholds were recalibrated (originally 90/80/70/60) against the real
achievable score distribution**, discovered while investigating why a live scan
could hit 78+ but a 5-year, 8958-trade backtest never once recorded a score
above 70. Root cause: `backtest_screener.py`'s call to `score_ticker` was
omitting `market_regime` and `risk_reward_ratio` — two categories worth 20
weight points combined — so they silently fell back to neutral defaults
instead of the same real values `scanner.py`'s live score already uses. Fixing
that (passing the real regime/R:R through, same as live) let the backtest
score properly: the corrected distribution across 8958 trades was `<50: 1485,
50-59: 4077, 60-69: 3357, 70-79: 39, 80+: 0`. Even fixed, 80+ never happened
once — composite-averaging 11 independently-scored categories means a setup
needs nearly every category maxed simultaneously to clear 70, so the old
80/90 thresholds were structurally unreachable, not a high bar rarely
cleared. The new thresholds sit where real (if thin — n=39 for the 70-79
band) separation actually exists in the data; worth revisiting as more live
scans accumulate rather than treating n=39 as final.

Every category's contribution and the specific reasons behind it are visible in
the dashboard's expanded row for each ticker — nothing is a black box.

**Structured trade explanation** (`TradePlan.explanation`): every setup that
passes the NO-TRADE engine is restructured into a fixed set of sections rather
than one undifferentiated bullet list — `why_it_passed`, `why_it_could_fail`,
`structure`, `momentum`, `volume`, `context` (market regime/sector/relative
strength), `levels` (entry/stop/target/R:R/room-to-resistance), and `risk`
(ATR, holding period, earnings/liquidity/float/gap risk notes). Same underlying
data as the category breakdown and reasons/risks lists above, just organized
for readability — shown in place of the old flat Reasons/Risks panel in the
dashboard's expanded row.

**Indicator redundancy:** RSI, MACD histogram and 20-day ROC are all derived from
the same underlying fact (recent price change), so they usually agree — summing a
full bonus for each would let one real "price is rising" observation get counted
three times as if it were three independent pieces of evidence. Momentum scoring
instead treats the three as votes and caps their *combined* contribution
(`score_momentum` in `scoring/scorer.py`); volume scoring does the same for OBV and
the Accumulation/Distribution line, which are both cumulative volume-flow measures
built from the same bars.

## Liquidity, float, and overnight gap risk

Three more filters/context signals, all deliberately kept OUTSIDE the weighted
score — they're either hard executability gates or pure risk disclosure, not
"more bullish/bearish evidence":

- **Liquidity** (`liquidity/liquidity.py`) goes beyond a simple volume filter, per
  an explicit design requirement: average dollar volume AND an estimated
  bid-ask spread are both hard universe gates (`config.universe.max_spread_pct_estimate`,
  default 0.5%, tighter for CONSERVATIVE/looser for AGGRESSIVE presets). Real
  historical bid-ask/quote data isn't available from this free data source, so
  the spread is estimated with the Corwin & Schultz (2012) high-low estimator —
  a published, peer-reviewed method for estimating effective spread from daily
  OHLC alone (see the module docstring for the citation and exact formula), not
  a guess. The module also compares average dollar volume on the most volatile
  vs. calmest days in the trailing window, and flags (as a risk note, not a
  gate) when liquidity measurably thins out exactly when a fast exit would be
  most needed.
- **Free float / shares outstanding** (`data/provider.py:TickerInfo`, best-effort
  via yfinance `.info`) is used strictly as **risk context, never a score
  input** — two otherwise-identical setups score identically regardless of
  float, per the explicit design requirement not to treat a low float as
  automatically bullish or bearish. A low free-float or small share count adds a
  risk note (can move more erratically than a typical large-cap); so does
  elevated short interest (`short_percent_of_float`, a point-in-time snapshot
  only — no free historical short-interest time series exists), explicitly
  without an automatic "high short interest = squeeze = buy" rule.
- **Overnight gap risk** (`risk/gap_risk.py`) is directly relevant to a
  multi-day hold: a ~5-trading-day position sits through ~4 overnight sessions
  where price can jump straight past a stop with no fill at the stop price.
  `avg_gap_pct`/`avg_abs_gap_pct`/`large_gap_frequency_pct`/`up_gap_bias` are
  computed purely from OHLCV (safe to use walk-forward in the backtest, no
  look-ahead) and surfaced as a risk note when gaps are frequent. Which
  fraction of those gaps coincided with a **known** earnings date is a
  **live-scan-only** enrichment (`earnings_gap_fraction`) — correctly
  attributing a historical gap to earnings in a backtest would require knowing
  exactly when that earnings date was first announced to stay causal, which
  isn't available, so this cross-reference is deliberately not computed in
  `backtest_screener.py` to avoid a subtle look-ahead bug.

### Deep technicals (`TickerContext`, `strategies/context.py`)

Beyond the headline indicators above, every scan also computes and exposes:

- **EMA 8/21/50**: slope of each (`ma_slope`), spread between 8-21 and 21-50 as %
  (`ema_spread_pct`), and the 8/21 cross event (`crossover`).
- **Market structure**: HH/HL/LH/LL (`indicators/trend.py:market_structure`), plus
  **Break of Structure / Change of Character** (`price_action/structure.py`) — a
  close beyond the last swing point, classified by whether it agrees with or
  reverses the prevailing structure. Named after the popular retail "ICT" framing,
  but implemented as plain mechanical price-action rules — no claim is made about
  market participants' intent.
- **Liquidity sweeps**: a wick that pierces a known support/resistance level and
  closes back inside it (`price_action/structure.py:detect_liquidity_sweep`).
- **Anchored VWAP** (`indicators/vwap.py`): a **daily-bar approximation** — true
  intraday VWAP needs tick/minute data this free source doesn't provide. Anchored
  by default at the most recent confirmed swing low.
- **Hidden divergence** (RSI and OBV): the trend-continuation counterpart to
  regular reversal divergence — see `indicators/trend.py:detect_divergence`'s
  docstring for the exact price/oscillator pairing each variant requires.
- **OBV divergence**, **volume dry-up** (`is_volume_drying_up` — recent average
  volume well below its longer-term baseline, the VCP "quiet before the breakout"
  tell).
- **ADX slope**, **Bollinger squeeze→expansion** (`is_expanding`), **MACD**
  zero-line state, cross event, and histogram acceleration.
- **Extension check**: how many ATRs price sits above its own EMA21
  (`distance_in_atr`) — a large value means the move may already be too stretched
  to chase, and penalizes the momentum score accordingly.
- **Overextension filter** (`risk/overextension.py`): a broader version of the
  single-EMA21 check above — distance in ATRs from EMA8/21/50, anchored VWAP,
  AND the most recent confirmed swing low, plus raw 1D/3D/5D/20D % gain. A
  stock can look calm relative to its EMA21 while still being wildly stretched
  from its most recent swing low, so an extra momentum-score penalty only
  applies when **multiple independent references agree** the move is extended
  (`is_severely_overextended`) — the same confluence principle used everywhere
  else in this scanner, applied to "is this too far from normal" rather than
  "is this at a meaningful level."
- **Distance to resistance in ATRs**: how much room is left before the nearest
  resistance, feeding into the risk/reward score.
- **Confluence** (`price_action/levels.py:confluence_score`): counts how many
  independent references — a support/resistance level, anchored VWAP, a Fibonacci
  retracement, a round number — cluster near the current price.
- **Fibonacci retracements** (`price_action/fibonacci.py`) are deliberately a
  **minor** confluence input, not a scored signal of their own — a research pass
  on well-known swing-trading systems found weak/contested evidence that Fibonacci
  levels carry standalone predictive value.
- **Gap classification** (`price_action/patterns.py:classify_gap`): breakaway
  (gapped out of a consolidation), exhaustion (gapped while already far extended),
  or continuation (neither) — an honest heuristic, not a certainty.
- **52-week / historical context** (`price_action/historical_context.py`):
  52-week high/low and distance to each, plus the strongest historical
  resistance level (from the existing swing-point clustering) still above the
  current price. `all_time_high_in_window` is honestly named — it's the highest
  close within whatever history was fetched, not necessarily the stock's real
  all-time high unless `config.data.period` is `"max"`. This feeds directly
  into Breakout quality (see below): a close above today's 20-day high isn't
  treated as equally bullish whether it's a fresh 52-week high with no overhead
  supply, or a local breakout still sitting well under a much bigger historical
  ceiling.

## The 7 strategies

Each strategy is an independent module (`strategies/*.py`) with its own matching
logic — never a single giant if-statement:

1. **Breakout** — close breaks the prior N-day high with volume confirmation.
   Rewarded further when it's a fresh 52-week high (no overhead supply);
   flagged as a risk when a stronger historical resistance level still sits
   close above — a local N-day-high break isn't automatically a real breakout
   of the bigger picture (see "52-week / historical context" above).
2. **Pullback** — an uptrend pulls back to EMA21 without breaking structure, RSI
   cools without crashing.
3. **Trend Continuation** — an already-strong trend (ADX>25, HH/HL structure)
   pauses briefly rather than reversing.
4. **Support Bounce** — price bounces off a support level with ≥2 prior touches,
   RVOL >= 0.8 (not on dead volume). Had the highest trade count and lowest win
   rate of the 7 in backtesting — still net positive on R:R asymmetry alone
   (low win rate + big-enough average winner is a legitimate, if less intuitive,
   profitable archetype — see "Hard entry gates" above), but the volume floor
   filters out the weakest, least-watched bounces.
5. **Momentum Continuation** — RSI rising through 50, MACD histogram expanding,
   ROC positive across 5/10/20-day windows with the 20-day figure required to
   exceed 2% (not just >0 — a barely-positive drift isn't "broadening
   momentum"), and RVOL >= 0.9 (not on thin, below-average volume). This was the
   single highest-trade-count strategy in every backtest with only mediocre
   expectancy, and both loosely-set conditions were part of why: a near-zero ROC
   floor and no volume floor let noise-level moves qualify.
6. **Mean Reversion** — a sharp, short-term oversold dip *within* a long-term
   uptrend (filtered by SMA200 to avoid catching a falling knife in an actual
   downtrend). Thresholds (RSI<35, band×1.03) were loosened from the original
   (RSI<30, band×1.01) after backtesting showed the tighter version had the best
   expectancy of all 7 strategies but fired far too rarely to be useful.
7. **Volatility Contraction** — reworked into a VCP-style ("Volatility
   Contraction Pattern") setup: a genuine prior momentum move (>15% over ~90
   days), then a tightening squeeze with real volume dry-up, not just a bare
   Bollinger squeeze. The original bare-squeeze version was the only one of the 7
   strategies with negative expectancy in backtesting; literature on squeeze
   breakouts generally shows only ~55-60% standalone win rate, which is why a
   real precondition (was there something worth consolidating from?) was added
   rather than just disabling the strategy.

Every strategy has a `tradeable` flag (`strategies/base.py`). A non-tradeable
strategy can still fire, appear in reasons, and contribute to the price-action
score, but can never be picked as the primary setup that drives entry/stop/target
(`strategies.best_tradeable_signal` is the single shared rule the scanner and
backtester both use). Volatility Contraction uses this: it fires far more rarely
than the other 6 (26-31 trades across three separate 5-year backtests, vs.
hundreds-to-thousands each for the rest), and its expectancy sign flipped between
those three runs — too small and unstable a sample to trust as a primary trigger,
even though the setup itself (see "The 7 strategies" above) is genuine.

Candlestick patterns (`price_action/candlesticks.py`) are detected but never used
as a standalone signal — they only contribute as supporting context inside a
strategy's reasons/score, per the design spec.

## Market regime & sector rotation

`market_regime/regime.py` classifies the market as **BULLISH / NEUTRAL / BEARISH /
HIGH_VOLATILITY** from multiple factors (SPY trend & momentum, VIX level, QQQ/IWM
confirmation, breadth = % of the scanned universe above its 50-day MA). VIX at or
above 30 overrides everything else to HIGH_VOLATILITY. Every factor is listed with
its own reasoning — see the Dashboard tab.

`sector/rotation.py` ranks the 11 SPDR sector ETFs by 1-month relative strength vs
SPY (5D/1M/3M performance, relative strength, an annualized volatility figure,
and improving/deteriorating trend); each ticker inherits its sector's rank via
`data.sector` from yfinance mapped to the corresponding ETF.

**Correlation to SPY/QQQ/sector** (`relative_strength/correlation.py`): a rolling
60-day Pearson correlation of daily returns, used to tell genuine idiosyncratic
strength apart from a stock that's simply riding the broader market/sector up.
Context only — a highly-correlated stock isn't automatically a worse setup — but
`score_relative_strength` gives a modest additional bonus when a stock is BOTH
outperforming its benchmark over 1M AND doing so with low correlation (below 0.3)
to SPY/QQQ/sector, since that combination is a stronger "genuine strength" signal
than outperformance during a rally everything is having.

## Risk management

`risk/stops_targets.py` computes an ATR-based stop and a structure-based stop
(nearest support/resistance), preferring the structure stop unless it's
unreasonably far from entry. Targets are computed at 1:1/1.5:1/2:1/3:1 R:R, plus
the nearest real resistance level when one exists.

`risk/position_sizing.py` sizes each position so a stop-out loses exactly
`risk_per_trade_pct` of the account (default 0.5% — see "Backtesting the whole
screener" above for why), capped by `max_position_pct` (default 20%) — shares
always round down, never up.

## Look-ahead bias: how it's actually prevented

This is the single most important correctness property of the backtester
(`backtesting/engine.py`), so it's worth being explicit:

1. The signal function is only ever given `history.iloc[:i+1]` — data through the
   bar that has already closed. It can never see bar i+1 or later.
2. A signal on bar i only opens a position at bar **i+1's open**, with slippage —
   never at bar i's own close (a classic look-ahead bug: you can't actually buy at
   a price you only saw after the bar closed).
3. Stop/target levels are computed from data known **before** the entry bar opened.
4. If both a stop and a target are breached within the same bar, the stop is
   assumed to have been hit first (the conservative assumption, since daily OHLC
   data can't tell you the actual intrabar order).
5. Walk-forward windows only count trades whose entry falls inside the test
   segment — a signal firing during the train/warmup segment is explicitly
   suppressed (`backtesting/walk_forward.py`).

`tests/test_backtesting_engine.py` and `tests/test_walk_forward.py` contain
regression tests that directly exercise these guarantees (e.g.
`test_signal_fn_never_receives_future_bars`,
`test_entry_executes_at_next_bar_open_not_signal_bar_close`).

## Project structure

```
config/          Config schema, presets, and the example YAML
data/            DataProvider interface, yfinance implementation, disk cache, universe filters
indicators/      Trend, momentum, volatility, volume, trend-strength (ADX), VWAP
price_action/    S/R levels + confluence, price-action setups, candlestick patterns,
                 BOS/CHOCH + liquidity sweeps (structure.py), Fibonacci (fibonacci.py)
market_regime/   SPY/QQQ/IWM/VIX-based regime classification
sector/          Sector ETF rotation ranking
relative_strength/  Stock-vs-benchmark performance
strategies/      TickerContext builder + the 7 independent strategy modules
scoring/         Weighted composite scoring engine + multi-timeframe confluence
risk/            Stops, targets, position sizing
events/          Earnings/dividend/split awareness
backtesting/     Event-driven backtester, metrics, walk-forward validation
watchlist/       JSON-backed watchlist + status state machine
alerts/          Alert rules + console/JSON-log dispatcher
ui/              Static HTML dashboard generator
tests/           300+ tests, all using synthetic/deterministic data (no network)
scanner.py           Main CLI entrypoint
backtest.py          Single-ticker, single-strategy backtest CLI
backtest_screener.py Whole-universe, all-strategies-combined backtest CLI
watchlist_cli.py     Watchlist management CLI
```

## Running the tests

```bash
pytest -v
```

300+ tests run against synthetic, deterministic data fixtures
(`tests/helpers.py`) — none require network access, which is why they can (and do)
pass in this sandboxed environment even though live data fetching can't be tested
here. Once you have network access, `python scanner.py --dry-run` becomes
`python scanner.py` and the same code path runs against real data.

## Scope & honest limitations

Documented up front so nothing here pretends to be more complete than it is:

- **4H/1H intraday timeframe**: best-effort only. yfinance's free intraday history
  is capped at roughly the last 60 days, so the multi-timeframe confluence score
  gracefully falls back to Weekly+Daily only when intraday data isn't available —
  it never fabricates a number.
- **Market breadth**: approximated as "% of the scanned universe above its 50-day
  MA" rather than true NYSE advance/decline data, which isn't available for free.
- **Fundamentals**: pulled from yfinance's `.info` (P/E, margins, ROE,
  debt/equity, etc.) best-effort — fields that are genuinely unavailable are
  listed in `TickerInfo.missing_fields`, never silently defaulted.
- **Institutional ownership**: not reliably available from yfinance; treated
  as unavailable rather than guessed. **Update**: Alpha Vantage's
  `INSTITUTIONAL_HOLDINGS` endpoint (connected as an MCP tool this session,
  free tier) DOES provide this — verified live for SMCI (892 holders, 78%
  institutional ownership, per-holder position changes with dates). Not wired
  into `scanner.py`/`backtest_screener.py`: those run as standalone Python
  processes with no MCP access, and the connector's API key isn't exposed as
  an environment variable to them — usable only interactively (by an agent
  in a chat session), not from the automated pipeline, unless the user
  separately supplies the API key as an env var for a direct HTTP client.
- **Walk-forward is validation, not optimization**: nothing here automatically
  re-fits scoring weights or strategy parameters per window. That's a
  substantially larger project (parameter search + overfitting control) and is a
  natural next step, not something silently skipped.
- **Alerts** write to console + a JSON log (`alerts_log.json`), not real OS/browser
  push notifications — that needs a running server and a browser permission flow
  that don't exist for a locally-run script. Any future UI can poll the log.
- **The dashboard is a single static HTML file** (Dashboard/Scanner/Watchlist
  tabs), not a multi-page app with its own backend server — a clean next step once
  there's a reason to add one (e.g. real users, live data feeds).
- **Anchored VWAP is a daily-bar approximation**, not true intraday VWAP (see
  "Deep technicals" above) — this data source has no tick/minute history to
  compute the real thing from.
- **Macro events / news catalysts are not implemented.** Earnings, dividends and
  splits are (via yfinance's calendar data), but general macro events (Fed
  decisions, CPI prints, etc.) and other news catalysts have no free, reliable
  data source available here — rather than fabricate or guess at these, they're
  simply left out. **Update**: Alpha Vantage's `NEWS_SENTIMENT` (free tier)
  works and returns genuinely useful, current, per-article sentiment-scored
  news — verified live for MRNA, which correctly surfaced "Moderna Stock
  Reached New 52-Week High" published the same day as a live scan that
  independently flagged MRNA on pure technicals, a real (if anecdotal)
  catalyst-confirms-technical-signal hit. Free tier is capped at 25
  requests/day, which rules out scanning the full ~130-ticker universe but
  comfortably covers checking a day's handful of final candidates by hand.
  Same integration boundary as institutional ownership above: interactive-
  only, not wired into the automated scanner.
- **Supply/demand "zones"** (as opposed to the price-point levels this scanner
  builds from swing highs/lows) were deliberately not implemented — turning a
  zone into a well-defined, testable rule is considerably more subjective than a
  clustered price level, and wasn't judged worth the added complexity relative to
  the levels/confluence system already in place.
- **Survivorship bias in the backtest universe.** `DEFAULT_UNIVERSE`
  (`data/universe.py`) is today's list of liquid large/mid-cap tickers, not a
  point-in-time historical index membership list. A company that got delisted,
  went bankrupt, or was dropped from its index partway through the 5-year backtest
  window simply isn't in the universe at all — only tickers healthy enough to
  still be liquid and mid/large-cap *today* are backtested. This structurally
  inflates backtest results versus what a real point-in-time universe would have
  shown, by an amount studies estimate at roughly 1-4 percentage points of annual
  return. Fixing this properly needs a paid point-in-time constituents data
  source (e.g. historical S&P 500/1000 membership with exact add/drop dates) that
  isn't available here — rather than approximate it with a guess, this limitation
  is left as-is and disclosed rather than silently ignored.
- **Options / implied volatility are not implemented.** yfinance exposes a
  current options chain (`Ticker.option_chain()`), but only a live snapshot —
  there is no free historical options/IV time series to backtest against, and
  a "live only" signal that silently can't be validated would contradict this
  project's own backtest-everything standard. Rather than wire up a
  live-only, never-backtested IV/options-flow signal, it's left out entirely.
  A future paid data source (e.g. a historical IV surface provider) is the
  natural way to add this properly. **Checked concretely**: Alpha Vantage's
  `HISTORICAL_OPTIONS` claims 15+ years of options history with IV and Greeks
  by date, which would solve this cleanly if accessible — but a live test
  call returned `"This is a premium endpoint"`, confirmed not usable on the
  connected account's current (free) API key. This limitation stands, but
  the concrete next step (upgrade that one endpoint) is now known rather
  than "look for a paid source someday."
- **Short interest has no historical time series either.** yfinance's
  `shortPercentOfFloat` (used for the free-float risk note — see "Liquidity,
  float, and overnight gap risk" above) is a point-in-time snapshot with no
  free history, so "change in short interest" (a specifically requested
  metric) can't be computed — only the current level is shown, as context,
  never as an automatic "high short interest = squeeze = buy" signal.
- **Time-of-day / intraday execution analysis is out of scope by design, not
  a missing feature.** This scanner produces one signal per ticker per DAY,
  entered at the next bar's open, for a multi-day hold — there is no
  same-day intraday execution decision here to analyze opening-range,
  first-30-minute volatility, or closing-strength timing for. That kind of
  analysis belongs to a same-day execution system, which this isn't; it
  wouldn't change which ticker the scanner picks or when it exits, only
  how an order is worked on the entry day, which isn't this tool's job.
- **Correlation-based idiosyncratic-strength detection, sector
  volatility/5D performance, and the 52-week/historical-resistance check on
  breakouts are all genuinely new signals added late in this project's
  development** (see "Correlation to SPY/QQQ/sector" and "52-week /
  historical context" above) and have NOT yet been validated with a
  dedicated before/after backtest the way the gates and strategy tightenings
  earlier in this README were — they're included because they're
  well-grounded, tested, and computed correctly (no look-ahead), not because
  their effect on live trade selection has been empirically proven the way
  the rest of this document's numbers have. Treat their scoring bonuses as
  reasoned but not yet independently backtest-validated, and re-validate with
  `backtest_screener.py` before trusting them more than that.
