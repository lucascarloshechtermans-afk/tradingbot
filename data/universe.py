from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from config.schema import UniverseConfig
from data.provider import TickerInfo
from indicators.volatility import atr_percent
from liquidity.liquidity import average_dollar_volume, corwin_schultz_spread_estimate

logger = logging.getLogger(__name__)

# Curated, liquid large/mid-cap US tickers. Hardcoded rather than scraped from an
# index provider (e.g. Wikipedia's S&P 500 list) so the universe has no dependency
# on a second, unrelated data source beyond the price/fundamentals API itself.
DEFAULT_UNIVERSE = [
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "ORCL", "CRM", "ADBE",
    "AMD", "QCOM", "INTC", "CSCO", "TXN", "INTU", "NOW", "IBM", "UBER", "SHOP",
    "PLTR", "SNOW", "PANW", "CRWD", "NET", "DDOG", "ABNB", "XYZ", "PYPL", "MU",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "C", "SCHW", "AXP", "BLK", "SPGI",
    "V", "MA", "COF", "USB", "PNC",
    # Healthcare
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR", "BMY",
    "AMGN", "GILD", "ISRG", "VRTX", "REGN",
    # Consumer
    "WMT", "COST", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "TJX", "BKNG",
    "DIS", "CMCSA", "NFLX", "PG", "KO", "PEP", "PM", "MO",
    # Industrials & Energy
    "CAT", "DE", "BA", "HON", "GE", "UPS", "RTX", "LMT", "UNP", "MMM",
    "XOM", "CVX", "COP", "SLB", "OXY",
    # High-beta / momentum names frequently traded on swings
    "TSLA", "COIN", "MSTR", "RIVN", "SMCI", "ARM", "DKNG", "ROKU", "RBLX", "MRNA",
    # Expansion: more liquid, typically higher-ATR% names across the same
    # sectors, to widen the daily candidate pool beyond the original 103 (a
    # small survivor pool after the RS/regime/ATR gates mechanically limits how
    # many high-conviction setups can appear on any given day, independent of
    # setup quality).
    "MRVL", "ON", "LRCX", "KLAC", "AMAT",           # semis
    "MDB", "TEAM", "ZS", "OKTA", "TTD", "GTLB", "PATH", "U",  # software/growth
    "SOFI", "AFRM", "HOOD", "DASH", "APP",           # fintech/consumer tech
    "CRSP", "NTLA", "BEAM",                          # biotech
    "FCX", "AA", "ALB", "CCJ", "VST", "CEG",         # materials/energy, higher-beta
    "CCL", "RCL", "EXPE", "W",                       # travel/consumer discretionary
]
# CFLT and EXAS were both in this list and removed: every yfinance fetch for
# them failed across every backtest/scan this session ("No history returned").
# Confirmed via IBKR (a real brokerage data feed, cross-checked interactively,
# not wired into this pipeline) that both now trade on IBKR's "VALUE" exchange
# -- IBKR's designation for a security no longer actively trading (acquired/
# delisted) -- so the failures were a real corporate action, not a yfinance bug.

# Sector -> SPDR sector ETF mapping lives in sector/rotation.py (SECTOR_ETF_MAP),
# which is the module that actually consumes it — avoid duplicating it here.


@dataclass
class UniverseFilterResult:
    included: list[str] = field(default_factory=list)
    excluded: dict[str, str] = field(default_factory=dict)


def apply_universe_filters(
    candidates: dict[str, tuple[TickerInfo, pd.DataFrame]],
    config: UniverseConfig,
) -> UniverseFilterResult:
    result = UniverseFilterResult()
    penny_floor = 5.0

    for ticker, (info, history) in candidates.items():
        if history is None or history.empty:
            result.excluded[ticker] = "no price history"
            continue

        last_price = float(history["close"].iloc[-1])
        if last_price < config.min_price:
            result.excluded[ticker] = f"price {last_price:.2f} < min_price {config.min_price}"
            continue
        if config.max_price is not None and last_price > config.max_price:
            result.excluded[ticker] = f"price {last_price:.2f} > max_price {config.max_price}"
            continue
        if config.exclude_penny_stocks and last_price < penny_floor:
            result.excluded[ticker] = f"price {last_price:.2f} below penny-stock floor {penny_floor}"
            continue

        dollar_vol = average_dollar_volume(history)
        if dollar_vol is None:
            result.excluded[ticker] = "insufficient history for average dollar volume"
            continue
        if dollar_vol < config.min_avg_dollar_volume:
            result.excluded[ticker] = (
                f"avg dollar volume {dollar_vol:,.0f} < min {config.min_avg_dollar_volume:,.0f}"
            )
            continue

        # Dollar volume alone doesn't capture actual execution cost — a stock can
        # have "enough" volume at a wide effective spread and still be expensive
        # to trade. Real historical bid/ask isn't available from this free data
        # source, so this uses the Corwin-Schultz (2012) high-low spread
        # ESTIMATOR (see liquidity/liquidity.py) rather than skipping the check.
        if len(history) >= 40:
            spread_series = corwin_schultz_spread_estimate(history["high"], history["low"])
            spread_last = spread_series.iloc[-1] if len(spread_series) else float("nan")
            if pd.notna(spread_last) and spread_last > config.max_spread_pct_estimate:
                result.excluded[ticker] = (
                    f"estimated spread {spread_last:.2f}% > max {config.max_spread_pct_estimate:.2f}% "
                    "(Corwin-Schultz estimate)"
                )
                continue

        if config.min_atr_pct > 0 and len(history) >= 15:
            atr_pct_series = atr_percent(history["high"], history["low"], history["close"])
            atr_pct_last = atr_pct_series.iloc[-1] if len(atr_pct_series) else float("nan")
            if pd.notna(atr_pct_last) and atr_pct_last < config.min_atr_pct:
                result.excluded[ticker] = (
                    f"ATR% {atr_pct_last:.2f} < min_atr_pct {config.min_atr_pct:.2f} (too low-movement)"
                )
                continue

        if info.market_cap is None:
            result.excluded[ticker] = "market cap unavailable from provider"
            continue
        if info.market_cap < config.min_market_cap:
            result.excluded[ticker] = f"market cap {info.market_cap:,.0f} < min {config.min_market_cap:,.0f}"
            continue
        if config.max_market_cap is not None and info.market_cap > config.max_market_cap:
            result.excluded[ticker] = f"market cap {info.market_cap:,.0f} > max {config.max_market_cap:,.0f} (mega-cap excluded)"
            continue

        if config.sectors:
            if info.sector is None:
                result.excluded[ticker] = "sector unavailable, cannot match sector filter"
                continue
            if info.sector not in config.sectors:
                result.excluded[ticker] = f"sector '{info.sector}' not in {config.sectors}"
                continue

        result.included.append(ticker)

    logger.info(
        "universe filter: %d included, %d excluded (of %d candidates)",
        len(result.included), len(result.excluded), len(candidates),
    )
    return result
