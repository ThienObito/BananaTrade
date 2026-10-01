"""Train, export (ONNX) and evaluate the optional entry filter.

Data: data/history/{BTCUSDT,ETHUSDT}_{15m,1h}.csv (crypto only; no EURUSD M1 exists here,
so the model is NOT validated for MT5 FX symbols).

Pipeline (strictly chronological, no shuffling):
  per dataset  [0%, 60%) train | [60%, 80%) validation | [80%, 100%) test
  1. Run the brain's ensemble signal through BacktestEngine on each segment. Each trade's
     label = 1 if its net PnL (after taker fees + slippage modelled by the engine) > 0.
     Features are taken at the signal bar (closed candle) -> no look-ahead.
  2. Fit StandardScaler + LogisticRegression on pooled train samples.
  3. Pick the threshold on validation only (max pooled net PnL, >= 30 kept trades).
  4. Export ONNX (initial_types, zipmap=False) and check parity with sklearn.
  5. Test segment, untouched until now: unfiltered vs filtered with BacktestEngine and
     WalkForwardOptimizer (3 rolling sub-windows) plus the entry_ablation V2 reference.

Usage:  python scripts/train_entry_filter.py [--out models/entry_filter.onnx]
Requires the ``ml`` extra: pip install -e ".[ml]"
This is research tooling, not investment advice; past backtests do not imply future profit.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_entry_research import load_dataset  # noqa: E402  (shared validated CSV loader)

from bananatrade.backtest.engine import BacktestEngine, BacktestResult  # noqa: E402
from bananatrade.backtest.walk_forward import WalkForwardOptimizer  # noqa: E402
from bananatrade.engine.entry_filter import FEATURE_NAMES, OnnxEntryFilter  # noqa: E402
from bananatrade.research.entry_ablation import AblationStrategy, _bootstrap_ci  # noqa: E402
from bananatrade.research.entry_filter_eval import EnsembleBacktestStrategy, RandomVetoStrategy  # noqa: E402

DATASETS = (("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "15m"), ("ETHUSDT", "1h"))
SPLITS = (0.60, 0.80)
THRESHOLD_GRID = tuple(round(x, 2) for x in np.arange(0.40, 0.71, 0.02))
MIN_VAL_TRADES = 30
SEED = 510
RANDOM_CONTROL_RUNS = 20


class ScaledEngine(BacktestEngine):
    """BacktestEngine sizes in whole units (floor). With the default 10k equity a BTC/ETH
    position rounds to 0 units and no trade is ever opened, so research runs use a large
    notional. Percent metrics and the sign of net PnL (the label) are scale-invariant."""

    def run(self, candles, strategy, initial_equity: float = 10_000_000.0, **kwargs):  # type: ignore[no-untyped-def,override]
        return super().run(candles, strategy, initial_equity, **kwargs)


@dataclass
class SegmentStats:
    trades: int
    net_return_pct: float
    net_sharpe: float
    net_max_dd_pct: float
    win_rate: float
    net_pnl_sum: float


def stats(result: BacktestResult) -> SegmentStats:
    net = [float(t["net_pnl"]) for t in result.trades]
    wins = sum(1 for v in net if v > 0)
    return SegmentStats(
        len(net),
        round(result.net_total_return_pct, 4),
        round(result.net_sharpe_ratio, 4),
        round(result.net_max_drawdown_pct, 4),
        round(wins / len(net), 4) if net else 0.0,
        round(sum(net), 2),
    )


def labelled_samples(
    engine: BacktestEngine, candles: list[dict[str, object]], min_index: int = 0
) -> tuple[np.ndarray, np.ndarray, list[float]]:
    strategy = EnsembleBacktestStrategy()
    result = engine.run(candles, strategy)
    xs, ys, pnl = [], [], []
    for trade in result.trades:
        idx = int(trade["signal_index"])  # type: ignore[arg-type]
        if idx < min_index:  # signal inside the warm-up prefix belongs to the previous segment
            continue
        feats = strategy.features_by_ts.get(candles[idx]["timestamp"])
        if feats is None:
            continue
        xs.append(feats)
        net = float(trade["net_pnl"])  # type: ignore[arg-type]
        ys.append(1 if net > 0 else 0)
        pnl.append(net)
    return np.asarray(xs, dtype=np.float32).reshape(-1, len(FEATURE_NAMES)), np.asarray(ys), pnl


def main() -> None:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="models/entry_filter.onnx")
    parser.add_argument("--report", default="reports/entry_filter_report.json")
    args = parser.parse_args()

    engine = ScaledEngine()
    segments: dict[str, dict[str, list[dict[str, object]]]] = {}
    for symbol, interval in DATASETS:
        candles = list(load_dataset(symbol, interval).candles)
        a, b = int(len(candles) * SPLITS[0]), int(len(candles) * SPLITS[1])
        warm = EnsembleBacktestStrategy.lookback
        # val/test get a warm-up prefix from the previous segment (features only; trades
        # are generated only after the prefix by construction of the samples below).
        segments[f"{symbol}_{interval}"] = {
            "train": candles[:a],
            "val": candles[a - warm:b],
            "test": candles[b - warm:],
            "test_start_ts": candles[b]["timestamp"],  # type: ignore[dict-item]
            "train_range": [candles[0]["timestamp"], candles[a - 1]["timestamp"]],  # type: ignore[dict-item]
        }

    x_parts, y_parts = [], []
    val_parts: list[tuple[np.ndarray, list[float]]] = []
    for name, seg in segments.items():
        x, y, _ = labelled_samples(engine, seg["train"])
        x_parts.append(x)
        y_parts.append(y)
        vx, vy, vpnl = labelled_samples(engine, seg["val"], EnsembleBacktestStrategy.lookback)
        val_parts.append((vx, vpnl))
        print(f"{name}: train samples={len(y)} win_rate={y.mean() if len(y) else 0:.3f}; val samples={len(vy)}")
    x_train, y_train = np.vstack(x_parts), np.concatenate(y_parts)
    if len(y_train) < 100 or len(set(y_train.tolist())) < 2:
        raise SystemExit(f"not enough labelled training trades ({len(y_train)})")

    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000, random_state=SEED))
    model.fit(x_train, y_train)
    x_val = np.vstack([p[0] for p in val_parts])
    pnl_val = np.concatenate([np.asarray(p[1]) for p in val_parts])
    y_val = (pnl_val > 0).astype(int)
    p_val = model.predict_proba(x_val)[:, 1]
    val_auc = float(roc_auc_score(y_val, p_val)) if len(set(y_val.tolist())) > 1 else float("nan")
    train_auc = float(roc_auc_score(y_train, model.predict_proba(x_train)[:, 1]))

    best_thr, best_pnl = None, float(pnl_val.sum())  # must beat "no filter" on validation
    curve = []
    for thr in THRESHOLD_GRID:
        keep = p_val >= thr
        kept_pnl = float(pnl_val[keep].sum())
        curve.append({"threshold": thr, "kept": int(keep.sum()), "kept_net_pnl": round(kept_pnl, 2)})
        if keep.sum() >= MIN_VAL_TRADES and kept_pnl > best_pnl:
            best_thr, best_pnl = thr, kept_pnl
    chosen = best_thr if best_thr is not None else 0.5
    print(f"train AUC={train_auc:.3f} val AUC={val_auc:.3f} chosen threshold={chosen} (beats unfiltered on val: {best_thr is not None})")

    onx = convert_sklearn(
        model,
        initial_types=[("input", FloatTensorType([None, len(FEATURE_NAMES)]))],
        options={id(model): {"zipmap": False}},
        target_opset=17,
    )
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(onx.SerializeToString())

    filt = OnnxEntryFilter(out, chosen)
    parity = float(np.max(np.abs(np.asarray([filt.probability(r) for r in x_val[:200]]) - p_val[:200])))
    print(f"ONNX vs sklearn max |dp| on 200 val rows = {parity:.2e}")

    report: dict[str, object] = {
        "features": list(FEATURE_NAMES),
        "split": {"train": "0-60%", "validation": "60-80%", "test": "80-100%", "shuffle": False},
        "costs": {"fee_rate_per_side": engine.fee_rate, "slippage_pct_per_side": engine.slippage_pct},
        "train_samples": int(len(y_train)),
        "train_win_rate": round(float(y_train.mean()), 4),
        "train_auc": round(train_auc, 4),
        "val_samples": int(len(y_val)),
        "val_auc": round(val_auc, 4),
        "threshold_curve_val": curve,
        "chosen_threshold": chosen,
        "threshold_beats_unfiltered_on_val": best_thr is not None,
        "onnx_parity_max_abs_diff": parity,
        "test": {},
    }

    wf = WalkForwardOptimizer(engine)
    total = {"unfiltered": 0.0, "filtered": 0.0, "random_veto_median": 0.0}
    for name, seg in segments.items():
        test = seg["test"]
        warm = EnsembleBacktestStrategy.lookback
        base = engine.run(test, EnsembleBacktestStrategy())
        gated_strategy = EnsembleBacktestStrategy(OnnxEntryFilter(out, chosen))
        gated = engine.run(test, gated_strategy)
        v2 = engine.run(test, AblationStrategy("V2"))
        # only trades whose signal is inside the true test segment
        for res in (base, gated, v2):
            res.trades[:] = [t for t in res.trades if int(t["signal_index"]) >= warm]  # type: ignore[arg-type]
        diff_lo, diff_hi = _bootstrap_ci([float(t["net_pnl"]) for t in gated.trades] or [0.0], SEED)
        factory = lambda use_filter: EnsembleBacktestStrategy(OnnxEntryFilter(out, chosen) if use_filter else None)  # noqa: E731
        wf_u = wf.optimize(test, factory, {"use_filter": [False]}, n_splits=3)
        wf_f = wf.optimize(test, factory, {"use_filter": [True]}, n_splits=3)
        s_base, s_gated = stats(base), stats(gated)
        # same-frequency random-veto control
        decided = len(gated_strategy.features_by_ts)  # signals the filter actually scored
        keep_rate = 1.0 - gated_strategy.vetoed / decided if decided else 1.0
        control = []
        for run in range(RANDOM_CONTROL_RUNS):
            res = engine.run(test, RandomVetoStrategy(keep_rate, SEED + run))
            control.append(sum(float(t["net_pnl"]) for t in res.trades if int(t["signal_index"]) >= warm))  # type: ignore[arg-type]
        control.sort()
        beats = sum(1 for v in control if s_gated.net_pnl_sum > v) / len(control)
        total["random_veto_median"] += control[len(control) // 2]
        total["unfiltered"] += s_base.net_pnl_sum
        total["filtered"] += s_gated.net_pnl_sum
        report["test"][name] = {  # type: ignore[index]
            "test_start_ts": seg["test_start_ts"],
            "unfiltered": asdict(s_base),
            "filtered": asdict(s_gated),
            "filter_vetoes": gated_strategy.vetoed,
            "filter_keep_rate": round(keep_rate, 4),
            "random_veto_control_net_pnl": {"min": round(control[0], 2), "median": round(control[len(control) // 2], 2), "max": round(control[-1], 2), "runs": len(control)},
            "filtered_beats_random_veto_fraction": round(beats, 3),
            "filtered_trade_pnl_bootstrap_ci": [round(diff_lo, 2), round(diff_hi, 2)],
            "reference_entry_ablation_V2": asdict(stats(v2)),
            "walk_forward_3win": {
                "unfiltered_avg_test_sharpe": round(wf_u.avg_sharpe, 4),
                "filtered_avg_test_sharpe": round(wf_f.avg_sharpe, 4),
                "unfiltered_stability": wf_u.stability_score,
                "filtered_stability": wf_f.stability_score,
            },
        }
        print(f"{name} TEST unfiltered={asdict(s_base)}\n{' ' * len(name)} TEST filtered  ={asdict(s_gated)} vetoes={gated_strategy.vetoed}")
    report["test_total_net_pnl"] = {k: round(v, 2) for k, v in total.items()}
    better_than_none = total["filtered"] > total["unfiltered"]
    better_than_random = total["filtered"] > total["random_veto_median"]
    has_signal = isinstance(val_auc, float) and val_auc >= 0.55
    if better_than_none and better_than_random and has_signal:
        verdict = "filter shows out-of-sample skill (beats no-filter and same-rate random veto; val AUC >= 0.55)"
    elif better_than_none:
        verdict = (
            "NO demonstrated skill: filtered test PnL is less negative than unfiltered, but "
            + ("it does not beat a same-rate random veto" if not better_than_random else "validation AUC < 0.55")
            + " -> improvement is explained by trading less, not by picking better trades"
        )
    else:
        verdict = "filter did NOT improve test net PnL"
    report["verdict"] = verdict
    meta = out.with_suffix(".meta.json")
    meta.write_text(json.dumps({k: report[k] for k in ("features", "chosen_threshold", "train_samples", "val_auc", "split", "costs")}, indent=2) + "\n", encoding="utf-8")
    rep = ROOT / args.report
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"verdict: {report['verdict']}; totals={report['test_total_net_pnl']}")


if __name__ == "__main__":
    main()
