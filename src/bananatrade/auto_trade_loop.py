"""60-second autonomous paper-trading loop."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import TypeGuard

from .agents.execution.auto_trader import AutoTradeDecision, AutoTrader
from .paper_broker import PaperBroker

LOGGER = logging.getLogger(__name__)
LOOP_INTERVAL_SECONDS = 60.0
SignalProvider = Callable[[], Mapping[str, object] | Awaitable[Mapping[str, object]]]


async def run_auto_trade_loop(
    trader: AutoTrader,
    signal_provider: SignalProvider,
    *,
    interval_seconds: float = LOOP_INTERVAL_SECONDS,
) -> None:
    """Run paper-trading decisions until cancelled."""
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    while True:
        state = trader.broker.state()
        provided = signal_provider()
        signal = await provided if asyncio.iscoroutine(provided) else provided
        if not _is_signal_mapping(signal):
            raise TypeError("signal provider must return a mapping")
        decision = trader.run_once(state, signal)
        LOGGER.info("auto-trade decision timestamp=%s decision=%s", datetime.now(UTC).isoformat(), decision)
        await asyncio.sleep(interval_seconds)


async def run_once_from_provider(
    trader: AutoTrader,
    signal_provider: SignalProvider,
) -> AutoTradeDecision:
    """Run one decision through a synchronous or asynchronous signal provider."""
    state = trader.broker.state()
    provided = signal_provider()
    signal = await provided if asyncio.iscoroutine(provided) else provided
    if not _is_signal_mapping(signal):
        raise TypeError("signal provider must return a mapping")
    decision = trader.run_once(state, signal)
    LOGGER.info("auto-trade decision timestamp=%s decision=%s", datetime.now(UTC).isoformat(), decision)
    return decision


def _is_signal_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    return isinstance(value, Mapping)


def build_auto_trader(cash: float = 10_000.0, symbol: str = "BTC/USDT") -> AutoTrader:
    """Build the default local paper trader."""
    return AutoTrader(PaperBroker(cash), symbol=symbol)
