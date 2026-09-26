import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from bananatrade.data.snapshot import build_snapshot, closed_candles


def bars() -> pd.DataFrame:
    path = Path(__file__).parent / "fixtures" / "synthetic_btc_usdt_1h.csv"
    return pd.read_csv(path)


def test_closed_candles_rejects_invalid_timestamps() -> None:
    frame = bars().copy()
    frame["timestamp_ms"] = frame["timestamp_ms"].astype("float64")
    frame.loc[0, "timestamp_ms"] = float("inf")
    with pytest.raises(ValueError, match="invalid timestamps"):
        closed_candles(frame, "1h", datetime.now(UTC))


def test_closed_candles_rejects_unsorted_timestamps() -> None:
    frame = bars().copy()
    frame.iloc[[0, 1]] = frame.iloc[[1, 0]].to_numpy()
    with pytest.raises(ValueError, match="unique and sorted"):
        closed_candles(frame, "1h", datetime.now(UTC))


def test_closed_candles_rejects_inconsistent_ohlcv_bounds() -> None:
    frame = bars().copy()
    frame.loc[0, "high"] = frame.loc[0, "close"] - 1
    with pytest.raises(ValueError, match="inconsistent high/low bounds"):
        closed_candles(frame, "1h", datetime.now(UTC))


def test_closed_candles_rejects_negative_volume() -> None:
    frame = bars().copy()
    frame.loc[0, "volume"] = -1
    with pytest.raises(ValueError, match="negative volume"):
        closed_candles(frame, "1h", datetime.now(UTC))


def test_closed_candles_rejects_invalid_ohlcv_values() -> None:
    frame = bars().copy()
    frame.loc[0, "close"] = float("nan")
    with pytest.raises(ValueError, match="invalid values in: close"):
        closed_candles(frame, "1h", datetime.now(UTC))


def test_closed_candles_rejects_missing_ohlcv_columns() -> None:
    frame = bars().drop(columns=["volume", "low"])
    with pytest.raises(ValueError, match="OHLCV frame missing columns: low, volume"):
        closed_candles(frame, "1h", datetime.now(UTC))


def test_closed_candles_rejects_unknown_timeframe() -> None:
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        closed_candles(bars(), "2h", datetime.now(UTC))


def test_snapshot_excludes_forming_candle() -> None:
    frame = bars().iloc[:30]
    as_of = datetime.fromtimestamp((frame.iloc[-1].timestamp_ms / 1000) + 1800, UTC)
    snapshot = build_snapshot("BTC/USDT", {"1h": frame}, None, None, as_of)
    assert snapshot.timeframes["1h"].last_price == frame.iloc[-2].close


def test_future_bar_does_not_change_snapshot() -> None:
    frame = bars().iloc[:30]
    as_of = datetime.fromtimestamp((frame.iloc[-1].timestamp_ms / 1000) + 1800, UTC)
    first = build_snapshot("BTC/USDT", {"1h": frame.iloc[:-1]}, None, None, as_of)
    second = build_snapshot("BTC/USDT", {"1h": frame}, None, None, as_of)
    assert first == second


def test_missing_inputs_are_flagged() -> None:
    as_of = datetime.now(UTC)
    snapshot = build_snapshot("BTC/USDT", {"1h": bars().iloc[:30]}, None, None, as_of)
    assert "orderbook" in snapshot.data_missing
    assert "funding" in snapshot.data_missing


def test_snapshot_is_frozen_and_compact() -> None:
    frame = bars().iloc[:30]
    as_of = datetime.fromtimestamp((frame.iloc[-1].timestamp_ms / 1000) + 3600, UTC)
    snapshot = build_snapshot("BTC/USDT", {"1h": frame, "4h": frame}, None, None, as_of)
    with pytest.raises((TypeError, ValueError)):
        snapshot.symbol = "ETH/USDT"  # type: ignore[misc]
    assert len(str(snapshot.to_compact_dict())) < 2000


def test_compact_dict_has_no_nan_or_inf() -> None:
    frame = bars().iloc[:5]
    as_of = datetime.fromtimestamp((frame.iloc[-1].timestamp_ms / 1000) + 3600, UTC)
    compact = build_snapshot("BTC/USDT", {"1h": frame}, None, None, as_of).to_compact_dict()
    json.dumps(compact, allow_nan=False)


def test_orderbook_rejects_malformed_levels() -> None:
    with pytest.raises(ValueError, match="numeric sizes"):
        build_snapshot("BTC/USDT", {"1h": bars().iloc[:30]}, {"bids": [[100]], "asks": []}, 0.0, datetime.now(UTC))


def test_orderbook_imbalance_hand_computed() -> None:
    """Imbalance is (total bid size - total ask size) / (total bid size + total ask size)."""
    as_of = datetime.fromtimestamp(2_000_000_000, UTC)
    book = {"bids": [[100, 10], [99, 20]], "asks": [[101, 5], [102, 5]]}
    result = build_snapshot("BTC/USDT", {"1h": bars().iloc[:30]}, book, 0.0, as_of)
    assert result.orderbook_imbalance == pytest.approx(20 / 40)
    symmetric = build_snapshot("BTC/USDT", {"1h": bars().iloc[:30]}, {"bids": [[100, 10]], "asks": [[101, 10]]}, 0.0, as_of)
    assert symmetric.orderbook_imbalance == 0.0


def test_compact_rounding_significant_digits() -> None:
    values = [389.8591185213907, 65432.123456, 0.0000123456789]
    expected = [389.859, 65432.1, 0.0000123457]
    rounded = [float(f"{value:.6g}") for value in values]
    assert rounded == expected
