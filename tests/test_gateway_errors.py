import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import openai
import pytest
from typer.testing import CliRunner

from bananatrade.cli import app
from bananatrade.gateway.errors import (
    GatewayAuthError,
    GatewayConnectionError,
    GatewayError,
    ModelNotAvailableError,
)
from bananatrade.gateway.llm_client import LLMClient, map_gateway_error
from bananatrade.gateway.quota import QuotaExhaustedError

CONFIG = Path(__file__).parents[1] / "config" / "models.yaml"
runner = CliRunner()


def response(status: int) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", "http://router.test/v1/chat/completions"))


def exc(kind: str) -> Exception:
    req = httpx.Request("POST", "http://router.test")
    if kind == "auth": return openai.AuthenticationError("bad key", response=response(401), body=None)
    if kind == "notfound": return openai.NotFoundError("missing", response=response(404), body=None)
    if kind == "model400": return openai.APIStatusError("model is not supported", response=response(400), body=None)
    if kind == "model503": return openai.APIStatusError("not supported", response=response(503), body=None)
    if kind == "rate": return openai.RateLimitError("quota", response=response(429), body=None)
    if kind == "connection": return openai.APIConnectionError(request=req)
    return openai.APIStatusError("server error", response=response(500), body=None)


@pytest.mark.parametrize("kind, expected", [("auth", GatewayAuthError), ("notfound", ModelNotAvailableError), ("model400", ModelNotAvailableError), ("model503", ModelNotAvailableError), ("rate", QuotaExhaustedError), ("connection", GatewayConnectionError), ("generic", GatewayError)])
def test_error_mapping(kind: str, expected: type[GatewayError]) -> None:
    mapped = map_gateway_error(exc(kind), "cx/test-model")
    assert isinstance(mapped, expected)
    assert isinstance(mapped, GatewayError)
    if expected is ModelNotAvailableError: assert "cx/test-model" in str(mapped)


@pytest.mark.parametrize("kind", ["auth", "notfound", "model400", "model503"])
def test_no_retry_on_non_retryable(kind: str, tmp_path: Path) -> None:
    mock = Mock(); mock.chat.completions.create = AsyncMock(side_effect=exc(kind))
    client = LLMClient(CONFIG, tmp_path / "db.sqlite", mock)
    with pytest.raises(GatewayError): asyncio.run(client.call("tier1_fast", "test"))
    assert mock.chat.completions.create.await_count == 1


@pytest.mark.parametrize("kind", ["rate", "generic"])
def test_retry_on_retryable(kind: str, tmp_path: Path) -> None:
    mock = Mock(); mock.chat.completions.create = AsyncMock(side_effect=exc(kind))
    client = LLMClient(CONFIG, tmp_path / "db.sqlite", mock)
    with patch("bananatrade.gateway.llm_client.asyncio.sleep", new=AsyncMock()), pytest.raises(GatewayError):
        asyncio.run(client.call("tier1_fast", "test"))
    assert mock.chat.completions.create.await_count == client.retry["max_attempts"]


def test_quota_record_rejects_negative_tokens(tmp_path: Path) -> None:
    from bananatrade.gateway.quota import QuotaLedger
    ledger = QuotaLedger(tmp_path / "db.sqlite")
    with pytest.raises(ValueError, match="cannot be negative"):
        ledger.record("tier1_fast", -1)


def test_quota_record_rejects_invalid_status(tmp_path: Path) -> None:
    from bananatrade.gateway.quota import QuotaLedger
    ledger = QuotaLedger(tmp_path / "db.sqlite")
    with pytest.raises(ValueError, match="Invalid ledger status"):
        ledger.record("tier1_fast", 1, "pending")


def test_quota_check_rejects_incomplete_limits(tmp_path: Path) -> None:
    from bananatrade.gateway.quota import QuotaLedger
    ledger = QuotaLedger(tmp_path / "db.sqlite")
    with pytest.raises(ValueError, match="Missing quota limits"):
        ledger.check("tier1_fast", {"max_calls_per_5h": 1})


def test_quota_check_rejects_negative_limits(tmp_path: Path) -> None:
    from bananatrade.gateway.quota import QuotaLedger
    ledger = QuotaLedger(tmp_path / "db.sqlite")
    with pytest.raises(ValueError, match="cannot be negative"):
        ledger.check("tier1_fast", {"max_calls_per_5h": -1, "max_calls_per_7d": 1})


def test_failed_call_ledger_status(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    mock = Mock(); mock.chat.completions.create = AsyncMock(side_effect=exc("notfound"))
    client = LLMClient(CONFIG, path, mock)
    with pytest.raises(ModelNotAvailableError): asyncio.run(client.call("tier1_fast", "test"))
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT status, tokens FROM calls ORDER BY rowid DESC LIMIT 1").fetchone()
        cost = 0.0
    assert row == ("failed", 0)
    assert cost == 0
    assert client.ledger.counts("tier1_fast") == (0, 0)


def test_ping_continues_after_failing_tier(monkeypatch) -> None:
    async def fake(skip: bool) -> list[dict[str, object]]:
        return [{"tier": "tier1_fast", "status": "PASS"}, {"tier": "tier2_analyst", "status": "FAIL", "error": "unsupported"}, {"tier": "tier3_strategist", "status": "PASS"}]
    monkeypatch.setattr("bananatrade.cli._ping", fake)
    result = runner.invoke(app, ["ping", "--skip-cio"])
    assert result.exit_code == 1
    assert result.output.count("PASS") == 2
    assert result.output.count("FAIL") == 1
    assert "tier2_analyst" in result.output and "Traceback" not in result.output


def test_ping_all_pass_exit_zero(monkeypatch) -> None:
    async def fake(skip: bool) -> list[dict[str, object]]:
        return [{"tier": "tier1_fast", "status": "PASS"}, {"tier": "tier2_analyst", "status": "PASS"}, {"tier": "tier3_strategist", "status": "PASS"}]
    monkeypatch.setattr("bananatrade.cli._ping", fake)
    result = runner.invoke(app, ["ping", "--skip-cio"])
    assert result.exit_code == 0
    assert result.output.count("PASS") == 3
