"""UTC clock abstractions for deterministic trading logic."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable
import re

UTC = timezone.utc


class NaiveDatetimeError(ValueError):
    """Raised when a clock receives a timezone-naive datetime."""


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("clock values must be datetime instances")
    if value.tzinfo is None or value.utcoffset() is None:
        raise NaiveDatetimeError("clock datetimes must be timezone-aware")
    return value.astimezone(UTC)


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Wall clock whose values are timezone-aware UTC datetimes."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def _timeframe_delta(timeframe: str | timedelta) -> timedelta:
    if isinstance(timeframe, timedelta):
        if timeframe <= timedelta(0):
            raise ValueError("timeframe must be positive")
        return timeframe
    if not isinstance(timeframe, str):
        raise TypeError("timeframe must be a string or timedelta")
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([mhdw])\s*", timeframe.lower())
    if not match:
        raise ValueError("invalid timeframe; expected e.g. 1m, 4h, 1d")
    amount, unit = float(match.group(1)), match.group(2)
    seconds = amount * {"m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]
    if seconds <= 0:
        raise ValueError("timeframe must be positive")
    return timedelta(seconds=seconds)


class SimulatedClock:
    """Manually controlled UTC clock. Time can never move backwards."""

    def __init__(self, initial: datetime):
        self._current = _utc(initial)

    def now(self) -> datetime:
        return self._current

    def set(self, value: datetime) -> datetime:
        value = _utc(value)
        if value < self._current:
            raise ValueError("simulated clock is monotonic and cannot move backwards")
        self._current = value
        return self._current

    def advance(self, delta: timedelta) -> datetime:
        if not isinstance(delta, timedelta):
            raise TypeError("delta must be a timedelta")
        if delta < timedelta(0):
            raise ValueError("simulated clock is monotonic and cannot move backwards")
        return self.set(self._current + delta)

    def step(self, timeframe: str | timedelta) -> datetime:
        """Advance to the next bar close strictly after the current instant."""
        delta = _timeframe_delta(timeframe)
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        elapsed = (self._current - epoch).total_seconds()
        boundary = (int(elapsed // delta.total_seconds()) + 1) * delta.total_seconds()
        return self.set(epoch + timedelta(seconds=boundary))
