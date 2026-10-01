from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from bananatrade.agents.schemas import AnalysisReport, KeyLevels

VALID_BIASES = ("LONG", "SHORT", "NEUTRAL")


def analysis_payload(bias: object) -> dict[str, object]:
    return {
        "agent": "test",
        "symbol": "BTC/USDT",
        "as_of": datetime.now(UTC),
        "bias": bias,
        "thesis": "test thesis",
        "key_levels": KeyLevels(support=[], resistance=[]),
        "invalidation": None,
        "confidence": 0.5,
        "evidence": [],
        "data_missing": [],
    }


@pytest.mark.parametrize("bias", VALID_BIASES)
def test_analysis_report_accepts_only_supported_bias_labels(bias: str) -> None:
    report = AnalysisReport.model_validate(analysis_payload(bias))

    assert report.bias == bias


@pytest.mark.parametrize(
    "bias",
    [
        VALID_BIASES[0].lower(),
        VALID_BIASES[1].lower(),
        VALID_BIASES[2].lower(),
        VALID_BIASES[2] + "+",
        "",
        None,
        1,
    ],
)
def test_analysis_report_rejects_unsupported_bias_labels(bias: object) -> None:
    with pytest.raises(ValidationError):
        AnalysisReport.model_validate(analysis_payload(bias))


def test_bias_labels_are_exactly_long_short_or_neutral() -> None:
    assert set(VALID_BIASES) == {"LONG", "SHORT", "NEUTRAL"}
