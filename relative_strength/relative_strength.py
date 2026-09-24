from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from indicators.momentum import roc

PERFORMANCE_WINDOWS = {"1W": 5, "1M": 20, "3M": 60, "6M": 120}


@dataclass
class RelativeStrength:
    performance: dict[str, float]
    benchmark_performance: dict[str, float]
    relative: dict[str, float]
    outperforming_benchmark_1m: bool


def _ytd_return(close: pd.Series) -> float | None:
    if close.empty:
        return None
    last_ts = close.index[-1]
    year_start = pd.Timestamp(year=last_ts.year, month=1, day=1, tz=close.index.tz)
    ytd_slice = close[close.index >= year_start]
    if len(ytd_slice) < 2:
        return None
    first = ytd_slice.iloc[0]
    if first == 0:
        return None
    return float((ytd_slice.iloc[-1] / first - 1) * 100)


def _performance_snapshot(close: pd.Series) -> dict[str, float]:
    perf = {}
    for label, window in PERFORMANCE_WINDOWS.items():
        value = roc(close, window).iloc[-1]
        perf[label] = float(value) if pd.notna(value) else float("nan")
    ytd = _ytd_return(close)
    perf["YTD"] = ytd if ytd is not None else float("nan")
    return perf


def compute_relative_strength(close: pd.Series, benchmark_close: pd.Series) -> RelativeStrength:
    """Performance across 1W/1M/3M/6M/YTD for a stock and a benchmark, plus the
    difference (relative strength) for each window.
    """
    perf = _performance_snapshot(close)
    bench_perf = _performance_snapshot(benchmark_close)
    relative = {
        k: (perf[k] - bench_perf[k]) if pd.notna(perf[k]) and pd.notna(bench_perf[k]) else float("nan")
        for k in perf
    }
    outperforming = pd.notna(relative["1M"]) and relative["1M"] > 0
    return RelativeStrength(
        performance=perf,
        benchmark_performance=bench_perf,
        relative=relative,
        outperforming_benchmark_1m=bool(outperforming),
    )
