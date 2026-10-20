# indicator_lab — swing buy/sell indicator research

A self-contained research harness for a single-ticker, daily swing-trading buy/sell indicator.
The original scanner in the repo root is untouched. All results and the experiment log are in `../PROGRESS.md`.

```bash
pip install -r requirements.txt               # pandas, numpy, yfinance
python -m indicator_lab.run best               # current best version: 4-cell report + robustness table
python -m indicator_lab.run bh                 # buy & hold reference
python -m indicator_lab.run breakout '{"n": 20, "m": 20, "trail": 4.0, "ibs_min": 0.7}'   # any strategy + params
```

| File | What it does |
|---|---|
| `data.py` | yfinance download and disk cache (`.cache/`, gitignored). Ticker groups: DEV / HOLDOUT / TRAIN_EXTRA |
| `ind.py` | Indicators matching TradingView `ta.*` (Wilder RSI/ATR/ADX, Supertrend, …) |
| `engine.py` | Long-only simulator: next-open fills, intrabar stops with gap handling, 0.10%/side costs |
| `evaluate.py` | Protocol: IS 2015-20 / OOS 2021-26 × DEV / HOLDOUT, 5-slot portfolio, walk-forward, robustness |
| `strategies.py` | Candidate indicators (v0 baseline … v2), `BEST` pointer |
| `meta.py` | v3: walk-forward logistic "breakout quality" model (meta-labeling), `export_final()` for Pine |
| `pine/` | TradingView Pine v5 ports of v1, v2, v3 (+ `v3_model.json` coefficients) |

Not financial advice. No broker connection; nothing here places orders.
