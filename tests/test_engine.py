import csv
from pathlib import Path

import pandas as pd
import pytest

from bananatrade.agents.execution.auto_trader import AutoTrader
from bananatrade.bot_runner import BotRunner
from bananatrade.engine.bar_engine import BarEngine
from bananatrade.engine.exit_manager import ExitManager
from bananatrade.engine.position_sizer import PositionSizer
from bananatrade.engine.strategy import MACrossStrategy
from bananatrade.engine.trade_journal import JOURNAL_COLUMNS, TradeJournal
from bananatrade.paper_broker import PaperBroker


def _cross_frame(direction: str, rsi_tail: float | None = None) -> list[dict[str, object]]:
    if direction == "up":
        values = [
            98.7324315490888, 98.01572992730257, 101.1966818019689, 98.6893868488538,
            99.89397172984782, 100.90077308178951, 100.22590249960885, 99.30392860419546,
            100.07339485081215, 100.221767499521, 101.1370899014619, 98.42443766841971,
            100.24118453433582, 98.99397728417236, 99.10766828185912, 101.08904439502196,
            100.03085596716929, 100.24691754662591, 101.03997257036006, 101.64995214531925,
            99.77299357430975, 100.45011153737784, 100.02221252340489, 100.04864588974128,
            100.77092401019291, 99.80938316905964, 100.13314175031668, 99.91214527212834,
            101.766004510154, 100.79687152872114, 101.50614192712237, 101.7687223531003,
            99.03836917647077, 100.23805522599086, 101.77306813605394, 101.35999913357283,
            98.5485377435874, 98.48648781753673, 99.76847235310018, 98.29018439862595,
            98.96255503381308, 98.2924830678907, 100.67788858123959, 101.13574406869262,
            101.58810573151507, 98.61778649507477, 100.86447953115278, 100.64102606076548,
            98.57191599169695, 101.5313313346283, 104.67544782666384,
        ]
    else:
        values = [
            98.13431630148422, 101.96161856862219, 101.46432997481449, 99.94526212175819,
            100.26873580257842, 99.0463876702039, 101.11676315307093, 99.70379993608915,
            101.78599832793658, 101.06899585107327, 101.275322962203, 101.85387280973505,
            99.01598214637478, 98.15148208555112, 98.80395644887132, 98.72294158870584,
            98.33462548337934, 98.20399001344472, 100.22952098755935, 101.48266767578025,
            99.8331237282406, 101.78882026212231, 101.63967886253599, 98.25674333760054,
            100.39227272986895, 99.58958673245176, 98.47966413814952, 101.83718642860524,
            99.02877480741473, 100.2579047153356, 100.5625318911607, 101.8256801045205,
            100.67888595183197, 99.57247348337934, 99.79337372927947, 98.63891370209787,
            101.86307395205284, 101.96686302783226, 98.8868874362744, 98.15452697087087,
            99.02344876352451, 99.4080436843418, 101.61101810791597, 101.6182890400705,
            101.34887161609858, 98.18816904002139, 101.14549253143968, 100.8384330791107,
            100.58674662594943, 101.94170410881713, 95.55767812587743,
        ]
    if rsi_tail is not None:
        values[-15:-1] = [rsi_tail] * 14
    return pd.DataFrame({"close": values}).to_dict("records")


def test_bar_engine_dispatches_and_keeps_last_50() -> None:
    engine = BarEngine()
    seen: list[dict[str, object]] = []
    engine.add_listener(seen.append)
    for index in range(55):
        engine.on_bar({"close": index})

    assert len(engine.candles) == 50
    assert engine.candles[0]["close"] == 5
    assert seen[-1]["close"] == 54


def test_ma_cross_up_detection() -> None:
    result = MACrossStrategy().generate_signal(_cross_frame("up"))

    assert result.bias == "LONG"
    assert result.confidence > 0


def test_ma_cross_down_detection() -> None:
    result = MACrossStrategy().generate_signal(_cross_frame("down"))

    assert result.bias == "SHORT"
    assert result.confidence > 0


def test_rsi_overbought_blocks_long() -> None:
    values = [
        91.51297772258701, 109.80625503110804, 93.63213869000867, 101.68735809671512,
        96.55293171485961, 91.0090097455121, 94.66652248922156, 98.21895211646579,
        90.91397047794776, 91.89960213654938, 100.33572818962307, 98.07180460293391,
        91.08778726490125, 96.30192726633146, 94.50269877800596, 107.1503666561693,
        108.51425180440262, 107.53577439279667, 107.9155188946254, 99.56796713666041,
        94.47360019304583, 102.61971160301512, 94.46777454497754, 108.44811187667202,
        94.38198929061541, 101.65895674545767, 102.30832982417375, 91.98895288764446,
        104.6286056263386, 99.57280454215713, 91.0538526276659, 95.62861849515866,
        98.67131921886266, 94.33666763109333, 95.6227968919427, 99.97477444257744,
        96.96837260376634, 98.71136502970855, 96.02507071266739, 96.79141834472166,
        90.5399790219816, 99.5379569780933, 97.02344990813741, 99.72961194138527,
        96.198148501203, 96.4755195385565, 96.78421098411768, 98.12383562396903,
        96.863904957763, 91.65439633800328, 148.07135379841424,
    ]
    result = MACrossStrategy().generate_signal(pd.DataFrame({"close": values}).to_dict("records"))

    assert result.bias == "NEUTRAL"
    assert "overbought" in result.reason


