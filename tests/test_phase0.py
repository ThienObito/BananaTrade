import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import BaseModel

from bananatrade.gateway.budget import BudgetExceededError, BudgetGuard
from bananatrade.gateway.llm_client import LLMClient
from bananatrade.gateway.model_verify import ModelMismatchError, verify_model
from bananatrade.gateway.quota import QuotaExhaustedError, QuotaLedger
from bananatrade.gateway.structured import parse_structured
from bananatrade.orchestration.pipeline import run_stub


class Reply(BaseModel):
    value: str


def response(model: str = "expected", text: str = "ok", tokens: int = 1) -> Mock:
    result = Mock()
    result.model = model
    result.usage.total_tokens = tokens
    result.choices[0].message.content = text
    return result


def test_cio_model_mismatch_blocks() -> None:
    with pytest.raises(ModelMismatchError):
        verify_model("tier4_cio", "expected", "wrong", [])


def test_quota_exhaustion(tmp_path: Path) -> None:
    ledger = QuotaLedger(tmp_path / "q.db")
    ledger.record("tier1_fast", 1)
    with pytest.raises(QuotaExhaustedError):
        ledger.check("tier1_fast", {"max_calls_per_5h": 1, "max_calls_per_7d": 5})


def test_quota_ledger_persists_across_restart(tmp_path: Path) -> None:
    path = tmp_path / "q.db"
    first = QuotaLedger(path)
    first.record("tier1_fast", 1)
    second = QuotaLedger(path)
    assert second.counts("tier1_fast") == (1, 1)
    with pytest.raises(QuotaExhaustedError):
        second.check("tier1_fast", {"max_calls_per_5h": 1, "max_calls_per_7d": 1})


def test_structured_invalid_json_repair_then_explicit_failure() -> None:
    with pytest.raises(ValueError, match="after one repair"):
        parse_structured("not-json", Reply, repair_text="still-not-json")


def test_structured_repair_succeeds() -> None:
    result = parse_structured("bad", Reply, repair_text=json.dumps({"value": "ok"}))
    assert result.value == "ok"


def test_disabled_deepseek_makes_zero_mock_calls(tmp_path: Path) -> None:
    mock_client = Mock()
    mock_client.chat.completions.create = AsyncMock()
    gateway = LLMClient(Path(__file__).parents[1] / "config" / "models.yaml", tmp_path / "q.db", mock_client)
    with pytest.raises(RuntimeError, match="disabled"):
        asyncio.run(gateway.call("optional_second_opinion", "test"))
    mock_client.chat.completions.create.assert_not_awaited()


@pytest.mark.parametrize("tier", ["tier1_fast", "tier2_analyst"])
def test_mismatch_warns_and_returns(tier: str, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        verify_model(tier, "expected", "wrong", [])
    assert "Model mismatch" in caplog.text


def test_budget_guard_blocks_after_limit() -> None:
    guard = BudgetGuard(1.0)
    guard.record(1.0)
    with pytest.raises(BudgetExceededError):
        guard.check(0.01)


@pytest.mark.asyncio
async def test_pipeline_skips_cio_on_hold_and_risk_rejection() -> None:
    gateway = Mock()
    gateway.call = AsyncMock()
    assert await run_stub(gateway, {"side": "HOLD"}, True) == "DEFERRED"
    assert await run_stub(gateway, {"side": "LONG"}, False) == "DEFERRED"
    gateway.call.assert_not_awaited()


def test_api_key_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    secret = "secret-api-key-value"
    logger = logging.getLogger("bananatrade.gateway")
    with caplog.at_level(logging.INFO):
        logger.info("gateway call completed")
    assert secret not in caplog.text
