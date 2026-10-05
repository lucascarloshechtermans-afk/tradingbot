"""Items 2/3/11/27: which features actually separate winning trades from
losing ones, which ones are redundant with each other, and do any
COMBINATIONS beat every feature in it alone?

Works entirely offline from a research.capture_trades pickle -- no network,
no re-running the backtest.

    python -m research.feature_importance --trades /path/to/trades.pkl
"""

from __future__ import annotations

import argparse
import pickle
import sys

import numpy as np
import pandas as pd

from research.feature_extraction import feature_names


def _analysis_feature_names() -> list[str]:
    """`feature_names()` includes the `raw_*` absolute price levels (kept only
    so research.stop_comparison can reconstruct alternative stop prices) --
    those are dollar quantities, not normalized indicators, so correlating them
    with each other or with pnl is dominated entirely by which ticker's price
    scale a trade happened to be on, not real information. Excluded here."""
    return [n for n in feature_names() if not n.startswith("raw_")]


def _build_dataframe(payload: dict) -> pd.DataFrame:
    trades = payload["trades"]
    features = payload["features"]
    rows = []
    for trade, feat in zip(trades, features):
        if trade.pnl_pct is None or feat is None:
            continue
        row = dict(feat)
        row["pnl_pct"] = trade.pnl_pct
        row["win"] = 1 if trade.pnl_pct > 0 else 0
        rows.append(row)
    return pd.DataFrame(rows)


def _point_biserial(feature: pd.Series, win: pd.Series) -> float | None:
    """Correlation between a continuous/ordinal feature and a binary win/loss
    outcome -- exactly a Pearson correlation when one side is 0/1, which is
    the point-biserial correlation coefficient by definition."""
    valid = feature.notna()
    if valid.sum() < 30:
        return None
    r = feature[valid].corr(win[valid])
    return float(r) if pd.notna(r) else None


def print_feature_importance(df: pd.DataFrame, min_n: int = 30) -> pd.DataFrame:
    """For every feature: correlation with win/loss, correlation with pnl_pct,
    and a quintile-expectancy spread (top quintile expectancy minus bottom
    quintile expectancy) -- three different lenses on "does this feature
    actually separate winners from losers", since a feature can correlate
    weakly overall but still have a strong, useful top/bottom spread (or vice
    versa: a real but small linear correlation across a huge sample)."""
    names = [c for c in _analysis_feature_names() if c in df.columns]
    results = []
    for name in names:
        col = df[name]
        valid_n = col.notna().sum()
        if valid_n < min_n:
            continue
        corr_win = _point_biserial(col, df["win"])
        corr_pnl = col.corr(df["pnl_pct"])
        corr_pnl = float(corr_pnl) if pd.notna(corr_pnl) else None

        spread = None
        nunique = col.dropna().nunique()
        if nunique >= 5:
            try:
                quintile = pd.qcut(col, 5, labels=False, duplicates="drop")
                grouped = df.assign(_q=quintile).dropna(subset=["_q"]).groupby("_q")["pnl_pct"].mean()
                if len(grouped) >= 2:
                    spread = float(grouped.iloc[-1] - grouped.iloc[0])
            except ValueError:
                pass

        results.append({"feature": name, "n": int(valid_n), "corr_vs_win": corr_win, "corr_vs_pnl_pct": corr_pnl, "top_minus_bottom_quintile_pnl_pct": spread})

    result_df = pd.DataFrame(results).sort_values("corr_vs_win", key=lambda s: s.abs(), ascending=False, na_position="last")

    print(f"\n{'=' * 90}")
    print(f"FEATURE IMPORTANCE  ({len(df)} trades)")
    print(f"{'=' * 90}")
    print(f"{'Feature':<32}{'N':<8}{'Corr vs win':<14}{'Corr vs pnl%':<14}{'Q5-Q1 pnl% spread'}")
    for _, row in result_df.iterrows():
        cw = f"{row['corr_vs_win']:+.3f}" if row["corr_vs_win"] is not None else "-"
        cp = f"{row['corr_vs_pnl_pct']:+.3f}" if row["corr_vs_pnl_pct"] is not None else "-"
        sp = f"{row['top_minus_bottom_quintile_pnl_pct']:+.2f}%" if row["top_minus_bottom_quintile_pnl_pct"] is not None else "-"
        print(f"{row['feature']:<32}{row['n']:<8}{cw:<14}{cp:<14}{sp}")
    print()
    return result_df


