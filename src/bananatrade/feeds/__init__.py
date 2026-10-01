"""Paper-trading market-data feed components."""

from .binance_feed import BinanceFeed, Candle
from .feed_manager import FeedManager

__all__ = ["BinanceFeed", "Candle", "FeedManager"]
