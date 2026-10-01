from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from bananatrade.data.history import (
    HistoryDownloadError,
    HistoryResult,
    download_klines,
    validate_klines,
)

START = datetime(2024, 1, 1, tzinfo=UTC)
INTERVAL = 900_000


def api_row(timestamp: int, close: float = 100.0) -> list[object]:
    return [timestamp, "99.0", str(max(100.0, close)), "98.0", str(close), "12.0", timestamp + INTERVAL - 1]


def history_rows(count: int = 4) -> list[list[object]]:
    start = int(START.timestamp() * 1000)
    return [api_row(start + index * INTERVAL, 100.0 + index) for index in range(count)]


def bounds() -> tuple[datetime, datetime]:
    return START, START + timedelta(minutes=45)


def test_download_returns_history_result(tmp_path: Path) -> None:
    start, end = bounds()
    result = download_klines("BTC/USDT", "15m", start, end, cache_dir=tmp_path, fetcher=lambda *args: history_rows())
    assert isinstance(result, HistoryResult)
    assert len(result) == 4


def test_download_normalizes_symbol_and_cache_name(tmp_path: Path) -> None:
    start, end = bounds()
    result = download_klines("btc/usdt", "15m", start, end, cache_dir=tmp_path, fetcher=lambda *args: history_rows())
    assert result.symbol == "BTCUSDT"
    assert result.path == tmp_path / "BTCUSDT_15m.csv"
    assert result.path.exists()


def test_download_paginates_until_end(tmp_path: Path) -> None:
    start, end = bounds()
    pages: list[int] = []

    def fetch(symbol: str, interval: str, page_start: int, page_end: int, limit: int) -> Sequence[Sequence[object]]:
        pages.append(page_start)
        rows = history_rows()
        return rows[:2] if len(pages) == 1 else rows[2:]

    result = download_klines("BTCUSDT", "15m", start, end, cache_dir=tmp_path, fetcher=fetch, limit=2)
    assert len(pages) >= 2
    assert len(result.rows) == 4


def test_download_resumes_from_cache(tmp_path: Path) -> None:
    start, end = bounds()
    first = download_klines("BTCUSDT", "15m", start, end, cache_dir=tmp_path, fetcher=lambda *args: history_rows())
    calls = 0

    def fail_fetch(*args: object) -> Sequence[Sequence[object]]:
        nonlocal calls
        calls += 1
        raise AssertionError("complete cache should not fetch")

    second = download_klines("BTCUSDT", "15m", start, end, cache_dir=tmp_path, fetcher=fail_fetch)
    assert second.rows == first.rows
    assert calls == 0


def test_download_repairs_missing_cached_timestamp(tmp_path: Path) -> None:
    start, end = bounds()
    first = download_klines("BTCUSDT", "15m", start, end, cache_dir=tmp_path, fetcher=lambda *args: history_rows())
    cache_lines = first.path.read_text(encoding="utf-8").splitlines()
    first.path.write_text("\n".join([cache_lines[0], *cache_lines[1:2], *cache_lines[3:]]) + "\n", encoding="utf-8")
    calls: list[int] = []

    def fetch(symbol: str, interval: str, page_start: int, page_end: int, limit: int) -> Sequence[Sequence[object]]:
        calls.append(page_start)
        return [history_rows()[1]]

    result = download_klines("BTCUSDT", "15m", start, end, cache_dir=tmp_path, fetcher=fetch)
    assert len(result.rows) == 4
    assert calls


def test_download_writes_validation_report(tmp_path: Path) -> None:
    start, end = bounds()
    result = download_klines("ETHUSDT", "15m", start, end, cache_dir=tmp_path, fetcher=lambda *args: history_rows())
    report = result.path.with_suffix(".validation.json")
    assert report.exists()
    assert result.validation.gap_count == 0


def test_download_wraps_fetch_failure(tmp_path: Path) -> None:
    start, end = bounds()

    def fail(*args: object) -> Sequence[Sequence[object]]:
        raise OSError("network down")

    with pytest.raises(HistoryDownloadError, match="network down"):
        download_klines("BTCUSDT", "15m", start, end, cache_dir=tmp_path, fetcher=fail)


def test_download_rejects_reverse_range(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="precede"):
        download_klines("BTCUSDT", "15m", START + timedelta(days=1), START, cache_dir=tmp_path, fetcher=lambda *args: [])


def test_download_rejects_bad_interval(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        download_klines("BTCUSDT", "7m", START, START, cache_dir=tmp_path, fetcher=lambda *args: [])


def test_download_rejects_bad_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="limit"):
        download_klines("BTCUSDT", "15m", START, START, cache_dir=tmp_path, limit=1001, fetcher=lambda *args: [])


def test_validation_reports_gap() -> None:
    rows = [
        {"timestamp": 0, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 1},
        {"timestamp": INTERVAL * 2, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 1},
    ]
    result = validate_klines(rows, "15m")
    assert result.gaps == (INTERVAL,)
    assert result.gap_count == 1


def test_validation_reports_duplicate() -> None:
    rows = [{"timestamp": 0, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 1}] * 2
    result = validate_klines(rows, "15m")
    assert result.duplicates == 1


def test_validation_reports_invalid_ohlc() -> None:
    rows = [{"timestamp": 0, "open": 3, "high": 2, "low": 1, "close": 3, "volume": 1}]
    assert validate_klines(rows, "15m").invalid_rows == 1


def test_validation_accepts_sane_rows() -> None:
    result = validate_klines(
        [{"timestamp": 0, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 1}],
        "15m",
    )
    assert result.invalid_rows == 0


def test_cache_contains_expected_fields(tmp_path: Path) -> None:
    start, end = bounds()
    result = download_klines("BTCUSDT", "15m", start, end, cache_dir=tmp_path, fetcher=lambda *args: history_rows())
    header = result.path.read_text(encoding="utf-8").splitlines()[0]
    assert header == "timestamp,open,high,low,close,volume,close_time"


def test_iso_timestamp_range_supported(tmp_path: Path) -> None:
    result = download_klines(
        "BTCUSDT",
        "15m",
        "2024-01-01T00:00:00Z",
        "2024-01-01T00:45:00Z",
        cache_dir=tmp_path,
        fetcher=lambda *args: history_rows(),
    )
    assert len(result) == 4


def test_fetch_empty_page_is_valid_empty_result(tmp_path: Path) -> None:
    result = download_klines("BTCUSDT", "15m", START, START, cache_dir=tmp_path, fetcher=lambda *args: [])
    assert len(result) == 0
    assert result.validation.rows == 0
