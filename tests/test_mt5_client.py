from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from bananatrade.brokers.mt5_client import MT5Client, MT5ConnectionError, MT5SymbolSpec


class FakeMT5:
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 16385

    def __init__(self, symbols=None) -> None:
        self.symbols = symbols or [SimpleNamespace(name="XAUUSDm")]
        self.initialized = False
        self.shutdown_called = False

    def initialize(self):
        self.initialized = True
        return True

    def shutdown(self):
        self.shutdown_called = True

    def last_error(self):
        return "fake error"

    def symbols_get(self):
        return self.symbols

    def symbol_select(self, name, selected):
        return True

    def copy_rates_from_pos(self, name, timeframe, start, count):
        return [{"time": 1700000000, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "tick_volume": 10, "spread": 2, "real_volume": 11}]

    def symbol_info_tick(self, name):
        return SimpleNamespace(bid=99.9, ask=100.0, last=99.95, time=1700000000)

    def symbol_info(self, name):
        return SimpleNamespace(digits=2, point=0.01, volume_min=0.01, volume_step=0.01, volume_max=10.0, trade_stops_level=20, filling_mode=3)


def test_connect_attaches_without_credentials() -> None:
    module = FakeMT5()
    client = MT5Client(module)
    assert client.connect()
    assert module.initialized


def test_shutdown_calls_terminal_shutdown() -> None:
    module = FakeMT5()
    client = MT5Client(module)
    client.connect()
    client.shutdown()
    assert module.shutdown_called
    assert not client.connected


def test_suffix_symbol_is_resolved() -> None:
    client = MT5Client(FakeMT5([SimpleNamespace(name="XAUUSDm")]))
    assert client.resolve_symbol("XAUUSD") == "XAUUSDm"


def test_unknown_symbol_rejected() -> None:
    client = MT5Client(FakeMT5([]))
    with pytest.raises(KeyError, match="not found"):
        client.resolve_symbol("BTCUSD")


def test_get_rates_normalizes_and_caches(tmp_path: Path) -> None:
    client = MT5Client(FakeMT5(), tmp_path)
    rows = client.get_rates("XAUUSD", 15, 1)
    assert rows[0]["close"] == 1.5
    assert list(tmp_path.glob("mt5_XAUUSDm_M15.csv"))


def test_timeframe_value_uses_official_constants() -> None:
    client = MT5Client(FakeMT5())
    assert client.timeframe_value("M15") == 15
    assert client.timeframe_value("H1") == 16385


def test_get_tick_returns_bid_ask() -> None:
    client = MT5Client(FakeMT5())
    assert client.get_tick("XAUUSD")["ask"] == 100.0


def test_symbol_spec_has_execution_fields() -> None:
    client = MT5Client(FakeMT5())
    value = client.symbol_spec("XAUUSD")
    assert isinstance(value, MT5SymbolSpec)
    assert value.volume_step == 0.01
    assert value.stops_level == 20
    assert value.spread == pytest.approx(0.1)


def test_initialize_failure_raises() -> None:
    class Failure(FakeMT5):
        def initialize(self):
            return False
    with pytest.raises(MT5ConnectionError):
        MT5Client(Failure()).connect()


def test_rates_failure_raises() -> None:
    class Failure(FakeMT5):
        def copy_rates_from_pos(self, *args):
            return None
    with pytest.raises(MT5ConnectionError):
        MT5Client(Failure()).get_rates("XAUUSD", 15)


def test_tick_failure_raises() -> None:
    class Failure(FakeMT5):
        def symbol_info_tick(self, name):
            return None
    with pytest.raises(MT5ConnectionError):
        MT5Client(Failure()).get_tick("XAUUSD")


def test_info_failure_raises() -> None:
    class Failure(FakeMT5):
        def symbol_info(self, name):
            return None
    with pytest.raises(MT5ConnectionError):
        MT5Client(Failure()).symbol_spec("XAUUSD")
