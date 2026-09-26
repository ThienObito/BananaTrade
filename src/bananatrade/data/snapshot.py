from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from .indicators import atr, ema, range_high, range_low, regime, rsi, volume_zscore, vwap


class TimeframeSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    last_price: float
    indicators: dict[str, float | None] = Field(default_factory=dict)
    regime: str = "range"


class MarketSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    timestamp: datetime
    timeframes: dict[str, TimeframeSummary]
    orderbook_imbalance: float | None = None
    funding: float | None = None
    data_missing: list[str] = Field(default_factory=list)

    def to_compact_dict(self, precision: int = 6) -> dict[str, Any]:
        data = self.model_dump(mode="json", exclude_none=True)
        for summary in data.get("timeframes", {}).values():
            summary["last_price"] = float(f"{summary['last_price']:.{precision}g}")
            summary["indicators"] = {key: (float(f"{value:.{precision}g}") if value is not None else None) for key, value in summary["indicators"].items()}
        if data.get("orderbook_imbalance") is not None:
            data["orderbook_imbalance"] = float(f"{data['orderbook_imbalance']:.{precision}g}")
        if data.get("funding") is not None:
            data["funding"] = float(f"{data['funding']:.{precision}g}")
        return data


def closed_candles(frame: pd.DataFrame, timeframe: str, as_of: datetime) -> pd.DataFrame:
    durations = {"15m": timedelta(minutes=15), "1h": timedelta(hours=1), "4h": timedelta(hours=4), "1d": timedelta(days=1)}
    if timeframe not in durations:
        supported = ", ".join(durations)
        raise ValueError(f"Unsupported timeframe {timeframe!r}; expected one of: {supported}")
    required = {"timestamp_ms", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"OHLCV frame missing columns: {', '.join(missing)}")
    numeric = frame[list(required)].apply(pd.to_numeric, errors="coerce")
    invalid = sorted(numeric.columns[numeric.isna().any()].tolist())
    if invalid:
        raise ValueError(f"OHLCV frame contains invalid values in: {', '.join(invalid)}")
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    opened = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True)
    return frame.loc[opened + durations[timeframe] <= as_of].copy()


def _number(value: Any) -> float | None:
    return None if pd.isna(value) else float(value)


def build_snapshot(symbol: str, ohlcv_by_tf: dict[str, pd.DataFrame], orderbook: dict[str, Any] | None, funding: float | None, as_of: datetime) -> MarketSnapshot:
    summaries: dict[str, TimeframeSummary] = {}
    missing: list[str] = []
    for timeframe, frame in ohlcv_by_tf.items():
        closed = closed_candles(frame, timeframe, as_of)
        if closed.empty:
            missing.append(f"ohlcv:{timeframe}")
            continue
        summaries[timeframe] = TimeframeSummary(
            last_price=float(closed.iloc[-1]["close"]),
            regime=str(regime(closed).iloc[-1]),
            indicators={
                "ema": _number(ema(closed["close"], 20).iloc[-1]),
                "rsi": _number(rsi(closed["close"], 14).iloc[-1]),
                "atr": _number(atr(closed, 14).iloc[-1]),
                "vwap": _number(vwap(closed, 20).iloc[-1]),
                "volume_zscore": _number(volume_zscore(closed["volume"], 20).iloc[-1]),
                "range_high": _number(range_high(closed["high"], 20).iloc[-1]),
                "range_low": _number(range_low(closed["low"], 20).iloc[-1]),
            },
        )
    imbalance: float | None = None
    if orderbook is None:
        missing.append("orderbook")
    else:
        bids = sum(float(level[1]) for level in orderbook.get("bids", []))
        asks = sum(float(level[1]) for level in orderbook.get("asks", []))
        imbalance = (bids - asks) / (bids + asks) if bids + asks else None
    if funding is None:
        missing.append("funding")
    return MarketSnapshot(symbol=symbol, timestamp=as_of, timeframes=summaries, orderbook_imbalance=imbalance, funding=funding, data_missing=missing)
