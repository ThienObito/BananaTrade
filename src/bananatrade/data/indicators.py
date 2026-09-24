import pandas as pd


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative = avg_gain / avg_loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + relative))
    return result.mask((avg_loss == 0) & (avg_gain > 0), 100.0)


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    previous = frame["close"].shift(1)
    true_range = pd.concat([frame["high"] - frame["low"], (frame["high"] - previous).abs(), (frame["low"] - previous).abs()], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def vwap(frame: pd.DataFrame, period: int = 20) -> pd.Series:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    return (typical * frame["volume"]).rolling(period, min_periods=period).sum() / frame["volume"].rolling(period, min_periods=period).sum()


def volume_zscore(volume: pd.Series, period: int = 20) -> pd.Series:
    mean = volume.rolling(period, min_periods=period).mean()
    std = volume.rolling(period, min_periods=period).std(ddof=0)
    return (volume - mean) / std.replace(0, float("nan"))


def range_high(high: pd.Series, period: int) -> pd.Series:
    return high.rolling(period, min_periods=period).max()


def range_low(low: pd.Series, period: int) -> pd.Series:
    return low.rolling(period, min_periods=period).min()


def regime(frame: pd.DataFrame, ema_period: int = 20, atr_period: int = 14) -> pd.Series:
    fast = ema(frame["close"], ema_period)
    slope = fast.diff()
    volatility = atr(frame, atr_period)
    return pd.Series("range", index=frame.index).mask((slope > 0) & volatility.notna(), "trend_up").mask((slope < 0) & volatility.notna(), "trend_down")
