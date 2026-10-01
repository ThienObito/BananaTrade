"""Async paper-trading bot orchestration."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any, TypeGuard

from .agents.execution.auto_trader import AutoTradeDecision, AutoTrader
from .brain import Brain
from .brokers.mt5_client import MT5Client
from .brokers.mt5_executor import MT5Executor
from .config import Config
from .engine.adaptive_trader import AdaptiveTrader
from .engine.bar_engine import BarEngine
from .engine.exit_manager import ExitManager
from .engine.strategy import MACrossStrategy
from .engine.trade_journal import TradeJournal
from .feeds.feed_manager import FeedManager

LOGGER = logging.getLogger(__name__)
SnapshotProvider = Callable[[], Mapping[str, object] | Awaitable[Mapping[str, object]]]


def _is_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    return isinstance(value, Mapping)


class BotRunner:
    """Run one deterministic paper-trading cycle or repeat every 60 seconds."""

    def __init__(
        self,
        snapshot_provider: SnapshotProvider,
        trader: AutoTrader | AdaptiveTrader | None,
        *,
        bar_engine: BarEngine | None = None,
        strategy: MACrossStrategy | None = None,
        exit_manager: ExitManager | None = None,
        journal: TradeJournal | None = None,
        feed_manager: FeedManager | None = None,
        interval_seconds: float = 60.0,
        mt5_client: MT5Client | None = None,
        mt5_executor: MT5Executor | None = None,
        brain: Brain | None = None,
        config: Config | None = None,
    ) -> None:
        self.snapshot_provider = snapshot_provider
        self.trader = trader if isinstance(trader, AdaptiveTrader) else AdaptiveTrader(trader, strategy=strategy, journal=journal) if trader is not None else None
        self.bar_engine = bar_engine or BarEngine(max_candles=200)
        self.strategy = strategy or (self.trader.strategy_protocol if isinstance(self.trader, AdaptiveTrader) else MACrossStrategy())
        self.exit_manager = exit_manager or ExitManager()
        self.journal = journal or (self.trader.journal if isinstance(self.trader, AdaptiveTrader) else TradeJournal())
        self.feed_manager = feed_manager
        self.interval_seconds = interval_seconds
        self.config = config or Config()
        self.mt5_client = mt5_client
        self.mt5_executor = mt5_executor
        self.brain = brain
        self.last_mt5_result: object | None = None
        self._last_mt5_bar_timestamp: object | None = None

    async def run_cycle(self) -> dict[str, object]:
        """Fetch one snapshot, process one bar, exits, and optional entry."""
        snapshot = await self._resolve_snapshot(self.snapshot_provider())
        candle = self._candle(snapshot)
        indicators = self._snapshot_indicators(snapshot)
        if indicators is not None:
            if "atr14" in indicators:
                candle["atr14"] = indicators["atr14"]
            elif "atr" in indicators:
                candle["atr14"] = indicators["atr"]
        mt5_mode = self.mt5_client is not None and self.mt5_executor is not None and self.brain is not None
        if mt5_mode and isinstance(snapshot.get("candles"), list):
            raw_history = snapshot["candles"]
            if not isinstance(raw_history, list):
                raw_history = []
            closed_history = snapshot.get("closed_candles", raw_history[:-1] if len(raw_history) > 1 else raw_history)
            if not isinstance(closed_history, list):
                closed_history = []
            history = [dict(item) for item in closed_history if isinstance(item, Mapping)]
            if history:
                latest_closed = history[-1]
                timestamp = latest_closed.get("timestamp", latest_closed.get("time"))
                if not self.bar_engine.candles:
                    for historical_candle in history:
                        self.bar_engine.on_bar(historical_candle)
                    self._last_mt5_bar_timestamp = timestamp
                elif timestamp != self._last_mt5_bar_timestamp:
                    self.bar_engine.on_bar(latest_closed)
                    self._last_mt5_bar_timestamp = timestamp
            else:
                self.bar_engine.on_bar(candle)
        else:
            self.bar_engine.on_bar(candle)
        price = self._number(snapshot.get("last_price", candle.get("close")))
        if mt5_mode:
            if self.mt5_client is None or self.mt5_executor is None or self.brain is None:
                raise RuntimeError("MT5 runner dependencies are missing")
            symbol = self.mt5_client.resolve_symbol(self.config.symbol)
            spec = self.mt5_client.symbol_spec(symbol)
            tick = self.mt5_client.get_tick(symbol)
            account_state_fn = getattr(self.mt5_client, "account_state", None)
            if "equity" not in snapshot and callable(account_state_fn):
                # Live terminal values: real equity, today's PnL and open positions.
                live = account_state_fn(symbol)
                daily_pnl = self._number(live.get("daily_pnl", 0.0))
                account_state: dict[str, object] = {**live, "daily_pnl": daily_pnl, **tick}
            else:
                daily_pnl = self._number(snapshot.get("daily_pnl", 0.0))
                account_state = {"equity": self._number(snapshot.get("equity", 0.0)), "daily_pnl": daily_pnl, "open_count": 0, **tick}
            mt5_decision = self.brain.decide(self.bar_engine.candles, vars(spec), account_state)
            self.last_mt5_result = self.mt5_executor.execute(symbol, mt5_decision, spec, today_pnl=daily_pnl)
            return {"decision": mt5_decision.as_dict(), "mt5_result": self.last_mt5_result}
        if price <= 0:
            raise ValueError("snapshot needs positive last_price or close")
        if self.trader is None:
            raise RuntimeError("paper trader is not configured")
        state = self.trader.broker.state({self.trader.symbol: price})
        positions = self._managed_positions(state)
        partial_exits = []
        for position in positions:
            partial = self.exit_manager.partial_take_profit(position, price)
            if partial is not None:
                partial_exits.append(partial)
                fill = self.trader.broker.submit_market(
                    str(partial.symbol),
                    partial.side,
                    partial.quantity,
                    partial.price,
                )
                if isinstance(self.trader, AdaptiveTrader):
                    self.trader.record_partial_exit()
                self.journal.append(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                        "symbol": partial.symbol,
                        "side": partial.side,
                        "entry": "",
                        "exit": partial.price,
                        "sl": "",
                        "tp": "",
                        "qty": partial.quantity,
                        "pnl": "",
                        "reason": partial.reason,
                        "order_id": fill.order_id,
                    }
                )
        exits = self.exit_manager.check_exits(positions, price)
        for action in exits:
            action_symbol = str(action["symbol"])
            action_side = str(action["side"])
            action_quantity = float(action["quantity"])
            fill = self.trader.broker.submit_market(action_symbol, action_side, action_quantity, price)
            self.journal.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "symbol": action_symbol,
                    "side": action_side,
                    "entry": "",
                    "exit": price,
                    "sl": "",
                    "tp": "",
                    "qty": action_quantity,
                    "pnl": "",
                    "reason": action["reason"],
                    "order_id": fill.order_id,
                }
            )
        sl: float | None = None
        tp: float | None = None
        paper_decision: AutoTradeDecision
        if not exits and isinstance(self.trader, AdaptiveTrader):
            paper_decision = self.trader.run_once(state, self.bar_engine.candles)
            signal = self.trader.last_signal or self.strategy.generate_signal(self.bar_engine.candles)
        elif not exits:
            signal = self.strategy.generate_signal(self.bar_engine.candles)
            signal_payload: dict[str, object] = {
                "bias": signal.bias,
                "confidence": signal.confidence,
                "reason": signal.reason,
                "price": price,
                "stale": False,
            }
            atr14 = self._atr14()
            sl = price - 2 * atr14 if signal.bias == "LONG" else price + 2 * atr14 if signal.bias == "SHORT" else None
            tp = price + 3 * atr14 if signal.bias == "LONG" else price - 3 * atr14 if signal.bias == "SHORT" else None
            paper_decision = self.trader.trader.run_once(state, signal_payload, stop_loss=sl, take_profit=tp)
        else:
            signal = self.strategy.generate_signal(self.bar_engine.candles)
            paper_decision = {"action": "NONE", "reason": "exit executed", "order_id": None}
        if paper_decision["order_id"] is not None and not isinstance(self.trader, AdaptiveTrader):
            if self.trader.symbol in self.trader.broker.positions:
                pos = self.trader.broker.positions[self.trader.symbol]
                pos.stop_loss = sl
                pos.take_profit = tp
            if not isinstance(self.trader, AdaptiveTrader):
                self.journal.append(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                        "symbol": self.trader.symbol,
                        "side": paper_decision["action"],
                        "entry": price,
                        "exit": "",
                        "sl": sl if sl is not None else "",
                        "tp": tp if tp is not None else "",
                        "qty": 1.0,
                        "pnl": "",
                        "reason": paper_decision["reason"],
                    }
                )
        result: dict[str, object] = {"signal": signal, "exits": exits, "partial_exits": partial_exits, "decision": paper_decision}
        LOGGER.info("paper bot cycle timestamp=%s result=%s", datetime.now(UTC).isoformat(), result)
        return result

    async def run_once(self) -> dict[str, object]:
        """Run one paper-trading cycle."""
        return await self.run_cycle()

    async def main_loop(self) -> None:
        """Run feed and paper cycles concurrently until cancellation."""
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if self.feed_manager is None:
            while True:
                await self.run_cycle()
                await asyncio.sleep(self.interval_seconds)

        async def trading_loop() -> None:
            while True:
                await self.run_cycle()
                await asyncio.sleep(self.interval_seconds)

        await asyncio.gather(self.feed_manager.start(), trading_loop())

    @staticmethod
    async def _resolve_snapshot(
        provided: Mapping[str, object] | Awaitable[Mapping[str, object]],
    ) -> Mapping[str, object]:
        if asyncio.iscoroutine(provided):
            resolved = await provided
            if _is_mapping(resolved):
                return resolved
            raise TypeError("snapshot provider must return a mapping")
        if _is_mapping(provided):
            return provided
        raise TypeError("snapshot provider must return a mapping")

    def _managed_positions(self, state: Mapping[str, object]) -> list[dict[str, object]]:
        if self.trader is None:
            return []
        positions = state.get("positions", [])
        if not isinstance(positions, list):
            return []
        result: list[dict[str, object]] = []
        for position in positions:
            if not isinstance(position, Mapping):
                continue
            broker_position = self.trader.broker.positions.get(str(position.get("symbol")))
            if broker_position is not None:
                managed = dict(position)
                managed["entry"] = broker_position.average_price
                if broker_position.stop_loss is not None:
                    managed["stop_loss"] = broker_position.stop_loss
                if broker_position.take_profit is not None:
                    managed["take_profit"] = broker_position.take_profit
                result.append(managed)
            else:
                result.append(dict(position))
        return result

    @staticmethod
    def _snapshot_indicators(snapshot: Mapping[str, object]) -> Mapping[str, object] | None:
        indicators = snapshot.get("indicators")
        if isinstance(indicators, Mapping):
            return indicators
        return None

    def _atr14(self) -> float:
        latest = self.bar_engine.candles[-1] if self.bar_engine.candles else {}
        value = self._number(latest.get("atr14", latest.get("atr")))
        return value if value > 0 else 1.0

    @staticmethod
    def _candle(snapshot: Mapping[str, object]) -> dict[str, Any]:
        candles = snapshot.get("candles")
        if isinstance(candles, list) and candles and isinstance(candles[-1], Mapping):
            return dict(candles[-1])
        last_price = snapshot.get("last_price", 0.0)
        return {
            "open": last_price,
            "high": last_price,
            "low": last_price,
            "close": last_price,
            "volume": 0.0,
        }

    @staticmethod
    def _number(value: object) -> float:
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0
