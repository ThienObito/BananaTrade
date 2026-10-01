from datetime import UTC, datetime

from bananatrade.data.snapshot import MarketSnapshot, TimeframeSummary


def test_snapshot_compact_last_price_is_single_source_value() -> None:
    snapshot = MarketSnapshot(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        timeframes={"1h": TimeframeSummary(last_price=123.4, indicators={"atr": 5.0})},
    )
    compact = snapshot.to_compact_dict()
    assert compact["timeframes"]["1h"]["last_price"] == 123.4
    assert compact["timeframes"]["1h"]["indicators"]["atr"] == 5.0


def test_snapshot_as_of_is_serialized() -> None:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    snapshot = MarketSnapshot(symbol="BTC/USDT", timestamp=timestamp, timeframes={})
    assert snapshot.to_compact_dict()["timestamp"] == "2025-01-01T00:00:00Z"
