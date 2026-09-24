from typing import Any

import ccxt.async_support as ccxt
import pandas as pd


class MarketDataError(RuntimeError):
    pass


class MarketDataNetworkError(MarketDataError):
    pass


class MarketDataExchangeError(MarketDataError):
    pass


class CCXTPublicSource:
    def __init__(self, exchange_id: str = "kraken", rate_limit: bool = True) -> None:
        exchange_type = getattr(ccxt, exchange_id)
        self.exchange: Any = exchange_type({"enableRateLimit": rate_limit})

    async def ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        try:
            rows = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            frame = pd.DataFrame(rows, columns=["timestamp_ms", "open", "high", "low", "close", "volume"])
            return frame.drop_duplicates("timestamp_ms").sort_values("timestamp_ms").reset_index(drop=True)
        except (ccxt.NetworkError, TimeoutError) as exc:
            raise MarketDataNetworkError(str(exc)) from exc
        except ccxt.BaseError as exc:
            raise MarketDataExchangeError(str(exc)) from exc

    async def orderbook(self, symbol: str, limit: int = 10) -> dict[str, Any]:
        try:
            return dict(await self.exchange.fetch_order_book(symbol, limit=limit))
        except (ccxt.NetworkError, TimeoutError) as exc:
            raise MarketDataNetworkError(str(exc)) from exc
        except ccxt.BaseError as exc:
            raise MarketDataExchangeError(str(exc)) from exc

    async def funding_rate(self, symbol: str) -> float | None:
        try:
            if not self.exchange.has.get("fetchFundingRate", False):
                return None
            result = await self.exchange.fetch_funding_rate(symbol)
            return float(result["fundingRate"]) if result.get("fundingRate") is not None else None
        except (ccxt.NotSupported, ccxt.BadSymbol):
            return None
        except (ccxt.NetworkError, TimeoutError) as exc:
            raise MarketDataNetworkError(str(exc)) from exc
        except ccxt.BaseError as exc:
            raise MarketDataExchangeError(str(exc)) from exc

    async def close(self) -> None:
        await self.exchange.close()
