import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from bananatrade.gateway.errors import EmptyCompletionError
from bananatrade.gateway.llm_client import LLMClient

CONFIG = Path(__file__).parents[1] / "config" / "models.yaml"


def response(content: str, tokens: int = 4) -> Mock:
    item = Mock()
    item.model = "gpt-5.6-terra"
    choice = Mock(content=content, finish_reason="length")
    item.choices = [Mock(message=choice, finish_reason="length")]
    item.usage = Mock(total_tokens=tokens)
    return item


def test_whitespace_only_content_retries(tmp_path: Path) -> None:
    mock = Mock(); mock.chat.completions.create = AsyncMock(side_effect=[response("   \n"), response("ok")])
    client = LLMClient(CONFIG, tmp_path / "db.sqlite", mock)
    assert asyncio.run(client.call("tier2_analyst", "test"))["text"] == "ok"


def test_empty_retry_doubles_and_returns_content(tmp_path: Path) -> None:
    mock = Mock(); mock.chat.completions.create = AsyncMock(side_effect=[response(" "), response("ok")])
    client = LLMClient(CONFIG, tmp_path / "db.sqlite", mock)
    result = asyncio.run(client.call("tier2_analyst", "test"))
    assert result["text"] == "ok"
    assert mock.chat.completions.create.await_args_list[1].kwargs["max_tokens"] == 2400


def test_empty_retry_is_capped(tmp_path: Path) -> None:
    mock = Mock(); mock.chat.completions.create = AsyncMock(side_effect=[response(""), response("ok")])
    client = LLMClient(CONFIG, tmp_path / "db.sqlite", mock)
    client.tiers["tier2_analyst"]["max_tokens_ceiling"] = 600
    asyncio.run(client.call("tier2_analyst", "test"))
    assert mock.chat.completions.create.await_args_list[1].kwargs["max_tokens"] == 600


def test_second_empty_raises_with_context(tmp_path: Path) -> None:
    mock = Mock(); mock.chat.completions.create = AsyncMock(side_effect=[response(""), response(" ")])
    client = LLMClient(CONFIG, tmp_path / "db.sqlite", mock)
    with pytest.raises(EmptyCompletionError, match="tier2_analyst.*gpt-5.6-terra.*length"):
        asyncio.run(client.call("tier2_analyst", "test"))
    assert mock.chat.completions.create.await_count == 2


def test_empty_attempt_records_consumed_tokens(tmp_path: Path) -> None:
    mock = Mock(); mock.chat.completions.create = AsyncMock(side_effect=[response(""), response("ok")])
    client = LLMClient(CONFIG, tmp_path / "db.sqlite", mock)
    asyncio.run(client.call("tier2_analyst", "test"))
    with client.ledger.path.open("rb"):
        pass
