import logging

from bananatrade.notify import NullNotifier, TelegramNotifier


class FakeTransport:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def post(self, url, *, data):
        if self.fail:
            raise RuntimeError("secret-token transport failure")
        self.calls.append((url, data))


def test_null_notifier_is_safe():
    notifier = NullNotifier()
    notifier.decision_approved("buy")
    notifier.position_closed("BTC")
    notifier.kill_switch_triggered("risk")
    notifier.quota_low(2)
    notifier.repeated_gateway_failures(3)


def test_telegram_event_content_and_credentials(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-42")
    transport = FakeTransport()
    notifier = TelegramNotifier(transport=transport)
    notifier.decision_approved("buy BTC")
    notifier.position_closed("BTC")
    notifier.kill_switch_triggered("drawdown")
    notifier.quota_low(2)
    notifier.repeated_gateway_failures(3)
    assert [call[1]["text"] for call in transport.calls] == [
        "Decision approved: buy BTC", "Position closed: BTC",
        "Kill-switch triggered: drawdown", "Quota low: 2 remaining",
        "Repeated gateway failures: 3",
    ]
    assert "secret-token" not in repr(notifier)
    assert "chat-42" not in repr(notifier)


def test_delivery_failure_is_logged_without_credentials(caplog):
    notifier = TelegramNotifier(token="secret-token", chat_id="chat-42", transport=FakeTransport(fail=True))
    with caplog.at_level(logging.WARNING):
        notifier.kill_switch_triggered("oops")
    assert "secret-token" not in caplog.text
    assert "chat-42" not in caplog.text
