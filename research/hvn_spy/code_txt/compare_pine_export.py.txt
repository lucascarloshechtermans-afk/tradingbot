"""Parity check Pine <-> Python twin on a TradingView "Export chart data" CSV.

How to produce the CSV (TradingView):
  1. 5m chart (e.g. SPY, RTH), indicator added with input "Intrabar timeframe" = "Off (CLV fallback)"
     (so both sides use the same buy/sell logic; intrabar 1m data is not in the export).
  2. Chart menu -> Export chart data -> ISO time. The export contains the data-window plots
     "Entry signal", "Entry price", "Stop price", "Target price", "Level absorption dir".
  3. python compare_pine_export.py export.csv
Prints every bar where Pine and Python disagree (signal, entry, stop, target)."""
import sys
import numpy as np
import pandas as pd
from hvn_pine_twin import run_twin

df = pd.read_csv(sys.argv[1])
tcol = "time"
df.index = pd.to_datetime(df[tcol], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
df.columns = [c.strip() for c in df.columns]
b5 = df[["open", "high", "low", "close", "Volume" if "Volume" in df.columns else "volume"]].copy()
b5.columns = ["open", "high", "low", "close", "volume"]
r = (b5.high - b5.low).replace(0, np.nan); clv = ((b5.close - b5.low) / r).fillna(0.5)
tw = run_twin(b5, (b5.volume * clv).to_numpy(), (b5.volume * (1 - clv)).to_numpy(), np.zeros(len(b5), bool), b5.index.date)
py_sig = np.zeros(len(b5)); py_ent = {}
for s in tw["signals"]:
    py_sig[s["bar"]] = s["dir"]
for e in tw["entries"]:
    py_ent[e["bar"]] = e
pine_sig = df["Level absorption dir"].fillna(0).to_numpy()
pine_ent = df["Entry signal"].fillna(0).to_numpy()
bad = 0
for i in range(len(b5)):
    pe = py_ent.get(i)
    msgs = []
    if pine_sig[i] != py_sig[i]:
        msgs.append(f"signal pine={pine_sig[i]:+.0f} py={py_sig[i]:+.0f}")
    if (pine_ent[i] != 0) != (pe is not None):
        msgs.append(f"entry pine={pine_ent[i]:+.0f} py={'none' if pe is None else pe['dir']}")
    elif pe is not None:
        for col, key in (("Entry price", "entry"), ("Stop price", "stop"), ("Target price", "target")):
            if abs(df[col].iloc[i] - pe[key]) > 1e-6 * max(1.0, abs(pe[key])):
                msgs.append(f"{col} pine={df[col].iloc[i]} py={pe[key]:.6f}")
    if msgs:
        bad += 1
        print(b5.index[i], "; ".join(msgs))
print(f"bars={len(b5)}  pine signals={int((pine_sig != 0).sum())} py signals={int((py_sig != 0).sum())}  "
      f"pine entries={int((pine_ent != 0).sum())} py entries={len(py_ent)}  mismatching bars={bad}")
print("NOTE: the first 5 sessions differ by construction if the export starts mid-history (Pine keeps 5 periods of nodes"
      " and its own history before the export window).")
