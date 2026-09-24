from unittest.mock import AsyncMock

import ccxt
import pytest

from bananatrade.data.ccxt_source import (
    CCXTPublicSource,
    MarketDataExchangeError,
    MarketDataNetworkError,
)


@pytest.mark.asyncio
async def test_ohlcv_parses_sorted_unique(monkeypatch: pytest.MonkeyPatch) -> None:
    source = CCXTPublicSource()
    source.exchange.fetch_ohlcv = AsyncMock(return_value=[[2, 1, 2, 0, 1, 10], [1, 1, 2, 0, 1, 10], [2, 1, 2, 0, 1, 10]])
    frame = await source.ohlcv("BTC/USDT", "1h")
    assert list(frame["timestamp_ms"]) == [1, 2]
    await source.close()

@pytest.mark.asyncio
async def test_funding_unsupported_none() -> None:
    source = CCXTPublicSource()
    source.exchange.has["fetchFundingRate"] = False
    assert await source.funding_rate("BTC/USDT") is None
    await source.close()

@pytest.mark.asyncio
async def test_errors_map_and_close() -> None:
    for error, expected in [(ccxt.NetworkError("x"), MarketDataNetworkError), (ccxt.ExchangeError("x"), MarketDataExchangeError)]:
        source = CCXTPublicSource()
        source.exchange.fetch_ohlcv = AsyncMock(side_effect=error)
        with pytest.raises(expected):
            await source.ohlcv("BTC/USDT", "1h")
        await source.close()


def test_rate_limit_enabled() -> None:
    source = CCXTPublicSource()
    assert source.exchange.enableRateLimit is True
