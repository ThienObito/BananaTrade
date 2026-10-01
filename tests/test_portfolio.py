from datetime import datetime, timezone
import pytest
from bananatrade.execution import Portfolio, UnknownPositionError


def test_long_short_pnl_and_fees():
    p = Portfolio(1000, fee_rate=.01)
    p.open_position('a', 'LONG', 2, 100)
    assert p.close_position('a', 110) == pytest.approx(15.8)
    p.open_position('b', 'SHORT', 2, 100)
    assert p.close_position('b', 90) == pytest.approx(16.2)
    assert p.realized_pnl == pytest.approx(32.0)
    assert p.total_fees == pytest.approx(8.0)


def test_equity_peak_drawdown():
    p = Portfolio(1000)
    p.open_position('a', 'LONG', 1, 100)
    p.mark({'a': 120})
    assert p.equity == 1020 and p.peak_equity == 1020
    p.mark({'a': 90})
    assert p.equity == 990 and p.drawdown == 30


def test_daily_reset_utc():
    p = Portfolio(100, now=datetime(2024, 1, 1, 23, tzinfo=timezone.utc))
    p.open_position('a', 'LONG', 1, 1)
    p.close_position('a', 1, timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc))
    assert p.trades_today == 1


def test_unknown_position():
    with pytest.raises(UnknownPositionError):
        Portfolio(10).close_position('missing', 1)
