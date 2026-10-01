"""Paper-trading bar engine and deterministic strategy components."""

from .bar_engine import BarEngine
from .entry_optimizer import EntryOptimizer, LimitEntry
from .exit_manager import ExitManager, PartialExit
from .position_sizer import PositionSizer
from .strategy import MACrossStrategy, SignalResult
from .trade_journal import TradeJournal

__all__ = [
    "BarEngine",
    "EntryOptimizer",
    "ExitManager",
    "LimitEntry",
    "MACrossStrategy",
    "PartialExit",
    "PositionSizer",
    "SignalResult",
    "TradeJournal",
]
