"""Bar-by-bar paper-trading backtester with conservative execution costs."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite, sqrt
from statistics import mean, pstdev
from typing import Protocol

from ..engine.bar_engine import BarEngine
from ..engine.strategy import SignalResult
from ..research.mt5_costs import MT5CostModel


class StrategyProtocol(Protocol):
    """Strategy contract required by the backtest engine."""

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        """Generate one signal from bars available before next-bar execution."""
        ...


@dataclass(frozen=True)
class BacktestResult:
    """Backtest trades, gross metrics, and realistic net-cost metrics.

    Existing fields retain gross, signal-level semantics for compatibility. The
    ``net_*`` fields include taker fees, market slippage, and actual limit fills.
    """

    trades: list[dict[str, object]]
    equity_curve: list[float]
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    fees_paid: float = 0.0
    limit_orders: int = 0
    limit_fills: int = 0
    slippage_paid: float = 0.0
    net_equity_curve: list[float] | None = None
    net_total_return_pct: float = 0.0
    net_max_drawdown_pct: float = 0.0
    net_sharpe_ratio: float = 0.0
    spread_cost_paid: float = 0.0
    commission_paid: float = 0.0

    @property
    def limit_fill_rate(self) -> float:
        """Return filled limit orders divided by submitted limit orders."""
        return self.limit_fills / self.limit_orders if self.limit_orders else 0.0


class BacktestEngine:
    """Simulate closed-bar signals and next-bar paper execution."""

    def __init__(
        self,
        fee_rate: float = 0.001,
        slippage_pct: float = 0.0002,
        limit_expiry_bars: int = 2,
        cost_model: MT5CostModel | None = None,
        quantity_step: float = 1.0,
    ) -> None:
        if not isfinite(fee_rate) or fee_rate < 0:
            raise ValueError("fee_rate must be non-negative and finite")
        if not isfinite(slippage_pct) or slippage_pct < 0:
            raise ValueError("slippage_pct must be non-negative and finite")
        if limit_expiry_bars <= 0:
            raise ValueError("limit_expiry_bars must be positive")
        if not isfinite(quantity_step) or quantity_step <= 0:
            raise ValueError("quantity_step must be positive and finite")
        self.fee_rate = float(fee_rate)
        self.slippage_pct = float(slippage_pct)
        self.limit_expiry_bars = limit_expiry_bars
        # Smallest tradable size increment. 1.0 keeps the historical whole-unit sizing;
        # crypto (e.g. BTCUSDT 0.00001) and MT5 lots (e.g. 0.01) need a fractional step,
        # otherwise any instrument priced above equity rounds to 0 and never trades.
        self.quantity_step = float(quantity_step)
        self.default_cost_model = cost_model
        self._fees_paid = 0.0
        self._slippage_paid = 0.0
        self._limit_orders = 0
        self._limit_fills = 0
        self._cancelled_orders = 0
        self._cost_model: MT5CostModel | None = None
        self._spread_cost_paid = 0.0
        self._commission_paid = 0.0

    def run(
        self,
        candles: list[dict[str, object]],
        strategy: StrategyProtocol,
        initial_equity: float = 10_000.0,
        *,
        partial_take_profit: bool = False,
        exit_model: str = "fixed_3r",
        time_stop_bars: int = 24,
        stop_atr_multiplier: float = 2.0,
        partial_take_profit_r: float = 1.0,
        trailing_r: float = 1.0,
        cost_model: MT5CostModel | None = None,
    ) -> BacktestResult:
        """Run one chronological backtest with no look-ahead."""
        if not candles:
            raise ValueError("candles must not be empty")
        if not isfinite(initial_equity) or initial_equity <= 0:
            raise ValueError("initial_equity must be positive and finite")
        if exit_model not in {"fixed_2r", "fixed_3r", "atr_trailing_2x", "time_stop_24"}:
            raise ValueError("unsupported exit_model")
        if time_stop_bars <= 0:
            raise ValueError("time_stop_bars must be positive")
        if not isfinite(stop_atr_multiplier) or stop_atr_multiplier <= 0:
            raise ValueError("stop_atr_multiplier must be positive and finite")
        if not isfinite(partial_take_profit_r) or partial_take_profit_r <= 0:
            raise ValueError("partial_take_profit_r must be positive and finite")
        if not isfinite(trailing_r) or trailing_r <= 0:
            raise ValueError("trailing_r must be positive and finite")
        active_model = cost_model if cost_model is not None else self.default_cost_model
        self._cost_model = active_model
        normalized = [self._normalize_candle(candle, require_spread=active_model is not None) for candle in candles]
        lookback = getattr(strategy, "lookback", None)
        max_candles = max(50, len(normalized))
        if isinstance(lookback, int) and lookback > 0:
            max_candles = lookback
        bar_engine = BarEngine(max_candles=max_candles)
        trades: list[dict[str, object]] = []
        equity_curve = [float(initial_equity)]
        net_equity_curve = [float(initial_equity)]
        gross_cash = float(initial_equity)
        net_cash = float(initial_equity)
        position: dict[str, object] | None = None
        pending: dict[str, object] | None = None
        symbol = "BTC/USDT"
        next_position_id = 1
        self._fees_paid = 0.0
        self._slippage_paid = 0.0
        self._limit_orders = 0
        self._limit_fills = 0
        self._cancelled_orders = 0
        self._spread_cost_paid = 0.0
        self._commission_paid = 0.0
        settled_trades = 0
        blocked_bias: str | None = None
        for index, candle in enumerate(normalized):
            closed_this_bar = False
            if position is not None and position.get("entry_index") != index:
                self._check_position_exit(position, candle, trades, partial_take_profit, exit_model, time_stop_bars, index, partial_take_profit_r, trailing_r)
                gross_cash, net_cash, settled_trades = self._settle_new_trades(
                    trades, settled_trades, gross_cash, net_cash
                )
                if position.get("exit") is not None:
                    blocked_bias = str(position["side"])
                    position = None
                    closed_this_bar = True
            if pending is not None and position is None:
                if self._pending_expired(pending, index):
                    self._cancelled_orders += 1
                    pending = None
                else:
                    filled_price = self._pending_fill_price(pending, candle)
                    if filled_price is not None:
                        signal = self._signal(pending)
                        position = self._open_position(
                            signal,
                            filled_price,
                            net_cash,
                            candle,
                            symbol,
                            partial_take_profit,
                            limit_fill=self._is_limit(pending),
                            exit_model=exit_model,
                            stop_atr_multiplier=stop_atr_multiplier,
                            partial_take_profit_r=partial_take_profit_r,
                            trailing_r=trailing_r,
                        )
                        if position is not None:
                            position["entry_index"] = index
                            pending_index = pending.get("index")
                            if not isinstance(pending_index, int) or isinstance(pending_index, bool):
                                raise TypeError("pending index must be an integer")
                            position["signal_index"] = pending_index
                            position["position_id"] = next_position_id
                            next_position_id += 1
                        if position is not None and self._is_limit(pending):
                            self._limit_fills += 1
                        pending = None
                        if position is not None:
                            self._check_position_exit(position, candle, trades, partial_take_profit, exit_model, time_stop_bars, index, partial_take_profit_r, trailing_r)
                            gross_cash, net_cash, settled_trades = self._settle_new_trades(
                                trades, settled_trades, gross_cash, net_cash
                            )
                            if position.get("exit") is not None:
                                blocked_bias = str(position["side"])
                                position = None
                                closed_this_bar = True
            bar_engine.on_bar(candle)
            history = bar_engine.candles
            lookback = getattr(strategy, "lookback", None)
            if isinstance(lookback, int) and lookback > 0:
                history = history[-lookback:]
            candles_for_signal = [dict(item) for item in history]
            signal = strategy.generate_signal(candles_for_signal)
            if not closed_this_bar and pending is None and position is None and index < len(normalized) - 1 and signal.bias != blocked_bias:
                pending = self._new_pending(signal, candle, index)
                if signal.bias != "NEUTRAL" and self._is_limit(pending):
                    self._limit_orders += 1
            gross_mark = gross_cash
            net_mark = net_cash
            if position is not None:
                quantity = self._number(position["qty"])
                direction = 1 if position["side"] == "LONG" else -1
                entry = self._number(position["entry"])
                entry_fill = self._number(position["entry_fill"])
                gross_mark += (candle["close"] - entry) * quantity * direction
                exit_mark = self._market_exit_fill(candle["close"], str(position["side"]), candle)
                exit_fee = exit_mark * quantity * self.fee_rate
                entry_fee = self._number(position.get("entry_fee", 0.0))
                entry_commission = self._number(position.get("entry_commission", 0.0))
                net_mark += (exit_mark - entry_fill) * quantity * direction - entry_fee - exit_fee - entry_commission
            equity_curve.append(gross_mark)
            net_equity_curve.append(net_mark)

        if pending is not None and self._is_limit(pending):
            self._cancelled_orders += 1
        if position is not None:
            position["exit_candle"] = dict(normalized[-1])
            self._close_position(position, float(normalized[-1]["close"]), "end_of_data", trades)
            gross_cash, net_cash, settled_trades = self._settle_new_trades(
                trades, settled_trades, gross_cash, net_cash
            )
            equity_curve[-1] = gross_cash
            net_equity_curve[-1] = net_cash
        return self._result(
            trades,
            equity_curve,
            initial_equity,
            net_equity_curve=net_equity_curve,
            fees_paid=self._fees_paid,
            slippage_paid=self._slippage_paid,
            spread_cost_paid=self._spread_cost_paid,
            commission_paid=self._commission_paid,
            limit_orders=self._limit_orders,
            limit_fills=self._limit_fills,
        )

    def _open_position(
        self,
        signal: SignalResult,
        entry: float,
        equity: float,
        candle: dict[str, float],
        symbol: str,
        partial_take_profit: bool = False,
        *,
        limit_fill: bool = False,
        exit_model: str = "fixed_3r",
        stop_atr_multiplier: float = 1.5,
        partial_take_profit_r: float = 1.0,
        trailing_r: float = 1.0,
    ) -> dict[str, object] | None:
        if signal.bias == "NEUTRAL" or equity <= 0:
            return None
        atr14 = self._atr_value(candle, entry)
        entry_fill = self._limit_entry_fill(entry, signal.bias, candle) if limit_fill and self._cost_model is not None else entry if limit_fill else self._market_entry_fill(entry, signal.bias, candle)
        if signal.bias == "LONG":
            stop_loss = entry_fill - stop_atr_multiplier * atr14
        else:
            stop_loss = entry_fill + stop_atr_multiplier * atr14
        per_lot_cost = 0.0
        if self._cost_model is not None:
            per_lot_cost = self._cost_model.commission(1.0) + self._cost_model.spread_cost(1.0, candle)
            if not limit_fill:
                per_lot_cost += self._cost_model.slippage_cost(1.0)
        risk_per_lot = abs(entry_fill - stop_loss) + per_lot_cost
        step = self.quantity_step
        risk_quantity = floor(equity * 0.01 / risk_per_lot / step + 1e-9) * step
        affordability_quantity = floor(equity / (entry_fill * (1.0 + self.fee_rate) + per_lot_cost) / step + 1e-9) * step
        quantity = float(min(risk_quantity, affordability_quantity))
        if quantity < step:
            return None
        cost_quantity = quantity
        entry_fee = entry_fill * quantity * self.fee_rate
        entry_commission = self._cost_model.commission(cost_quantity) if self._cost_model is not None else 0.0
        entry_spread = self._cost_model.spread_cost(cost_quantity, candle) if self._cost_model is not None else 0.0
        entry_slippage = self._cost_model.slippage_cost(cost_quantity) if self._cost_model is not None and not limit_fill else 0.0
        if self._cost_model is not None:
            self._commission_paid += entry_commission
            self._spread_cost_paid += entry_spread
            self._slippage_paid += entry_slippage
        target_price = signal.target_price
        if target_price is None:
            target_distance = 2.0 * stop_atr_multiplier * atr14 if exit_model == "fixed_2r" else 3.0 * atr14
            target_price = entry_fill + target_distance if signal.bias == "LONG" else entry_fill - target_distance
        return {
            "symbol": symbol,
            "side": signal.bias,
            "quantity_unit": "research_lots",
            "volume_lots": float(quantity),
            "entry": entry,
            "entry_fill": entry_fill,
            "risk_entry": entry_fill,
            "exit": None,
            "sl": stop_loss,
            "tp": target_price,
            "signal_sl": entry - 2 * atr14 if signal.bias == "LONG" else entry + 2 * atr14,
            "signal_tp": entry + 3 * atr14 if signal.bias == "LONG" else entry - 3 * atr14,
            "qty": float(quantity),
            "pnl": 0.0,
            "gross_pnl": 0.0,
            "net_pnl": 0.0,
            "fees": 0.0,
            "slippage_cost": 0.0,
            "reason": signal.reason,
            "partial_enabled": partial_take_profit,
            "tp1_hit": False,
            "limit_fill": limit_fill,
            "entry_index": -1,
            "signal_index": -1,
            "position_id": 0,
            "entry_candle": dict(candle),
            "entry_spread": entry_spread,
            "entry_slippage": entry_slippage,
            "entry_commission": entry_commission,
            "entry_fee": entry_fee,
            "initial_risk": abs(entry_fill - stop_loss),
            "exit_model": exit_model,
            "entry_atr": atr14,
            "high_water": entry_fill,
            "low_water": entry_fill,
        }

    def _check_position_exit(
        self,
        position: dict[str, object],
        candle: dict[str, float],
        trades: list[dict[str, object]],
        partial_take_profit: bool,
        exit_model: str = "fixed_3r",
        time_stop_bars: int = 24,
        current_index: int = 0,
        partial_take_profit_r: float = 1.0,
        trailing_r: float = 1.0,
    ) -> None:
        side = str(position["side"])
        stop = self._number(position["sl"])
        target = self._number(position["tp"])
        entry = self._number(position["entry"])
        atr14 = self._number(position.get("entry_atr", self._atr_value(candle, entry)))
        entry_index = self._number(position.get("entry_index", current_index))
        elapsed = current_index - int(entry_index)
        position["high_water"] = max(self._number(position.get("high_water", entry)), candle["high"])
        position["low_water"] = min(self._number(position.get("low_water", entry)), candle["low"])
        position["exit_trigger"] = None
        initial_risk = self._initial_risk(position, atr14)
        if side == "LONG":
            stop_hit = candle["low"] <= stop
            target_hit = exit_model in {"fixed_2r", "fixed_3r"} and candle["high"] >= target
            tp1 = self._number(position["entry_fill"]) + partial_take_profit_r * initial_risk
            tp1_hit = candle["high"] >= tp1
        else:
            stop_hit = candle["high"] >= stop
            target_hit = exit_model in {"fixed_2r", "fixed_3r"} and candle["low"] <= target
            tp1 = self._number(position["entry_fill"]) - partial_take_profit_r * initial_risk
            tp1_hit = candle["low"] <= tp1
        if stop_hit:
            position["exit_candle"] = dict(candle)
            stop_fill = self._stop_fill_price(candle, stop, side)
            position["sl_trigger"] = stop_fill
            reason = "atr_trailing" if exit_model == "atr_trailing_2x" and bool(position.get("trailing_active")) else "stop_loss"
            self._close_position(position, stop_fill, reason, trades, fill_reference=stop_fill)
            return
        if exit_model == "time_stop_24" and elapsed >= time_stop_bars:
            position["exit_candle"] = dict(candle)
            self._close_position(position, candle["close"], "time_stop", trades)
            return
        if partial_take_profit and not bool(position.get("tp1_hit")) and tp1_hit:
            position["exit_candle"] = dict(candle)
            self._close_partial(position, tp1, trades)
            position["tp1_hit"] = True
            position["sl"] = self._number(position["entry_fill"])
            position["sl_trigger"] = self._number(position["entry_fill"])
            if target_hit:
                self._close_position(position, target, "take_profit", trades)
            return
        if target_hit:
            position["exit_candle"] = dict(candle)
            position["tp_trigger"] = self._number(position.get("signal_tp", target))
            self._close_position(position, target, "take_profit", trades)
            return
        if exit_model == "atr_trailing_2x":
            trailing_stop = max(stop, self._number(position.get("high_water", entry)) - trailing_r * atr14) if side == "LONG" else min(stop, self._number(position.get("low_water", entry)) + trailing_r * atr14)
            position["sl"] = trailing_stop
            position["trailing_active"] = True
            if (side == "LONG" and candle["low"] <= trailing_stop) or (side == "SHORT" and candle["high"] >= trailing_stop):
                position["exit_candle"] = dict(candle)
                position["sl_trigger"] = trailing_stop
                self._close_position(position, trailing_stop, "atr_trailing", trades, fill_reference=self._stop_fill_price(candle, trailing_stop, side))
                return
        if bool(position.get("tp1_hit")):
            risk = self._initial_risk(position, atr14)
            high_water = self._number(position.get("high_water", candle["high"]))
            low_water = self._number(position.get("low_water", candle["low"]))
            position["sl"] = max(stop, high_water - risk) if side == "LONG" else min(stop, low_water + risk)

    def _close_partial(self, position: dict[str, object], exit_price: float, trades: list[dict[str, object]]) -> None:
        original_qty = self._number(position["qty"])
        partial_qty = original_qty * 0.5
        fraction = partial_qty / original_qty if original_qty else 0.0
        leg = dict(position)
        leg["leg"] = "tp1"
        leg["qty"] = partial_qty
        for field in ("entry_commission", "entry_spread", "entry_slippage"):
            value = self._number(position.get(field, 0.0))
            leg[field] = value * fraction
        leg["volume_lots"] = self._number(position.get("volume_lots", original_qty)) * fraction
        self._close_position(leg, exit_price, "partial_take_profit", trades)
        position["leg"] = "remainder"
        position["qty"] = original_qty - partial_qty
        for field in ("entry_commission", "entry_spread", "entry_slippage"):
            value = self._number(position.get(field, 0.0))
            position[field] = value - value * fraction
        position["volume_lots"] = self._number(position.get("volume_lots", original_qty)) * (1.0 - fraction)

    def _close_position(
        self,
        position: dict[str, object],
        exit_price: float,
        reason: str,
        trades: list[dict[str, object]],
        *,
        fill_reference: float | None = None,
    ) -> None:
        entry = self._number(position["entry"])
        entry_fill = self._number(position["entry_fill"])
        quantity = self._number(position["qty"])
        cost_quantity = self._number(position.get("volume_lots", quantity))
        side = str(position["side"])
        direction = 1 if side == "LONG" else -1
        candle = position.get("exit_candle")
        exit_candle = candle if isinstance(candle, dict) else None
        exit_fill = self._market_exit_fill(fill_reference if fill_reference is not None else exit_price, side, exit_candle)
        gross_pnl = (exit_price - entry) * quantity * direction
        entry_fee = self._number(position.get("entry_fee", entry_fill * quantity * self.fee_rate))
        exit_fee = exit_fill * quantity * self.fee_rate
        entry_commission = self._number(position.get("entry_commission", 0.0))
        entry_spread = self._number(position.get("entry_spread", 0.0))
        entry_slippage = self._number(position.get("entry_slippage", 0.0))
        exit_spread = 0.0
        exit_commission = 0.0
        exit_slippage = 0.0
        if self._cost_model is not None and exit_candle is not None:
            exit_spread = self._cost_model.spread_cost(cost_quantity, exit_candle)
            exit_commission = self._cost_model.commission(cost_quantity)
            exit_slippage = self._cost_model.slippage_cost(cost_quantity)
            self._spread_cost_paid += exit_spread
            self._commission_paid += exit_commission
            self._slippage_paid += exit_slippage
            slippage_cost = entry_slippage + exit_slippage
        else:
            slippage_cost = self._slippage_cost(entry, entry_fill, exit_price, exit_fill, quantity, direction)
        commission_cost = entry_commission + exit_commission
        fees = entry_fee + exit_fee + commission_cost
        net_pnl = (exit_fill - entry_fill) * quantity * direction - fees
        self._fees_paid += fees
        if self._cost_model is None:
            self._slippage_paid += slippage_cost
        trigger_exit = position.get("tp_trigger") if reason == "take_profit" else position.get("sl_trigger") if reason in {"stop_loss", "atr_trailing"} else exit_price
        position["exit_trigger"] = trigger_exit if isinstance(trigger_exit, (int, float)) else exit_price
        position["exit"] = position["exit_trigger"]
        position["exit_fill"] = exit_fill
        position["pnl"] = gross_pnl
        position["gross_pnl"] = gross_pnl
        position["gross_entry"] = entry
        position["net_pnl"] = net_pnl
        position["fees"] = fees
        position["spread_cost"] = entry_spread + exit_spread
        position["commission_cost"] = commission_cost
        position["slippage_cost"] = slippage_cost
        risk_amount = self._number(position.get("initial_risk", abs(entry - self._number(position["sl"])))) * quantity
        position["r_multiple"] = net_pnl / risk_amount if risk_amount > 0 else 0.0
        position["reason"] = reason
        trades.append(dict(position))

    @staticmethod
    def _stop_fill_price(candle: dict[str, float], stop: float, side: str) -> float:
        if side == "LONG" and candle["open"] < stop:
            return candle["open"]
        if side == "SHORT" and candle["open"] > stop:
            return candle["open"]
        return stop

    @staticmethod
    def _slippage_cost(entry: float, entry_fill: float, exit: float, exit_fill: float, quantity: float, direction: int) -> float:
        if direction > 0:
            return max(0.0, entry_fill - entry) * quantity + max(0.0, exit - exit_fill) * quantity
        return max(0.0, entry - entry_fill) * quantity + max(0.0, exit_fill - exit) * quantity

    def _settle_new_trades(
        self,
        trades: list[dict[str, object]],
        settled: int,
        gross_cash: float,
        net_cash: float,
    ) -> tuple[float, float, int]:
        for trade in trades[settled:]:
            gross_cash += self._number(trade["pnl"])
            net_cash += self._number(trade["net_pnl"])
        return gross_cash, net_cash, len(trades)

    def _new_pending(self, signal: SignalResult, candle: dict[str, float], index: int) -> dict[str, object]:
        entry_mode = signal.entry_mode
        limit_price = signal.limit_price
        if entry_mode == "limit" and limit_price is None:
            atr14 = self._atr_value(candle, candle["close"])
            limit_price = candle["close"] - 0.3 * atr14 if signal.bias == "LONG" else candle["close"] + 0.3 * atr14
        return {
            "signal": signal,
            "index": index,
            "expiry": index + self.limit_expiry_bars,
            "entry_mode": entry_mode,
            "limit_price": limit_price,
        }

    def _pending_fill_price(self, pending: dict[str, object], candle: dict[str, float]) -> float | None:
        signal = self._signal(pending)
        if not self._is_limit(pending):
            return candle["open"]
        limit = pending.get("limit_price")
        if not isinstance(limit, (int, float)) or isinstance(limit, bool) or limit <= 0:
            return None
        if signal.bias == "LONG":
            if candle["open"] <= limit:
                return candle["open"]
            if candle["low"] <= limit:
                return float(limit)
        elif signal.bias == "SHORT":
            if candle["open"] >= limit:
                return candle["open"]
            if candle["high"] >= limit:
                return float(limit)
        return None

    @staticmethod
    def _pending_expired(pending: dict[str, object], index: int) -> bool:
        expiry = pending.get("expiry")
        return isinstance(expiry, int) and index >= expiry

    @staticmethod
    def _is_limit(pending: dict[str, object]) -> bool:
        return pending.get("entry_mode") == "limit"

    @staticmethod
    def _signal(pending: dict[str, object]) -> SignalResult:
        signal = pending.get("signal")
        if not isinstance(signal, SignalResult):
            raise TypeError("pending signal must be SignalResult")
        return signal

    def _limit_entry_fill(self, price: float, side: str, candle: dict[str, float]) -> float:
        if self._cost_model is None:
            return price
        return self._cost_model.limit_fill(price, side, True, candle)

    def _market_entry_fill(self, price: float, side: str, candle: dict[str, float] | None = None) -> float:
        if self._cost_model is not None and candle is not None:
            direction = "LONG" if side == "LONG" else "SHORT"
            return self._cost_model.market_fill(price, direction, True, candle)
        return price * (1 + self.slippage_pct) if side == "LONG" else price * (1 - self.slippage_pct)

    def _market_exit_fill(self, price: float, side: str, candle: dict[str, float] | None = None) -> float:
        if self._cost_model is not None and candle is not None:
            direction = "LONG" if side == "LONG" else "SHORT"
            return self._cost_model.market_fill(price, direction, False, candle)
        return price * (1 - self.slippage_pct) if side == "LONG" else price * (1 + self.slippage_pct)

    @classmethod
    def _result(
        cls,
        trades: list[dict[str, object]],
        equity_curve: list[float],
        initial_equity: float,
        *,
        net_equity_curve: list[float] | None = None,
        fees_paid: float | None = None,
        slippage_paid: float | None = None,
        spread_cost_paid: float = 0.0,
        commission_paid: float = 0.0,
        limit_orders: int | None = None,
        limit_fills: int | None = None,
    ) -> BacktestResult:
        total_return_pct, max_drawdown_pct, sharpe_ratio = cls._metrics(equity_curve, initial_equity)
        net_curve = net_equity_curve or list(equity_curve)
        net_return, net_drawdown, net_sharpe = cls._metrics(net_curve, initial_equity)
        wins = sum(1 for trade in trades if cls._number(trade["pnl"]) > 0)
        win_rate = wins / len(trades) * 100 if trades else 0.0
        fees = fees_paid if fees_paid is not None else sum(cls._number(trade.get("fees", 0.0)) for trade in trades)
        slippage = slippage_paid if slippage_paid is not None else sum(cls._number(trade.get("slippage_cost", 0.0)) for trade in trades)
        filled_limits = limit_fills if limit_fills is not None else sum(1 for trade in trades if trade.get("limit_fill") is True)
        submitted_limits = limit_orders if limit_orders is not None else filled_limits
        return BacktestResult(
            trades,
            equity_curve,
            total_return_pct,
            max_drawdown_pct,
            sharpe_ratio,
            win_rate,
            len(trades),
            fees,
            submitted_limits,
            filled_limits,
            slippage,
            net_curve,
            net_return,
            net_drawdown,
            net_sharpe,
            spread_cost_paid,
            commission_paid,
        )

    @staticmethod
    def _metrics(curve: list[float], initial_equity: float) -> tuple[float, float, float]:
        final_equity = curve[-1]
        total_return_pct = (final_equity / initial_equity - 1) * 100
        peak = initial_equity
        max_drawdown = 0.0
        for equity in curve:
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
        returns = [curve[index] / curve[index - 1] - 1 for index in range(1, len(curve)) if curve[index - 1] > 0]
        deviation = pstdev(returns) if len(returns) > 1 else 0.0
        sharpe_ratio = mean(returns) / deviation * sqrt(252) if deviation > 0 else 0.0
        return total_return_pct, max_drawdown, sharpe_ratio

    @staticmethod
    def _number(value: object) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("trade value must be numeric")
        return float(value)

    @staticmethod
    def _normalize_candle(candle: dict[str, object], *, require_spread: bool = False) -> dict[str, float]:
        if not isinstance(candle, dict):
            raise TypeError("each candle must be a dictionary")
        values: dict[str, float] = {}
        for field in ("open", "high", "low", "close"):
            value = candle.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value) or value <= 0:
                raise ValueError(f"candle {field} must be positive and finite")
            values[field] = float(value)
        if values["low"] > values["high"]:
            raise ValueError("candle OHLC values are inconsistent")
        if require_spread and (values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"])):
            raise ValueError("candle OHLC values are inconsistent")
        volume = candle.get("volume", 0.0)
        values["volume"] = float(volume) if isinstance(volume, (int, float)) and not isinstance(volume, bool) else 0.0
        spread = candle.get("spread")
        if spread is None and not require_spread:
            values["spread"] = 0.0
        elif not isinstance(spread, (int, float)) or isinstance(spread, bool) or not isfinite(spread) or spread < 0:
            raise ValueError("candle spread must be non-negative and finite")
        else:
            values["spread"] = float(spread)
        timestamp = candle.get("timestamp")
        if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool) and isfinite(timestamp):
            values["timestamp"] = float(timestamp)
        atr14 = candle.get("atr14", candle.get("atr"))
        if isinstance(atr14, (int, float)) and not isinstance(atr14, bool) and isfinite(atr14) and atr14 > 0:
            values["atr14"] = float(atr14)
        return values

    @staticmethod
    def _atr_value(candle: dict[str, float], entry: float) -> float:
        value = candle.get("atr14", candle.get("atr"))
        if value is not None and isfinite(value) and value > 0:
            return value
        return max(entry * 0.01, 0.01)

    @staticmethod
    def _initial_risk(position: dict[str, object], fallback: float) -> float:
        entry = BacktestEngine._number(position["entry"])
        stop = BacktestEngine._number(position["sl"])
        stored = position.get("initial_risk")
        if isinstance(stored, (int, float)) and not isinstance(stored, bool) and stored > 0:
            return float(stored)
        return abs(entry - stop) or fallback
