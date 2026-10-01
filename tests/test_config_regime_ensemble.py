import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bananatrade import __version__, web_server
from bananatrade.cli import app
from bananatrade.config import Config
from bananatrade.engine.ensemble_signal import EnsembleSignal
from bananatrade.engine.regime_detector import Regime, RegimeDetector
from bananatrade.engine.strategy import MACrossStrategy


def make_candles(count: int = 80, mode: str = "range") -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for index in range(count):
        if mode == "trend":
            close = 100.0 + index * 2.0
            spread = 1.0
        elif mode == "volatile":
            close = 100.0 + (5.0 if index % 2 else -5.0)
            spread = 8.0
        else:
            close = 100.0 + (1.0 if index % 2 else -1.0)
            spread = 0.5
        values.append({"open": close, "high": close + spread, "low": close - spread, "close": close, "volume": 100.0})
    return values


def test_config_defaults() -> None:
    assert Config() == Config("BTCUSDT", "1m", 10000.0, 0.01, 3, "H1", "fixed_2r", "ws://localhost:8765", "localhost", 8000)


def test_config_fields() -> None:
    config = Config(symbol="ETHUSDT", timeframe="5m", initial_equity=5000.0, risk_pct=0.02, max_positions=2, ws_url="ws://x", server_host="0.0.0.0", server_port=9000)
    assert config.symbol == "ETHUSDT"
    assert config.server_port == 9000
    assert config.entry_hypothesis == "H1"
    assert config.exit_model == "fixed_2r"


def test_config_save_load(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    config = Config(symbol="ETHUSDT")
    config.save_to_file(path)
    assert Config.load_from_file(path) == config


def test_config_json_is_object(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(TypeError, match="object"):
        Config.load_from_file(path)


def test_config_creates_parent(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.json"
    Config().save_to_file(path)
    assert path.exists()


def test_config_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("BT_SYMBOL", "BT_EQUITY", "BT_RISK_PCT", "BT_MAX_POSITIONS"):
        monkeypatch.delenv(name, raising=False)
    assert Config.load_from_env() == Config()


def test_config_env_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BT_SYMBOL", "ETHUSDT")
    assert Config.load_from_env().symbol == "ETHUSDT"


def test_config_env_equity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BT_EQUITY", "2500.5")
    assert Config.load_from_env().initial_equity == 2500.5


def test_config_env_risk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BT_RISK_PCT", "0.03")
    assert Config.load_from_env().risk_pct == 0.03


def test_config_env_positions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BT_MAX_POSITIONS", "7")
    assert Config.load_from_env().max_positions == 7


def test_config_invalid_env_float(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BT_EQUITY", "bad")
    with pytest.raises(ValueError, match="BT_EQUITY"):
        Config.load_from_env()


def test_config_invalid_env_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BT_MAX_POSITIONS", "bad")
    with pytest.raises(ValueError, match="BT_MAX_POSITIONS"):
        Config.load_from_env()


def test_cli_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_cli_backtest_config(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    Config(symbol="ETHUSDT").save_to_file(path)
    result = CliRunner().invoke(app, ["backtest", "--config", str(path)])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["symbol"] == "ETHUSDT"


def test_cli_serve_config(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    Config(server_port=9999).save_to_file(path)
    result = CliRunner().invoke(app, ["serve", "--config", str(path)])
    assert result.exit_code == 0
    assert result.stdout.strip() == "localhost:9999"


def test_cli_run_accepts_config_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def fake_run(*args: object) -> dict[str, object]:
        return {"status": "ok"}

    monkeypatch.setattr("bananatrade.cli.RuntimeService.run", fake_run)
    path = tmp_path / "config.json"
    Config().save_to_file(path)
    result = CliRunner().invoke(app, ["run", "BTC/USDT", "--config", str(path)])
    assert result.exit_code == 0, result.output


def test_regime_last_initially_none() -> None:
    assert RegimeDetector().last_regime is None


def test_regime_trending() -> None:
    detector = RegimeDetector()
    assert detector.detect(make_candles(mode="trend")) is Regime.TRENDING


def test_regime_ranging() -> None:
    detector = RegimeDetector()
    assert detector.detect(make_candles(mode="range")) is Regime.RANGING


def test_regime_volatile() -> None:
    detector = RegimeDetector()
    assert detector.detect(make_candles(mode="volatile")) is Regime.VOLATILE


def test_regime_last_property() -> None:
    detector = RegimeDetector()
    detector.detect(make_candles(mode="range"))
    assert detector.last_regime is Regime.RANGING


def test_regime_snapshot_metrics() -> None:
    detector = RegimeDetector()
    detector.detect(make_candles(mode="trend"))
    assert detector.last_snapshot is not None
    assert detector.last_snapshot.adx >= 0
    assert detector.last_snapshot.atr_pct >= 0


def test_regime_short_input_rejected() -> None:
    with pytest.raises(ValueError, match="15"):
        RegimeDetector().detect(make_candles(14))


def test_regime_missing_high_rejected() -> None:
    data = make_candles()
    for candle in data:
        del candle["high"]
    with pytest.raises(ValueError, match="high"):
        RegimeDetector().detect(data)


def test_regime_invalid_values_rejected() -> None:
    data = make_candles()
    data[0]["close"] = 0
    with pytest.raises(ValueError, match="positive"):
        RegimeDetector().detect(data)


def test_ensemble_short_input_neutral() -> None:
    score = EnsembleSignal().score(make_candles(20))
    assert score.bias == "NEUTRAL"
    assert score.confidence == 0.0


def test_ensemble_components_schema() -> None:
    score = EnsembleSignal().score(make_candles(mode="range"))
    assert set(score.components) == {"ma_cross_score", "rsi_score", "regime_multiplier"}


def test_ensemble_components_bounds() -> None:
    score = EnsembleSignal().score(make_candles(mode="trend"))
    assert all(0.0 <= value <= 1.0 for value in score.components.values())


def test_ensemble_confidence_bounds() -> None:
    score = EnsembleSignal().score(make_candles(mode="trend"))
    assert 0.0 <= score.confidence <= 1.0


def test_ensemble_low_confidence_gates_neutral() -> None:
    score = EnsembleSignal().score(make_candles(mode="range"))
    assert score.confidence < 0.65
    assert score.bias == "NEUTRAL"


def test_ensemble_volatile_always_neutral() -> None:
    score = EnsembleSignal().score(make_candles(mode="volatile"))
    assert score.components["regime_multiplier"] == 0.3
    assert score.bias == "NEUTRAL"


def test_ensemble_regime_detector_shared() -> None:
    detector = RegimeDetector()
    EnsembleSignal(detector).score(make_candles(mode="range"))
    assert detector.last_regime is Regime.RANGING


def test_strategy_keeps_signal_interface() -> None:
    result = MACrossStrategy().generate_signal(make_candles(mode="range"))
    assert result.bias in {"LONG", "SHORT", "NEUTRAL"}
    assert 0.0 <= result.confidence <= 1.0


def test_strategy_volatile_reason() -> None:
    result = MACrossStrategy().generate_signal(make_candles(mode="volatile"))
    assert result.bias == "NEUTRAL"
    assert "volatil" in result.reason


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


def test_regime_endpoint_schema() -> None:
    with running_server() as (host, port):
        connection = HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/api/regime")
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
    assert response.status == 200
    assert set(payload) == {"regime", "adx", "atr_pct", "confidence"}
    assert payload["regime"] in {"TRENDING", "RANGING", "VOLATILE"}
