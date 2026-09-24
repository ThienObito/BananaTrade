import logging
from pathlib import Path

from bananatrade.gateway.llm_client import LLMClient


def test_config_backward_compat(tmp_path: Path, monkeypatch, caplog) -> None:
    monkeypatch.setenv("NINEROUTER_API_KEY", "x")
    old = tmp_path / "old.yaml"
    old.write_text("retry: {max_attempts: 1, daily_budget_usd: 2, cache_ttl_s: 7}\ntiers: {}\n")
    with caplog.at_level(logging.WARNING):
        client = LLMClient(old, tmp_path / "old.db", client=object())
    assert client.budget.daily_limit == 2
    assert "deprecated" in caplog.text
    new = tmp_path / "new.yaml"
    new.write_text("retry: {max_attempts: 1, daily_budget_usd: 2}\ngateway: {daily_budget_usd: 9, cache_ttl_s: 8}\ntiers: {}\n")
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        client = LLMClient(new, tmp_path / "new.db", client=object())
    assert client.budget.daily_limit == 9
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)
