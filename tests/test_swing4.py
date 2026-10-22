"""Swing v4 round: the holdout is unreachable in development mode, and the new simulator equals the engine."""
import os
import subprocess
import sys

import pytest

from indicator_lab import data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = r'''
from indicator_lab.swing4 import protocol as P
P.install_dev_cutoff()
from indicator_lab import evaluate as E
from indicator_lab.swing4 import core as C
from indicator_lab.strategies import BEST
import numpy as np
assert E.get("AAPL").index[-1] < P.H_START
try:
    E.get(sorted(P.H_TICKERS)[0])
    raise SystemExit("holdout ticker was readable")
except PermissionError:
    pass
for t in ["AAPL", "JPM"]:
    r1, t1 = E.run_ticker(BEST[0], BEST[1], t)
    s = C.signals(t)
    r2, t2 = C.simulate(s["df"], s["entry"], s["exit_sig"], s["atr"])
    assert [(a["entry_date"], a["exit_date"]) for a in t1] == [(b["entry_date"], b["exit_date"]) for b in t2]
    assert np.abs(r1.to_numpy() - r2).max() < 1e-12
print("ok")
'''


def test_dev_cutoff_and_engine_parity():
    if not all(os.path.exists(os.path.join(data.CACHE_DIR, f"{t}.csv")) for t in ("AAPL", "JPM", "SPY", "^VIX")):
        pytest.skip("no cached market data")
    out = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, capture_output=True, text=True, check=False,
                         env={**os.environ, "PYTHONPATH": ROOT}, timeout=600)
    assert out.returncode == 0 and out.stdout.strip().endswith("ok"), out.stderr[-2000:]
