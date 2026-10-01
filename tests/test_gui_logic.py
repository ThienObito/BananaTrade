from __future__ import annotations

from pathlib import Path

import pytest

from bananatrade.brokers.mt5_client import MT5ConnectionError, MT5Unavailable
from bananatrade.brokers.mt5_executor import LiveAccountRefused, MT5OrderRefused
from bananatrade.gui import (
    build_config,
    describe_result,
    friendly_error,
    read_decisions,
    translate_reason,
)


def test_build_config_defaults_to_dry_run() -> None:
    cfg = build_config("M15 (15 phút)", "1", "", False)
    assert cfg.mt5_execution_enabled is False
    assert cfg.risk_pct == pytest.approx(0.01)
    assert cfg.mt5_timeframe == 15
    assert cfg.mt5_volume_max is None
    assert build_config("H1 (1 giờ)", "0,5", "0.1", True).mt5_timeframe == 16385


@pytest.mark.parametrize("risk,vmax", [("abc", ""), ("0", ""), ("10", ""), ("1", "x"), ("1", "-1")])
def test_build_config_rejects_bad_input(risk: str, vmax: str) -> None:
    with pytest.raises(ValueError):
        build_config("M15 (15 phút)", risk, vmax, False)


def test_describe_result_none_and_buy() -> None:
    none = describe_result({"symbol": "EURUSDm", "account": {"equity": 100.0, "daily_pnl": 0, "open_count": 0},
                            "decision": {"side": "NONE", "confidence": 0.105, "reasons": ["confidence 0.1050 below threshold 0.6500"]},
                            "execution": {"sent": False, "dry_run": True, "message": "NONE decision; no order"}})
    assert none["headline"] == "KHÔNG VÀO LỆNH"
    assert "Tín hiệu chưa đủ mạnh" in none["reasons"]
    assert "dry-run" in none["execution"]
    buy = describe_result({"decision": {"side": "BUY", "volume": 0.01, "entry": 1.1, "sl": 1.09, "tp": 1.12, "reasons": []},
                           "execution": {"sent": True, "order_id": "42"}})
    assert buy["headline"].startswith("MUA") and "ĐÃ GỬI LỆNH" in buy["execution"]


def test_friendly_errors_are_vietnamese() -> None:
    assert "MetaTrader5" in friendly_error(MT5Unavailable("x"))
    assert "demo" in friendly_error(LiveAccountRefused("non-demo"))
    assert "Không kết nối" in friendly_error(MT5ConnectionError("(-10004, 'No IPC connection')"))
    assert "Kill-switch" in friendly_error(MT5OrderRefused("daily loss kill switch active"))
    assert "mã giao dịch" in friendly_error(KeyError("MT5 symbol not found: XYZ"))
    assert translate_reason("something else") == "something else"


def test_read_decisions_newest_first(tmp_path: Path) -> None:
    path = tmp_path / "d.csv"
    assert read_decisions(path) == []
    path.write_text("timestamp,symbol,side\n1,A,NONE\n2,B,BUY\n", encoding="utf-8")
    assert [r["symbol"] for r in read_decisions(path)] == ["B", "A"]
