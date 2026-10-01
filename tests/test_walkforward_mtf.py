import json
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path
from typing import Literal

import pytest

from bananatrade import web_server
from bananatrade.agents.execution.auto_trader import AutoTrader
from bananatrade.backtest.walk_forward import WalkForwardOptimizer, WalkForwardResult
from bananatrade.engine.adaptive_trader import AdaptiveTrader
from bananatrade.engine.execution_model import ExecutionModel
from bananatrade.engine.mtf_signal import MultiTimeframeSignal
from bananatrade.engine.strategy import SignalResult
from bananatrade.engine.trade_journal import TradeJournal
from bananatrade.paper_broker import PaperBroker


def candles(count: int = 200, start: float = 100.0, step: float = 0.1) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for index in range(count):
        close = start + index * step
        result.append({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 10.0})
    return result


class ParamStrategy:
    def __init__(self, ma_fast: int = 20, ma_slow: int = 50) -> None:
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow

    def generate_signal(self, history: list[dict[str, object]]) -> SignalResult:
        bias: Literal["LONG", "SHORT", "NEUTRAL"] = "LONG" if self.ma_fast < self.ma_slow else "NEUTRAL"
        return SignalResult(bias, 0.9, f"{self.ma_fast}/{self.ma_slow}")


class SequenceStrategy:
    def __init__(self, signals: Sequence[SignalResult]) -> None:
        self.signals = list(signals)

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        return self.signals[0]


def test_walkforward_result_type() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10, 20], "ma_slow": [40, 50]}, 5)
    assert isinstance(result, WalkForwardResult)


def test_walkforward_default_has_five_windows() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10, 20], "ma_slow": [40, 50]})
    assert len(result.windows) == 5


def test_walkforward_custom_split_count() -> None:
    result = WalkForwardOptimizer().optimize(candles(120), ParamStrategy, {"ma_fast": [10], "ma_slow": [40]}, 3)
    assert len(result.windows) == 3


def test_walkforward_train_is_before_test() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10], "ma_slow": [40]}, 5)
    assert all(window.train_end == window.test_start for window in result.windows)


def test_walkforward_train_ratio_near_seventy_percent() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10], "ma_slow": [40]}, 5)
    window = result.windows[0]
    assert (window.train_end - window.train_start) / (window.test_end - window.train_start) == pytest.approx(0.7, abs=0.02)


def test_walkforward_windows_cover_data() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10], "ma_slow": [40]}, 5)
    assert result.windows[0].train_start == 0
    assert result.windows[-1].test_end == 200


def test_walkforward_best_params_schema() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10, 20], "ma_slow": [40, 50]}, 2)
    assert set(result.windows[0].best_params) == {"ma_fast", "ma_slow"}


def test_walkforward_best_params_are_grid_values() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10, 20], "ma_slow": [40, 50]}, 2)
    params = result.windows[0].best_params
    assert params["ma_fast"] in {10, 20}
    assert params["ma_slow"] in {40, 50}


def test_walkforward_train_sharpe_present() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10], "ma_slow": [40]}, 2)
    assert isinstance(result.windows[0].train_sharpe, float)


def test_walkforward_test_sharpe_present() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10], "ma_slow": [40]}, 2)
    assert isinstance(result.windows[0].test_sharpe, float)


def test_walkforward_avg_sharpe_computed() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10], "ma_slow": [40]}, 5)
    assert result.avg_sharpe == pytest.approx(sum(window.test_sharpe for window in result.windows) / 5)


def test_walkforward_stability_between_zero_one() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10], "ma_slow": [40]}, 5)
    assert 0.0 <= result.stability_score <= 1.0


def test_walkforward_stability_counts_positive_tests() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10], "ma_slow": [40]}, 5)
    expected = sum(window.test_sharpe > 0 for window in result.windows) / 5
    assert result.stability_score == expected


def test_walkforward_test_result_attached() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10], "ma_slow": [40]}, 2)
    assert result.windows[0].test_result.total_trades >= 0


def test_walkforward_rejects_bad_split_count() -> None:
    with pytest.raises(ValueError, match="positive"):
        WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10]}, 0)


def test_walkforward_rejects_short_data() -> None:
    with pytest.raises(ValueError, match="short"):
        WalkForwardOptimizer().optimize(candles(5), ParamStrategy, {"ma_fast": [10]}, 5)


def test_walkforward_rejects_empty_grid() -> None:
    with pytest.raises(ValueError, match="param_grid"):
        WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": []}, 2)


def test_walkforward_grid_evaluates_multiple_params() -> None:
    result = WalkForwardOptimizer().optimize(candles(), ParamStrategy, {"ma_fast": [10, 20], "ma_slow": [40, 50]}, 2)
    assert result.windows[0].best_params["ma_fast"] == 10


def test_mtf_resample_groups_five_bars() -> None:
    result = MultiTimeframeSignal.resample(candles(10))
    assert len(result) == 2


def test_mtf_resample_ohlc() -> None:
    data = candles(5)
    result = MultiTimeframeSignal.resample(data)
    assert result[0]["open"] == data[0]["open"]
    assert result[0]["close"] == data[-1]["close"]
    high_values = [item["high"] for item in data]
    assert result[0]["high"] == max(value for value in high_values if isinstance(value, (int, float)))


