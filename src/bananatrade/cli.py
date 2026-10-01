import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import typer
import yaml
from dotenv import load_dotenv

from .brain import Brain
from .brokers.mt5_client import MT5Client
from .brokers.mt5_executor import MT5Executor
from .config import Config
from .data.ccxt_source import CCXTPublicSource
from .data.snapshot import build_snapshot
from .data.triggers import evaluate_triggers
from .engine.execution_model import ExecutionModel
from .gateway.errors import GatewayError
from .gateway.llm_client import ConfigError, LLMClient
from .runtime import RuntimeService

app = typer.Typer()
ROOT = Path(__file__).resolve().parents[2]


@app.command()
def ping(skip_cio: bool = typer.Option(False, "--skip-cio")) -> None:
    """Call each enabled configured tier once through 9Router."""
    load_dotenv(ROOT / ".env", override=False)
    try:
        tiers = asyncio.run(_ping(skip_cio))
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    failed = False
    for result in tiers:
        typer.echo(f"{result['tier']} {result['status']} model={result.get('actual_model', '-')} {result.get('error', '')}".rstrip())
        failed = failed or result["status"] == "FAIL"
    if failed:
        raise typer.Exit(code=1)


async def _ping(skip_cio: bool) -> list[dict[str, object]]:
    client = LLMClient(ROOT / "config" / "models.yaml", Path(os.getenv("BANANATRADE_DB_PATH", ROOT / "data" / "bananatrade.db")))
    results = []
    for tier, config in client.tiers.items():
        if not config["enabled"] or (skip_cio and tier == "tier4_cio"):
            continue
        try:
            results.append({**(await client.call(tier, "Reply with the word PASS.")), "status": "PASS"})
        except GatewayError as exc:
            results.append({"tier": tier, "status": "FAIL", "error": str(exc)})
    return results


def _offline_frame(symbol: str, timeframe: str) -> pd.DataFrame:
    if symbol != "BTC/USDT":
        raise RuntimeError(f"no offline fixture for {symbol}")
    name = "synthetic_btc_usdt_1h.csv" if timeframe == "1h" else "synthetic_btc_usdt_4h.csv"
    return pd.read_csv(ROOT / "tests" / "fixtures" / name)


def _offline_as_of(frames: dict[str, pd.DataFrame]) -> pd.Timestamp:
    closes = []
    for timeframe, frame in frames.items():
        duration = {"1h": 3_600_000, "4h": 14_400_000}[timeframe]
        closes.append(int(frame.iloc[-1]["timestamp_ms"]) + duration)
        
    return pd.Timestamp(max(closes), unit="ms", tz="UTC")


def _config() -> dict[str, Any]:
    return dict(yaml.safe_load((ROOT / "config" / "markets.yaml").read_text(encoding="utf-8")))


async def _load_symbol(symbol: str, offline: bool) -> tuple[dict[str, pd.DataFrame], dict[str, Any] | None, float | None]:
    config = _config()
    timeframes = config.get("timeframes", ["1h", "4h"])
    if offline:
        frames = {tf: _offline_frame(symbol, tf) for tf in timeframes}
        orderbook = json.loads((ROOT / "tests" / "fixtures" / "orderbook_btc.json").read_text(encoding="utf-8"))
        funding_data = json.loads((ROOT / "tests" / "fixtures" / "funding_supported.json").read_text(encoding="utf-8"))
        return frames, orderbook, float(funding_data["fundingRate"])
    source = CCXTPublicSource(config.get("exchange", "kraken"))
    try:
        frames = {tf: await source.ohlcv(symbol, tf, 300) for tf in timeframes}
        return frames, await source.orderbook(symbol), await source.funding_rate(symbol)
    finally:
        await source.close()


@app.command()
def snapshot(symbol: str, offline: bool = typer.Option(False, "--offline")) -> None:
    """Print the compact market snapshot as JSON."""
    try:
        frames, orderbook, funding = asyncio.run(_load_symbol(symbol, offline))
        as_of = _offline_as_of(frames) if offline else pd.Timestamp.now(tz="UTC")
        snap = build_snapshot(symbol, frames, orderbook, funding, as_of.to_pydatetime())
        typer.echo(json.dumps(snap.to_compact_dict(), separators=(",", ":"), allow_nan=False))
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, GatewayError, ConfigError) as exc:
        typer.echo(f"ERROR {symbol}: {exc}")
        raise typer.Exit(code=1) from exc


def _load_runtime_config(config_path: str | None) -> Config:
    return Config.load_from_file(config_path) if config_path else Config.load_from_env()


