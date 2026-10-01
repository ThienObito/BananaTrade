from pathlib import Path

APP_JS = Path(__file__).parents[1] / "web" / "app.js"


def test_order_ticket_reads_signal_endpoint_and_only_prefills_directional_bias() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert "fetch('/api/signal?' + params.toString())" in source
    assert "['LONG', 'SHORT'].includes(bias)" in source
    assert "side.value = bias === 'LONG' ? 'buy' : 'sell'" in source
    assert "prefillFromSignal();" in source


def test_neutral_signal_does_not_prefill_order_side() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    helper_start = source.index("function signalBias(signal)")
    helper_end = source.index("function renderSnapshotViews()", helper_start)
    helper = source[helper_start:helper_end]

    assert "['LONG', 'SHORT'].includes(bias)" in helper
    assert "NEUTRAL" not in helper
