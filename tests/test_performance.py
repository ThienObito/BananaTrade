import csv
from pathlib import Path

import pytest

from bananatrade import web_server
from bananatrade.analytics.performance import PerformanceMetrics, compute_metrics


def row(pnl: float, entry: float = 100.0, sl: float = 95.0, qty: float = 1.0) -> dict[str, object]:
    return {"pnl": pnl, "entry": entry, "sl": sl, "qty": qty}


def test_metrics_type() -> None:
    assert isinstance(compute_metrics([]), PerformanceMetrics)


def test_empty_total_trades() -> None:
    assert compute_metrics([]).total_trades == 0


def test_empty_all_zero() -> None:
    metrics = compute_metrics([])
    assert metrics.as_dict() == {"total_trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "avg_r_multiple": 0.0, "expectancy_r": 0.0, "max_drawdown_pct": 0.0, "sharpe": 0.0, "longest_losing_streak": 0}


def test_empty_generator() -> None:
    assert compute_metrics(row for row in []).total_trades == 0


def test_single_win_count() -> None:
    assert compute_metrics([row(10.0)]).total_trades == 1


def test_single_win_rate() -> None:
    assert compute_metrics([row(10.0)]).win_rate == 1.0


def test_single_loss_rate() -> None:
    assert compute_metrics([row(-10.0)]).win_rate == 0.0


def test_all_wins_win_rate() -> None:
    assert compute_metrics([row(5.0), row(10.0)]).win_rate == 1.0


def test_all_losses_win_rate() -> None:
    assert compute_metrics([row(-5.0), row(-10.0)]).win_rate == 0.0


def test_all_wins_profit_factor_infinite() -> None:
    assert compute_metrics([row(5.0)]).profit_factor == float("inf")


def test_all_losses_profit_factor_zero() -> None:
    assert compute_metrics([row(-5.0)]).profit_factor == 0.0


def test_known_r_multiple() -> None:
    assert compute_metrics([row(10.0, sl=95.0)]).avg_r_multiple == pytest.approx(2.0)


def test_known_expectancy() -> None:
    metrics = compute_metrics([row(10.0), row(-5.0)])
    assert metrics.expectancy_r == pytest.approx(0.5)


def test_known_average_r() -> None:
    metrics = compute_metrics([row(10.0), row(-5.0)])
    assert metrics.avg_r_multiple == pytest.approx(0.5)


def test_known_profit_factor() -> None:
    metrics = compute_metrics([row(10.0), row(-5.0)])
    assert metrics.profit_factor == pytest.approx(2.0)


def test_known_drawdown() -> None:
    metrics = compute_metrics([row(10.0), row(-5.0)])
    assert metrics.max_drawdown_pct == pytest.approx(33.3333333333)


def test_losing_drawdown() -> None:
    metrics = compute_metrics([row(-5.0), row(-5.0)])
    assert metrics.max_drawdown_pct == pytest.approx(100.0)


def test_longest_losing_streak() -> None:
    metrics = compute_metrics([row(1.0), row(-1.0), row(-2.0), row(1.0), row(-1.0)])
    assert metrics.longest_losing_streak == 2


def test_streak_zero_without_losses() -> None:
    assert compute_metrics([row(1.0), row(2.0)]).longest_losing_streak == 0


def test_sharpe_finite_for_constant_results() -> None:
    assert compute_metrics([row(1.0), row(1.0)]).sharpe == 0.0


def test_string_numbers_supported() -> None:
    assert compute_metrics([{"pnl": "10", "entry": "100", "sl": "95", "qty": "1"}]).avg_r_multiple == pytest.approx(2.0)


def test_invalid_rows_ignored() -> None:
    assert compute_metrics([{"pnl": "bad"}, row(5.0)]).total_trades == 1


def test_missing_risk_uses_pnl_as_r() -> None:
    assert compute_metrics([{"pnl": 2.0}]).avg_r_multiple == pytest.approx(2.0)


def test_zero_stop_uses_pnl_as_r() -> None:
    assert compute_metrics([row(2.0, sl=100.0)]).avg_r_multiple == pytest.approx(2.0)


def test_metrics_are_immutable() -> None:
    metrics = compute_metrics([])
    assert metrics.total_trades == 0
    assert type(metrics).__dataclass_params__.frozen is True


def test_web_performance_empty_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "journal.csv"
    monkeypatch.setattr(web_server, "JOURNAL_PATH", path)
    assert web_server.performance_state()["total_trades"] == 0


def test_web_performance_reads_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "journal.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("pnl", "entry", "sl", "qty"))
        writer.writeheader()
        writer.writerow(row(10.0))
    monkeypatch.setattr(web_server, "JOURNAL_PATH", path)
    payload = web_server.performance_state()
    assert payload["total_trades"] == 1
    assert payload["win_rate"] == 1.0
