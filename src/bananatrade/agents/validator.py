import re
from typing import Any

from pydantic import BaseModel


class EvidenceMismatchError(ValueError):
    def __init__(self, fields: list[str]) -> None:
        super().__init__(f"Evidence mismatch: {', '.join(fields)}")
        self.fields = fields


def validate_report(report: BaseModel, snapshot: dict[str, Any]) -> BaseModel:
    """Validate evidence and require summaries to avoid numeric claims.

    Digits are allowed only in timeframe labels (15m, 1h, 4h, 1d) and standalone
    reference thresholds 2, 30, 50, and 70.
    """
    bad: list[str] = []
    evidence = list(getattr(report, "evidence", []))
    for signal in getattr(report, "signals", []):
        evidence.extend(signal.evidence)

    def lookup(field: str) -> Any:
        value: Any = snapshot
        for part in field.split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    for item in evidence:
        actual = lookup(item.field)
        if not isinstance(actual, (int, float)) or abs(actual - item.value) > 1e-4 * max(abs(actual), 1.0):
            bad.append(item.field)
    summary = getattr(report, "summary", getattr(report, "thesis", ""))
    allowed = re.compile(r"(?:15m|1h|4h|1d|(?<![\d.])(?:2|30|50|70)(?![\d.]))")
    scrubbed = allowed.sub("", summary)
    if re.search(r"\d", scrubbed):
        bad.append("summary")
    levels = getattr(report, "key_levels", None)
    last_price = snapshot.get("timeframes", {}).get("1h", {}).get("last_price")
    evidence_values = [item.value for item in evidence]
    if levels is not None and isinstance(last_price, (int, float)):
        for label, values in (("support", levels.support), ("resistance", levels.resistance)):
            for level in values:
                if not any(abs(level - value) <= 1e-4 * max(abs(value), 1.0) for value in evidence_values):
                    bad.append(label)
                if level <= 0 or abs(level - last_price) > last_price * 0.5:
                    bad.append(label)
                if label == "support" and level >= last_price:
                    bad.append(label)
                if label == "resistance" and level <= last_price:
                    bad.append(label)
        invalidation = getattr(report, "invalidation", None)
        bias = getattr(report, "bias", "NEUTRAL")
        if bias in {"LONG", "SHORT"} and invalidation is None:
            bad.append("invalidation")
        if invalidation is not None:
            level = invalidation.level
            if not any(abs(level - value) <= 1e-4 * max(abs(value), 1.0) for value in evidence_values):
                bad.append("invalidation.level")
            if level <= 0 or abs(level - last_price) > last_price * 0.5:
                bad.append("invalidation.level")
            if bias == "LONG" and level >= last_price:
                bad.append("invalidation.level")
            if bias == "SHORT" and level <= last_price:
                bad.append("invalidation.level")
            if re.search(r"\d", re.sub(r"(?:15m|1h|4h|1d|(?<![\d.])(?:2|30|50|70)(?![\d.]))", "", invalidation.condition)):
                bad.append("invalidation.condition")
    if bad:
        raise EvidenceMismatchError(bad)
    return report
