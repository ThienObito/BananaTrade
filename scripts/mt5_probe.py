"""Read-only MT5 diagnostic: prints what the bot will see. Never sends or checks orders."""

from __future__ import annotations

import json
import sys

import MetaTrader5 as mt5


def nt(x):
    return x._asdict() if hasattr(x, "_asdict") else x


symbol = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
print("package", mt5.__version__)
print("initialize", mt5.initialize(), mt5.last_error())
acc = mt5.account_info()
if acc is not None:
    a = nt(acc)
    print("account", json.dumps({k: a.get(k) for k in ("trade_mode", "currency", "balance", "equity", "leverage", "server")}))
    print("is_demo", a.get("trade_mode") == mt5.ACCOUNT_TRADE_MODE_DEMO)
names = [s.name for s in (mt5.symbols_get() or ())]
matches = [n for n in names if n.upper().startswith(symbol.upper().replace("/", ""))]
print("symbols_total", len(names), "matches", matches[:10])
if matches:
    s = nt(mt5.symbol_info(matches[0]))
    print("symbol_info", json.dumps({k: s.get(k) for k in ("name", "digits", "point", "volume_min", "volume_step", "volume_max", "trade_stops_level", "filling_mode", "trade_tick_value", "trade_tick_size", "trade_contract_size", "visible")}))
    print("tick", nt(mt5.symbol_info_tick(matches[0])))
    r = mt5.copy_rates_from_pos(matches[0], mt5.TIMEFRAME_M15, 0, 3)
    print("rates_type", type(r).__name__, getattr(r, "dtype", None), "rows", None if r is None else len(r))
    print("margin_1lot", mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, matches[0], 1.0, mt5.symbol_info_tick(matches[0]).ask))
print("history_deals_today", mt5.history_deals_get(__import__("datetime").datetime.now(__import__("datetime").UTC).replace(hour=0, minute=0, second=0, microsecond=0), __import__("datetime").datetime.now(__import__("datetime").UTC)), mt5.last_error())
print("positions", len(mt5.positions_get() or ()))
mt5.shutdown()
