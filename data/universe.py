from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from config.schema import UniverseConfig
from data.provider import TickerInfo

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
]

# Sector -> SPDR sector ETF mapping lives in sector/rotation.py (SECTOR_ETF_MAP),
# which is the module that actually consumes it — avoid duplicating it here.


@dataclass
class UniverseFilterResult:
    included: list[str] = field(default_factory=list)
    excluded: dict[str, str] = field(default_factory=dict)


def average_dollar_volume(history: pd.DataFrame, window: int = 20) -> float | None:
    if history is None or history.empty or len(history) < window:
        return None
    recent = history.tail(window)
    dollar_volume = (recent["close"] * recent["volume"]).mean()
    return float(dollar_volume) if pd.notna(dollar_volume) else None


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

        if info.market_cap is None:
            result.excluded[ticker] = "market cap unavailable from provider"
            continue
        if info.market_cap < config.min_market_cap:
            result.excluded[ticker] = f"market cap {info.market_cap:,.0f} < min {config.min_market_cap:,.0f}"
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
