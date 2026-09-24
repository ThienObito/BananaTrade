import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import openai
import yaml
from openai import AsyncOpenAI

from .budget import BudgetGuard
from .errors import (
    EmptyCompletionError,
    GatewayAuthError,
    GatewayConnectionError,
    GatewayError,
    ModelNotAvailableError,
)
from .model_verify import verify_model
from .quota import QuotaExhaustedError, QuotaLedger


class ConfigError(RuntimeError):
    pass


def map_gateway_error(exc: Exception, model_id: str) -> GatewayError:
    message = str(exc)
    if isinstance(exc, openai.AuthenticationError):
        return GatewayAuthError(message)
    if isinstance(exc, openai.NotFoundError) or (isinstance(exc, openai.APIStatusError) and exc.status_code in {400, 503} and ("model" in message.lower() or "not supported" in message.lower())):
        return ModelNotAvailableError(f"{model_id}: {message}")
    if isinstance(exc, openai.RateLimitError):
        return QuotaExhaustedError(message)
    if isinstance(exc, openai.APIConnectionError):
        return GatewayConnectionError(message)
    return GatewayError(message)


class LLMClient:
    def __init__(self, config_path: Path, db_path: Path, client: Any = None) -> None:
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.tiers = cfg["tiers"]
        self.retry = cfg.get("retry", {})
        gateway = cfg.get("gateway", {})
        if not gateway and ("daily_budget_usd" in self.retry or "cache_ttl_s" in self.retry):
            logging.getLogger(__name__).warning("retry cache/budget keys are deprecated; move them to gateway")
        self.gateway = gateway
        self.ledger = QuotaLedger(db_path)
        self.budget = BudgetGuard(float(gateway.get("daily_budget_usd", self.retry.get("daily_budget_usd", 10.0))))
        self.base_url = os.getenv("NINEROUTER_BASE_URL", "http://localhost:20128/v1")
        self.api_key = os.getenv("NINEROUTER_API_KEY", "")
        if client is None and not self.api_key:
            raise ConfigError("NINEROUTER_API_KEY is not set. Add it to .env (see .env.example).")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigError("NINEROUTER_BASE_URL must be a valid http(s) URL.")
        logging.getLogger(__name__).info("Using 9Router host %s", parsed.netloc)
        self.client = client or AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    async def call(self, tier: str, prompt: str) -> dict[str, Any]:
        config = self.tiers[tier]
        if not config["enabled"]:
            raise RuntimeError(f"Tier disabled: {tier}")
        self.ledger.check(tier, config["quota"])
        started = time.perf_counter()
        attempts = int(self.retry.get("max_attempts", 3))
        response: Any = None
        for attempt in range(attempts):
            try:
                max_tokens = min(config["max_tokens"] * (2 if attempt == 1 else 1), config.get("max_tokens_ceiling", config["max_tokens"] * 2))
                response = await self.client.chat.completions.create(model=config["model_id"], messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens, temperature=config["temperature"], timeout=config["timeout_s"])
                break
            except Exception as exc:
                error = map_gateway_error(exc, config["model_id"])
                self.ledger.record(tier, 0, "failed")
                retryable = isinstance(error, QuotaExhaustedError) or (isinstance(exc, openai.APIStatusError) and exc.status_code >= 500 and not isinstance(error, ModelNotAvailableError))
                if retryable and attempt < attempts - 1:
                    await asyncio.sleep(float(self.retry.get("base_delay_s", 0.5)) * (2**attempt))
                    continue
                raise error from exc
        actual = response.model
        verify_model(tier, config["model_id"], actual, config.get("model_aliases", []))
        content = response.choices[0].message.content or ""
        if not content.strip():
            finish_reason = response.choices[0].finish_reason
            consumed = response.usage.total_tokens if response.usage else 0
            self.ledger.record(tier, consumed, "failed")
            if attempt == 0:
                max_tokens = min(config["max_tokens"] * 2, config.get("max_tokens_ceiling", config["max_tokens"] * 2))
                response = await self.client.chat.completions.create(model=config["model_id"], messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens, temperature=config["temperature"], timeout=config["timeout_s"])
                content = response.choices[0].message.content or ""
                if not content.strip():
                    raise EmptyCompletionError(f"Empty completion for {tier} model {config['model_id']} finish_reason={response.choices[0].finish_reason}")
            else:
                raise EmptyCompletionError(f"Empty completion for {tier} model {config['model_id']} finish_reason={finish_reason}")
        tokens = response.usage.total_tokens if response.usage else 0
        cost = (tokens / 1_000_000) * (config["est_price_per_1m_in"] + config["est_price_per_1m_out"])
        self.budget.check(cost)
        self.budget.record(cost)
        self.ledger.record(tier, tokens)
        return {"tier": tier, "configured_model": config["model_id"], "actual_model": actual, "tokens": tokens, "cost": cost, "latency_s": time.perf_counter() - started, "text": response.choices[0].message.content or ""}
