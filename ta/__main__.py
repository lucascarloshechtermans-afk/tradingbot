"""Command line: full technical report for one or more tickers.

    python -m ta NVDA MRNA KO --html ta_report.html

Uses yfinance (10 years of daily bars, 730 days of hourly bars), completed
sessions only. Prints a text summary and optionally writes the HTML report.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    from data.sessions import drop_incomplete_daily
    from ta.engine import analyze
    from ta.regime import classify_regime
    from ta.scoring import FAMILY_NL

    ap = argparse.ArgumentParser(description="Technical analysis report")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--html", default=None)
    ap.add_argument("--no-hourly", action="store_true")
    args = ap.parse_args(argv)
    import yfinance as yf

    def get(t, **kw):
        return yf.Ticker(t).history(auto_adjust=True, **kw)

    spy, qqq = drop_incomplete_daily(get("SPY", period="10y")), drop_incomplete_daily(get("QQQ", period="10y"))
    regime = classify_regime(spy)
    reports = []
    for t in args.tickers:
        daily = drop_incomplete_daily(get(t, period="10y"))
        hourly = None if args.no_hourly else get(t, period="730d", interval="1h")
        try:
            sector = yf.Ticker(t).info.get("sector")
        except Exception:  # noqa: BLE001
            sector = None
        from sector.rotation import SECTOR_ETF_MAP

        bm = {"SPY": spy["Close"], "QQQ": qqq["Close"]}
        etf = SECTOR_ETF_MAP.get(sector or "")
        if etf:
            bm[etf] = drop_incomplete_daily(get(etf, period="10y"))["Close"]
        r = analyze(t, daily, hourly, bm, regime)
        reports.append(r)
        print(f"\n=== {t}  slot {r.close:,.2f} ({r.as_of:%d-%m-%Y})  score {r.score.total:.0f}/100 "
              f"({'long' if r.direction > 0 else 'short'})  trend: {r.daily.trend.label_nl}")
        for s in sorted(r.setups, key=lambda s: -s.quality):
            print(f"  {'*' if s is r.primary else ' '} {s.name_nl:<26} {s.status_nl:<32} trigger: {s.trigger}; "
                  f"invalidatie: {s.invalidation}; TF mee {', '.join(s.tf_agree) or '-'} / tegen {', '.join(s.tf_disagree) or '-'}")
        for c in r.score.contributions:
            print(f"    {FAMILY_NL[c.family]:<20} {'-' if c.sub is None else f'{c.sub:5.0f}'}  x{c.weight:4.0f}%  = {c.points:5.1f}  {c.why}")
        for line in r.mtf.narrative:
            print("   ", line)
    print(f"\nMarktregime: {regime.label_nl} -- {regime.breakout_context()}")
    if args.html:
        from ui.ta_report import standalone_page

        with open(args.html, "w") as f:
            f.write(standalone_page(reports, regime))
        print(f"HTML: {args.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