def print_redundancy_matrix(df: pd.DataFrame, threshold: float = 0.6) -> None:
    """Item 11: pairwise correlations among features. Any pair above
    `threshold` (in absolute value) is flagged as likely carrying the same
    information -- a composite score that grants each of them independent
    weight is quietly double/triple-counting one underlying fact."""
    names = [c for c in _analysis_feature_names() if c in df.columns and df[c].notna().sum() >= 30]
    numeric = df[names].apply(pd.to_numeric, errors="coerce")
    corr = numeric.corr()

    print(f"\n{'=' * 90}")
    print(f"REDUNDANCY CHECK — feature pairs with |correlation| >= {threshold}")
    print(f"{'=' * 90}")
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            r = corr.loc[a, b]
            if pd.notna(r) and abs(r) >= threshold:
                pairs.append((a, b, float(r)))
    pairs.sort(key=lambda t: -abs(t[2]))
    if not pairs:
        print("(none found at this threshold)")
    for a, b, r in pairs:
        print(f"  {a:<28} <-> {b:<28} r={r:+.2f}")
    print()


def print_interaction_analysis(df: pd.DataFrame) -> None:
    """Item 3: do named combinations beat their own parts? Each combo is a
    simple AND of binary/ordinal conditions already in the feature set --
    deliberately simple (median/threshold splits) rather than a fitted model,
    since the point is to check specific, named hypotheses from the
    strategy's own stated logic, not to data-mine for whatever combination
    happens to look best in this one sample."""
    combos = {
        "EMA aligned + RS>0 + RVOL>1.5": (df["ema_alignment"] == 1) & (df["relative_strength_1m"] > 0) & (df["rvol"] >= 1.5),
        "Structure HH/HL + volume confirm (RVOL>1.2)": (df["structure_ordinal"] == 1) & (df["rvol"] >= 1.2),
        "BB squeeze + ADX rising": (df["squeeze"] == 1) & (df["adx_slope"] > 0),
        "RSI bullish div + liquidity sweep": (df["rsi_bullish_divergence"] == 1) & (df["liquidity_sweep_bullish"] == 1),
        "VWAP above + higher-high structure + RS>0": (df["vwap_distance_pct"] > 0) & (df["structure_ordinal"] == 1) & (df["relative_strength_1m"] > 0),
    }
    print(f"\n{'=' * 90}")
    print("INTERACTION ANALYSIS — named combinations vs. their own parts")
    print(f"{'=' * 90}")
    for label, mask in combos.items():
        mask = mask.fillna(False)
        n = int(mask.sum())
        if n < 20:
            print(f"{label}: only {n} matching trades, skipped (too few to trust)")
            continue
        combo_trades = df[mask]
        rest = df[~mask]
        combo_exp = _expectancy(combo_trades["pnl_pct"])
        rest_exp = _expectancy(rest["pnl_pct"])
        print(f"{label}")
        print(f"  combo present (n={n}): expectancy {combo_exp:+.2f}%  |  combo absent (n={len(rest)}): expectancy {rest_exp:+.2f}%")
    print()


def _expectancy(pnl_pct: pd.Series) -> float:
    wins = pnl_pct[pnl_pct > 0]
    losses = pnl_pct[pnl_pct < 0]
    n = len(pnl_pct)
    if n == 0:
        return 0.0
    return (len(wins) / n * wins.mean() if len(wins) else 0.0) + (len(losses) / n * losses.mean() if len(losses) else 0.0)


def print_regime_conditional_importance(df: pd.DataFrame) -> None:
    """Item 6: does the same feature carry different (or opposite-signed)
    predictive power in different market regimes? Only run for regimes with
    a reasonable sample."""
    if "market_regime_ordinal" not in df.columns:
        return
    print(f"\n{'=' * 90}")
    print("REGIME-CONDITIONAL FEATURE IMPORTANCE (top 5 features by |corr vs win|, split by regime)")
    print(f"{'=' * 90}")
    key_features = ["rvol", "adx14", "relative_strength_1m", "extension_atr", "atr_pct", "ema_alignment", "distance_to_resistance_atr"]
    for regime_value, label in [(1.0, "BULLISH"), (0.0, "NEUTRAL"), (-1.0, "BEARISH"), (-0.5, "HIGH_VOLATILITY")]:
        subset = df[df["market_regime_ordinal"] == regime_value]
        if len(subset) < 50:
            print(f"{label}: only {len(subset)} trades, skipped")
            continue
        print(f"\n{label} (n={len(subset)}):")
        for feat in key_features:
            if feat not in subset.columns:
                continue
            r = _point_biserial(subset[feat], subset["win"])
            if r is not None:
                print(f"  {feat:<28} corr vs win: {r:+.3f}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=str, required=True)
    parser.add_argument("--redundancy-threshold", type=float, default=0.6)
    args = parser.parse_args(argv)

    with open(args.trades, "rb") as f:
        payload = pickle.load(f)
    df = _build_dataframe(payload)
    print(f"Loaded {len(df)} closed trades with feature data (of {len(payload['trades'])} total)")

    print_feature_importance(df)
    print_redundancy_matrix(df, threshold=args.redundancy_threshold)
    print_interaction_analysis(df)
    print_regime_conditional_importance(df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
