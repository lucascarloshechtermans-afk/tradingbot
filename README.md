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

## Running the scanner

```bash
python scanner.py                          # full scan, default config
python scanner.py --preset AGGRESSIVE       # override the universe preset
python scanner.py --min-score 70            # only print setups scoring >= 70
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

## How scoring works

Every ticker gets a 0-100 composite score from 10 weighted categories (weights
configurable in `config.yaml`, must sum to ~100):

| Category | Default weight | What it measures |
|---|---|---|
| Trend | 15% | MA alignment, swing structure (HH/HL vs LH/LL), ADX/DI |
| Price Action | 15% | Best-matched strategy setup + candlestick confluence |
| Momentum | 10% | RSI, MACD histogram, ROC, RSI divergence |
| Volume | 10% | Relative volume, OBV, Accumulation/Distribution |
| Volatility | 10% | ATR% in a healthy range, squeeze detection |
| Relative Strength | 10% | 1M/3M performance vs SPY |
| Market Regime | 10% | SPY/QQQ/IWM/VIX-based regime (see below) |
| Risk/Reward | 10% | Computed R:R ratio for the trade plan |
| Sector | 5% | Sector ETF's relative-strength rank (1-11) |
| Multi-Timeframe | 5% | Weekly/Daily trend confluence |

Thresholds (configurable): **90-100 Exceptional · 80-89 Strong · 70-79 Interesting
· 60-69 Watchlist · <60 Ignore**.

Every category's contribution and the specific reasons behind it are visible in
the dashboard's expanded row for each ticker — nothing is a black box.

## The 7 strategies

Each strategy is an independent module (`strategies/*.py`) with its own matching
logic — never a single giant if-statement:

1. **Breakout** — close breaks the prior N-day high with volume confirmation.
2. **Pullback** — an uptrend pulls back to EMA21 without breaking structure, RSI
   cools without crashing.
3. **Trend Continuation** — an already-strong trend (ADX>25, HH/HL structure)
   pauses briefly rather than reversing.
4. **Support Bounce** — price bounces off a support level with ≥2 prior touches.
5. **Momentum Continuation** — RSI rising through 50, MACD histogram expanding,
   positive ROC across 5/10/20-day windows.
6. **Mean Reversion** — a sharp, short-term oversold dip *within* a long-term
   uptrend (filtered by SMA200 to avoid catching a falling knife in an actual
   downtrend).
7. **Volatility Contraction** — a Bollinger Band squeeze within an uptrend and low
   ADX: a "setup forming" watchlist signal, not a directional entry.

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
SPY; each ticker inherits its sector's rank and trend (improving/deteriorating) via
`data.sector` from yfinance mapped to the corresponding ETF.

## Risk management

`risk/stops_targets.py` computes an ATR-based stop and a structure-based stop
(nearest support/resistance), preferring the structure stop unless it's
unreasonably far from entry. Targets are computed at 1:1/1.5:1/2:1/3:1 R:R, plus
the nearest real resistance level when one exists.

`risk/position_sizing.py` sizes each position so a stop-out loses exactly
`risk_per_trade_pct` of the account (default 1%), capped by `max_position_pct`
(default 20%) — shares always round down, never up.

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
indicators/      Trend, momentum, volatility, volume, trend-strength (ADX) indicators
price_action/    Support/resistance levels, price-action setups, candlestick patterns
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
tests/           ~250 tests, all using synthetic/deterministic data (no network)
scanner.py       Main CLI entrypoint
backtest.py      Backtest CLI entrypoint
watchlist_cli.py Watchlist management CLI
```

## Running the tests

```bash
pytest -v
```

All ~250 tests run against synthetic, deterministic data fixtures
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
- **Institutional ownership**: not reliably available from this data source;
  treated as unavailable rather than guessed.
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
