from pathlib import Path

import pandas as pd
import pytest

from bananatrade.data.indicators import (
    atr,
    ema,
    range_high,
    range_low,
    regime,
    rsi,
    volume_zscore,
    vwap,
)


@pytest.fixture
def tiny() -> pd.DataFrame:
    return pd.DataFrame({"high": [2, 3, 4, 5, 6], "low": [0, 1, 2, 3, 4], "close": [1, 2, 3, 4, 5], "volume": [1, 2, 3, 4, 5]})


@pytest.mark.parametrize("indicator", ["ema", "rsi", "atr", "vwap", "volume_zscore", "range_high_low"])
def test_indicators_hand_computed(indicator: str, tiny: pd.DataFrame) -> None:
    # Period-three hand calculations: EMA uses alpha=.5, RSI/ATR use Wilder alpha=1/3,
    # VWAP is sum(close*volume)/sum(volume), and z-score uses population std.
    if indicator == "ema":
        assert ema(tiny.close, 3).iloc[2] == pytest.approx(2.25, abs=1e-9)
    elif indicator == "rsi":
        assert rsi(tiny.close, 3).iloc[3] == pytest.approx(100.0, abs=1e-9)
    elif indicator == "atr":
        assert atr(tiny, 3).iloc[3] == pytest.approx(2.0, abs=1e-9)
    elif indicator == "vwap":
        assert vwap(tiny, 3).iloc[2] == pytest.approx(14 / 6, abs=1e-9)
    elif indicator == "volume_zscore":
        assert volume_zscore(tiny.volume, 3).iloc[2] == pytest.approx(1.224744871391589, abs=1e-9)
    else:
        assert range_high(tiny.high, 3).iloc[3] == 5
        assert range_low(tiny.low, 3).iloc[3] == 1


@pytest.mark.parametrize("fixture", ["synthetic_btc_usdt_1h.csv", "synthetic_randomwalk_btc_1h.csv"])
@pytest.mark.parametrize("n,k", [(20, 5), (50, 10), (100, 20)])
def test_indicators_no_lookahead(fixture: str, n: int, k: int) -> None:
    frame = pd.read_csv(Path(__file__).parent / "fixtures" / fixture)
    short, long = frame.iloc[:n], frame.iloc[: n + k]
    funcs = [lambda x: ema(x.close, 10), lambda x: rsi(x.close, 10), lambda x: atr(x, 10), lambda x: vwap(x, 10), lambda x: volume_zscore(x.volume, 10), lambda x: range_high(x.high, 10), lambda x: range_low(x.low, 10), lambda x: regime(x, 10, 10)]
    for func in funcs:
        pd.testing.assert_series_equal(func(short).reset_index(drop=True), func(long).iloc[:n].reset_index(drop=True), check_names=False)


def test_rsi_flat_market_is_neutral() -> None:
    result = rsi(pd.Series([10.0] * 20), 3)
    assert result.iloc[-1] == pytest.approx(50.0)


def test_volume_zscore_zero_std() -> None:
    result = volume_zscore(pd.Series([5.0] * 10), 3)
    assert not result.replace([float("inf"), float("-inf")], pd.NA).dropna().any()


def test_regime_labels() -> None:
    up = pd.DataFrame({"high": range(1, 31), "low": range(30), "close": range(1, 31), "volume": [1] * 30})
    down = up.iloc[::-1].reset_index(drop=True)
    flat = up.copy(); flat["close"] = 10; flat["high"] = 11; flat["low"] = 9
    assert regime(up, 3, 3).iloc[-1] == "trend_up"
    assert regime(down, 3, 3).iloc[-1] == "trend_down"
    assert regime(flat, 3, 3).iloc[-1] == "range"
