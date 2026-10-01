from __future__ import annotations

import pytest

from bananatrade.order_ticket_api import post_order_prefill, prefill_order


@pytest.fixture
def snapshot() -> dict[str, object]:
    return {
        "symbol": "BTC/USDT",
        "timeframes": {
            "1h": {
                "last_price": 100.0,
                "indicators": {"atr": 10.0},
            }
        },
    }


def test_long_prefill_computes_atr_levels_and_reward_risk(snapshot: dict[str, object]) -> None:
    result = prefill_order("BTC/USDT", "LONG", snapshot)

    assert result["symbol"] == "BTC/USDT"
    assert result["side"] == "LONG"
    assert result["entry"] == pytest.approx(100.0)
    assert result["stop"] == pytest.approx(85.0)
    assert result["target"] == pytest.approx(131.5)
    assert result["reward"] == pytest.approx(31.5)
    assert result["risk"] == pytest.approx(15.0)
    assert result["reward_risk"] == pytest.approx(2.1)


def test_short_prefill_computes_atr_levels_and_reward_risk(snapshot: dict[str, object]) -> None:
    result = prefill_order("BTC/USDT", "SHORT", snapshot)

    assert result["entry"] == pytest.approx(100.0)
    assert result["stop"] == pytest.approx(115.0)
    assert result["target"] == pytest.approx(68.5)
    assert result["reward"] == pytest.approx(31.5)
    assert result["risk"] == pytest.approx(15.0)
    assert result["reward_risk"] == pytest.approx(2.1)


def test_prefill_uses_side_specific_snapshot_levels(snapshot: dict[str, object]) -> None:
    timeframes = snapshot["timeframes"]
    assert isinstance(timeframes, dict)
    one_hour = timeframes["1h"]
    assert isinstance(one_hour, dict)
    one_hour["indicators"] = {
        "atr": 10.0,
        "atr_stop_long": 86.0,
        "atr_target_long": 130.0,
    }

    result = prefill_order("BTC/USDT", "LONG", snapshot)

    assert result["stop"] == pytest.approx(86.0)
    assert result["target"] == pytest.approx(130.0)
    assert result["reward_risk"] == pytest.approx(30.0 / 14.0)


def test_post_prefill_accepts_endpoint_payload(snapshot: dict[str, object]) -> None:
    result = post_order_prefill({"symbol": "BTC/USDT", "side": "buy", "snapshot": snapshot})

    assert result["side"] == "LONG"
    assert result["entry"] == pytest.approx(100.0)
