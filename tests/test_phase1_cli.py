import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from bananatrade.cli import app

runner = CliRunner()


def test_missing_key_cli_message(monkeypatch) -> None:
    monkeypatch.delenv("NINEROUTER_API_KEY", raising=False)
    monkeypatch.setattr("bananatrade.cli.load_dotenv", lambda *args, **kwargs: None)
    result = runner.invoke(app, ["ping", "--skip-cio"])
    assert result.exit_code == 2
    assert "NINEROUTER_API_KEY is not set" in result.output
    assert "Traceback" not in result.output


def test_scan_offline_has_real_table() -> None:
    result = runner.invoke(app, ["scan", "--offline"])
    assert result.exit_code == 0
    assert "BTC/USDT" in result.stdout
    assert "last_close" in result.stdout
    assert "regime" in result.stdout
    assert "No triggers: configure" not in result.stdout
    assert "400.0" in result.stdout


def test_snapshot_offline_is_compact_json() -> None:
    result = runner.invoke(app, ["snapshot", "BTC/USDT", "--offline"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["symbol"] == "BTC/USDT"
    assert "timeframes" in payload
    assert "1h" in payload["timeframes"]


def test_offline_snapshot_is_deterministic() -> None:
    first = runner.invoke(app, ["snapshot", "BTC/USDT", "--offline"])
    second = runner.invoke(app, ["snapshot", "BTC/USDT", "--offline"])
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    frame = Path(__file__).parent / "fixtures" / "synthetic_btc_usdt_4h.csv"
    last = json.loads(frame.read_text().splitlines()[-1].split(",")[0])
    assert payload["timestamp"] == datetime.fromtimestamp((last + 14_400_000) / 1000, UTC).isoformat().replace("+00:00", "Z")


def test_offline_btc_loads_orderbook_and_funding() -> None:
    payload = json.loads(runner.invoke(app, ["snapshot", "BTC/USDT", "--offline"]).stdout)
    assert payload["data_missing"] == []
    assert payload["funding"] == 0.0001
    assert "orderbook_imbalance" in payload


def test_offline_skips_symbol_without_fixture() -> None:
    output = runner.invoke(app, ["scan", "--offline"]).stdout
    assert "no offline fixture for ETH/USDT" in output
    assert "BTC/USDT | 1h" in output
    assert "ETH/USDT |" not in output


def test_scan_offline_continues_after_symbol_error(monkeypatch) -> None:
    from bananatrade import cli

    original = cli._offline_frame

    def failing(symbol: str, timeframe: str):
        if symbol == "ETH/USDT":
            raise RuntimeError("fixture failure")
        return original(symbol, timeframe)

    monkeypatch.setattr(cli, "_offline_frame", failing)
    result = runner.invoke(app, ["scan", "--offline"])
    assert result.exit_code == 0
    assert "ERROR ETH/USDT" in result.stdout
    assert "BTC/USDT" in result.stdout