def test_rsi_oversold_blocks_short() -> None:
    values = [
        97.72236768233516, 90.64449199702722, 100.39880750797555, 109.79417489792837,
        90.00176094491005, 102.7617019301339, 100.79884012316623, 103.06722172702447,
        104.72238512027162, 104.6697167987387, 98.40903237907679, 103.33138089367547,
        109.814566694026, 103.2337653501967, 90.65268123212226, 106.77133797364682,
        108.63673693360603, 108.10539900070381, 103.54787168950344, 105.88350529585318,
        91.7124149605137, 95.92618564722736, 96.47120878361885, 103.29619978303862,
        108.72145955127922, 102.25992550345612, 106.94672633614925, 106.34310427010251,
        106.33678975545254, 95.83151578611506, 106.59274821784751, 104.60195344666208,
        100.58380433511283, 106.7791223747047, 106.59275257859798, 100.7715457381965,
        101.05878236081186, 109.0812159823705, 103.6985645444949, 106.9754298815542,
        101.7174558966957, 102.5879796287251, 100.91217750187351, 100.89169104072519,
        108.0170541930598, 102.63121476889322, 106.44959833710121, 101.35896528925097,
        103.68107161246123, 100.76626968844123, 65.26542995470847,
    ]
    result = MACrossStrategy().generate_signal(pd.DataFrame({"close": values}).to_dict("records"))

    assert result.bias == "NEUTRAL"
    assert "oversold" in result.reason


def test_strategy_without_crossover_is_neutral() -> None:
    result = MACrossStrategy().generate_signal([{"close": 100.0}] * 50)

    assert result.bias == "NEUTRAL"


def test_exit_manager_stop_loss_hit_closes_long() -> None:
    actions = ExitManager().check_exits(
        [{"symbol": "BTC/USDT", "quantity": 1.0, "entry": 100.0, "stop_loss": 95.0, "take_profit": 115.0}],
        94.0,
    )

    assert actions[0]["side"] == "SELL"
    assert actions[0]["reason"] == "stop_loss"


def test_exit_manager_take_profit_hit_closes_long() -> None:
    actions = ExitManager().check_exits(
        [{"symbol": "BTC/USDT", "quantity": 1.0, "entry": 100.0, "stop_loss": 95.0, "take_profit": 105.0}],
        106.0,
    )

    assert actions[0]["side"] == "SELL"
    assert actions[0]["reason"] == "take_profit"


def test_exit_manager_trailing_stop_moves_to_breakeven() -> None:
    position: dict[str, object] = {
        "symbol": "BTC/USDT",
        "quantity": 1.0,
        "entry": 100.0,
        "stop_loss": 95.0,
        "take_profit": 120.0,
    }

    actions = ExitManager().check_exits([position], 105.0)

    assert actions == []
    assert position["stop_loss"] == 100.0


def test_exit_manager_trailing_stop_uses_two_r() -> None:
    position: dict[str, object] = {
        "symbol": "BTC/USDT",
        "quantity": 1.0,
        "entry": 100.0,
        "stop_loss": 95.0,
        "take_profit": 130.0,
    }

    ExitManager().check_exits([position], 112.0)

    assert position["stop_loss"] == 102.0


def test_position_sizing_formula() -> None:
    assert PositionSizer.compute_qty(10_000.0, 100.0, 90.0) == 10
    assert PositionSizer.compute_qty(100.0, 100.0, 99.0) == 1


def test_journal_csv_appends_row(tmp_path: Path) -> None:
    path = tmp_path / "trades" / "journal.csv"
    journal = TradeJournal(path)
    journal.append({"timestamp": "2025-01-01T00:00:00Z", "symbol": "BTC/USDT", "side": "BUY", "entry": 100, "qty": 1, "reason": "signal"})
    journal.append({"timestamp": "2025-01-01T01:00:00Z", "symbol": "BTC/USDT", "side": "SELL", "exit": 105, "qty": 1, "pnl": 5, "reason": "take_profit"})

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == JOURNAL_COLUMNS
    assert len(rows) == 2
    assert rows[1]["pnl"] == "5"


@pytest.mark.asyncio
async def test_bot_runner_one_cycle_integration(tmp_path: Path) -> None:
    broker = PaperBroker(10_000.0)
    trader = AutoTrader(broker)
    closes = [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1_000.0}]

    async def snapshot() -> dict[str, object]:
        return {"last_price": 100.0, "candles": closes}

    runner = BotRunner(snapshot, trader, journal=TradeJournal(tmp_path / "journal.csv"))
    result = await runner.run_cycle()

    assert result["decision"]["action"] == "NONE"
    assert len(runner.bar_engine.candles) == 1
