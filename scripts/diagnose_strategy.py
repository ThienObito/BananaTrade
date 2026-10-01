"""Honest diagnosis of why the base strategy loses money. NO parameter tuning.

Everything runs with the project's existing, fixed rules and default costs:
BacktestEngine(fee_rate=0.001, slippage_pct=0.0002), default exit ("fixed_3r"),
initial equity 10,000 and a fractional ``quantity_step`` per symbol (Binance lot
steps: BTCUSDT 0.00001, ETHUSDT 0.0001), so results are no longer distorted by
whole-unit sizing.

Questions answered per dataset (BTC/ETH x 15m/1h, data/history):
  (a) Does the signal have an edge?  -> exit-free signed forward returns after each
      signal vs round-trip cost, plus realized GROSS PnL vs same-count random entries.
  (b) Do costs kill a thin edge?     -> fees+slippage as % of |gross PnL| and per trade.
  (c) Are sizing/exits the problem? -> realized gross R vs forward-return edge, exit mix,
      and the backtest exit vs the exit the live Brain actually uses.

Uses backtest/walk_forward.py (fixed single-parameter grid = pure rolling OOS, no
optimisation) and research/entry_ablation.py (V0/V2 reference rules, random-entry null,
5 chronological windows). Not investment advice.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_entry_research import load_dataset

from bananatrade.backtest.engine import BacktestEngine, BacktestResult
from bananatrade.backtest.walk_forward import WalkForwardOptimizer
from bananatrade.research.entry_ablation import (
    AblationStrategy,
    RandomEntryStrategy,
    _split_windows,
)
from bananatrade.research.entry_filter_eval import EnsembleBacktestStrategy

DATASETS = (("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "15m"), ("ETHUSDT", "1h"))
QUANTITY_STEP = {"BTCUSDT": 0.00001, "ETHUSDT": 0.0001}
EQUITY = 10_000.0
HORIZONS = (1, 4, 12, 24)
RANDOM_RUNS = 30
SEED = 510


def summarize(result: BacktestResult, engine: BacktestEngine) -> dict[str, object]:
    trades = result.trades
    gross = sum(float(t["pnl"]) for t in trades)
    net = sum(float(t["net_pnl"]) for t in trades)
    cost = gross - net
    r_gross = [float(t["pnl"]) / max(float(t.get("initial_risk", 0) or 0) * float(t["qty"]), 1e-12) for t in trades]
    r_net = [float(t.get("r_multiple", 0.0)) for t in trades]
    reasons: dict[str, int] = {}
    for t in trades:
        key = str(t.get("exit_reason", t.get("reason", "?")))
        reasons[key] = reasons.get(key, 0) + 1
    return {
        "trades": len(trades),
        "win_rate_gross": round(sum(1 for t in trades if float(t["pnl"]) > 0) / len(trades), 4) if trades else None,
        "win_rate_net": round(sum(1 for t in trades if float(t["net_pnl"]) > 0) / len(trades), 4) if trades else None,
        "gross_pnl": round(gross, 2),
        "costs_fees_slippage": round(cost, 2),
        "net_pnl": round(net, 2),
        "net_return_pct": round(result.net_total_return_pct, 3),
        "net_max_drawdown_pct": round(result.net_max_drawdown_pct, 3),
        "cost_pct_of_abs_gross": round(100 * cost / abs(gross), 1) if gross else None,
        "avg_gross_R": round(mean(r_gross), 4) if r_gross else None,
        "avg_net_R": round(mean(r_net), 4) if r_net else None,
        "avg_cost_R": round(mean(r_gross) - mean(r_net), 4) if r_net else None,
        "exit_reasons": reasons,
    }


def forward_edge(candles: list[dict[str, object]], signals: list[tuple[int, int]]) -> dict[str, object]:
    """Exit-free test: signed return from next open to close[t+h], in basis points."""
    out: dict[str, object] = {}
    n = len(candles)
    for h in HORIZONS:
        vals = []
        for idx, direction in signals:
            if idx + h < n:
                entry = float(candles[idx + 1]["open"])  # type: ignore[arg-type]
                exit_ = float(candles[idx + h]["close"])  # type: ignore[arg-type]
                vals.append(direction * (exit_ / entry - 1) * 1e4)
        if len(vals) > 2:
            m, sd = mean(vals), pstdev(vals)
            out[f"h{h}"] = {"n": len(vals), "mean_bps": round(m, 2), "t_stat": round(m / (sd / math.sqrt(len(vals))), 2) if sd else None}
    return out


def collect_signals(candles: list[dict[str, object]]) -> list[tuple[int, int]]:
    strat = EnsembleBacktestStrategy()
    look = strat.lookback
    sig = []
    for i in range(look, len(candles) - 1):
        s = strat.generate_signal(candles[i - look + 1 : i + 1])
        if s.bias != "NEUTRAL":
            sig.append((i, 1 if s.bias == "LONG" else -1))
    return sig


def main() -> None:
    report: dict[str, object] = {
        "assumptions": {
            "fee_rate_per_side": 0.001,
            "slippage_pct_per_side": 0.0002,
            "round_trip_cost_bps": 24.0,
            "initial_equity": EQUITY,
            "quantity_step": QUANTITY_STEP,
            "exit_model": "engine default fixed_3r (SL 2 ATR, TP 3 ATR => 1.5R)",
            "no_parameter_tuning": True,
        },
        "datasets": {},
    }
    for symbol, interval in DATASETS:
        ds = load_dataset(symbol, interval)
        candles = list(ds.candles)
        engine = BacktestEngine(quantity_step=QUANTITY_STEP[symbol])
        whole_unit = BacktestEngine()  # historical default, to show the sizing distortion
        prod = engine.run(candles, EnsembleBacktestStrategy(), EQUITY)
        prod_whole_unit = whole_unit.run(candles, EnsembleBacktestStrategy(), EQUITY)
        v0 = engine.run(candles, AblationStrategy("V0"), EQUITY)
        v2 = engine.run(candles, AblationStrategy("V2"), EQUITY)
        signals = collect_signals(candles)
        entry_idx = sorted({int(t["signal_index"]) for t in prod.trades})  # type: ignore[arg-type]
        rnd_gross = []
        for k in range(RANDOM_RUNS):
            r = engine.run(candles, RandomEntryStrategy(random.Random(SEED + k), entry_idx), EQUITY)
            rnd_gross.append(sum(float(t["pnl"]) for t in r.trades))
        rnd_gross.sort()
        prod_gross = sum(float(t["pnl"]) for t in prod.trades)
        windows = []
        for w, (_train, test, *_rest) in enumerate(_split_windows(candles, 5), 1):
            res = engine.run(list(test), EnsembleBacktestStrategy(), EQUITY)
            s = summarize(res, engine)
            windows.append({"window": w, **{k: s[k] for k in ("trades", "gross_pnl", "net_pnl", "win_rate_net")}})
        wfo = WalkForwardOptimizer(engine)
        wfr = wfo.optimize(candles, lambda unused=0: EnsembleBacktestStrategy(), {"unused": [0]}, n_splits=5)
        name = f"{symbol}_{interval}"
        report["datasets"][name] = {  # type: ignore[index]
            "bars": len(candles),
            "production_ensemble": summarize(prod, engine),
            "production_ensemble_whole_unit_sizing_10k": {"trades": prod_whole_unit.total_trades},
            "entry_ablation_V0": summarize(v0, engine),
            "entry_ablation_V2": summarize(v2, engine),
            "forward_return_edge_bps": forward_edge(candles, signals),
            "random_entry_same_count_gross_pnl": {
                "runs": RANDOM_RUNS,
                "p10": round(rnd_gross[len(rnd_gross) // 10], 2),
                "median": round(rnd_gross[len(rnd_gross) // 2], 2),
                "p90": round(rnd_gross[(len(rnd_gross) * 9) // 10], 2),
                "production_gross_percentile": round(sum(1 for v in rnd_gross if v < prod_gross) / len(rnd_gross), 3),
            },
            "five_windows_production": windows,
            "walk_forward_fixed_rules": {
                "window_test_sharpes": [round(w.test_sharpe, 4) for w in wfr.windows],
                "avg_test_sharpe": round(wfr.avg_sharpe, 4),
                "stability_positive_fraction": wfr.stability_score,
            },
        }
        print(name, json.dumps(report["datasets"][name]["production_ensemble"]), flush=True)  # type: ignore[index]
    out = ROOT / "reports" / "strategy_diagnosis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"written {out}")


if __name__ == "__main__":
    main()
