"""Generate deterministic synthetic random-walk OHLCV data for offline tests."""
import csv
import random
from pathlib import Path


def main() -> None:
    rng = random.Random(20250101)
    rows = [["timestamp_ms", "open", "high", "low", "close", "volume"]]
    price = 100.0
    for index in range(300):
        opening = price
        if 120 <= index < 140:
            change = 0.0
        else:
            change = rng.choice([-1.0, 1.0]) * rng.uniform(0.1, 2.0)
        closing = opening + change
        high = max(opening, closing) + rng.uniform(0.1, 0.8)
        low = min(opening, closing) - rng.uniform(0.1, 0.8)
        volume = 800.0 + rng.uniform(0, 500) + (200 if index % 17 == 0 else 0)
        rows.append([index * 3_600_000, opening, high, low, closing, volume])
        price = closing
    target = Path(__file__).parents[1] / "tests" / "fixtures" / "synthetic_randomwalk_btc_1h.csv"
    with target.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)


if __name__ == "__main__":
    main()