def test_mtf_resample_volume() -> None:
    result = MultiTimeframeSignal.resample(candles(5))
    assert result[0]["volume"] == 50.0


def test_mtf_resample_empty() -> None:
    assert MultiTimeframeSignal.resample([]) == []


def test_mtf_disagreement_false() -> None:
    long_signal = SignalResult("LONG", 0.9, "long")
    short_signal = SignalResult("SHORT", 0.9, "short")

    class Disagree:
        def __init__(self) -> None:
            self.calls = 0

        def generate_signal(self, data: list[dict[str, object]]) -> SignalResult:
            self.calls += 1
            return long_signal if self.calls == 1 else short_signal

    assert MultiTimeframeSignal(Disagree()).confirm(candles(10), candles(2)) is False


def test_mtf_agreement_true() -> None:
    signal = SignalResult("LONG", 0.9, "long")

    class Agree:
        def generate_signal(self, data: list[dict[str, object]]) -> SignalResult:
            return signal

    assert MultiTimeframeSignal(Agree()).confirm(candles(10), candles(2)) is True


def test_mtf_short_agreement_true() -> None:
    signal = SignalResult("SHORT", 0.8, "short")

    class Agree:
        def generate_signal(self, data: list[dict[str, object]]) -> SignalResult:
            return signal

    assert MultiTimeframeSignal(Agree()).confirm(candles(10), candles(2)) is True


def test_mtf_low_confidence_false() -> None:
    signal = SignalResult("LONG", 0.59, "weak")

    class Weak:
        def generate_signal(self, data: list[dict[str, object]]) -> SignalResult:
            return signal

    assert MultiTimeframeSignal(Weak()).confirm(candles(10), candles(2)) is False


def test_mtf_neutral_false() -> None:
    signal = SignalResult("NEUTRAL", 0.9, "none")

    class Neutral:
        def generate_signal(self, data: list[dict[str, object]]) -> SignalResult:
            return signal

    assert MultiTimeframeSignal(Neutral()).confirm(candles(10), candles(2)) is False


def test_mtf_custom_threshold() -> None:
    assert MultiTimeframeSignal(min_confidence=0.8).min_confidence == 0.8


def test_mtf_invalid_threshold() -> None:
    with pytest.raises(ValueError, match="confidence"):
        MultiTimeframeSignal(min_confidence=1.1)


def test_mtf_missing_ohlc_resample() -> None:
    assert MultiTimeframeSignal.resample([{"close": 1.0}]) == []


def test_mtf_uses_explicit_five_minute_data() -> None:
    signal = SignalResult("LONG", 0.9, "ok")

    class Agree:
        def generate_signal(self, data: list[dict[str, object]]) -> SignalResult:
            return signal

    assert MultiTimeframeSignal(Agree()).confirm(candles(10), candles(2))


def test_adaptive_mtf_blocks_disagreement(tmp_path: Path) -> None:
    class Fixed:
        def generate_signal(self, data: Sequence[dict[str, object]]) -> SignalResult:
            return SignalResult("LONG", 0.9, "fixed")

    class Block:
        def confirm(self, one: Sequence[dict[str, object]], five: Sequence[dict[str, object]] | None = None) -> bool:
            return False

    trader = AdaptiveTrader(AutoTrader(PaperBroker(10_000.0)), strategy=Fixed(), mtf_signal=Block(), journal=TradeJournal(tmp_path / "j.csv"))
    decision = trader.run_once(trader.broker.state(), candles(60))
    assert decision["action"] == "NONE"
    assert "multi-timeframe" in decision["reason"]


def test_adaptive_mtf_allows_agreement(tmp_path: Path) -> None:
    class Fixed:
        def generate_signal(self, data: Sequence[dict[str, object]]) -> SignalResult:
            return SignalResult("LONG", 0.9, "fixed")

    class Allow:
        def confirm(self, one: Sequence[dict[str, object]], five: Sequence[dict[str, object]] | None = None) -> bool:
            return True

    trader = AdaptiveTrader(AutoTrader(PaperBroker(10_000.0)), strategy=Fixed(), mtf_signal=Allow(), execution_model=ExecutionModel(), journal=TradeJournal(tmp_path / "j.csv"))
    decision = trader.run_once(trader.broker.state(), candles(60))
    assert decision["action"] == "BUY"


def test_walkforward_endpoint_schema() -> None:
    payload = web_server.walkforward_state()
    assert set(payload) == {"windows", "avg_sharpe", "stability_score"}
    assert isinstance(payload["windows"], list)
    stability_score = payload["stability_score"]
    assert isinstance(stability_score, (int, float))
    assert 0.0 <= stability_score <= 1.0


@contextmanager
def running_server() -> Iterator[tuple[str, int]]:
    server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = server.server_address
        assert isinstance(address, tuple)
        host, port = address[0], address[1]
        assert isinstance(host, str)
        assert isinstance(port, int)
        yield host, port
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_walkforward_endpoint_http() -> None:
    with running_server() as (host, port):
        connection = HTTPConnection(host, port, timeout=20)
        connection.request("GET", "/api/walkforward")
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
    assert response.status == 200
    assert {"windows", "avg_sharpe", "stability_score"} <= set(payload)
