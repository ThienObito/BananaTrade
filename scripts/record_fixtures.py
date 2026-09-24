"""Record public CCXT fixtures for offline tests; generated files must be labeled recorded."""
import asyncio
import csv
from pathlib import Path

import ccxt.async_support as ccxt


async def main() -> None:
    out = Path(__file__).parents[1] / "tests" / "fixtures"
    exchange = ccxt.kraken({"enableRateLimit": True})
    try:
        for timeframe, limit in (("1h", 300), ("4h", 200)):
            rows = await exchange.fetch_ohlcv("BTC/USDT", timeframe, limit=limit)
            with (out / f"btc_usdt_{timeframe}.csv").open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["timestamp_ms", "open", "high", "low", "close", "volume"])
                writer.writerows(rows)
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