@app.command()
def version() -> None:
    """Print package version."""
    from . import __version__

    typer.echo(__version__)


@app.command()
def backtest(config: str | None = typer.Option(None, "--config")) -> None:
    """Load and validate backtest configuration."""
    loaded = _load_runtime_config(config)
    typer.echo(json.dumps({"symbol": loaded.symbol, "timeframe": loaded.timeframe, "initial_equity": loaded.initial_equity}, separators=(",", ":")))


@app.command()
def serve(config: str | None = typer.Option(None, "--config")) -> None:
    """Print configured server binding."""
    loaded = _load_runtime_config(config)
    typer.echo(f"{loaded.server_host}:{loaded.server_port}")


@app.command()
def run(
    symbol: str = typer.Argument("BTC/USDT"),
    config: str | None = typer.Option(None, "--config"),
    broker: str = typer.Option("paper", "--broker"),
) -> None:
    """Fetch market data and run paper or demo-only MT5 flow."""
    loaded = _load_runtime_config(config)
    symbol = symbol or loaded.symbol
    load_dotenv(ROOT / ".env", override=False)
    try:
        if broker == "mt5":
            result = _run_mt5_once(loaded, symbol)
        else:
            result = asyncio.run(RuntimeService(ROOT, Path(os.getenv("BANANATRADE_DB_PATH", ROOT / "data" / "bananatrade.db"))).run(symbol))
        typer.echo(json.dumps(result, separators=(",", ":"), allow_nan=False, default=str))
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, GatewayError, ConfigError) as exc:
        typer.echo(f"ERROR {symbol}: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _run_mt5_once(config: Config, symbol: str) -> dict[str, object]:
    """Attach to logged-in MT5 terminal and process one closed-bar cycle."""
    client = MT5Client()
    client.connect()
    resolved = client.resolve_symbol(symbol)
    spec = client.symbol_spec(resolved)
    rates = client.get_rates(resolved, config.mt5_timeframe, 100)
    tick = client.get_tick(resolved)
    account = {"equity": config.initial_equity, "daily_pnl": 0.0, **tick}
    brain = Brain(
        execution_model=ExecutionModel(config.initial_equity, config.risk_pct),
        decision_log_path=ROOT / "trades" / "decisions.csv",
    )
    decision = brain.decide(rates[:-1] if len(rates) > 1 else rates, vars(spec), account)
    executor = MT5Executor(config, client.mt5)
    result = executor.execute(resolved, decision, spec)
    return {"broker": "mt5", "symbol": resolved, "decision": decision.as_dict(), "execution": vars(result)}


@app.command()
def scan(offline: bool = typer.Option(False, "--offline")) -> None:
    """Scan configured symbols and print closed-candle regimes and triggers."""
    config = _config()
    typer.echo("symbol | timeframe | last_close | regime | triggers")
    for symbol in config.get("symbols", ["BTC/USDT", "ETH/USDT"]):
        try:
            frames, orderbook, funding = asyncio.run(_load_symbol(symbol, offline))
            as_of = (_offline_as_of(frames) if offline else pd.Timestamp.now(tz="UTC")).to_pydatetime()
            snap = build_snapshot(symbol, frames, orderbook, funding, as_of)
            for timeframe, summary in snap.timeframes.items():
                triggers = evaluate_triggers(symbol, frames, funding, as_of, config.get("triggers", {}))
                text = ",".join(f"{item.name}={item.value}/{item.threshold}({item.direction})" for item in triggers if item.timeframe == timeframe) or "-"
                typer.echo(f"{symbol} | {timeframe} | {summary.last_price} | {summary.regime} | {text}")
        except RuntimeError as exc:
            typer.echo(f"ERROR {symbol}: {exc}")


def build_parser() -> argparse.ArgumentParser:
    """Build standard argparse interface for core runtime commands."""
    parser = argparse.ArgumentParser(prog="bananatrade")
    parser.add_argument("command", choices=("run", "backtest", "serve", "version"))
    parser.add_argument("--config", default=None)
    parser.add_argument("--broker", choices=("paper", "mt5"), default="paper")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "version":
        from . import __version__

        print(__version__)
    elif args.command == "serve":
        loaded = _load_runtime_config(args.config)
        print(f"{loaded.server_host}:{loaded.server_port}")
    elif args.command == "backtest":
        loaded = _load_runtime_config(args.config)
        print(json.dumps({"symbol": loaded.symbol, "timeframe": loaded.timeframe, "initial_equity": loaded.initial_equity}, separators=(",", ":")))
    else:
        run(config=args.config, broker=args.broker)


if __name__ == "__main__":
    main()
