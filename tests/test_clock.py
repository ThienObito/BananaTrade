from datetime import datetime, timedelta, timezone

import pytest

from bananatrade.core.clock import NaiveDatetimeError, SimulatedClock, SystemClock


def test_system_clock_is_utc_aware():
    value = SystemClock().now()
    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


def test_simulated_advance_and_set():
    clock = SimulatedClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert clock.advance(timedelta(minutes=5)).minute == 5
    assert clock.set(datetime(2024, 1, 1, 0, 10, tzinfo=timezone.utc)).minute == 10


def test_step_to_next_bar_close():
    clock = SimulatedClock(datetime(2024, 1, 1, 10, 7, tzinfo=timezone.utc))
    assert clock.step("15m") == datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc)
    assert clock.step("1h") == datetime(2024, 1, 1, 11, tzinfo=timezone.utc)


def test_naive_datetimes_rejected():
    with pytest.raises(NaiveDatetimeError):
        SimulatedClock(datetime(2024, 1, 1))
    clock = SimulatedClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(NaiveDatetimeError):
        clock.set(datetime(2024, 1, 2))


def test_simulated_clock_is_monotonic():
    clock = SimulatedClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError):
        clock.set(datetime(2023, 12, 31, tzinfo=timezone.utc))
    with pytest.raises(ValueError):
        clock.advance(timedelta(seconds=-1))
