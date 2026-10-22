# Swing v4 — phase 2 summary (development data, 2015-01 .. 2024-10, 253 tickers)

101 phase-2 trials (+3 phase-1 baselines) are logged in `../experiments.csv`; full tables per family with every
metric, the top-10%-winners column and the criteria flags: `phase2_tables.md`; 2-parameter grids:
`p2_heatmaps.png`; the accepted idea's plateau: `p2_f1_plateau.png`.

**Accepted: one idea, F1 — only take a breakout when SPY's 63-day return is ≤ +3%.** It passes every criterion at
all three grid values (0 / 0.03 / 0.06); 0.03 is the middle of that plateau.

| | baseline v3 | v4 = v3 + F1 (0.03) |
|---|---|---|
| trades | 6146 | 2739 |
| win rate | 44.1% | **49.4%** |
| expectancy | 2.28% / 0.200R | **4.21% / 0.338R** |
| 95% CI exp R (trades / clustered by month) | 0.171–0.231 | 0.288–0.391 / 0.171–0.504 |
| profit factor | 1.73 | 2.53 |
| CAGR (10 positions) | 14.7% | 13.4% |
| max drawdown | −25.1% | −20.4% |
| MAR | 0.60 | **0.67** |
| exposure | 92% | 61% |
| years better | – | 7 of 10 (2015, 2017, 2024 not) |
| halves A / B | – | win +6.1 / +4.6 pt, exp R 0.358 / 0.319 vs 0.195 / 0.205 |

Deflated Sharpe (101 trials): 0.99 — the portfolio Sharpe (1.01) is very unlikely to be pure selection luck. Note that
this tests "is there an edge at all", not "is v4 better than v3"; for the latter the month-clustered CI of the
expectancy (0.17–0.50R) overlaps v3's 0.20R at its lower end: the improvement is likely but not certain.

**Why taking profit earlier was rejected.** In v3 the top 10% of trades make 151% of the P&L. Every exit that raised
the win rate noticeably (partial at +1R: 46%, tight trail after +1R: 46%, time stop 5 bars: 47%, over-extension
exit at SMA50+4ATR: 53%, exit before earnings: 51–52%) cut those top trades from 2.71R to 0.8–2.2R and lost more
than the allowed 15% of expectancy; most also lowered MAR. The time stop of 15 bars is the one exit that clearly
helped the portfolio (MAR 0.74, drawdown −21.7%) by recycling capital, but it lost 25% expectancy per trade.

**Other notable results.** Ranking by momentum, model score, sector or volatility did not beat random selection
(MAR 0.37–0.56). Setup filters (contraction, 52-week high, post-earnings drift) raised win rate or MAR in places but
never both with ≥70% of the years. A buy-stop entry over the signal high (3 days) came close (MAR 0.68, win 44.3%,
years 0.6). Relabelled / gradient-boosted models were not better than v3's model. On top of F1 nothing added
reliably; F1 without any model (G1) is as good as F1 with the v3 model, i.e. the regime rule carries most of what
the 17-feature model did.
