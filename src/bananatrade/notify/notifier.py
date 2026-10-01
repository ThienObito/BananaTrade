"""Safe, best-effort notifications."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    def decision_approved(self, decision: str | Mapping[str, Any]) -> None: ...
    def position_closed(self, position: str | Mapping[str, Any]) -> None: ...
    def kill_switch_triggered(self, reason: str) -> None: ...
    def quota_low(self, remaining: int | str) -> None: ...
    def repeated_gateway_failures(self, failures: int | str) -> None: ...


class NullNotifier:
    """Notifier that intentionally discards all events."""

    def decision_approved(self, decision: str | Mapping[str, Any]) -> None:
        pass

    def position_closed(self, position: str | Mapping[str, Any]) -> None:
        pass

    def kill_switch_triggered(self, reason: str) -> None:
        pass

    def quota_low(self, remaining: int | str) -> None:
        pass

    def repeated_gateway_failures(self, failures: int | str) -> None:
        pass


class TelegramNotifier:
    """Best-effort Telegram notifier; credentials never enter logs or repr."""

    def __init__(self, token: str | None = None, chat_id: str | None = None, transport: Any = None) -> None:
        self._token = token if token is not None else os.getenv("TELEGRAM_BOT_TOKEN")
        self._chat_id = chat_id if chat_id is not None else os.getenv("TELEGRAM_CHAT_ID")
        self._transport = transport

    def __repr__(self) -> str:
        return "TelegramNotifier(configured={})".format(bool(self._token and self._chat_id))

    def _send(self, text: str) -> None:
        if not self._token or not self._chat_id:
            return
        try:
            if self._transport is None:
                import httpx
                httpx.post(f"https://api.telegram.org/bot{self._token}/sendMessage", data={"chat_id": self._chat_id, "text": text}, timeout=10)
            else:
                url = f"https://api.telegram.org/bot{self._token}/sendMessage"
                payload = {"chat_id": self._chat_id, "text": text}
                if hasattr(self._transport, "post"):
                    self._transport.post(url, data=payload)
                else:
                    self._transport(url, payload)
        except Exception as exc:
            logger.warning("notification delivery failed: %s", self._safe_error(exc))

    def _safe_error(self, exc: Exception) -> str:
        message = str(exc)
        if self._token:
            message = message.replace(self._token, "[REDACTED]")
        if self._chat_id:
            message = message.replace(self._chat_id, "[REDACTED]")
        return message

    @staticmethod
    def _value(value: str | Mapping[str, Any]) -> str:
        if isinstance(value, Mapping):
            return ", ".join(f"{key}={val}" for key, val in value.items())
        return str(value)

    def decision_approved(self, decision: str | Mapping[str, Any]) -> None:
        self._send(f"Decision approved: {self._value(decision)}")

    def position_closed(self, position: str | Mapping[str, Any]) -> None:
        self._send(f"Position closed: {self._value(position)}")

    def kill_switch_triggered(self, reason: str) -> None:
        self._send(f"Kill-switch triggered: {reason}")

    def quota_low(self, remaining: int | str) -> None:
        self._send(f"Quota low: {remaining} remaining")

    def repeated_gateway_failures(self, failures: int | str) -> None:
        self._send(f"Repeated gateway failures: {failures}")
