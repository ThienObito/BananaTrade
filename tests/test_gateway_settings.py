from pathlib import Path
from unittest.mock import patch

import pytest

from bananatrade.gateway.llm_client import ConfigError, LLMClient

CONFIG = Path(__file__).parents[1] / "config" / "models.yaml"


def test_client_uses_ninerouter_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NINEROUTER_BASE_URL", "http://router.test/v1")
    monkeypatch.setenv("NINEROUTER_API_KEY", "router-key")
    with patch("bananatrade.gateway.llm_client.AsyncOpenAI") as constructor:
        LLMClient(CONFIG, tmp_path / "db.sqlite")
    constructor.assert_called_once_with(base_url="http://router.test/v1", api_key="router-key")


def test_client_ignores_openai_env(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("NINEROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "wrong-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    with patch("bananatrade.gateway.llm_client.AsyncOpenAI") as constructor, pytest.raises(ConfigError, match="NINEROUTER_API_KEY is not set"):
        LLMClient(CONFIG, tmp_path / "db.sqlite")
    constructor.assert_not_called()


def test_dotenv_loaded_without_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NINEROUTER_API_KEY", "real-env")
    dotenv = tmp_path / ".env"
    dotenv.write_text("NINEROUTER_API_KEY=dotenv-key\n", encoding="utf-8")
    from dotenv import load_dotenv
    load_dotenv(dotenv, override=False)
    assert __import__("os").environ["NINEROUTER_API_KEY"] == "real-env"
